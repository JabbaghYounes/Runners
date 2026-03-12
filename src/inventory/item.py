"""Item base class and concrete subclasses for the Runners inventory system.

Each item carries a ``value`` integer representing its monetary worth when
extracted.  The value is sourced from ``data/items.json``; if omitted from
the data file the ``RARITY_DEFAULT_VALUES`` dict provides a sensible fallback
based on the item's rarity tier.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Rarity tier constants (string-based for JSON compatibility)
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

# Rarity value multipliers (used by extraction system)
# Keyed by both string and Rarity enum for compatibility
class _RarityMultiplierDict(dict):
    """Dict that accepts both string and Rarity enum keys."""
    def __getitem__(self, key):
        if hasattr(key, 'value'):
            key = key.value
        return super().__getitem__(key)
    def get(self, key, default=None):
        if hasattr(key, 'value'):
            key = key.value
        return super().get(key, default)
    def __contains__(self, key):
        if hasattr(key, 'value'):
            key = key.value
        return super().__contains__(key)

RARITY_VALUE_MULTIPLIERS = _RarityMultiplierDict({
    RARITY_COMMON: 1.0,
    RARITY_UNCOMMON: 1.5,
    RARITY_RARE: 2.5,
    RARITY_EPIC: 5.0,
    RARITY_LEGENDARY: 10.0,
})

# ---------------------------------------------------------------------------
# Enum-based Rarity (kept for backward compatibility with older code)
# ---------------------------------------------------------------------------

class Rarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"

    def __eq__(self, other):
        if isinstance(other, Rarity):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self):
        return hash(self.value)

    @classmethod
    def from_str(cls, s: str) -> 'Rarity':
        mapping = {r.value: r for r in cls}
        return mapping.get(s.lower(), cls.COMMON)


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
        item_id: str = "unknown",
        name: str = "Unknown",
        item_type: str = "item",
        rarity: str = RARITY_COMMON,
        value: int = 0,
        weight: float = 0.0,
        sprite: str = "",
        stats: dict[str, Any] | None = None,
        quantity: int = 1,
        # Legacy kwargs from the old dataclass-based API
        type: str | None = None,
        armor_value: int = 0,
        # Aliases from dataclass-based API
        id: str | None = None,
        base_value: float | None = None,
        sprite_path: str | None = None,
        **extra_kwargs: Any,
    ) -> None:
        # Support 'id' as alias for 'item_id'
        if id is not None and item_id == "unknown":
            item_id = id
        self.item_id: str = item_id
        self.name: str = name
        # Support both 'item_type' and legacy 'type' parameter
        self.item_type: str = item_type if type is None else type
        # Support both string rarity and Rarity enum — store the enum when given
        if isinstance(rarity, Rarity):
            self.rarity = rarity
        elif isinstance(rarity, str):
            self.rarity = Rarity.from_str(rarity)
        else:
            self.rarity = rarity
        self.weight: float = weight
        self.sprite: str = sprite_path if sprite_path is not None else sprite
        self.stats: dict[str, Any] = stats or {}
        self.quantity: int = quantity

        # Track whether base_value was explicitly provided (including 0)
        self._has_base_value = base_value is not None

        # Resolve value: prefer base_value if provided, then value, then fallback
        if base_value is not None:
            self.base_value: float = float(base_value)
            self.value: int = int(base_value)
        elif value and value > 0:
            self.base_value = float(value)
            self.value = int(value)
        else:
            rarity_key = self.rarity.value if isinstance(self.rarity, Rarity) else self.rarity
            fallback = RARITY_DEFAULT_VALUES.get(
                rarity_key, RARITY_DEFAULT_VALUES[RARITY_COMMON]
            )
            self.base_value = float(fallback)
            self.value = fallback

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        """Alias for item_id."""
        return self.item_id

    @id.setter
    def id(self, value: str) -> None:
        self.item_id = value

    @property
    def rarity_color(self) -> tuple[int, int, int]:
        """RGB colour tuple for this item's rarity tier."""
        rarity_key = self.rarity.value if isinstance(self.rarity, Rarity) else self.rarity
        return RARITY_COLORS.get(rarity_key, RARITY_COLORS[RARITY_COMMON])

    @property
    def monetary_value(self) -> float:
        """Value adjusted by rarity multiplier."""
        mult = RARITY_VALUE_MULTIPLIERS.get(self.rarity, 1.0)
        return self.base_value * mult

    @property
    def type(self) -> str:
        return self.item_type

    def get_stat(self, key: str, default=0):
        return self.stats.get(key, default)

    def to_save_dict(self) -> dict[str, Any]:
        """Serialise this item to a JSON-safe dictionary."""
        rarity_str = self.rarity.value if isinstance(self.rarity, Rarity) else str(self.rarity)
        return {
            "item_id": self.item_id,
            "name": self.name,
            "item_type": self.item_type,
            "rarity": rarity_str,
            "value": self.value,
            "weight": self.weight,
            "sprite": self.sprite,
            "stats": dict(self.stats),
            "quantity": self.quantity,
        }

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
        self.mod_slots: list = kwargs.pop("mod_slots", [])
        self._damage = kwargs.pop("damage", None)
        self._fire_rate = kwargs.pop("fire_rate", None)
        self._magazine_size = kwargs.pop("magazine_size", None)
        self.attachments: Dict[str, Any] = {}
        kwargs.pop("item_type", None)
        kwargs.pop("type", None)
        super().__init__(item_type="weapon", **kwargs)

    # ------------------------------------------------------------------
    # Attachment management
    # ------------------------------------------------------------------

    def attach(self, attachment: "Attachment", slot_type: str | None = None) -> bool:
        """Equip *attachment* into the appropriate mod slot.

        Args:
            attachment: The attachment to equip.
            slot_type:  Override the attachment's own ``slot_type``.

        Returns:
            ``True`` on success, ``False`` if the slot is unavailable,
            already occupied, or the attachment is incompatible.
        """
        target_slot = slot_type if slot_type is not None else attachment.slot_type
        # Slot type must be non-empty
        if not target_slot:
            return False
        # Weapon must have this mod slot
        if target_slot not in self.mod_slots:
            return False
        # Slot must not be occupied
        if target_slot in self.attachments:
            return False
        # Compatibility check
        if attachment.compatible_weapons and self.item_id not in attachment.compatible_weapons:
            return False
        self.attachments[target_slot] = attachment
        return True

    def detach(self, slot_type: str) -> "Attachment | None":
        """Remove and return the attachment in *slot_type*, or ``None``."""
        return self.attachments.pop(slot_type, None)

    def get_attachment(self, slot_type: str) -> "Attachment | None":
        """Return the attachment in *slot_type* without removing it."""
        return self.attachments.get(slot_type, None)

    def available_slots(self) -> list[str]:
        """Return mod slots that are not currently occupied."""
        return [s for s in self.mod_slots if s not in self.attachments]

    def occupied_slots(self) -> list[str]:
        """Return mod slots that currently have an attachment."""
        return [s for s in self.mod_slots if s in self.attachments]

    def _attachment_bonus(self, stat_key: str) -> float:
        """Sum the stat delta for *stat_key* across all equipped attachments."""
        total = 0.0
        for att in self.attachments.values():
            total += att.stat_delta.get(stat_key, 0.0)
        return total

    def effective_stat(self, stat_key: str, base: float | None = None) -> float:
        """Return the effective value of *stat_key* including attachment bonuses.

        The base value is resolved from (in order):
        1. Explicit *base* parameter
        2. Direct weapon attribute (damage, fire_rate)
        3. ``self.stats`` dict
        4. Fallback to 0.0
        """
        if base is not None:
            base_val = float(base)
        elif stat_key == "damage" and self._damage is not None:
            base_val = float(self._damage)
        elif stat_key == "fire_rate" and self._fire_rate is not None:
            base_val = float(self._fire_rate)
        else:
            base_val = float(self.stats.get(stat_key, 0.0))
        return base_val + self._attachment_bonus(stat_key)

    # ------------------------------------------------------------------
    # Base stat properties
    # ------------------------------------------------------------------

    @property
    def damage(self) -> int:
        if self._damage is not None:
            return int(self._damage)
        return int(self.stats.get("damage", 0))

    @property
    def fire_rate(self) -> float:
        if self._fire_rate is not None:
            return float(self._fire_rate)
        return float(self.stats.get("fire_rate", 1.0))

    @property
    def magazine(self) -> int:
        return int(self._magazine_size or self.stats.get("magazine", self.stats.get("magazine_size", 1)))

    @property
    def magazine_size(self) -> int:
        return self.magazine

    @property
    def reload_time(self) -> float:
        return float(self.stats.get("reload_time", 2.0))

    @property
    def range(self) -> int:
        return int(self.stats.get("range", 300))


