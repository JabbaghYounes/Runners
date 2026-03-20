"""Slot-based inventory with quick-slots, consumable use, and an armor slot."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from src.core.event_bus import event_bus

if TYPE_CHECKING:
    from src.entities.player import Player
    from src.inventory.item import Armor, Consumable, Item


class _CallableList(list):
    """A list that can also be called (returns a copy of itself)."""
    def __call__(self):
        return list(self)


class Inventory:
    """Fixed-capacity item grid with 4 dedicated quick-slots."""

    MAX_SLOTS: int = 24
    QUICK_SLOT_COUNT: int = 4

    def __init__(self, capacity: int = MAX_SLOTS, max_slots: int | None = None, max_weight: float = 20.0) -> None:
        if max_slots is not None:
            capacity = max_slots
        self.capacity = capacity
        self.max_weight: float = max_weight
        self._slots: list[Item | None] = [None] * capacity
        self.quick_slots: list[int | None] = [None] * self.QUICK_SLOT_COUNT
        self._equipped: "Item | None" = None
        self.equipped_weapon: "Item | None" = None
        self.equipped_armor: "Item | None" = None
        # Callback fired whenever the equipped armor changes (set by Player)
        self.on_armor_changed: Callable[[], None] | None = None

    # ------------------------------------------------------------------
    # Slot inspection
    # ------------------------------------------------------------------

    @property
    def slots(self) -> "list[Item | None]":
        """Shallow copy of the slot list (read-only snapshot).
        Returns a callable list that can also be invoked as slots()."""
        return _CallableList(self._slots)

    def item_at(self, slot_idx: int) -> "Item | None":
        if 0 <= slot_idx < self.capacity:
            return self._slots[slot_idx]
        return None

    @property
    def used_slots(self) -> int:
        return sum(1 for s in self._slots if s is not None)

    @property
    def total_weight(self) -> float:
        return sum(getattr(item, 'weight', 0) for item in self._slots if item is not None)

    @property
    def is_full(self) -> bool:
        if all(slot is not None for slot in self._slots):
            return True
        if self.total_weight >= self.max_weight:
            return True
        return False

    # ------------------------------------------------------------------
    # Adding / removing items
    # ------------------------------------------------------------------

    def add_item(self, item: "Item") -> "int | None":
        # Check weight cap
        item_weight = getattr(item, 'weight', 0)
        if self.total_weight + item_weight > self.max_weight:
            return None
        for i, slot in enumerate(self._slots):
            if slot is None:
                self._slots[i] = item
                return i
        return None

    # Legacy alias
    def add(self, item: "Item") -> bool:
        return self.add_item(item) is not None

    def remove_item(self, slot_idx: int) -> "Item | None":
        if not (0 <= slot_idx < self.capacity):
            return None
        item = self._slots[slot_idx]
        self._slots[slot_idx] = None
        for i, qs in enumerate(self.quick_slots):
            if qs == slot_idx:
                self.quick_slots[i] = None
        return item

    # Legacy alias
    def remove(self, item: "Item") -> bool:
        for i, slot in enumerate(self._slots):
            if slot is item:
                self._slots[i] = None
                return True
        return False

    def drop(self, item: "Item") -> "Item":
        """Remove item from inventory and return it. Raises ValueError if not present."""
        for i, slot in enumerate(self._slots):
            if slot is item:
                self._slots[i] = None
                for qi, qs in enumerate(self.quick_slots):
                    if qs == i:
                        self.quick_slots[qi] = None
                return item
        raise ValueError(f"Item {item!r} not in inventory")

    def expand_capacity(self, n: int) -> None:
        """Expand inventory by n slots."""
        if n > 0:
            self.capacity += n
            self._slots.extend([None] * n)

    def clear(self) -> None:
        """Remove all items."""
        self._slots = [None] * self.capacity
        self.quick_slots = [None] * self.QUICK_SLOT_COUNT
        self._equipped = None
        self.equipped_weapon = None
        self.equipped_armor = None

    # ------------------------------------------------------------------
    # Equipment
    # ------------------------------------------------------------------

    def equip(self, item: "Item") -> None:
        # Must be in inventory
        if item not in self._slots:
            raise ValueError(f"Cannot equip item not in inventory: {item!r}")
        item_type = getattr(item, 'item_type', getattr(item, 'type', 'item'))
        if item_type not in ('weapon', 'armor'):
            raise TypeError(f"Cannot equip item of type {item_type!r}")
        if item_type == 'weapon':
            self.equipped_weapon = item
        elif item_type == 'armor':
            self.equipped_armor = item
        self._equipped = item

    def unequip(self, category: str = None, slot_idx: int | None = None) -> None:
        if category == 'weapon':
            self.equipped_weapon = None
            if self._equipped and getattr(self._equipped, 'item_type', '') == 'weapon':
                self._equipped = None
        elif category == 'armor':
            self.equipped_armor = None
            if self._equipped and getattr(self._equipped, 'item_type', '') == 'armor':
                self._equipped = None
        elif category is None:
            self._equipped = None
        else:
            raise ValueError(f"Unknown equipment category: {category!r}")

    @property
    def equipped(self) -> "Item | None":
        return self._equipped

    # ------------------------------------------------------------------
    # Dedicated armor slot
    # ------------------------------------------------------------------

    def equip_armor(self, armor_item: "Armor") -> "Armor | None":
        """Equip an armor piece, displacing any currently equipped one.

        The old piece (if any) is returned so the caller can decide what to
        do with it (e.g. return it to the main grid).

        Args:
            armor_item: The :class:`Armor` instance to equip.

        Returns:
            The previously equipped :class:`Armor`, or ``None`` if the slot
            was empty.

        Raises:
            TypeError: If *armor_item* is not an :class:`Armor` instance.
        """
        from src.inventory.item import Armor
        if not isinstance(armor_item, Armor):
            raise TypeError(
                f"equip_armor() requires an Armor instance, got {type(armor_item).__name__!r}"
            )
        displaced = self.equipped_armor
        self.equipped_armor = armor_item
        if self.on_armor_changed is not None:
            self.on_armor_changed()
        event_bus.emit("armor_equipped", item=armor_item)
        return displaced

    def unequip_armor(self) -> "Armor | None":
        """Remove the currently equipped armor piece and return it.

        Returns:
            The removed :class:`Armor` item, or ``None`` if no armor was
            equipped.
        """
        displaced = self.equipped_armor
        self.equipped_armor = None
        if self.on_armor_changed is not None:
            self.on_armor_changed()
        if displaced is not None:
            event_bus.emit("armor_unequipped", item=displaced)
        return displaced

    # ------------------------------------------------------------------
    # Quick-slot management
    # ------------------------------------------------------------------

    def assign_quick_slot(self, inv_slot_idx: int, qs_idx: int) -> None:
        if 0 <= qs_idx < self.QUICK_SLOT_COUNT:
            self.quick_slots[qs_idx] = inv_slot_idx

    def quick_slot_item(self, qs_idx: int) -> "Item | None":
        if not (0 <= qs_idx < self.QUICK_SLOT_COUNT):
            return None
        inv_slot = self.quick_slots[qs_idx]
        if inv_slot is None:
            return None
        return self._slots[inv_slot] if 0 <= inv_slot < self.capacity else None

    # ------------------------------------------------------------------
    # Consumable use
    # ------------------------------------------------------------------

    def use_consumable(self, slot_idx: int, player: "Player") -> bool:
        from src.inventory.item import Consumable

        if not (0 <= slot_idx < self.QUICK_SLOT_COUNT):
            return False
        inv_slot = self.quick_slots[slot_idx]
        if inv_slot is None:
            return False
        item = self._slots[inv_slot]
        if item is None or not isinstance(item, Consumable):
            return False

        item.use(player)
        self.remove_item(inv_slot)
        event_bus.emit("consumable_used", item=item, player=player)
        return True

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_items(self) -> "list[Item]":
        return [s for s in self._slots if s is not None]

    def get_consumables(self) -> "list[Item]":
        return [s for s in self._slots if s is not None and getattr(s, 'type', '') == 'consumable'][:4]

    def __len__(self) -> int:
        return self.used_slots

    def append(self, item) -> None:
        """Append an item to the first empty slot (list-like interface)."""
        for i, slot in enumerate(self._slots):
            if slot is None:
                self._slots[i] = item
                return
        # If all slots are full, expand capacity by 1
        self._slots.append(item)
        self.capacity += 1

    def __iter__(self):
        return iter(s for s in self._slots if s is not None)

    def __contains__(self, item) -> bool:
        return item in self._slots

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_save_list(self) -> list[dict]:
        """Serialise all items in the inventory to a JSON-safe list of dicts.

        The equipped armor item is appended with a ``"_slot": "equipped_armor"``
        sentinel so it can be restored by :meth:`from_save_list`.
        """
        result: list[dict] = []
        for item in self._slots:
            if item is not None and hasattr(item, "to_save_dict"):
                result.append(item.to_save_dict())
        if self.equipped_armor is not None and hasattr(self.equipped_armor, "to_save_dict"):
            entry = self.equipped_armor.to_save_dict()
            entry["_slot"] = "equipped_armor"
            result.append(entry)
        return result

    def from_save_list(self, data: list[dict]) -> None:
        """Restore inventory contents from a list of item dicts.

        Existing items are cleared before loading.  Each dict is passed
        through ``make_item()`` to reconstruct the correct Item subclass.
        Weapon dicts that include an ``attachments`` key have their
        attachments re-equipped via ``weapon_from_save_dict()``.
        """
        from src.inventory.item import Weapon, make_item

        self.clear()
        for item_data in data:
            if not isinstance(item_data, dict):
                continue
            try:
                # Detect the equipped-armor sentinel
                if item_data.get("_slot") == "equipped_armor":
                    entry = {k: v for k, v in item_data.items() if k != "_slot"}
                    item = make_item(entry)
                    if isinstance(item, Armor):
                        self.equipped_armor = item
                        if self.on_armor_changed is not None:
                            self.on_armor_changed()
                    continue

                item = make_item(item_data)
                # Rebuild attachments when the saved dict carries them.
                if (
                    isinstance(item, Weapon)
                    and "attachments" in item_data
                    and isinstance(item_data["attachments"], dict)
                ):
                    from src.inventory.weapon_attachments import weapon_from_save_dict
                    restored_atts = weapon_from_save_dict(item_data)
                    for slot_type, att in restored_atts.items():
                        if slot_type in item.mod_slots:
                            item.attachments[slot_type] = att
                # Bypass weight check for saved items -- they were valid when saved
                for i, slot in enumerate(self._slots):
                    if slot is None:
                        self._slots[i] = item
                        break
                else:
                    # Expand if all slots full (saved data may have had more slots)
                    self._slots.append(item)
                    self.capacity += 1
            except (TypeError, KeyError, ValueError):
                # Skip items that can't be reconstructed
                continue
