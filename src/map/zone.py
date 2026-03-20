"""Zone model -- a named rectangular region of the game map."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pygame


@dataclass
class Zone:
    """A rectangular region that triggers music and houses spawn points.

    Attributes:
        name:          Human-readable zone identifier.
        rect:          Bounding box -- either a pygame.Rect or (x, y, w, h) tuple.
        spawn_points:  List of (x, y) positions.
        music_track:   Path to the OGG file to loop, or None.
        enemy_spawns:  List of {"type": str, "pos": [x, y]} dicts.
        color:         RGB tint used on the mini-map and tactical overlay.
    """

    name: str
    rect: "pygame.Rect | Tuple[int, int, int, int]"
    spawn_points: Optional[List[Tuple[float, float]]] = field(default_factory=list)
    music_track: Optional[str] = None
    enemy_spawns: Optional[List[dict]] = field(default_factory=list)
    color: Tuple[int, int, int] = (60, 120, 180)

    def __post_init__(self) -> None:
        if self.spawn_points is None:
            self.spawn_points = []
        if self.enemy_spawns is None:
            self.enemy_spawns = []

    def contains(self, pos: Tuple[float, float]) -> bool:
        """Return True if *pos* falls within the zone's bounding rectangle."""
        if isinstance(self.rect, pygame.Rect):
            return self.rect.collidepoint(int(pos[0]), int(pos[1]))
        x, y, w, h = self.rect
        px, py = pos
        return x <= px < x + w and y <= py < y + h

    def __repr__(self) -> str:
        return f"Zone({self.name!r}, {self.rect})"
