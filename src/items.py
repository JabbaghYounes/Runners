"""Item data classes for all game item types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ItemType(Enum):
    WEAPON = "weapon"
    ATTACHMENT = "attachment"
    ARMOR = "armor"
    CONSUMABLE = "consumable"


class Rarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"


@dataclass
class Item:
    id: str
    name: str
    item_type: ItemType
    rarity: Rarity
    value: int = 0
    weight: float = 1.0
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "item_type": self.item_type.value,
            "rarity": self.rarity.value,
            "value": self.value,
            "weight": self.weight,
            "stats": self.stats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Item:
        return cls(
            id=data["id"],
            name=data["name"],
            item_type=ItemType(data["item_type"]),
            rarity=Rarity(data["rarity"]),
            value=data.get("value", 0),
            weight=data.get("weight", 1.0),
            stats=data.get("stats", {}),
        )
