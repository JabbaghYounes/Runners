"""Zone — named rectangular region of the game map."""
from __future__ import annotations
from typing import List, Optional, Tuple


class Zone:
    """A named rectangular zone on the map.

    Attributes:
        name: Human-readable zone identifier (e.g. "SECTOR ALPHA").
        rect: Bounding rectangle in world-tile coordinates.
        spawn_points: List of (x, y) world positions for enemy/loot spawning.
        music_track: Audio track filename to play when player is in this zone.
    """

    def __init__(
        self,
        name: str,
        rect,
        spawn_points: Optional[List[Tuple[float, float]]] = None,
        music_track: Optional[str] = None,
    ) -> None:
        self.name = name
        self.rect = rect
        self.spawn_points: List[Tuple[float, float]] = spawn_points or []
        self.music_track: Optional[str] = music_track

    def contains(self, pos: Tuple[float, float]) -> bool:
        """Return True if world position *pos* is inside this zone."""
        return self.rect.collidepoint(pos)
