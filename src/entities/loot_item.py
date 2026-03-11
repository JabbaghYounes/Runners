"""LootItem — a world-space wrapper for a dropped Item.

When the player presses E while within PICKUP_RADIUS of a LootItem,
``LootSystem`` calls ``pickup()`` which returns the wrapped item and
marks this entity as dead (removing it from the world next frame).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from src.entities.entity import Entity

if TYPE_CHECKING:
    from src.inventory.item import Item

# Pixels: the player must be within this distance to pick up the item.
PICKUP_RADIUS: int = 48


class LootItem(Entity):
    """A dropped item lying in the game world.

    Attributes:
        item:        The wrapped ``Item`` instance.
        picked_up:   Set to ``True`` after a successful pickup; also sets
                     ``alive = False`` so the owning system removes it.
    """

    def __init__(self, item: "Item", x: float, y: float) -> None:
        super().__init__(x, y, width=24, height=24)
        self.item = item
        self.picked_up = False

    # ------------------------------------------------------------------
    # Proximity helpers
    # ------------------------------------------------------------------

    def distance_to(self, px: float, py: float) -> float:
        """Euclidean distance from this entity's centre to point *(px, py)*."""
        cx, cy = self.center
        return math.hypot(cx - px, cy - py)

    def in_pickup_range(self, px: float, py: float) -> bool:
        """Return ``True`` if *(px, py)* is within ``PICKUP_RADIUS``."""
        return self.distance_to(px, py) <= PICKUP_RADIUS

    # ------------------------------------------------------------------
    # Pickup
    # ------------------------------------------------------------------

    def pickup(self) -> "Item":
        """Mark as picked up, deactivate, and return the wrapped item."""
        self.picked_up = True
        self.alive = False
        return self.item

    # ------------------------------------------------------------------
    # Frame methods (rendering deferred to full engine integration)
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:  # noqa: ARG002
        pass

    def render(
        self,
        surface: object,  # noqa: ARG002
        camera_offset: tuple[float, float] = (0.0, 0.0),  # noqa: ARG002
    ) -> None:
        pass