class Armor(Item):
    """A piece of protective armor."""

    def __init__(self, **kwargs: Any) -> None:
        self._armor_rating = kwargs.pop("armor_rating", None)
        # armor_value can also set the armor rating
        _armor_value = kwargs.pop("armor_value", None)
        if self._armor_rating is None and _armor_value is not None:
            self._armor_rating = int(_armor_value)
        self.defense: float = kwargs.pop("defense", 0)
        self.slot = kwargs.pop("slot_type", kwargs.pop("slot", "body"))
        kwargs.pop("item_type", None)
        kwargs.pop("type", None)
        super().__init__(item_type="armor", **kwargs)

    @property
    def armor(self) -> int:
        if self._armor_rating is not None:
            return int(self._armor_rating)
        return int(self.stats.get("armor", self.stats.get("armor_rating", 0)))

    @property
    def armor_value(self) -> int:
        return self.armor

    @property
    def armor_rating(self) -> int:
        return self.armor

    @property
    def mobility_penalty(self) -> int:
        return int(self.stats.get("mobility_penalty", 0))


class Consumable(Item):
    """A single-use item (med kit, stim, etc.).

    Supports both the new keyword-based API and the old dict-based API.
    """

    def __init__(self, **kwargs: Any) -> None:
        # Extract consumable-specific fields before passing to parent
        self.consumable_type: str = kwargs.pop("consumable_type", "heal")
        self._heal_amount: int = kwargs.pop("heal_amount", 0)
        self.buff_type: str = kwargs.pop("buff_type", "")
        self.buff_value: float = kwargs.pop("buff_value", 0.0)
        self.buff_duration: float = kwargs.pop("buff_duration", 0.0)
        self.buff_icon_key: str = kwargs.pop("buff_icon_key", "")
        self.sprite_key: str = kwargs.get("sprite_key", kwargs.get("sprite", ""))
        kwargs.pop("sprite_key", None)
        # Dataclass-based API fields
        self.effect_type: str = kwargs.pop("effect_type", "")
        self.effect_value: float = kwargs.pop("effect_value", 0)

        # Remap 'id' to 'item_id' if needed
        if "id" in kwargs and "item_id" not in kwargs:
            kwargs["item_id"] = kwargs.pop("id")
        else:
            kwargs.pop("id", None)

        kwargs.pop("item_type", None)
        kwargs.pop("type", None)
        super().__init__(item_type="consumable", **kwargs)

    @property
    def heal_amount(self) -> int:
        return self._heal_amount or int(self.stats.get("heal_amount", 0))

    @property
    def use_time(self) -> float:
        return float(self.stats.get("use_time", 1.5))

    @property
    def id(self) -> str:
        return self.item_id

    @id.setter
    def id(self, value: str) -> None:
        self.item_id = value

    def use(self, player: Any) -> None:
        """Apply this consumable's effect to the player."""
        if self.consumable_type == "heal":
            player.heal(self.heal_amount)
        elif self.consumable_type == "buff":
            from src.systems.buff_system import ActiveBuff
            icon = self.buff_icon_key if self.buff_icon_key else self.sprite_key
            buff = ActiveBuff(
                buff_type=self.buff_type,
                value=self.buff_value,
                duration=self.buff_duration,
                time_remaining=self.buff_duration,
                icon_key=icon,
            )
            player.apply_buff(buff)


