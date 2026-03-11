"""Item hierarchy: base Item and the Consumable subclass.

Consumables carry either a heal effect or a timed buff.  Calling
``Consumable.use(player)`` dispatches to the appropriate player method and
the item is then removed from the inventory by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.entities.player import Player


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


@dataclass
class Item:
    """Base class for every inventory item.

    Attributes:
        id:         Unique string identifier (matches key in items.json).
        name:       Human-readable display name.
        rarity:     "common" | "uncommon" | "rare" | "legendary"
        sprite_key: Key into AssetManager for the item icon surface.
        value:      Monetary loot value in credits.
    """

    id: str
    name: str
    rarity: str
    sprite_key: str
    value: int


# ---------------------------------------------------------------------------
# Consumable subclass
# ---------------------------------------------------------------------------


@dataclass
class Consumable(Item):
    """An item that is destroyed on use, applying a heal or buff effect.

    consumable_type:
        "heal" — restores ``heal_amount`` HP immediately.
        "buff" — applies a timed stat modifier via ``player.apply_buff()``.
    """

    consumable_type: str = "heal"      # "heal" | "buff"
    heal_amount: int = 0
    buff_type: str | None = None       # e.g. "speed", "damage"
    buff_value: float = 0.0            # Additive modifier magnitude
    buff_duration: float = 0.0        # Duration in seconds
    buff_icon_key: str = ""            # Sprite key for HUD countdown icon

    # ------------------------------------------------------------------
    # Use
    # ------------------------------------------------------------------

    def use(self, player: "Player") -> None:
        """Apply this consumable's effect to *player*.

        The item is *not* removed from inventory here; that is the
        responsibility of ``Inventory.use_consumable()``.
        """
        if self.consumable_type == "heal":
            player.heal(self.heal_amount)
        elif self.consumable_type == "buff":
            # Lazy import to avoid circular dependency at module load time.
            from src.systems.buff_system import ActiveBuff  # noqa: PLC0415

            buff = ActiveBuff(
                buff_type=self.buff_type or "",
                value=self.buff_value,
                duration=self.buff_duration,
                time_remaining=self.buff_duration,
                icon_key=self.buff_icon_key or self.sprite_key,
            )
            player.apply_buff(buff)
