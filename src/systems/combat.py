"""
CombatSystem — resolves projectile-vs-entity collisions and emits events.
"""
from __future__ import annotations

from typing import Any

import src.constants as consts
from src.entities.player import Player
from src.entities.player_agent import PlayerAgent


class CombatSystem:
    """Checks projectile collisions each frame and handles hit resolution."""

    def __init__(self, event_bus: Any) -> None:
        self._event_bus = event_bus

    def update(self, projectiles: list, targets: list, dt: float) -> None:
        """Process all projectile/target pairs for the current frame."""
        for proj in projectiles:
            if not proj.alive:
                continue
            for target in targets:
                if not target.alive:
                    continue
                if proj.owner is target:
                    continue
                if not proj.rect.colliderect(target.rect):
                    continue

                # Friendly-fire gate: only applies to PvP (Player ↔ PlayerAgent)
                if isinstance(proj.owner, (Player, PlayerAgent)) and isinstance(
                    target, (Player, PlayerAgent)
                ):
                    if not consts.PVP_FRIENDLY_FIRE:
                        continue

                # Apply hit
                target.take_damage(proj.damage)
                proj.alive = False

                if not target.alive:
                    self._event_bus.emit(
                        "player_killed", killer=proj.owner, victim=target
                    )
                break  # projectile consumed — stop checking further targets
