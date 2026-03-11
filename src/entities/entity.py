"""Base entity class for all game objects."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame


class Entity:
    """Base class for all game entities.

    Attributes:
        rect: Position and size in world space.
        visible: Whether the entity should be rendered.
        alive: False signals that the entity should be removed.
    """

    def __init__(self, x: float, y: float, width: int, height: int) -> None:
        import pygame
        self.rect = pygame.Rect(x, y, width, height)
        self.visible: bool = True
        self.alive: bool = True
        self.sprite = None

    @property
    def center(self):
        return self.rect.center

    def update(self, dt: float) -> None:
        """Advance entity state by *dt* seconds (override in subclasses)."""

    def render(self, surface, camera_offset=(0, 0)) -> None:
        """Draw the entity onto *surface* (override in subclasses)."""
