"""Item base class and concrete subclasses for the Runners inventory system.

Each item carries a ``value`` integer representing its monetary worth when
extracted.  The value is sourced from ``data/items.json``; if omitted from
the data file the ``RARITY_DEFAULT_VALUES`` dict provides a sensible fallback
based on the item's rarity tier.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Rarity tier constants
# ---------------------------------------------------------------------------

RARITY_COMMON: str = "common"
RARITY_UNCOMMON: str = "uncommon"
RARITY_RARE: str = "rare"
RARITY_EPIC: str = "epic"
RARITY_LEGENDARY: str = "legendary"

RARITY_ORDER: list[str] = [
    RARITY_COMMON,
    RARITY_UNCOMMON,
    RARITY_RARE,
    RARITY_EPIC,
    RARITY_LEGENDARY,
]

# Fallback monetary values used when a data entry omits the ``value`` field.
# Mid-point of the documented rarity ranges from the feature plan.
RARITY_DEFAULT_VALUES: dict[str, int] = {
    RARITY_COMMON: 100,
    RARITY_UNCOMMON: 300,
    RARITY_RARE: 550,
    RARITY_EPIC: 1150,
    RARITY_LEGENDARY: 2500,
}

# Rarity display colors (R, G, B) — used by the UI layer.
RARITY_COLORS: dict[str, tuple[int, int, int]] = {
    RARITY_COMMON: (180, 180, 180),
    RARITY_UNCOMMON: (80, 200, 80),
    RARITY_RARE: (60, 120, 220),
    RARITY_EPIC: (160, 60, 220),
    RARITY_LEGENDARY: (220, 160, 40),
}


# ---------------------------------------------------------------------------
# Base Item
# ---------------------------------------------------------------------------

class Item:
    """Abstract base for all in-game items.

    Attributes:
        item_id:  Unique identifier matching the ``data/items.json`` entry.
        name:     Human-readable display name.
        item_type: Category string: ``"weapon"``, ``"armor"``,
                  ``"consumable"``, or ``"attachment"``.
        rarity:   One of the ``RARITY_*`` constants.
        value:    Monetary value when extracted.  Sourced from JSON; falls
                  back to ``RARITY_DEFAULT_VALUES`` if the JSON entry is
                  missing or zero.
        weight:   Carry weight in arbitrary units.
        sprite:   Asset path (relative, without extension) used by
                  ``AssetManager.load_image()``.
        stats:    Dict of item-specific numeric properties.
        quantity: Stack size (default 1; consumables may stack).
    """

    def __init__(
        self,
        item_id: str,
        name: str,
        item_type: str,
        rarity: str,
        value: int,
        weight: float,
        sprite: str,
        stats: dict[str, Any] | None = None,
        quantity: int = 1,
    ) -> None:
        self.item_id: str = item_id
        self.name: str = name
        self.item_type: str = item_type
        self.rarity: str = rarity
        self.weight: float = weight
        self.sprite: str = sprite
        self.stats: dict[str, Any] = stats or {}
        self.quantity: int = quantity

        # Resolve value: use supplied value if positive, else fall back.
        if value and value > 0:
            self.value: int = int(value)
        else:
            self.value = RARITY_DEFAULT_VALUES.get(rarity, RARITY_DEFAULT_VALUES[RARITY_COMMON])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def rarity_color(self) -> tuple[int, int, int]:
        """RGB colour tuple for this item's rarity tier."""
        return RARITY_COLORS.get(self.rarity, RARITY_COLORS[RARITY_COMMON])

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self.item_id!r}, "
            f"rarity={self.rarity!r}, value={self.value})"
        )


# ---------------------------------------------------------------------------
# Concrete subclasses
# ---------------------------------------------------------------------------

class Weapon(Item):
    """A firearm or melee weapon."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(item_type="weapon", **kwargs)

    @property
    def damage(self) -> int:
        return int(self.stats.get("damage", 0))

    @property
    def fire_rate(self) -> float:
        return float(self.stats.get("fire_rate", 1.0))

    @property
    def magazine(self) -> int:
        return int(self.stats.get("magazine", 1))

    @property
    def reload_time(self) -> float:
        return float(self.stats.get("reload_time", 2.0))

    @property
    def range(self) -> int:
        return int(self.stats.get("range", 300))


class Armor(Item):
    """A piece of protective armor."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(item_type="armor", **kwargs)

    @property
    def armor(self) -> int:
        return int(self.stats.get("armor", 0))

    @property
    def mobility_penalty(self) -> int:
        return int(self.stats.get("mobility_penalty", 0))


class Consumable(Item):
    """A single-use item (med kit, stim, etc.)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(item_type="consumable", **kwargs)

    @property
    def heal_amount(self) -> int:
        return int(self.stats.get("heal_amount", 0))

    @property
    def use_time(self) -> float:
        return float(self.stats.get("use_time", 1.5))


class Attachment(Item):
    """A weapon attachment (scope, suppressor, grip, etc.)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(item_type="attachment", **kwargs)


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

# Maps item_type strings to concrete classes.
_TYPE_TO_CLASS: dict[str, type[Item]] = {
    "weapon": Weapon,
    "armor": Armor,
    "consumable": Consumable,
    "attachment": Attachment,
}


def make_item(
    item_id: str,
    name: str,
    item_type: str,
    rarity: str,
    value: int,
    weight: float,
    sprite: str,
    stats: dict[str, Any] | None = None,
    quantity: int = 1,
) -> Item:
    """Instantiate the correct :class:`Item` subclass for *item_type*.

    Falls back to the base :class:`Item` class for unknown types.
    """
    cls = _TYPE_TO_CLASS.get(item_type, Item)
    # Concrete subclasses hardcode their own item_type in __init__; only the
    # base-class fallback path requires it to be supplied explicitly.
    extra = {"item_type": item_type} if cls is Item else {}
    return cls(
        item_id=item_id,
        name=name,
        rarity=rarity,
        value=value,
        weight=weight,
        sprite=sprite,
        stats=stats,
        quantity=quantity,
        **extra,
    )
