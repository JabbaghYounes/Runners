"""Item base class and subclasses for Runners inventory system."""
from __future__ import annotations
from typing import Any

RARITY_COMMON    = 'common'
RARITY_UNCOMMON  = 'uncommon'
RARITY_RARE      = 'rare'
RARITY_EPIC      = 'epic'
RARITY_LEGENDARY = 'legendary'

RARITY_ORDER = [RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE, RARITY_EPIC, RARITY_LEGENDARY]

RARITY_DEFAULT_VALUES = {
    RARITY_COMMON:    50,
    RARITY_UNCOMMON:  150,
    RARITY_RARE:      400,
    RARITY_EPIC:      900,
    RARITY_LEGENDARY: 2000,
}

RARITY_COLORS = {
    RARITY_COMMON:    (170, 170, 170),
    RARITY_UNCOMMON:  (57,  255, 20),
    RARITY_RARE:      (0,   165, 255),
    RARITY_EPIC:      (192, 64,  255),
    RARITY_LEGENDARY: (255, 140, 0),
}


class Item:
    """Base class for all inventory items."""

    def __init__(
        self,
        item_id: str,
        name: str,
        item_type: str,
        rarity: str = RARITY_COMMON,
        value: int | None = None,
        weight: float = 1.0,
        sprite: object = None,
        stats: dict[str, Any] | None = None,
        quantity: int = 1,
    ) -> None:
        self.item_id = item_id
        self.name = name
        self.item_type = item_type
        self.rarity = rarity
        self.value = value if value is not None else RARITY_DEFAULT_VALUES.get(rarity, 50)
        self.weight = weight
        self.sprite = sprite
        self.stats: dict[str, Any] = stats or {}
        self.quantity = quantity

    def rarity_color(self) -> tuple[int, int, int]:
        return RARITY_COLORS.get(self.rarity, RARITY_COLORS[RARITY_COMMON])

    def __repr__(self) -> str:
        return f'Item({self.item_id!r}, value={self.value!r})'


class Weapon(Item):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('item_type', 'weapon')
        super().__init__(**kwargs)

    @property
    def damage(self) -> int:
        return self.stats.get('damage', 10)

    @property
    def fire_rate(self) -> float:
        return self.stats.get('fire_rate', 1.0)

    @property
    def magazine(self) -> int:
        return self.stats.get('magazine', 30)

    @property
    def reload_time(self) -> float:
        return self.stats.get('reload_time', 2.0)

    @property
    def range(self) -> float:
        return self.stats.get('range', 400.0)


class Armor(Item):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('item_type', 'armor')
        super().__init__(**kwargs)

    @property
    def armor(self) -> int:
        return self.stats.get('armor', 0)

    @property
    def mobility_penalty(self) -> float:
        return self.stats.get('mobility_penalty', 0.0)


class Consumable(Item):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('item_type', 'consumable')
        super().__init__(**kwargs)

    @property
    def heal_amount(self) -> int:
        return self.stats.get('heal_amount', 0)

    @property
    def use_time(self) -> float:
        return self.stats.get('use_time', 1.0)

    def use(self, player: object) -> None:
        """Apply consumable effect to *player*."""
        if self.heal_amount:
            player.heal(self.heal_amount)


class Attachment(Item):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('item_type', 'attachment')
        super().__init__(**kwargs)


def make_item(item_id: str, item_type: str = 'item', **kwargs: Any) -> Item:
    """Factory helper: create an Item of the appropriate subclass."""
    cls_map = {
        'weapon':      Weapon,
        'armor':       Armor,
        'consumable':  Consumable,
        'attachment':  Attachment,
    }
    cls = cls_map.get(item_type, Item)
    return cls(item_id=item_id, item_type=item_type, **kwargs)
