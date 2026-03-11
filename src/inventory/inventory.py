"""Inventory — slot-based item container with quick-slot support."""
from __future__ import annotations

from typing import Optional

from src.inventory.item import Armor, Item, Weapon


class Inventory:
    """Fixed-capacity inventory with weight tracking and equip slots."""

    def __init__(self, max_slots: int, max_weight: float) -> None:
        self._max_slots = max_slots
        self._max_weight = max_weight
        self._slots: list[Item] = []
        self._equipped_weapon: Optional[Weapon] = None
        self._equipped_armor: Optional[Armor] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def slots(self) -> list[Item]:
        return self._slots

    @property
    def max_slots(self) -> int:
        return self._max_slots

    @property
    def max_weight(self) -> float:
        return self._max_weight

    @property
    def used_slots(self) -> int:
        return len(self._slots)

    @property
    def total_weight(self) -> float:
        return sum(item.weight for item in self._slots)

    @property
    def is_full(self) -> bool:
        return self.used_slots >= self._max_slots or self.total_weight >= self._max_weight

    @property
    def equipped_weapon(self) -> Optional[Weapon]:
        return self._equipped_weapon

    @property
    def equipped_armor(self) -> Optional[Armor]:
        return self._equipped_armor

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add(self, item: Item) -> bool:
        """Add *item* to the inventory.

        Returns True on success, False if slot cap or weight cap would be exceeded.
        """
        if self.used_slots >= self._max_slots:
            return False
        if self.total_weight + item.weight > self._max_weight:
            return False
        self._slots.append(item)
        return True

    def remove(self, item: Item) -> bool:
        """Remove *item* from the inventory without raising.

        Returns True if the item was present and removed, False otherwise.
        """
        try:
            self._slots.remove(item)
            return True
        except ValueError:
            return False

    def drop(self, item: Item) -> Item:
        """Remove *item* from the inventory and return it.

        Raises ValueError if the item is not in the inventory.
        """
        if item not in self._slots:
            raise ValueError(f"Item {item!r} is not in the inventory")
        self._slots.remove(item)
        return item

    def equip(self, item: Item) -> None:
        """Equip *item* as a weapon or armor piece.

        Raises ValueError if the item is not in the inventory.
        Raises TypeError if the item is not equippable (not a Weapon or Armor).
        """
        if item not in self._slots:
            raise ValueError(f"Item {item!r} must be in the inventory before equipping")
        if isinstance(item, Weapon):
            self._equipped_weapon = item
        elif isinstance(item, Armor):
            self._equipped_armor = item
        else:
            raise TypeError(
                f"Item of type {type(item).__name__!r} cannot be equipped; "
                "only Weapon and Armor are equippable"
            )

    def unequip(self, category: str) -> None:
        """Clear the equipped item for *category* ("weapon" or "armor").

        The item stays in the inventory slots.
        Raises ValueError for an unknown category string.
        Does not raise if the slot is already empty.
        """
        if category == "weapon":
            self._equipped_weapon = None
        elif category == "armor":
            self._equipped_armor = None
        else:
            raise ValueError(f"Unknown equip category: {category!r}")
