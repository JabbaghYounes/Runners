import pygame
from typing import Tuple, Optional
from src.entities.entity import Entity
from src.inventory.item import Item

class LootItem(Entity):
    def __init__(self, x: float, y: float, item: Item):
        super().__init__(x, y, 20, 20)
        self.item: Item = item
        self.despawn: bool = False
        self._bob_timer: float = 0.0

    def update(self, dt: float) -> None:
        self._bob_timer += dt

    def render(self, screen: pygame.Surface, camera_offset: Tuple[int, int]) -> None:
        if self.despawn:
            return
        ox, oy = camera_offset
        import math
        bob = int(math.sin(self._bob_timer * 3) * 3)
        sx = self.rect.x - ox
        sy = self.rect.y - oy + bob
        pygame.draw.rect(screen, (255, 200, 50), (sx, sy, self.rect.w, self.rect.h))
        pygame.draw.rect(screen, (255, 255, 100), (sx + 2, sy + 2, self.rect.w - 4, self.rect.h - 4), 1)
