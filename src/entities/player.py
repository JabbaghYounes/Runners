"""Player entity — health management, buff delegation, and stat access.

The Player owns its ``active_buffs`` list but delegates buff lifecycle
management to an injected ``BuffSystem``.  This keeps the system layer
responsible for ticking and expiry while the entity owns its state.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.event_bus import EventBus

from src.core import event_bus as _event_bus_module
from src.entities.entity import Entity
from src.inventory.inventory import Inventory
from src.systems.buff_system import ActiveBuff, BuffSystem


class Player(Entity):
    """Player entity with health, inventory, and buff state.

    Args:
        x: World-space x position.
        y: World-space y position.
        max_health: Maximum (and starting) HP.  Defaults to 100.
        buff_system: Injected BuffSystem instance (or None).
        inventory: Injected Inventory instance (or None — one is created).
    """

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        max_health: int = 100,
        buff_system: BuffSystem | None = None,
        inventory: Inventory | None = None,
    ) -> None:
        super().__init__(x, y, 32, 48)
        self.max_health: int = max_health
        self.health: int = max_health
        self.armor: int = 0
        self.active_buffs: list[ActiveBuff] = []
        self._buff_system: BuffSystem | None = buff_system
        self.inventory: Inventory = inventory if inventory is not None else Inventory()

    def set_buff_system(self, buff_system: BuffSystem) -> None:
        """Attach or replace the BuffSystem after construction."""
        self._buff_system = buff_system

    def heal(self, amount: int) -> int:
        """Restore *amount* HP, clamped to ``max_health``.

        Returns:
            The actual HP gained (0 if already at full health or amount <= 0).

        Emits:
            ``player_healed`` with ``{"player": self, "amount": <gained>}``
            only when HP is actually gained.
        """
        if amount <= 0:
            return 0
        before = self.health
        self.health = min(self.max_health, self.health + amount)
        gained = self.health - before
        if gained > 0:
            _event_bus_module.event_bus.emit(
                "player_healed", {"player": self, "amount": gained}
            )
        return gained

    def take_damage(self, amount: int) -> int:
        """Apply *amount* of damage after armor reduction.

        Returns:
            Effective HP lost.

        Emits:
            ``player_killed`` with ``{"victim": self}`` if health reaches 0.
        """
        if amount <= 0:
            return 0
        effective = max(0, amount - self.armor)
        self.health = max(0, self.health - effective)
        if self.health <= 0:
            self.alive = False
            _event_bus_module.event_bus.emit("player_killed", {"victim": self})
        return effective

    def apply_buff(self, buff: ActiveBuff) -> None:
        """Apply a timed stat modifier.

        Delegates to ``BuffSystem.add_buff()`` when a buff system is
        attached.  Falls back to direct list append so the class works
        standalone in tests.
        """
        if self._buff_system is not None:
            self._buff_system.add_buff(self, buff)
        else:
            self.active_buffs.append(buff)
        _event_bus_module.event_bus.emit("buff_applied", {"player": self, "buff": buff})

    def get_stat(self, name: str) -> float:
        """Return the effective value of *name* including active buff modifiers.

        Formula: ``base_stat + sum(buff.value for matching buffs)``
        """
        base = getattr(self, name, 0.0)
        if self._buff_system is not None:
            modifiers = self._buff_system.get_modifiers(self, name)
        else:
            modifiers = [b.value for b in self.active_buffs if b.stat == name]
        return base + sum(modifiers)

    def update(self, dt: float) -> None:
        pass

    def render(self, surface, camera_offset=(0, 0)) -> None:
        try:
            import pygame
            draw_rect = self.rect.move(-camera_offset[0], -camera_offset[1])
            pygame.draw.rect(surface, (0, 245, 255), draw_rect)
        except Exception:
            pass
