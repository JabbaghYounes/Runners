"""WeaponSystem -- manages weapon state: ammo, fire-rate cooldown, reload.

Each player (or entity) that can shoot has a WeaponState managed by this
system.  The system is pure logic with no rendering or input; the
ShootingSystem orchestrates input and delegates to WeaponSystem for state
transitions.
"""
from __future__ import annotations

import math
from typing import Any, Optional

from src.constants import DEFAULT_WEAPON_STATS, PROJECTILE_SPEED


class WeaponState:
    """Per-entity weapon state: tracks ammo, cooldowns, and current weapon stats."""

    def __init__(
        self,
        fire_rate: float = DEFAULT_WEAPON_STATS["fire_rate"],
        damage: float = DEFAULT_WEAPON_STATS["damage"],
        magazine_size: int = int(DEFAULT_WEAPON_STATS["magazine_size"]),
        reload_time: float = DEFAULT_WEAPON_STATS["reload_time"],
        projectile_speed: float = DEFAULT_WEAPON_STATS["projectile_speed"],
    ) -> None:
        self.fire_rate: float = fire_rate
        self.damage: float = damage
        self.magazine_size: int = magazine_size
        self.reload_time: float = reload_time
        self.projectile_speed: float = projectile_speed

        self.ammo: int = magazine_size
        self.fire_cooldown: float = 0.0
        self.reloading: bool = False
        self.reload_timer: float = 0.0

    @property
    def fire_interval(self) -> float:
        """Seconds between consecutive shots."""
        return 1.0 / self.fire_rate if self.fire_rate > 0 else 1.0

    @property
    def can_fire(self) -> bool:
        """True when the weapon is ready to shoot."""
        return (
            not self.reloading
            and self.fire_cooldown <= 0
            and self.ammo > 0
        )

    @property
    def needs_reload(self) -> bool:
        """True when the magazine is empty and not already reloading."""
        return self.ammo <= 0 and not self.reloading

    def load_from_weapon(self, weapon: Any) -> None:
        """Copy stats from an inventory Weapon item, including attachment bonuses."""
        # Use effective_stat() when available so attachment deltas are included.
        if hasattr(weapon, "effective_stat"):
            self.fire_rate = float(weapon.effective_stat("fire_rate"))
            self.damage = float(weapon.effective_stat("damage"))
        else:
            self.fire_rate = float(getattr(weapon, "fire_rate", DEFAULT_WEAPON_STATS["fire_rate"]))
            self.damage = float(getattr(weapon, "damage", DEFAULT_WEAPON_STATS["damage"]))

        # reload_time: use the property (correct default) plus any attachment bonus.
        base_reload = float(getattr(weapon, "reload_time", DEFAULT_WEAPON_STATS["reload_time"]))
        att_reload_bonus = (
            weapon._attachment_bonus("reload_time")
            if hasattr(weapon, "_attachment_bonus")
            else 0.0
        )
        self.reload_time = base_reload + att_reload_bonus

        self.magazine_size = int(getattr(weapon, "magazine_size", int(DEFAULT_WEAPON_STATS["magazine_size"])))
        self.projectile_speed = float(
            getattr(weapon, "projectile_speed",
                    weapon.stats.get("projectile_speed", DEFAULT_WEAPON_STATS["projectile_speed"])
                    if hasattr(weapon, "stats") else DEFAULT_WEAPON_STATS["projectile_speed"])
        )
        self.ammo = self.magazine_size
        self.fire_cooldown = 0.0
        self.reloading = False
        self.reload_timer = 0.0


class WeaponSystem:
    """Stateless system that ticks weapon cooldowns and processes fire/reload requests."""

    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(self, state: WeaponState, dt: float) -> None:
        """Advance cooldown and reload timers."""
        if state.fire_cooldown > 0:
            state.fire_cooldown = max(0.0, state.fire_cooldown - dt)

        if state.reloading:
            state.reload_timer -= dt
            if state.reload_timer <= 0:
                state.reloading = False
                state.reload_timer = 0.0
                state.ammo = state.magazine_size
                # Prevent firing in the same frame the reload completes
                state.fire_cooldown = state.fire_interval
                if self._event_bus is not None:
                    self._event_bus.emit("reload_complete")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def try_fire(self, state: WeaponState, owner: Any,
                 target_x: float, target_y: float) -> "Optional[Any]":
        """Attempt to fire a projectile.  Returns Projectile or None."""
        if not state.can_fire:
            return None

        from src.entities.projectile import Projectile

        cx, cy = owner.center
        dx = target_x - cx
        dy = target_y - cy
        dist = math.hypot(dx, dy) or 1.0
        vx = dx / dist * state.projectile_speed
        vy = dy / dist * state.projectile_speed

        proj = Projectile(
            cx - 4, cy - 2,
            vx, vy,
            damage=int(state.damage),
            owner=owner,
        )

        state.ammo -= 1
        state.fire_cooldown = state.fire_interval

        if self._event_bus is not None:
            self._event_bus.emit("weapon_fired", owner=owner, ammo=state.ammo)

        # Auto-reload on empty magazine
        if state.ammo <= 0:
            self.start_reload(state)

        return proj

    def start_reload(self, state: WeaponState) -> bool:
        """Begin reload.  Returns True if reload actually started."""
        if state.reloading:
            return False
        if state.ammo >= state.magazine_size:
            return False
        state.reloading = True
        state.reload_timer = state.reload_time
        if self._event_bus is not None:
            self._event_bus.emit("reload_start", reload_time=state.reload_time)
        return True
