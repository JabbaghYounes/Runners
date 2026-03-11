"""
Base Entity class for all game objects.
"""
from __future__ import annotations

import types as _types
from typing import Optional, Tuple


class Entity:
    """Minimal entity: position, bounding rect, alive flag."""

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        w: int = 28,
        h: int = 48,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.width = int(w)
        self.height = int(h)
        self.alive: bool = True
        self.animation_controller = None
        self._init_rect()

    def _init_rect(self) -> None:
        rect = _types.SimpleNamespace(
            x=self.x,
            y=self.y,
            w=self.width,
            h=self.height,
            centerx=self.x + self.width / 2,
            centery=self.y + self.height / 2,
            center=(self.x + self.width / 2, self.y + self.height / 2),
        )

        def colliderect(other) -> bool:
            return (
                rect.x < other.x + other.w
                and rect.x + rect.w > other.x
                and rect.y < other.y + other.h
                and rect.y + rect.h > other.y
            )

        rect.colliderect = colliderect
        self.rect = rect

    def update(self, dt: float, tile_map=None) -> None:
        pass

    def render(self, screen, camera_offset: Tuple[int, int] = (0, 0)) -> None:
        pass
