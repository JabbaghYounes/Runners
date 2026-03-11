"""
Human-controlled player entity.
"""
from __future__ import annotations

from src.entities.entity import Entity


class Player(Entity):
    """The human-controlled player.  ``is_player_controlled`` is always True."""

    is_player_controlled: bool = True

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        super().__init__(x=x, y=y)
        self.health: int = 100

    def take_damage(self, amount: int) -> None:
        """Reduce health by *amount*; set ``alive = False`` on lethal damage."""
        self.health -= amount
        if self.health <= 0:
            self.alive = False
