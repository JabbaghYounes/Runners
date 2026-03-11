"""Item hierarchy — base Item plus Weapon, Armor, Consumable, Attachment."""
from __future__ import annotations
from typing import Any

RARITY_COMMON = "common"
RARITY_UNCOMMON = "uncommon"
RARITY_RARE = "rare"
RARITY_EPIC = "epic"
RARITY_LEGENDARY = "legendary"

RARITY_ORDER = [RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE, RARITY_EPIC, RARITY_LEGENDARY]

RARITY_DEFAULT_VALUES = {
    RARITY_COMMON: 50,
    RARITY_UNCOMMON: 150,
    RARITY_RARE: 400,
    RARITY_EPIC: 900,
    RARITY_LEGENDARY: 2000,
}

RARITY_COLORS = {
    RARITY_COMMON: (170, 170, 170),
    RARITY_UNCOMMON: (57, 255, 20),
    RARITY_RARE: (0, 165, 255),
    RARITY_EPIC: (192, 64, 255),
    RARITY_LEGENDARY: (255, 140, 0),
}


class Item:
    """Base class for all in-game items."""

    def __init__(
        self,
        item_id: str,
        name: str,
        item_type: str = "misc",
        rarity: str = RARITY_COMMON,
        value: int = 0,
        weight: float = 0.0,
        sprite: Any = None,
        stats: dict | None = None,
        quantity: int = 1,
    ) -> None:
        self.item_id = item_id
        self.name = name
        self.item_type = item_type
        self.rarity = rarity
        self.value = value or RARITY_DEFAULT_VALUES.get(rarity, 50)
        self.weight = weight
        self.sprite = sprite
        self.stats: dict = stats or {}
        self.quantity = quantity

    def rarity_color(self):
        return RARITY_COLORS.get(self.rarity, (170, 170, 170))

    def __repr__(self) -> str:
        return f"Item({self.item_id!r}, {self.rarity!r}, value={self.value})"


class Weapon(Item):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.item_type = "weapon"

    @property
    def damage(self) -> int:
        return self.stats.get("damage", 10)

    @property
    def fire_rate(self) -> float:
        return self.stats.get("fire_rate", 1.0)

    @property
    def magazine(self) -> int:
        return self.stats.get("magazine", 30)

    @property
    def reload_time(self) -> float:
        return self.stats.get("reload_time", 2.0)

    @property
    def range(self) -> float:
        return self.stats.get("range", 400.0)


class Armor(Item):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.item_type = "armor"

    @property
    def armor(self) -> int:
        return self.stats.get("armor", 0)

    @property
    def mobility_penalty(self) -> float:
        return self.stats.get("mobility_penalty", 0.0)


class Consumable(Item):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.item_type = "consumable"

    @property
    def heal_amount(self) -> int:
        return self.stats.get("heal_amount", 0)

    @property
    def use_time(self) -> float:
        return self.stats.get("use_time", 1.0)

    def use(self, player) -> None:
        """Apply consumable effect to *player*."""
        if self.heal_amount > 0:
            player.heal(self.heal_amount)


class Attachment(Item):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.item_type = "attachment"


def make_item(data: dict) -> Item:
    """Factory: create the correct Item subclass from a data dict."""
    item_type = data.get("item_type", "misc")
    cls_map = {
        "weapon": Weapon,
        "armor": Armor,
        "consumable": Consumable,
        "attachment": Attachment,
    }
    cls = cls_map.get(item_type, Item)
    return cls(**data)
