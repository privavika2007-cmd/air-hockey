"""Голы, звуки и стикеры победы/поражения (шаг 10).

Вспышка ворот — чисто клиентская, сервер цвет не присылает.
Сервер уже зеркалит GameState: на любом клиенте «я» = player1 снизу.

  score.first  — мои очки
  score.second — очки соперника

  ┌─────────────────────┐
  │  ВЕРХ: ворота       │  ← сюда летит шайба, когда Я забил
  │  соперника          │     → score.first вырос → ЗЕЛЁНАЯ вспышка
  ├─────────────────────┤
  │                     │
  │       поле          │
  │                     │
  ├─────────────────────┤
  │  НИЗ: мои ворота    │  ← сюда летит шайба, когда мне забили
  └─────────────────────┘     → score.second вырос → КРАСНАЯ вспышка

Победа/поражение (First To Five) — зеркало server GameMaster.max_score = 5:
  score.first >= 5  → я победил → стикер You Won + звук победы
  score.second >= 5 → я проиграл → стикер You Lost + звук поражения
  дублирующий триггер: Message «max_score reached» с сервера
"""
from __future__ import annotations

from pathlib import Path

import pygame

from game_field import (
    FieldTransform,
    goal_flash_rect,
)

ROOT = Path(__file__).resolve().parent.parent
SOUNDS_DIR = ROOT / "sound_effects"
VISUAL_DIR = ROOT / "visual_effects"
RESULT_STICKER_FILES: dict[str, str] = {
    "won": "you_won.png",
    "lost": "you_lost.png",
}

GOAL_FLASH_FRAMES = 36
RESULT_OVERLAY_SECONDS = 6.0
RESULT_OVERLAY_FRAMES = int(60 * RESULT_OVERLAY_SECONDS)
HIT_COOLDOWN_MS = 45
MATCH_WIN_SCORE = 5
RESULT_BADGE_FIELD_FRAC = 0.30

# Вспышка: цвет ↔ событие для этого клиента (см. docstring модуля).
GOAL_FLASH_COLOR_SCORED = (80, 255, 120)
GOAL_FLASH_COLOR_CONCEDED = (255, 70, 90)
GOAL_FLASH_TARGET_WHEN_SCORED = "top"      # верхние ворота — я забил
GOAL_FLASH_TARGET_WHEN_CONCEDED = "bottom"  # нижние ворота — я пропустил


# Ключевые слова в именах файлов sound_effects/ (см. sound_effects/*.mp3).
SOUND_FILE_KEYS: dict[str, str] = {
    "hit": "удар",
    "goal": "гола",
    "win": "побед",
    "loss": "поражен",
}
RESULT_SOUND_BY_KIND: dict[str, str] = {
    "won": "win",
    "lost": "loss",
}
RESULT_CHANNEL = 0


from puck_hit_detection import puck_hit_between


def _sticker_content_rect(sticker: pygame.Surface) -> pygame.Rect:
    w, h = sticker.get_width(), sticker.get_height()
    minx, miny, maxx, maxy = w, h, 0, 0
    found = False
    for y in range(h):
        for x in range(w):
            r, g, b, a = sticker.get_at((x, y))
            if a > 40 and r + g + b > 60:
                found = True
                minx, miny = min(minx, x), min(miny, y)
                maxx, maxy = max(maxx, x), max(maxy, y)
    if not found:
        return pygame.Rect(0, 0, w, h)
    return pygame.Rect(minx, miny, maxx - minx + 1, maxy - miny + 1)


def _sound_path(keyword: str) -> Path | None:
    key = keyword.lower()
    for path in SOUNDS_DIR.iterdir():
        if key in path.name.lower() and path.suffix.lower() == ".mp3":
            return path
    return None


def _visual_path(keyword: str) -> Path | None:
    key = keyword.lower()
    for path in VISUAL_DIR.iterdir():
        if key in path.name.lower() and path.suffix.lower() == ".png":
            return path
    return None


