"""
CombatSystem -- resolves projectile-vs-entity collisions and emits events.
"""
from __future__ import annotations

from typing import Any, List

import src.constants as consts


class CombatSystem:
    """Checks projectile collisions each frame and handles hit resolution."""

    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus

    def update(self, projectiles: list, targets: list, dt: float) -> None:
        """Process all projectile/target pairs for the current frame."""
        for proj in list(projectiles):
            if not proj.alive:
                continue
            for target in targets:
                if not getattr(target, 'alive', True):
                    continue
                if proj.owner is target:
                    continue
                if not proj.rect.colliderect(target.rect):
                    continue

                # Friendly-fire gate: only applies to PvP (Player <-> PlayerAgent)
                try:
                    from src.entities.player import Player
                    from src.entities.player_agent import PlayerAgent
                    if isinstance(proj.owner, (Player, PlayerAgent)) and isinstance(
                        target, (Player, PlayerAgent)
                    ):
                        if not consts.PVP_FRIENDLY_FIRE:
                            continue
                except ImportError:
                    pass

                # Compute effective damage (armor-aware)
                raw_damage = proj.damage
                if hasattr(target, 'get_effective_armor'):
                    armor = target.get_effective_armor()
                    effective = max(1, raw_damage - int(armor))
                else:
                    effective = raw_damage

                # Apply hit
                if hasattr(target, 'take_damage'):
                    target.take_damage(effective)
                proj.alive = False

                if not getattr(target, 'alive', True):
                    if self._event_bus is not None:
                        self._event_bus.emit(
                            "player_killed", killer=proj.owner, victim=target
                        )
                break  # projectile consumed

    def fire(self, owner: Any, target_x: float, target_y: float,
             damage: int = 15, speed: float = 600.0) -> Any:
        from src.entities.projectile import Projectile
        import math
        cx, cy = owner.center
        dx = target_x - cx
        dy = target_y - cy
        dist = math.hypot(dx, dy) or 1
        vx = dx / dist * speed
        vy = dy / dist * speed
        return Projectile(cx - 4, cy - 2, vx, vy, damage, owner=owner)
