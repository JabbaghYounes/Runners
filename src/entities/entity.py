"""Base entity class."""
from __future__ import annotations


class Entity:
    """Base class for all game entities.

    Attributes:
        rect:    pygame.Rect representing world position and size.
        alive:   False once the entity should be removed from the world.
        visible: Whether to draw this entity.
    """

    def __init__(self, x: float, y: float, width: int = 32, height: int = 32) -> None:
        self.x = float(x)
        self.y = float(y)
        self.width = int(width)
        self.height = int(height)
        self.alive: bool = True
        self.visible: bool = True

        # Lazy pygame rect — created on first access to avoid importing pygame
        # at module load time (handy for headless tests).
        self._rect: object = None

    @property
    def rect(self) -> object:
        if self._rect is None:
            import pygame
            self._rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)
        else:
            self._rect.x = int(self.x)
            self._rect.y = int(self.y)
        return self._rect

    @rect.setter
    def rect(self, value: object) -> None:
        self._rect = value
        if value is not None:
            self.x = float(value.x)
            self.y = float(value.y)

    def update(self, dt: float) -> None:
        """Advance entity state by *dt* seconds."""

    def render(self, surface: object, camera_offset: tuple[int, int] = (0, 0)) -> None:
        """Draw the entity on *surface* adjusted by *camera_offset*."""
