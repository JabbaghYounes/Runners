"""LootItem entity — an item lying in the world waiting to be picked up."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.inventory.item import Item


class LootItem:
    """A dropped item lying in the world."""

    def __init__(self, item: "Item", x: float, y: float) -> None:
        self.item = item
        self.alive: bool = True
        self._x = x
        self._y = y

        import pygame
        self.rect = pygame.Rect(int(x), int(y), 24, 24)
