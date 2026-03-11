import pygame
from typing import Tuple

class Entity:
    def __init__(self, x: float, y: float, w: int = 32, h: int = 48):
        self.rect = pygame.Rect(int(x), int(y), w, h)
        self.alive: bool = True

    @property
    def center(self) -> Tuple[float, float]:
        return float(self.rect.centerx), float(self.rect.centery)

    def update(self, dt: float) -> None:
        pass

    def render(self, screen: pygame.Surface, camera_offset: Tuple[int, int]) -> None:
        pass
