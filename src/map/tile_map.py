from __future__ import annotations

import math
import json
from typing import List, Tuple, Optional

import pygame

from src.map.zone import Zone

TILE_AIR = 0
TILE_SOLID = 1
TILE_EXTRACTION = 2


class TileMap:
    def __init__(self) -> None:
        self.tile_size: int = TILE_SIZE
        self.tiles: List[List[int]] = []
        self.width: int = 0
        self.height: int = 0
        self.zones: List[Zone] = []
        self.extraction_rect: Optional[pygame.Rect] = None
        # player_spawns is the canonical list; player_spawn is kept for backward compat.
        self.player_spawns: List[Tuple[float, float]] = [(96.0, 832.0)]
        self.player_spawn: Tuple[float, float] = (96.0, 832.0)
        self.loot_spawns: List[Tuple[float, float]] = []
        self._tick: float = 0.0
        self.baked_minimap: Optional[pygame.Surface] = None

    @classmethod
    def load(cls, path: str) -> TileMap:
        tm = cls()
        with open(path, 'r') as f:
            data = json.load(f)
        tm.tile_size = data.get('tile_size', TILE_SIZE)
        # 'tiles' is mandatory -- raise KeyError if absent
        tm.tiles = data['tiles']
        tm.height = len(tm.tiles)
        tm.width = len(tm.tiles[0]) if tm.height > 0 else 0

        # player_spawns (new multi-point format) with backward-compat shim for
        # the legacy singular "player_spawn" key.
        if 'player_spawns' in data:
            raw = data['player_spawns']
            tm.player_spawns = [(float(p[0]), float(p[1])) for p in raw]
        elif 'player_spawn' in data:
            spawn = data['player_spawn']
            tm.player_spawns = [(float(spawn[0]), float(spawn[1]))]
        else:
            tm.player_spawns = [(96.0, 832.0)]
        # Keep the legacy scalar attribute pointing at the first spawn point.
        tm.player_spawn = tm.player_spawns[0] if tm.player_spawns else (96.0, 832.0)

        er = data.get('extraction_rect', [0, 0, 32, 32])
        tm.extraction_rect = pygame.Rect(er[0], er[1], er[2], er[3])
        tm.loot_spawns = [
            (float(p[0]), float(p[1]))
            for p in data.get('loot_spawns', [])
        ]
        for zd in data.get('zones', []):
            r = zd['rect']
            zone = Zone(
                name=zd['name'],
                rect=pygame.Rect(r[0], r[1], r[2], r[3]),
                spawn_points=[
                    (float(p[0]), float(p[1]))
                    for p in zd.get('spawn_points', [])
                ],
                music_track=zd.get('music_track'),
                enemy_spawns=zd.get('enemy_spawns', []),
                color=tuple(zd.get('color', [60, 120, 180])),
            )
            tm.zones.append(zone)
        tm.baked_minimap = tm._bake_minimap()
        return tm

    def _bake_minimap(self) -> Optional[pygame.Surface]:
        """Return a 1-px-per-tile Surface for the mini-map tile layer.

        Returns None when the map has zero dimensions (e.g. empty test maps).
        """
        if self.width == 0 or self.height == 0:
            return None
        surf = pygame.Surface((self.width, self.height))
        surf.fill((6, 10, 18))  # TILE_AIR background
        for row in range(self.height):
            for col in range(self.width):
                tile = self.tiles[row][col]
                if tile == TILE_SOLID:
                    surf.set_at((col, row), (35, 50, 70))
                elif tile == TILE_EXTRACTION:
                    surf.set_at((col, row), (0, 200, 80))
        return surf

    def is_solid(self, tx: int, ty: int) -> bool:
        if tx < 0 or ty < 0 or ty >= self.height or tx >= self.width:
            return True
        return self.tiles[ty][tx] == TILE_SOLID

    @property
    def walkability_grid(self) -> List[List[int]]:
        return [
            [1 if self.tiles[r][c] != TILE_SOLID else 0
             for c in range(self.width)]
            for r in range(self.height)
        ]

    @property
    def map_rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, self.width * self.tile_size, self.height * self.tile_size)

    def update(self, dt: float) -> None:
        self._tick += dt

    def render(self, screen: pygame.Surface, camera: object) -> None:
        ts = self.tile_size
        ox, oy = camera.offset  # type: ignore[attr-defined]
        # Visible tile range
        col_start = max(0, ox // ts)
        col_end = min(self.width, (ox + screen.get_width()) // ts + 2)
        row_start = max(0, oy // ts)
        row_end = min(self.height, (oy + screen.get_height()) // ts + 2)

        pulse = abs(math.sin(self._tick * 2.0))

        for row in range(row_start, row_end):
            for col in range(col_start, col_end):
                tile = self.tiles[row][col]
                if tile == TILE_AIR:
                    continue
                sx, sy = camera.world_to_screen(col * ts, row * ts)  # type: ignore[attr-defined]
                draw_rect = pygame.Rect(sx, sy, ts, ts)
                if tile == TILE_SOLID:
                    pygame.draw.rect(screen, (35, 50, 70), draw_rect)
                    pygame.draw.rect(screen, BORDER_DIM, draw_rect, 1)
                elif tile == TILE_EXTRACTION:
                    g = int(180 + pulse * 75)
                    color = (0, g, 80)
                    pygame.draw.rect(screen, color, draw_rect)
                    pygame.draw.rect(screen, ACCENT_GREEN, draw_rect, 2)
