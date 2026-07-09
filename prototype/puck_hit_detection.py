"""Детекция удара шайбы — зеркало server/physics_engine.py + server/objects.update_puck_data."""
from __future__ import annotations

import math

from game_field import (
    DOWN_WALL,
    GOAL_LEFT,
    GOAL_RIGHT,
    LEFT_WALL,
    PLAYER_RADIUS,
    PUCK_RADIUS,
    RIGHT_WALL,
    TOP_WALL,
)

# Минимальная скорость удара (после server/update_puck_data, до friction).
MIN_HIT_SPEED = 0.35


def _vel(vector: tuple[float, float], speed: float) -> tuple[float, float]:
    return vector[0] * speed, vector[1] * speed


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _wall_hit_at(pos: tuple[float, float], velocity: tuple[float, float]) -> bool:
    """True, если calculate_puck_wall_collision отразила бы скорость (удар о борт)."""
    px, py = pos
    vx, vy = velocity

    if px <= LEFT_WALL + PUCK_RADIUS and vx < 0:
        return True

    in_goal_band_y = py >= TOP_WALL - PUCK_RADIUS or py <= DOWN_WALL + PUCK_RADIUS
    if in_goal_band_y and px <= GOAL_LEFT + PUCK_RADIUS and vx < 0:
        return True

    if px >= RIGHT_WALL - PUCK_RADIUS and vx > 0:
        return True

    if in_goal_band_y and px >= GOAL_RIGHT - PUCK_RADIUS and vx > 0:
        return True

    if py >= TOP_WALL - PUCK_RADIUS:
        if px <= GOAL_LEFT + PUCK_RADIUS or px >= GOAL_RIGHT - PUCK_RADIUS:
            if vy > 0:
                return True

    if py <= DOWN_WALL + PUCK_RADIUS:
        if px <= GOAL_LEFT + PUCK_RADIUS or px >= GOAL_RIGHT - PUCK_RADIUS:
            if vy < 0:
                return True

    return False


def _stick_hit_at(
    player_pos: tuple[float, float],
    player_velocity: tuple[float, float],
    puck_pos: tuple[float, float],
    puck_velocity: tuple[float, float],
) -> bool:
    """True, если calculate_player_puck_collision отразила бы шайбу (удар о стик)."""
    distance = _dist(player_pos, puck_pos)
    if distance >= PLAYER_RADIUS + PUCK_RADIUS:
        return False
    if distance == 0:
        return math.hypot(*puck_velocity) >= MIN_HIT_SPEED

    rel_vx = puck_velocity[0] - player_velocity[0]
    rel_vy = puck_velocity[1] - player_velocity[1]
    nx = (puck_pos[0] - player_pos[0]) / distance
    ny = (puck_pos[1] - player_pos[1]) / distance
    return rel_vx * nx + rel_vy * ny < 0


def _simulate_puck_tick(prev, live) -> bool:
    """
    Один тик update_puck_data на сервере:
    move → wall → player1 → player2. Возвращает True при любом ударе.
    """
    px, py = prev.puck
    puck_vel = _vel(prev.puck_vector, prev.puck_speed)
    if math.hypot(*puck_vel) < MIN_HIT_SPEED:
        return False

    px += puck_vel[0]
    py += puck_vel[1]
    pos = (px, py)

    if _wall_hit_at(pos, puck_vel):
        return True

    p1_vel = _vel(live.player1_vector, live.player1_speed)
    if _stick_hit_at(live.player1, p1_vel, pos, puck_vel):
        return True

    p2_vel = _vel(live.player2_vector, live.player2_speed)
    if _stick_hit_at(live.player2, p2_vel, pos, puck_vel):
        return True

    return False


def puck_hit_between(prev, live) -> bool:
    """Удар шайбы между двумя последовательными GameState с сервера."""
    if prev is None or live is None:
        return False
    if prev.score != live.score:
        # Гол / сброс после гола — не звук удара.
        return False
    if live.puck_speed < MIN_HIT_SPEED and prev.puck_speed < MIN_HIT_SPEED:
        return False
    return _simulate_puck_tick(prev, live)
