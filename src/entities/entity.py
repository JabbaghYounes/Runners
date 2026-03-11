"""Base entity class for all renderable game objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame


class Entity:
    """Minimal base for every in-world object.

    Attributes:
        x, y:        World-space position (top-left corner) in pixels.
        width, height: Collision/render dimensions.
        visible:     When False the entity is skipped by the renderer.
        alive:       When False the entity is removed from the world by
                     the owning system on the next update pass.
    """

    def __init__(
        self,
        x: float,
        y: float,
        width: int = 32,
        height: int = 32,
    ) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.visible = True
        self.alive = True

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    # ------------------------------------------------------------------
    # Frame methods — override in subclasses
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:  # noqa: ARG002
        """Advance entity state by *dt* seconds."""

    def render(
        self,
        surface: "pygame.Surface",  # noqa: ARG002
        camera_offset: tuple[float, float] = (0.0, 0.0),  # noqa: ARG002
    ) -> None:
        """Draw entity to *surface* adjusted by *camera_offset*."""
