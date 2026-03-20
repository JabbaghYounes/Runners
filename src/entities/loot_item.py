"""LootItem entity -- a dropped item in the world that can be picked up."""
from __future__ import annotations

import math
import pygame
from typing import Tuple, Optional, Any
from src.entities.entity import Entity
from src.inventory.item import Item

PICKUP_RADIUS: float = 48.0
_SPRITE_SIZE: int = 24


class LootItem:
    """A dropped item in the game world.

    Attributes:
        item:      The :class:`~src.inventory.item.Item` this loot represents.
        x, y:      World-space position (top-left of the sprite rect).
        picked_up: True once a player has collected this loot.
        alive:     False once picked up or otherwise removed from the world.
    """

    def __init__(self, item: Item, x: float, y: float) -> None:
        self.item: Item = item
        self.x: float = x
        self.y: float = y
        self.picked_up: bool = False
        self.alive: bool = True
        self._bob_timer: float = 0.0

    @property
    def center(self) -> Tuple[float, float]:
        """Centre of the loot sprite (24x24 default)."""
        return self.x + _SPRITE_SIZE / 2, self.y + _SPRITE_SIZE / 2

    def distance_to(self, px: float, py: float) -> float:
        """Euclidean distance from the loot centre to *(px, py)*."""
        cx, cy = self.center
        return math.hypot(px - cx, py - cy)

    def in_pickup_range(self, px: float, py: float) -> bool:
        """True if *(px, py)* is within ``PICKUP_RADIUS`` of the loot centre."""
        return self.distance_to(px, py) <= PICKUP_RADIUS

    def pickup(self) -> Item:
        """Mark as picked up and return the wrapped item."""
        self.picked_up = True
        self.alive = False
        return self.item

    def update(self, dt: float) -> None:
        self._bob_timer += dt

    def render(self, screen: pygame.Surface, camera_offset: Tuple[int, int]) -> None:
        if not self.alive:
            return
        ox, oy = camera_offset
        bob = int(math.sin(self._bob_timer * 3) * 3)
        sx = int(self.x) - ox
        sy = int(self.y) - oy + bob
        # Outer rect: rarity-colored border so players can read item tier at a glance
        pygame.draw.rect(screen, self.item.rarity_color, (sx, sy, _SPRITE_SIZE, _SPRITE_SIZE))
        # Inner rect: dark neutral fill so the colored border stands out
        pygame.draw.rect(
            screen,
            (30, 30, 40),
            (sx + 2, sy + 2, _SPRITE_SIZE - 4, _SPRITE_SIZE - 4),
        )
