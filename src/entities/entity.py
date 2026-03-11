import pygame
from typing import Optional, Tuple

class Entity:
    def __init__(self, x: float, y: float, w: int = 32, h: int = 48):
        self.rect = pygame.Rect(int(x), int(y), w, h)
        self.alive: bool = True
        # Optional animation controller; when set, render() uses its current
        # frame instead of a plain-colour fallback.
        self.animation_controller: Optional['AnimationController'] = None  # type: ignore[name-defined]

    @property
    def center(self) -> Tuple[float, float]:
        return float(self.rect.centerx), float(self.rect.centery)

    def update(self, dt: float) -> None:
        pass

    def render(self, screen: pygame.Surface, camera_offset: Tuple[int, int]) -> None:
        """Base render.

        Subclasses that do not override this method will automatically use the
        ``animation_controller``'s current frame if one has been assigned,
        blitting it at the entity's world position adjusted by *camera_offset*.
        """
        if self.animation_controller is not None:
            ox, oy = camera_offset
            frame = self.animation_controller.get_current_frame()
            screen.blit(frame, (self.rect.x - ox, self.rect.y - oy))