class Attachment(Item):
    """A weapon attachment (scope, suppressor, grip, etc.)."""

    def __init__(self, **kwargs: Any) -> None:
        self.compatible_weapons: list = kwargs.pop("compatible_weapons", [])
        self._stat_delta: dict = kwargs.pop("stat_delta", {})
        self.slot_type: str = kwargs.pop("slot_type", "")
        kwargs.pop("item_type", None)
        kwargs.pop("type", None)
        super().__init__(item_type="attachment", **kwargs)

    @property
    def stat_delta(self) -> dict[str, float]:
        """Return stat modifications this attachment provides."""
        return dict(self._stat_delta) if self._stat_delta else dict(self.stats)


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
    item_id_or_data=None,
    name: str | None = None,
    item_type: str | None = None,
    rarity: str | None = None,
    value: int | None = None,
    weight: float | None = None,
    sprite: str | None = None,
    stats: dict[str, Any] | None = None,
    quantity: int = 1,
    **extra_kwargs: Any,
) -> Item:
    """Instantiate the correct :class:`Item` subclass for *item_type*.

    Supports two call conventions:
    1. Positional/keyword args: make_item(item_id, name, item_type, ...)
    2. Dict-based: make_item(data_dict) where data_dict has keys matching fields.
    """
    # Dict-based call convention (legacy)
    if isinstance(item_id_or_data, dict):
        data = item_id_or_data
        _item_type = data.get("item_type", data.get("type", "item"))
        _rarity = data.get("rarity", RARITY_COMMON)
        if isinstance(_rarity, Rarity):
            _rarity = _rarity.value
        cls = _TYPE_TO_CLASS.get(_item_type, Item)
        kwargs: dict[str, Any] = {
            "item_id": data.get("item_id", "unknown"),
            "name": data.get("name", "Unknown"),
            "rarity": _rarity,
            "value": int(data.get("value", 0)),
            "weight": float(data.get("weight", 0)),
            "sprite": data.get("sprite", ""),
            "stats": data.get("stats", {}),
            "quantity": int(data.get("quantity", 1)),
        }
        if cls is Item:
            kwargs["item_type"] = _item_type
        if _item_type == "armor":
            kwargs.setdefault("armor_value", int(data.get("armor_value", 0)))
        if _item_type == "attachment":
            if "slot_type" in data:
                kwargs["slot_type"] = data["slot_type"]
            if "stat_delta" in data:
                kwargs["stat_delta"] = data["stat_delta"]
            if "compatible_weapons" in data:
                kwargs["compatible_weapons"] = data["compatible_weapons"]
        if _item_type == "weapon":
            for wk in ("damage", "fire_rate", "magazine_size", "mod_slots"):
                if wk in data:
                    kwargs[wk] = data[wk]
        return cls(**kwargs)

    # Positional/keyword call convention
    _item_id = item_id_or_data if isinstance(item_id_or_data, str) else "unknown"
    _name = name or "Unknown"
    _item_type = item_type or "item"
    _rarity = rarity or RARITY_COMMON
    if isinstance(_rarity, Rarity):
        _rarity = _rarity.value
    _value = value if value is not None else 0
    _weight = weight if weight is not None else 0.0
    _sprite = sprite or ""

    cls = _TYPE_TO_CLASS.get(_item_type, Item)
    kwargs = {
        "item_id": _item_id,
        "name": _name,
        "rarity": _rarity,
        "value": _value,
        "weight": _weight,
        "sprite": _sprite,
        "stats": stats,
        "quantity": quantity,
    }
    kwargs.update(extra_kwargs)
    if cls is Item:
        kwargs["item_type"] = _item_type
    return cls(**kwargs)
