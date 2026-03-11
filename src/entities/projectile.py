import pygame
from typing import Tuple, Optional
from src.entities.entity import Entity

class Projectile(Entity):
    def __init__(self, x: float, y: float, vx: float, vy: float, damage: int, owner: object = None):
        super().__init__(x, y, 8, 4)
        self.vx: float = vx
        self.vy: float = vy
        self.damage: int = damage
        self.owner = owner
        self.ttl: float = 2.0

    def update(self, dt: float) -> None:
        self.rect.x += int(self.vx * dt)
        self.rect.y += int(self.vy * dt)
        self.ttl -= dt
        if self.ttl <= 0:
            self.alive = False

    def render(self, screen: pygame.Surface, camera_offset: Tuple[int, int]) -> None:
        if not self.alive:
            return
        ox, oy = camera_offset
        sx = self.rect.x - ox
        sy = self.rect.y - oy
        pygame.draw.rect(screen, (255, 220, 80), (sx, sy, self.rect.w, self.rect.h))
