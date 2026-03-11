"""Player entity — health management, buff delegation, and stat access.

The Player owns its ``active_buffs`` list but delegates buff lifecycle
management to an injected ``BuffSystem``.  This keeps the system layer
responsible for ticking and expiry while the entity owns its state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.event_bus import event_bus
from src.entities.entity import Entity

if TYPE_CHECKING:
    from src.inventory.inventory import Inventory
    from src.systems.buff_system import ActiveBuff, BuffSystem


class Player(Entity):
    """The player character.

    Responsibilities:
    - Track health / armor state.
    - Expose ``heal()``, ``take_damage()``, ``apply_buff()``, ``get_stat()``.
    - Hold a reference to ``Inventory`` and ``BuffSystem`` (injected at
      construction or via setters so they can be swapped in tests).

    Base stats are defined in ``_BASE_STATS``.  ``get_stat(name)`` returns
    the base value plus the sum of matching active buff modifiers.
    """

    # Default per-character base stats (before skill-tree / home-base bonuses).
    _BASE_STATS: dict[str, float] = {
        "speed": 200.0,   # pixels per second
        "damage": 25.0,   # hit damage
        "armor": 0.0,
    }

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        max_health: int = 100,
        buff_system: "BuffSystem | None" = None,
        inventory: "Inventory | None" = None,
    ) -> None:
        super().__init__(x, y, width=32, height=48)
        self.max_health: int = max_health
        self.health: int = max_health
        self.armor: int = 0
        self.active_buffs: list["ActiveBuff"] = []

        self._buff_system = buff_system
        self.inventory = inventory

    # ------------------------------------------------------------------
    # Dependency injection
    # ------------------------------------------------------------------

    def set_buff_system(self, buff_system: "BuffSystem") -> None:
        """Attach or replace the BuffSystem after construction."""
        self._buff_system = buff_system

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def heal(self, amount: int) -> int:
        """Restore *amount* HP, clamped to ``max_health``.

        Returns:
            The actual HP gained (0 if already at full health or amount ≤ 0).

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
            event_bus.emit("player_healed", {"player": self, "amount": gained})
        return gained

    def take_damage(self, amount: int) -> int:
        """Apply *amount* of damage after armor reduction.

        Returns:
            Effective HP lost.

        Emits:
            ``player_killed`` with ``{"victim": self}`` if health reaches 0.
        """
        effective = max(0, amount - self.armor)
        self.health = max(0, self.health - effective)
        if self.health == 0 and self.alive:
            self.alive = False
            event_bus.emit("player_killed", {"victim": self})
        return effective

    # ------------------------------------------------------------------
    # Buffs
    # ------------------------------------------------------------------

    def apply_buff(self, buff: "ActiveBuff") -> None:
        """Apply a timed stat modifier.

        Delegates to ``BuffSystem.add_buff()`` when a buff system is
        attached.  Falls back to direct list append so the class works
        standalone in tests.
        """
        if self._buff_system is not None:
            self._buff_system.add_buff(self, buff)
        else:
            # Standalone mode: manage the list ourselves and still emit.
            self.active_buffs.append(buff)
            event_bus.emit(
                "buff_applied",
                {
                    "entity": self,
                    "buff_type": buff.buff_type,
                    "value": buff.value,
                    "duration": buff.duration,
                    "icon_key": buff.icon_key,
                },
            )

    # ------------------------------------------------------------------
    # Stat access
    # ------------------------------------------------------------------

    def get_stat(self, name: str) -> float:
        """Return the effective value of *name* including active buff modifiers.

        Formula: ``base_stat + sum(buff.value for matching buffs)``
        """
        base = self._BASE_STATS.get(name, 0.0)
        if self._buff_system is not None:
            modifier = self._buff_system.get_modifiers(self, name)
        else:
            modifier = sum(
                b.value for b in self.active_buffs if b.buff_type == name
            )
        return base + modifier

    # ------------------------------------------------------------------
    # Frame methods
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:  # noqa: ARG002
        pass

    def render(
        self,
        surface: object,  # noqa: ARG002
        camera_offset: tuple[float, float] = (0.0, 0.0),  # noqa: ARG002
    ) -> None:
        pass
