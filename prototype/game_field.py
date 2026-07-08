"""
Экран 2 — отрисовка игрового поля.
Координаты совпадают с server/constants.py (центр поля — 0,0; Y вверх).
"""
from __future__ import annotations

from pathlib import Path

import pygame

# Зеркало server/constants.py — не менять без согласования с сервером.
LEFT_WALL = -200.0
RIGHT_WALL = 200.0
TOP_WALL = 300.0
DOWN_WALL = -300.0
GOAL_LEFT = -100.0
GOAL_RIGHT = 100.0
CENTER_CIRCLE_R = 65.0
PLAYER_RADIUS = 50.0

FIELD_W = RIGHT_WALL - LEFT_WALL
FIELD_H = TOP_WALL - DOWN_WALL

FIELDS_DIR = Path(__file__).resolve().parent.parent / "images" / "fields"
NEON_VELOCITY_FIELD_FILE = "neon_velocity_field.png"

# Области внутри мокапа 703×1024. Ширина игровой зоны — до табло, не включая его.
NEON_MOCKUP_SIZE = (703, 1024)
NEON_PLAY_NORM = (58 / 703, 58 / 1024, 517 / 703, 908 / 1024)
NEON_SCORE_NORM = (584 / 703, 58 / 1024, 82 / 703, 908 / 1024)

NEON_THEME = {
    "background": (0, 0, 0),
    "score_text": (47, 208, 255),
}

_neon_field_image: pygame.Surface | None = None


def _load_neon_field_image() -> pygame.Surface:
    global _neon_field_image
    if _neon_field_image is None:
        _neon_field_image = pygame.image.load(str(FIELDS_DIR / NEON_VELOCITY_FIELD_FILE)).convert()
    return _neon_field_image


def _fit_image_on_screen(surf: pygame.Surface, image: pygame.Surface) -> pygame.Rect:
    sw, sh = surf.get_size()
    iw, ih = image.get_size()
    scale = min(sw / iw, sh / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    scaled = pygame.transform.smoothscale(image, (nw, nh))
    rect = scaled.get_rect(center=(sw // 2, sh // 2))
    surf.fill((0, 0, 0))
    surf.blit(scaled, rect)
    return rect


def _norm_rect(dest: pygame.Rect, norm: tuple[float, float, float, float]) -> pygame.Rect:
    nx, ny, nw, nh = norm
    return pygame.Rect(
        int(dest.x + nx * dest.w),
        int(dest.y + ny * dest.h),
        max(1, int(nw * dest.w)),
        max(1, int(nh * dest.h)),
    )


class FieldTransform:
    """Игровые координаты → пиксели. Игрок 1 (я) — снизу (отрицательный Y)."""

    def __init__(self, field_rect: pygame.Rect, score_box_rect: pygame.Rect):
        self.field_rect = field_rect
        self.score_box_rect = score_box_rect
        self.scale = field_rect.width / FIELD_W
        self.origin_x = field_rect.centerx
        self.origin_y = field_rect.centery

    def to_screen(self, gx: float, gy: float) -> tuple[int, int]:
        sx = self.origin_x + gx * self.scale
        sy = self.origin_y - gy * self.scale
        return int(round(sx)), int(round(sy))

    def to_game(self, sx: float, sy: float) -> tuple[float, float]:
        gx = (sx - self.origin_x) / self.scale
        gy = (self.origin_y - sy) / self.scale
        return gx, gy

    def clamp_player1(self, gx: float, gy: float) -> tuple[float, float]:
        """Ограничения как на сервере для player1 (нижняя половина поля)."""
        gx = max(LEFT_WALL + PLAYER_RADIUS, min(RIGHT_WALL - PLAYER_RADIUS, gx))
        gy = max(DOWN_WALL + PLAYER_RADIUS, min(-PLAYER_RADIUS, gy))
        return gx, gy

    def radius_px(self, game_radius: float) -> int:
        return max(1, int(round(game_radius * self.scale)))


def draw_score_values(
    surf: pygame.Surface,
    score_box_rect: pygame.Rect,
    score_first: int,
    score_second: int,
) -> None:
    """
    Обновляет цифры в табло поверх мокапа.
    score_first — мой счёт (низ), score_second — соперник (верх), как data.score на сервере.

    Пока не реализовано: на экране остаются 0:0 из мокапа.
    Подключим, когда будет GameState с бэкенда — цифры в том же стиле и позиции.
    """
    _ = (surf, score_box_rect, score_first, score_second)


def draw_game_field(
    surf: pygame.Surface,
    screen_size: tuple[int, int],
    theme: dict | None = None,
    live_score: tuple[int, int] | None = None,
):
    """Neon Velocity — фон и табло строго из мокапа. live_score — для будущего обновления с сервера."""
    theme = theme or NEON_THEME
    mockup = _load_neon_field_image()
    dest_rect = _fit_image_on_screen(surf, mockup)

    play_rect = _norm_rect(dest_rect, NEON_PLAY_NORM)
    score_rect = _norm_rect(dest_rect, NEON_SCORE_NORM)
    tf = FieldTransform(play_rect, score_rect)

    if live_score is not None:
        draw_score_values(surf, score_rect, live_score[0], live_score[1])

    return tf
