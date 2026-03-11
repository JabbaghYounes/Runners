"""Minimal Player stub consumed by ExtractionSystem and GameScene.

This class will be expanded by the ``player-character`` and
``player-movement`` features.  For now it exposes only the attributes
required by the round-timer / extraction-flow feature.
"""

from __future__ import annotations

import pygame


class Player:
    """Represents the user-controlled character in a round.

    Attributes:
        rect:      World-space position and bounding box.
        velocity:  Current movement vector in pixels per second.
                   ``(0, 0)`` means the player is stationary.
        inventory: Loot items the player is carrying.  Each entry is a
                   :class:`dict` (item snapshot) until the inventory system
                   is wired up.
        health:    Current health points (float, 0.0 = dead).
    """

    # Default size matches a typical 32×64 sprite hitbox.
    DEFAULT_WIDTH: int = 32
    DEFAULT_HEIGHT: int = 64
    MAX_HEALTH: float = 100.0

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> None:
        self.rect: pygame.Rect = pygame.Rect(x, y, width, height)
        self.velocity: pygame.Vector2 = pygame.Vector2(0.0, 0.0)
        self.inventory: list[dict] = []
        self.health: float = self.MAX_HEALTH

    # ------------------------------------------------------------------
    # Convenience helpers (to be replaced by full input/physics systems)
    # ------------------------------------------------------------------

    @property
    def is_alive(self) -> bool:
        """``True`` while the player still has health."""
        return self.health > 0.0

    @property
    def center(self) -> tuple[int, int]:
        """World-space center of the player rect."""
        return self.rect.center
