"""PhysicsSystem — gravity, smooth acceleration/deceleration, tile collision."""
from __future__ import annotations

from typing import List

import pygame

from src.constants import (
    GRAVITY, ACCEL, DECEL, SLIDE_DECEL, TILE_SIZE,
)


class PhysicsSystem:
    """Applies physics to all entities that expose ``vx``, ``vy``, and ``rect``.

    Each entity must have:
    - ``vx``, ``vy``  — current velocity (px/s)
    - ``target_vx``   — desired horizontal velocity set by input
    - ``slide_timer`` — seconds remaining in slide (0 when not sliding)
    - ``on_ground``   — bool, written by this system
    - ``rect``        — pygame.Rect

    The tile_map must implement ``is_solid(col, row) -> bool``.
    """

    def update(self, entities: List, tile_map, dt: float) -> None:
        for entity in entities:
            if not getattr(entity, "alive", True):
                continue
            self._step(entity, tile_map, dt)

    # ------------------------------------------------------------------
    # Single-entity step
    # ------------------------------------------------------------------

    def _step(self, entity, tile_map, dt: float) -> None:
        # 1. Gravity
        entity.vy += GRAVITY * dt

        # 2. Horizontal acceleration / deceleration
        slide_timer = getattr(entity, "slide_timer", 0.0)
        target_vx   = getattr(entity, "target_vx",  0.0)

        if slide_timer > 0:
            # Slide friction: decelerate vx toward 0 regardless of target
            entity.vx = self._approach(entity.vx, 0.0, SLIDE_DECEL * dt)
        else:
            if target_vx == 0.0:
                entity.vx = self._approach(entity.vx, 0.0, DECEL * dt)
            else:
                entity.vx = self._approach(entity.vx, target_vx, ACCEL * dt)

        # 3. Move X then resolve, then move Y then resolve
        entity.rect.x += int(entity.vx * dt)
        self._resolve_x(entity, tile_map)

        entity.rect.y += int(entity.vy * dt)
        on_ground = self._resolve_y(entity, tile_map)
        entity.on_ground = on_ground

    # ------------------------------------------------------------------
    # Collision resolution helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _approach(current: float, target: float, step: float) -> float:
        """Move *current* toward *target* by at most *step*, never overshooting."""
        if current < target:
            return min(current + step, target)
        return max(current - step, target)

    @staticmethod
    def _tiles_for_rect(rect: pygame.Rect, tile_size: int):
        """Yield (col, row) pairs for all tiles overlapping *rect*."""
        left_col  = rect.left   // tile_size
        right_col = (rect.right  - 1) // tile_size
        top_row   = rect.top    // tile_size
        bot_row   = (rect.bottom - 1) // tile_size
        for row in range(top_row, bot_row + 1):
            for col in range(left_col, right_col + 1):
                yield col, row

    def _resolve_x(self, entity, tile_map) -> None:
        ts = getattr(tile_map, "tile_size", TILE_SIZE)
        for col, row in self._tiles_for_rect(entity.rect, ts):
            if tile_map.is_solid(col, row):
                tile_rect = pygame.Rect(col * ts, row * ts, ts, ts)
                if entity.rect.colliderect(tile_rect):
                    if entity.vx > 0:
                        entity.rect.right = tile_rect.left
                    elif entity.vx < 0:
                        entity.rect.left = tile_rect.right
                    break

    def _resolve_y(self, entity, tile_map) -> bool:
        """Resolve vertical collisions; return True if entity is now on_ground."""
        on_ground = False
        ts = getattr(tile_map, "tile_size", TILE_SIZE)
        for col, row in self._tiles_for_rect(entity.rect, ts):
            if tile_map.is_solid(col, row):
                tile_rect = pygame.Rect(col * ts, row * ts, ts, ts)
                if entity.rect.colliderect(tile_rect):
                    if entity.vy > 0:
                        entity.rect.bottom = tile_rect.top
                        on_ground = True
                    elif entity.vy < 0:
                        entity.rect.top = tile_rect.bottom
                    entity.vy = 0.0
                    break
        return on_ground
