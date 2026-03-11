"""
AI-controlled player-agent entity (bot player in PvP).
"""
from __future__ import annotations

from typing import Any

from src.entities.entity import Entity


class _Inventory:
    """Minimal inventory: a list of slot items plus equipped gear."""

    def __init__(self) -> None:
        self._slots: list = []
        self.equipped_weapon: Any = None
        self.equipped_armor: Any = None

    @property
    def slots(self) -> list:
        return self._slots

    def add(self, item: Any) -> bool:
        self._slots.append(item)
        return True

    def clear(self) -> None:
        self._slots.clear()
        self.equipped_weapon = None
        self.equipped_armor = None


class PlayerAgent(Entity):
    """Bot-controlled agent in PvP.  ``is_player_controlled`` is always False."""

    is_player_controlled: bool = False

    def __init__(self, x: float = 0.0, y: float = 0.0, driver: Any = None) -> None:
        super().__init__(x=x, y=y)
        self.health: int = 100
        self.driver = driver
        self.inventory = _Inventory()

    def take_damage(self, amount: int) -> None:
        """Reduce health by *amount*; set ``alive = False`` on lethal damage."""
        self.health -= amount
        if self.health <= 0:
            self.alive = False
