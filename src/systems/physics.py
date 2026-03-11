import pygame
from typing import List, Any
from src.constants import GRAVITY, TILE_SIZE

class PhysicsSystem:
    def update(self, entities: List[Any], tile_map: Any, dt: float) -> None:
        for entity in entities:
            if not getattr(entity, 'alive', True):
                continue
            if not hasattr(entity, 'vx') or not hasattr(entity, 'vy'):
                continue
            # Gravity
            entity.vy += GRAVITY * dt
            # Move X
            entity.rect.x += int(entity.vx * dt)
            self._resolve_x(entity, tile_map)
            # Move Y
            entity.rect.y += int(entity.vy * dt)
            entity.on_ground = False
            self._resolve_y(entity, tile_map)

    def _colliding_tiles(self, entity: Any, tile_map: Any) -> List[tuple]:
        ts = tile_map.tile_size
        r = entity.rect
        tiles = []
        col_start = r.left // ts
        col_end = (r.right - 1) // ts
        row_start = r.top // ts
        row_end = (r.bottom - 1) // ts
        for row in range(row_start, row_end + 1):
            for col in range(col_start, col_end + 1):
                if tile_map.is_solid(col, row):
                    tiles.append((col, row))
        return tiles

    def _resolve_x(self, entity: Any, tile_map: Any) -> None:
        ts = tile_map.tile_size
        for col, row in self._colliding_tiles(entity, tile_map):
            tile_rect = pygame.Rect(col * ts, row * ts, ts, ts)
            if entity.rect.colliderect(tile_rect):
                if entity.vx > 0:
                    entity.rect.right = tile_rect.left
                    entity.vx = 0
                elif entity.vx < 0:
                    entity.rect.left = tile_rect.right
                    entity.vx = 0

    def _resolve_y(self, entity: Any, tile_map: Any) -> None:
        ts = tile_map.tile_size
        for col, row in self._colliding_tiles(entity, tile_map):
            tile_rect = pygame.Rect(col * ts, row * ts, ts, ts)
            if entity.rect.colliderect(tile_rect):
                if entity.vy > 0:
                    entity.rect.bottom = tile_rect.top
                    entity.vy = 0
                    entity.on_ground = True
                elif entity.vy < 0:
                    entity.rect.top = tile_rect.bottom
                    entity.vy = 0
