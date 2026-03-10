"""World-space loot drop entity — picked up on E-key proximity check."""

from __future__ import annotations

import math

import pygame

from src.entities.base import Entity
from src.items import Item


class LootDrop(Entity):
    """A dropped item sitting in the world.

    Has a gentle bob animation and can be picked up by the player when
    within *pickup_radius* pixels.
    """

    PICKUP_RADIUS: float = 40.0

    def __init__(self, x: float, y: float, item: Item) -> None:
        super().__init__(x, y, health=1, width=24, height=24)
        self.item = item
        self._bob_timer: float = 0.0
        self._base_y = y

    def update(self, dt: float, **kwargs) -> None:
        self._bob_timer += dt
        self.pos.y = self._base_y + math.sin(self._bob_timer * 3.0) * 3.0
        self._sync_rect()

    def draw(self, surface: pygame.Surface, camera) -> None:
        screen_pos = camera.world_to_screen(self.pos)
        # Placeholder coloured square
        colour = (180, 180, 180)
        rect = pygame.Rect(
            int(screen_pos.x - 12),
            int(screen_pos.y - 12),
            24,
            24,
        )
        pygame.draw.rect(surface, colour, rect)

    def in_pickup_range(self, player_pos: pygame.math.Vector2) -> bool:
        return self.pos.distance_to(player_pos) <= self.PICKUP_RADIUS
