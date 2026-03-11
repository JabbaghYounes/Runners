"""Extraction zone value object.

Represents the rectangular area on the map where players can initiate
extraction.  It is a pure data object with no behaviour — the
:class:`~src.systems.extraction_system.ExtractionSystem` uses it only for
overlap detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame


@dataclass
class ExtractionZone:
    """A named rectangular region that triggers extraction.

    Args:
        rect: World-space :class:`pygame.Rect` defining the zone boundary.
        name: Human-readable label shown on the map overlay.
    """

    rect: pygame.Rect
    name: str = "Extraction"

    # Convenience constructor -----------------------------------------------

    @classmethod
    def from_topleft(
        cls,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str = "Extraction",
    ) -> "ExtractionZone":
        """Build a zone from top-left coordinates and dimensions."""
        return cls(rect=pygame.Rect(x, y, width, height), name=name)
