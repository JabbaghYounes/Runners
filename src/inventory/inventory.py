"""Slot-based inventory with quick-slots and consumable use.

Layout
------
- ``_slots``:      Fixed-capacity list of ``Item | None``.  Slot 0 is the
                   first usable slot.
- ``quick_slots``: 4-element list of *inventory slot indices* (or None).
                   Pressing key [1]–[4] triggers ``use_consumable(qs_idx)``.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.entities.player import Player

from src.core import event_bus as _event_bus_module
from src.inventory.item import Consumable, Item


class Inventory:
    """Slot-based container for Items."""

    def __init__(self, capacity: int = 24) -> None:
        self._capacity: int = capacity
        self._slots: list[Optional[Item]] = [None] * capacity
        self.quick_slots: list[Optional[int]] = [None, None, None, None]

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    @property
    def slots(self) -> list[Optional[Item]]:
        """Shallow copy of the slot list (read-only snapshot)."""
        return list(self._slots)

    def item_at(self, slot_idx: int) -> Optional[Item]:
        """Return the item in *slot_idx*, or ``None`` for empty / out-of-range."""
        if slot_idx < 0 or slot_idx >= len(self._slots):
            return None
        return self._slots[slot_idx]

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def add_item(self, item: Item) -> Optional[int]:
        """Place *item* in the first empty slot.

        Returns:
            The slot index where the item was placed, or ``None`` if the
            inventory is full.
        """
        for i, slot in enumerate(self._slots):
            if slot is None:
                self._slots[i] = item
                return i
        return None

    def remove_item(self, slot_idx: int) -> Optional[Item]:
        """Remove and return the item at *slot_idx*.

        Also clears any quick-slot that was linked to *slot_idx*.

        Returns:
            The item that was removed, or ``None`` if the slot was already
            empty or the index is out of range.
        """
        if slot_idx < 0 or slot_idx >= len(self._slots):
            return None
        item = self._slots[slot_idx]
        if item is None:
            return None
        self._slots[slot_idx] = None
        # Clear any quick-slot pointing to this slot
        for i, qs in enumerate(self.quick_slots):
            if qs == slot_idx:
                self.quick_slots[i] = None
        return item

    def assign_quick_slot(self, inv_slot_idx: int, qs_idx: int) -> None:
        """Link quick-slot *qs_idx* to inventory slot *inv_slot_idx*."""
        if 0 <= qs_idx < 4:
            self.quick_slots[qs_idx] = inv_slot_idx

    def quick_slot_item(self, qs_idx: int) -> Optional[Item]:
        """Return the item assigned to quick-slot *qs_idx*, or ``None``."""
        if qs_idx < 0 or qs_idx >= 4:
            return None
        inv_slot = self.quick_slots[qs_idx]
        if inv_slot is None:
            return None
        return self.item_at(inv_slot)

    def use_consumable(self, slot_idx: int, player) -> bool:
        """Use the consumable assigned to quick-slot *slot_idx*.

        Resolves the linked inventory slot from ``quick_slots[slot_idx]``,
        calls ``item.use(player)``, removes the item, and emits
        ``consumable_used``.

        Returns:
            ``True`` if a consumable was successfully used.
            ``False`` if the quick-slot is unassigned, the inventory slot
            is empty, or the item is not a ``Consumable``.
        """
        if slot_idx < 0 or slot_idx >= 4:
            return False
        inv_slot = self.quick_slots[slot_idx]
        if inv_slot is None:
            return False
        item = self.item_at(inv_slot)
        if item is None:
            return False
        if not isinstance(item, Consumable):
            return False
        item.use(player)
        self.remove_item(inv_slot)
        _event_bus_module.event_bus.emit(
            "consumable_used", {"player": player, "item": item}
        )
        return True

    # ------------------------------------------------------------------
    # Capacity expansion (added for HomeBase storage bonus)
    # ------------------------------------------------------------------

    def expand_capacity(self, n: int) -> None:
        """Append *n* empty slots, increasing total capacity.

        Called at round start when the Storage facility is upgraded.
        """
        if n <= 0:
            return
        self._slots.extend([None] * n)
        self._capacity += n

    def to_save_list(self) -> list:
        """Serialise non-None items to a list of dicts."""
        result = []
        for item in self._slots:
            if item is not None:
                result.append({
                    "item_id": item.item_id,
                    "quantity": item.quantity,
                })
        return result
