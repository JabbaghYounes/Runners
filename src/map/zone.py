"""Zone model — a named rectangular region of the game map."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Zone:
    """A rectangular region that triggers music and houses spawn points.

    Attributes:
        name:          Human-readable zone identifier (e.g. ``"zone_alpha"``).
        rect:          ``(x, y, width, height)`` bounding box in world pixels.
        spawn_points:  List of ``(x, y)`` positions where loot/players may spawn.
        music_track:   Path to the OGG file to loop while the player is here,
                       or *None* for silence.
        enemy_spawns:  List of ``{"type": str, "pos": [x, y]}`` dicts describing
                       which robot types to place in this zone at round start.
    """

    name: str
    rect: Tuple[int, int, int, int]
    spawn_points: List[Tuple[int, int]] = field(default_factory=list)
    music_track: Optional[str] = None
    enemy_spawns: List[dict] = field(default_factory=list)

    def contains(self, pos: Tuple[int, int]) -> bool:
        """Return True if *pos* falls within the zone's bounding rectangle.

        The left and top edges are inclusive; right and bottom edges are
        exclusive — matching ``pygame.Rect`` hit-test semantics.
        """
        x, y, w, h = self.rect
        px, py = pos
        return x <= px < x + w and y <= py < y + h
