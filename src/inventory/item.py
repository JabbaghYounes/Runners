"""Item base class and subclasses for Runners inventory system."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Rarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


# Monetary value multiplier per rarity tier.
# Also re-exported by src.core.constants.RARITY_VALUE_MULTIPLIERS.
RARITY_VALUE_MULTIPLIERS: dict[Rarity, float] = {
    Rarity.COMMON: 1.0,
    Rarity.UNCOMMON: 1.5,
    Rarity.RARE: 2.5,
    Rarity.EPIC: 5.0,
    Rarity.LEGENDARY: 10.0,
}


@dataclass(eq=False)
class Item:
    """Base item.  Uses identity-based equality and hashing so that two
    weapon instances with identical stats are treated as distinct objects
    (as they would be in a real game inventory)."""

    id: str
    name: str
    type: str
    rarity: Rarity
    weight: float
    base_value: float
    stats: dict[str, Any]
    sprite_path: str

    @property
    def monetary_value(self) -> float:
        return self.base_value * RARITY_VALUE_MULTIPLIERS[self.rarity]


@dataclass(eq=False)
class Weapon(Item):
    damage: float = 0
    fire_rate: float = 0
    magazine_size: int = 0
    mod_slots: list[str] = field(default_factory=list)


@dataclass(eq=False)
class Armor(Item):
    defense: float = 0
    slot: str = "chest"


@dataclass(eq=False)
class Consumable(Item):
    effect_type: str = ""
    effect_value: float = 0


@dataclass(eq=False)
class Attachment(Item):
    compatible_weapons: list[str] = field(default_factory=list)
    stat_delta: dict[str, Any] = field(default_factory=dict)


# Mapping from type string to Item subclass
_ITEM_CLASSES: dict[str, type[Item]] = {
    "weapon": Weapon,
    "armor": Armor,
    "consumable": Consumable,
    "attachment": Attachment,
}


def make_item(item_type: str, **kwargs: Any) -> Item:
    """Factory: return the correct Item subclass for *item_type*."""
    cls = _ITEM_CLASSES.get(item_type)
    if cls is None:
        raise KeyError(f"Unknown item type: {item_type!r}")
    return cls(**kwargs)
