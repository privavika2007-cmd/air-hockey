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
PUCK_RADIUS = 20.0

FIELD_W = RIGHT_WALL - LEFT_WALL
FIELD_H = TOP_WALL - DOWN_WALL

FIELDS_DIR = Path(__file__).resolve().parent.parent / "images" / "fields"
NEON_VELOCITY_FIELD_FILE = "neon_velocity_field.png"

# Области внутри мокапа 703×1024.
NEON_MOCKUP_SIZE = (703, 1024)
# Координаты игры — вся площадь внутри cyan-борта (включая зону у табло и ворот).
NEON_COORD_NORM = (58 / 703, 58 / 1024, 613 / 703, 908 / 1024)
# Счётные панели (скруглённые квадраты справа) — внутри neon-обводки, мокап 703×1024.
NEON_SCORE_TOP_PANEL_NORM = (575 / 703, 80 / 1024, 86 / 703, 417 / 1024)
NEON_SCORE_BOTTOM_PANEL_NORM = (575 / 703, 520 / 1024, 86 / 703, 429 / 1024)
SCORE_PANEL_RADIUS_FRAC = 0.14

NEON_THEME = {
    "background": (0, 0, 0),
    "score_text": (47, 208, 255),
}

_neon_field_image: pygame.Surface | None = None
_field_bg_cache: dict[tuple[int, int], tuple[pygame.Surface, pygame.Rect]] = {}
_field_scene_cache: dict[tuple[int, int], tuple[pygame.Surface, "FieldTransform", tuple[pygame.Rect, pygame.Rect]]] = {}
_score_overlay_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}
_score_font_cache: dict[int, pygame.font.Font] = {}
_puck_surface_cache: dict[int, pygame.Surface] = {}


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


def _score_panel_rects(dest: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect]:
    """Верхняя и нижняя счётные панели на мокапе (соперник / я)."""
    top = _norm_rect(dest, NEON_SCORE_TOP_PANEL_NORM)
    bottom = _norm_rect(dest, NEON_SCORE_BOTTOM_PANEL_NORM)
    return top, bottom


def _score_font(cell_rect: pygame.Rect, value: int) -> pygame.font.Font:
    digits = len(str(value))
    base = min(cell_rect.w, cell_rect.h) * (0.48 if digits == 1 else 0.36)
    size = max(18, int(base))
    font = _score_font_cache.get(size)
    if font is None:
        font = pygame.font.SysFont("arial", size, bold=True)
        _score_font_cache[size] = font
    return font