class GameEffects:
    def __init__(self) -> None:
        self._mixer_ready = False
        self._sounds: dict[str, pygame.mixer.Sound | None] = {}
        self._stickers: dict[str, pygame.Surface | None] = {}
        self._badge_cache: dict[tuple[str, int], pygame.Surface] = {}

        self.goal_flash_frames = 0
        self.goal_flash_color: tuple[int, int, int] | None = None
        self.goal_flash_target: str | None = None

        self.result_kind: str | None = None
        self.result_frames = 0
        self._match_settled = False

        self._last_score: tuple[int, int] | None = None
        self._prev_live = None
        self._last_hit_ms = 0
        self._result_channel: pygame.mixer.Channel | None = None

    def reset(self) -> None:
        self.goal_flash_frames = 0
        self.goal_flash_color = None
        self.goal_flash_target = None
        self._clear_match_result()
        self._last_score = None
        self._prev_live = None
        self._last_hit_ms = 0

    def _clear_match_result(self) -> None:
        """Новый матч (счёт сброшен) — можно снова показать стикер."""
        self.result_kind = None
        self.result_frames = 0
        self._match_settled = False

    def warm_up(self) -> None:
        """Предзагрузка стикеров и звуков при старте матча."""
        self._load_stickers()
        try:
            self._ensure_mixer()
        except pygame.error:
            pass

    def _load_stickers(self) -> None:
        for kind, filename in RESULT_STICKER_FILES.items():
            path = VISUAL_DIR / filename
            if not path.is_file():
                path = _visual_path("you won" if kind == "won" else "you lost")
            if path is None or not path.is_file():
                self._stickers[kind] = None
                continue
            try:
                loaded = pygame.image.load(str(path))
                if pygame.display.get_surface() is not None:
                    loaded = loaded.convert_alpha()
                self._stickers[kind] = loaded
            except pygame.error:
                self._stickers[kind] = None

    def _ensure_mixer(self) -> None:
        if self._mixer_ready:
            return
        if not pygame.mixer.get_init():
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
        self._result_channel = pygame.mixer.Channel(RESULT_CHANNEL)
        for name, key in SOUND_FILE_KEYS.items():
            path = _sound_path(key)
            if path is None:
                self._sounds[name] = None
            else:
                try:
                    self._sounds[name] = pygame.mixer.Sound(str(path))
                except pygame.error:
                    self._sounds[name] = None
        self._load_stickers()
        self._mixer_ready = True

    def _play(self, name: str, volume: float) -> None:
        try:
            self._ensure_mixer()
        except pygame.error:
            return
        snd = self._sounds.get(name)
        if snd is None:
            return
        snd.set_volume(max(0.0, min(1.0, volume)))
        snd.play()

    def _play_result_sound(self, result_kind: str, volume: float) -> None:
        """Звук победы/поражения — отдельный канал, вместе со стикером."""
        try:
            self._ensure_mixer()
        except pygame.error:
            return
        sound_name = RESULT_SOUND_BY_KIND.get(result_kind)
        if sound_name is None:
            return
        snd = self._sounds.get(sound_name)
        if snd is None or self._result_channel is None:
            return
        vol = max(0.0, min(1.0, volume))
        self._result_channel.stop()
        self._result_channel.set_volume(vol)
        self._result_channel.play(snd)

    def _trigger_goal_flash(self, *, i_scored: bool) -> None:
        """i_scored=True — я забил (зелёный, верх); False — пропустил (красный, низ)."""
        if i_scored:
            self.goal_flash_target = GOAL_FLASH_TARGET_WHEN_SCORED
            self.goal_flash_color = GOAL_FLASH_COLOR_SCORED
        else:
            self.goal_flash_target = GOAL_FLASH_TARGET_WHEN_CONCEDED
            self.goal_flash_color = GOAL_FLASH_COLOR_CONCEDED
        self.goal_flash_frames = GOAL_FLASH_FRAMES

    def _handle_score_change(
        self,
        my_score: int,
        their_score: int,
        volume: float,
        *,
        match_result_enabled: bool = False,
    ) -> None:
        """Реагирует на изменение счёта с прошлого кадра (вспышки и звуки гола)."""
        if self._last_score is None:
            return

        prev_mine, prev_theirs = self._last_score
        if my_score + their_score < prev_mine + prev_theirs:
            return

        i_scored = my_score > prev_mine
        i_conceded = their_score > prev_theirs
        first_to_five = match_result_enabled

        if i_scored:
            self._trigger_goal_flash(i_scored=True)
            if not (first_to_five and my_score >= MATCH_WIN_SCORE):
                self._play("goal", volume)
        if i_conceded:
            self._trigger_goal_flash(i_scored=False)
            if not (first_to_five and their_score >= MATCH_WIN_SCORE):
                self._play("goal", volume)

    def _current_score(
        self,
        live,
        persisted_score: tuple[int, int] | None,
    ) -> tuple[int, int] | None:
        candidates: list[tuple[int, int]] = []
        if live is not None:
            candidates.append(live.score)
        if self._last_score is not None:
            candidates.append(self._last_score)
        if persisted_score is not None:
            candidates.append(persisted_score)
        if not candidates:
            return None
        return max(candidates, key=lambda s: (s[0] + s[1], max(s[0], s[1])))

    def _try_show_match_result(
        self,
        my_score: int,
        their_score: int,
        volume: float,
        *,
        first_to_five: bool,
    ) -> None:
        if not first_to_five or self._match_settled:
            return
        if my_score >= MATCH_WIN_SCORE:
            self._activate_result("won", volume)
        elif their_score >= MATCH_WIN_SCORE:
            self._activate_result("lost", volume)

    def _activate_result(self, result_kind: str, volume: float) -> None:
        self._load_stickers()
        if self._stickers.get(result_kind) is None:
            return
        self.result_kind = result_kind
        self.result_frames = RESULT_OVERLAY_FRAMES
        self._match_settled = True
        try:
            self._play_result_sound(result_kind, volume)
        except pygame.error:
            pass

    def _result_badge(
        self,
        sticker_key: str,
        sticker: pygame.Surface,
        diameter: int,
    ) -> pygame.Surface:
        cache_key = (sticker_key, diameter)
        cached = self._badge_cache.get(cache_key)
        if cached is not None:
            return cached
        content = _sticker_content_rect(sticker)
        trimmed = sticker.subsurface(content).copy()
        tw, th = trimmed.get_size()
        scale = diameter / max(tw, th)
        sw, sh = max(1, int(tw * scale)), max(1, int(th * scale))
        scaled = pygame.transform.smoothscale(trimmed, (sw, sh))
        badge = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        badge.blit(scaled, ((diameter - sw) // 2, (diameter - sh) // 2))
        mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (diameter // 2, diameter // 2), diameter // 2)
        badge.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self._badge_cache[cache_key] = badge
        return badge

    def _play_hit_sound(self, volume: float) -> None:
        now = pygame.time.get_ticks()
        if now - self._last_hit_ms < HIT_COOLDOWN_MS:
            return
        self._play("hit", volume)
        self._last_hit_ms = now

    def _process_state_step(
        self,
        prev,
        live,
        volume: float,
        *,
        first_to_five: bool,
    ) -> None:
        """Один шаг GameState с сервера (~1/120 с): голы, удары, конец матча."""
        my_score, their_score = live.score

        if self._last_score is not None:
            prev_mine, prev_theirs = self._last_score
            if my_score + their_score < prev_mine + prev_theirs:
                self._clear_match_result()
            else:
                self._handle_score_change(
                    my_score,
                    their_score,
                    volume,
                    match_result_enabled=first_to_five,
                )

        if puck_hit_between(prev, live):
            self._play_hit_sound(volume)

        self._try_show_match_result(
            my_score,
            their_score,
            volume,
            first_to_five=first_to_five,
        )
        self._last_score = (my_score, their_score)

    def tick(
        self,
        live,
        state_steps: list,
        messages: list[str],
        volume: float,
        *,
        first_to_five: bool = False,
        persisted_score: tuple[int, int] | None = None,
    ) -> None:
        if self.goal_flash_frames > 0:
            self.goal_flash_frames -= 1
            if self.goal_flash_frames == 0:
                self.goal_flash_color = None
                self.goal_flash_target = None

        steps = state_steps
        if not steps and live is not None:
            steps = [live]

        prev = self._prev_live
        for step in steps:
            if prev is not None:
                self._process_state_step(
                    prev,
                    step,
                    volume,
                    first_to_five=first_to_five,
                )
            else:
                my_score, their_score = step.score
                if self._last_score is not None:
                    prev_mine, prev_theirs = self._last_score
                    if my_score + their_score < prev_mine + prev_theirs:
                        self._clear_match_result()
                self._try_show_match_result(
                    my_score,
                    their_score,
                    volume,
                    first_to_five=first_to_five,
                )
                self._last_score = step.score
            prev = step

        if prev is not None:
            self._prev_live = prev

        score = self._current_score(live, persisted_score)
        if score is not None:
            self._try_show_match_result(
                score[0],
                score[1],
                volume,
                first_to_five=first_to_five,
            )

        for msg in messages:
            if first_to_five and "max_score" in msg.lower() and score is not None:
                self._try_show_match_result(
                    score[0],
                    score[1],
                    volume,
                    first_to_five=True,
                )

        if self.result_frames > 0:
            self.result_frames -= 1
            if self.result_frames == 0:
                self.result_kind = None

    def draw_goal_flash(
        self,
        surf: pygame.Surface,
        tf: FieldTransform,
        mode_name: str | None = None,
    ) -> None:
        if self.goal_flash_frames <= 0 or not self.goal_flash_color or not self.goal_flash_target:
            return
        rect = goal_flash_rect(tf, mode_name, self.goal_flash_target)
        pulse = self.goal_flash_frames / GOAL_FLASH_FRAMES
        alpha = int(120 + 90 * pulse)
        pad = 8
        layer = pygame.Surface((rect.w + pad * 2, rect.h + pad * 2), pygame.SRCALPHA)
        color = (*self.goal_flash_color, alpha)
        pygame.draw.rect(layer, color, layer.get_rect(), border_radius=max(6, rect.h // 2))
        surf.blit(layer, (rect.x - pad, rect.y - pad))

    def draw_result_overlay(
        self,
        surf: pygame.Surface,
        tf: FieldTransform | None = None,
    ) -> None:
        if not self.result_kind or self.result_frames <= 0:
            return
        self._load_stickers()
        sticker_key = "won" if self.result_kind == "won" else "lost"
        sticker = self._stickers.get(sticker_key)
        if sticker is None:
            return

        if tf is not None:
            field_rect = tf.field_overlay_rect()
            center = tf.field_overlay_center()
            diameter = max(
                96,
                int(min(field_rect.width, field_rect.height) * RESULT_BADGE_FIELD_FRAC),
            )
            field_dim = pygame.Surface((field_rect.w, field_rect.h), pygame.SRCALPHA)
            field_dim.fill((0, 0, 0, 130))
            surf.blit(field_dim, field_rect.topleft)
        else:
            center = (surf.get_width() // 2, surf.get_height() // 2)
            diameter = max(
                96,
                int(min(surf.get_width(), surf.get_height()) * RESULT_BADGE_FIELD_FRAC),
            )
            dim = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 100))
            surf.blit(dim, (0, 0))

        badge = self._result_badge(sticker_key, sticker, diameter)
        glow = pygame.Surface((diameter + 24, diameter + 24), pygame.SRCALPHA)
        pygame.draw.circle(
            glow,
            (0, 0, 0, 100),
            (glow.get_width() // 2, glow.get_height() // 2),
            diameter // 2 + 10,
        )
        surf.blit(glow, glow.get_rect(center=center))
        surf.blit(badge, badge.get_rect(center=center))
