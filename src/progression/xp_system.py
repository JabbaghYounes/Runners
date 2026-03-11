"""
XPSystem — awards experience points for PvP kills.
"""
from __future__ import annotations

from typing import Any

from src.constants import PVP_KILL_XP


class XPSystem:
    """Tracks the player's XP and grants ``PVP_KILL_XP`` for each PvP kill."""

    def __init__(self, event_bus: Any) -> None:
        self.xp: int = 0
        event_bus.subscribe("player_killed", self._on_player_killed)

    def _on_player_killed(self, killer: Any, victim: Any) -> None:
        """Award XP only when a human player made the kill."""
        if killer.is_player_controlled:
            self.xp += PVP_KILL_XP