def _draw_score_in_panel(surf: pygame.Surface, panel: pygame.Rect, value: int) -> None:
    """Закрывает «0» на мокапе и рисует счёт по центру скруглённой панели."""
    radius = max(6, int(min(panel.w, panel.h) * SCORE_PANEL_RADIUS_FRAC))
    patch = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)
    pygame.draw.rect(patch, (0, 0, 0, 235), patch.get_rect(), border_radius=radius)
    surf.blit(patch, panel.topleft)

    text = _score_font(panel, value).render(str(value), True, NEON_THEME["score_text"])
    surf.blit(
        text,
        (panel.centerx - text.get_width() // 2, panel.centery - text.get_height() // 2),
    )


def _norm_rect(dest: pygame.Rect, norm: tuple[float, float, float, float]) -> pygame.Rect:
    nx, ny, nw, nh = norm
    return pygame.Rect(
        int(dest.x + nx * dest.w),
        int(dest.y + ny * dest.h),
        max(1, int(nw * dest.w)),
        max(1, int(nh * dest.h)),
    )


def _field_background(screen_size: tuple[int, int]) -> tuple[pygame.Surface, pygame.Rect]:
    cached = _field_bg_cache.get(screen_size)
    if cached is not None:
        return cached

    mockup = _load_neon_field_image()
    sw, sh = screen_size
    iw, ih = mockup.get_size()
    scale = min(sw / iw, sh / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    scaled = pygame.transform.smoothscale(mockup, (nw, nh))
    bg = pygame.Surface(screen_size)
    bg.fill((0, 0, 0))
    dest_rect = scaled.get_rect(center=(sw // 2, sh // 2))
    bg.blit(scaled, dest_rect)
    _field_bg_cache[screen_size] = (bg, dest_rect)
    return bg, dest_rect


class FieldTransform:
    """Игровые координаты → пиксели. Игрок 1 (я) — снизу (отрицательный Y)."""

    def __init__(
        self,
        field_rect: pygame.Rect,
        score_panel_rects: tuple[pygame.Rect, pygame.Rect],
    ):
        self.field_rect = field_rect
        self.score_panel_rects = score_panel_rects
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
        """Нижняя половина: только бортики и центральная линия (табло не блокирует)."""
        r = PLAYER_RADIUS
        gx = max(LEFT_WALL + r, min(RIGHT_WALL - r, gx))
        gy = max(DOWN_WALL + r, min(-r, gy))

        rad = self.radius_px(r)
        rink = self.field_rect
        sx, sy = self.to_screen(gx, gy)
        sx = max(rink.left + rad, min(rink.right - rad, sx))
        sy = max(self.to_screen(0, -r)[1], min(rink.bottom - rad, sy))

        gx, gy = self.to_game(sx, sy)
        gx = max(LEFT_WALL + r, min(RIGHT_WALL - r, gx))
        gy = max(DOWN_WALL + r, min(-r, gy))
        return gx, gy

    def radius_px(self, game_radius: float) -> int:
        return max(1, int(round(game_radius * self.scale)))


def draw_score_values(
    surf: pygame.Surface,
    score_panel_rects: tuple[pygame.Rect, pygame.Rect],
    score_first: int,
    score_second: int,
) -> None:
    """score_first — мой счёт (низ), score_second — соперник (верх)."""
    top_panel, bottom_panel = score_panel_rects
    _draw_score_in_panel(surf, top_panel, score_second)
    _draw_score_in_panel(surf, bottom_panel, score_first)


def get_field_scene(
    screen_size: tuple[int, int],
) -> tuple[pygame.Surface, FieldTransform, tuple[pygame.Rect, pygame.Rect]]:
    """Кэш фона и FieldTransform — не пересчитываем каждый кадр."""
    cached = _field_scene_cache.get(screen_size)
    if cached is not None:
        return cached

    bg, dest_rect = _field_background(screen_size)
    play_rect = _norm_rect(dest_rect, NEON_COORD_NORM)
    score_panel_rects = _score_panel_rects(dest_rect)
    tf = FieldTransform(play_rect, score_panel_rects)
    scene = (bg, tf, score_panel_rects)
    _field_scene_cache[screen_size] = scene
    return scene


def _score_overlay(
    screen_size: tuple[int, int],
    score_panel_rects: tuple[pygame.Rect, pygame.Rect],
    live_score: tuple[int, int],
) -> pygame.Surface:
    key = (screen_size[0], screen_size[1], live_score[0], live_score[1])
    overlay = _score_overlay_cache.get(key)
    if overlay is None:
        overlay = pygame.Surface(screen_size, pygame.SRCALPHA)
        draw_score_values(overlay, score_panel_rects, live_score[0], live_score[1])
        _score_overlay_cache[key] = overlay
    return overlay


def draw_puck(surf: pygame.Surface, tf: "FieldTransform", gx: float, gy: float) -> None:
    radius = tf.radius_px(PUCK_RADIUS)
    puck_surf = _puck_surface_cache.get(radius)
    if puck_surf is None:
        size = radius * 2 + 2
        puck_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        pygame.draw.circle(puck_surf, (80, 255, 120), center, radius)
        pygame.draw.circle(puck_surf, (200, 255, 220), center, max(1, radius // 3))
        _puck_surface_cache[radius] = puck_surf
    center = tf.to_screen(gx, gy)
    surf.blit(puck_surf, puck_surf.get_rect(center=center))


def draw_game_field(
    surf: pygame.Surface,
    screen_size: tuple[int, int],
    theme: dict | None = None,
    live_score: tuple[int, int] | None = None,
):
    """Neon Velocity — фон и табло строго из мокапа."""
    bg, tf, score_panel_rects = get_field_scene(screen_size)
    surf.blit(bg, (0, 0))
    if live_score is not None:
        surf.blit(_score_overlay(screen_size, score_panel_rects, live_score), (0, 0))
    return tf
