"""Zone model — a named rectangular region of the game map."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Zone:
    """A rectangular region that triggers music and houses spawn points.

    Attributes:
        name:         Human-readable zone identifier (e.g. ``"zone_alpha"``).
        rect:         ``(x, y, width, height)`` bounding box in world pixels.
        spawn_points: List of ``(x, y)`` positions where entities may spawn.
        music_track:  Path to the OGG file to loop while the player is here,
                      or *None* for silence.
    """

    name: str
    rect: Tuple[int, int, int, int]
    spawn_points: List[Tuple[int, int]] = field(default_factory=list)
    music_track: Optional[str] = None

    # ------------------------------------------------------------------

    def contains(self, pos: Tuple[int, int]) -> bool:
        """Return *True* if world-space *pos* ``(x, y)`` lies inside this zone."""
        x, y, w, h = self.rect
        px, py = pos
        return x <= px < x + w and y <= py < y + h
