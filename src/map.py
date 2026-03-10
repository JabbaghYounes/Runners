"""TileMap, Camera, Zone, and SpawnPoint — world/map management."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import pygame


@dataclass
class Zone:
    """Named rectangular region with type metadata."""

    name: str
    zone_type: str  # "spawn", "challenge", "extraction"
    rect: pygame.Rect
    metadata: dict = field(default_factory=dict)


@dataclass
class SpawnPoint:
    """Marker for entity spawning."""

    pos: tuple[float, float]
    entity_type: str  # "player", "enemy", "loot"
    metadata: dict = field(default_factory=dict)


class Camera:
    """Follows the player with smooth lerp; converts world <-> screen coords."""

    def __init__(self, width: int, height: int) -> None:
        self.offset = pygame.math.Vector2(0, 0)
        self.width = width
        self.height = height
        self.lerp_speed = 5.0

    def update(self, target_pos: pygame.math.Vector2, dt: float) -> None:
        target_offset = pygame.math.Vector2(
            target_pos.x - self.width / 2,
            target_pos.y - self.height / 2,
        )
        self.offset += (target_offset - self.offset) * min(self.lerp_speed * dt, 1.0)

    def world_to_screen(self, world_pos: pygame.math.Vector2) -> pygame.math.Vector2:
        return world_pos - self.offset

    def screen_to_world(self, screen_pos: pygame.math.Vector2) -> pygame.math.Vector2:
        return screen_pos + self.offset


class TileMap:
    """Loads tile data from JSON, provides collision grid, zones, and spawns.

    Expected JSON schema::

        {
          "width": 80, "height": 60, "tile_size": 32,
          "layers": {"ground": [...], "walls": [...], "decoration": [...]},
          "collision": [[0,0,1,...], ...],
          "zones": [...],
          "enemy_spawns": [{"pos": [x,y], "tier": "scout", "patrol_path": [...]}]
        }
    """

    def __init__(self, map_path: str | Path | None = None) -> None:
        self.tile_size: int = 32
        self.width: int = 0   # in tiles
        self.height: int = 0  # in tiles
        self.layers: dict[str, list[list[int]]] = {}
        self.collision: list[list[int]] = []
        self.zones: list[Zone] = []
        self._enemy_spawns: list[dict] = []

        if map_path is not None:
            self.load(map_path)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, map_path: str | Path) -> None:
        with open(map_path, "r") as fh:
            data = json.load(fh)

        self.width = data.get("width", 0)
        self.height = data.get("height", 0)
        self.tile_size = data.get("tile_size", 32)
        self.layers = data.get("layers", {})
        self.collision = data.get("collision", [])

        # Parse zones
        self.zones = []
        for z in data.get("zones", []):
            self.zones.append(
                Zone(
                    name=z["name"],
                    zone_type=z["type"],
                    rect=pygame.Rect(*z["rect"]),
                    metadata={k: v for k, v in z.items() if k not in ("name", "type", "rect")},
                )
            )

        # Store raw enemy spawn data
        self._enemy_spawns = data.get("enemy_spawns", [])

    # ------------------------------------------------------------------
    # Collision
    # ------------------------------------------------------------------

    def is_solid(self, grid_x: int, grid_y: int) -> bool:
        """Return ``True`` if the tile at grid position is solid (wall)."""
        if grid_x < 0 or grid_y < 0:
            return True
        if grid_y >= len(self.collision) or grid_x >= len(self.collision[0]) if self.collision else True:
            return True
        return self.collision[grid_y][grid_x] != 0

    # ------------------------------------------------------------------
    # Raycast
    # ------------------------------------------------------------------

    def raycast_solid(
        self,
        start: Sequence[float],
        end: Sequence[float],
    ) -> bool:
        """Bresenham grid raycast.  Returns ``True`` if any solid tile lies
        between *start* and *end* (world-pixel coordinates)."""
        ts = self.tile_size
        x0, y0 = int(start[0]) // ts, int(start[1]) // ts
        x1, y1 = int(end[0]) // ts, int(end[1]) // ts

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            if (x0, y0) != (int(start[0]) // ts, int(start[1]) // ts):
                if self.is_solid(x0, y0):
                    return True
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
        return False

    # ------------------------------------------------------------------
    # Spawns
    # ------------------------------------------------------------------

    def get_enemy_spawns(self) -> list[dict]:
        """Return the parsed ``enemy_spawns`` array from the map JSON."""
        return list(self._enemy_spawns)

    # ------------------------------------------------------------------
    # Drawing (stub — actual rendering handled by tilemap-rendering feature)
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        """Render visible tiles.  Placeholder for tilemap-rendering feature."""
