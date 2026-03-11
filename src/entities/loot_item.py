"""LootItem — a world-space item entity that the player can pick up."""
from __future__ import annotations

from src.inventory.item import Item


class _SimpleRect:
    """Minimal rect used when pygame is not available."""

    def __init__(self, x: float, y: float) -> None:
        self.centerx = x
        self.centery = y
        self.center = (x, y)


class LootItem:
    """A dropped item sitting in the game world at a specific position."""

    def __init__(self, item: Item, x: float, y: float) -> None:
        self.item = item
        self.rect = _SimpleRect(x, y)
        self.alive = True
