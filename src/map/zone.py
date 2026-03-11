"""Zone — named rectangular region of the game world."""
from __future__ import annotations
from typing import List, Optional, Tuple


class Zone:
    """Named rectangular region on the tile map.

    Args:
        name:         Human-readable zone name (e.g. "SECTOR ALPHA").
        rect:         A pygame.Rect (or duck-typed rect with x/y/w/h) defining
                      the world-space bounds.
        spawn_points: List of (x, y) world-space spawn positions within the zone.
        music_track:  Asset path for the background music track for this zone.
    """

    def __init__(
        self,
        name: str,
        rect: object,
        spawn_points: Optional[List[Tuple[float, float]]] = None,
        music_track: Optional[str] = None,
    ) -> None:
        self.name = name
        self.rect = rect
        self.spawn_points: List[Tuple[float, float]] = spawn_points or []
        self.music_track = music_track

    def contains(self, pos: Tuple[float, float]) -> bool:
        """Return True if world-space point *pos* lies within this zone's rect."""
        return self.rect.collidepoint(pos)
