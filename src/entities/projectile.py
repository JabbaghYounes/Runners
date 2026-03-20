from __future__ import annotations

import pygame
from typing import Tuple, Optional
from src.entities.entity import Entity
from src.constants import TILE_SIZE


class Projectile(Entity):
    def __init__(self, x: float, y: float, vx: float, vy: float, damage: int, owner: object = None):
        super().__init__(x, y, 8, 4)
        self.vx: float = vx
        self.vy: float = vy
        self.damage: int = damage
        self.owner = owner
        self.ttl: float = 2.0

    def update(self, dt: float, tile_map=None) -> None:
        self.rect.x += int(self.vx * dt)
        self.rect.y += int(self.vy * dt)
        self.ttl -= dt
        if self.ttl <= 0:
            self.alive = False
            return

        # Tile collision: despawn when the projectile centre enters a solid tile.
        if tile_map is not None:
            col = self.rect.centerx // TILE_SIZE
            row = self.rect.centery // TILE_SIZE

            # Out-of-map (negative edge)
            if col < 0 or row < 0:
                self.alive = False
                return

            # Out-of-map (positive edge) — only checked when the map exposes size.
            cols = getattr(tile_map, 'cols', None)
            rows = getattr(tile_map, 'rows', None)
            if cols is not None and col >= cols:
                self.alive = False
                return
            if rows is not None and row >= rows:
                self.alive = False
                return

            if tile_map.is_solid(col, row):
                self.alive = False

    def render(self, screen: pygame.Surface, camera_offset: Tuple[int, int]) -> None:
        if not self.alive:
            return
        ox, oy = camera_offset
        sx = self.rect.x - ox
        sy = self.rect.y - oy
        pygame.draw.rect(screen, (255, 220, 80), (sx, sy, self.rect.w, self.rect.h))
