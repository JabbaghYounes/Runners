"""Slot-based inventory with quick-slots and consumable use.

Layout
------
- ``_slots``:      Fixed-capacity list of ``Item | None``.  Slot 0 is the
                   first usable slot.
- ``quick_slots``: 4-element list of *inventory slot indices* (or None).
                   Pressing key [1]–[4] triggers ``use_consumable(qs_idx)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.event_bus import event_bus

if TYPE_CHECKING:
    from src.entities.player import Player
    from src.inventory.item import Consumable, Item


class Inventory:
    """Fixed-capacity item grid with 4 dedicated quick-slots.

    Empty slots are represented by ``None``.  Quick-slots store inventory
    slot indices so an item can be used without knowing its slot number.
    """

    MAX_SLOTS: int = 20
    QUICK_SLOT_COUNT: int = 4

    def __init__(self, capacity: int = MAX_SLOTS) -> None:
        self.capacity = capacity
        self._slots: list[Item | None] = [None] * capacity
        # quick_slots[i] = inventory slot index, or None if unassigned.
        self.quick_slots: list[int | None] = [None] * self.QUICK_SLOT_COUNT

    # ------------------------------------------------------------------
    # Slot inspection
    # ------------------------------------------------------------------

    def slots(self) -> list["Item | None"]:
        """Shallow copy of the slot list (read-only snapshot)."""
        return list(self._slots)

    def item_at(self, slot_idx: int) -> "Item | None":
        """Return the item in *slot_idx*, or ``None`` for empty / out-of-range."""
        if 0 <= slot_idx < self.capacity:
            return self._slots[slot_idx]
        return None

    # ------------------------------------------------------------------
    # Adding / removing items
    # ------------------------------------------------------------------

    def add_item(self, item: "Item") -> int | None:
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

    def remove_item(self, slot_idx: int) -> "Item | None":
        """Remove and return the item at *slot_idx*.

        Also clears any quick-slot that was linked to *slot_idx*.

        Returns:
            The item that was removed, or ``None`` if the slot was already
            empty or the index is out of range.
        """
        if not (0 <= slot_idx < self.capacity):
            return None
        item = self._slots[slot_idx]
        self._slots[slot_idx] = None
        # Unlink quick-slots that pointed at this inventory slot.
        for i, qs in enumerate(self.quick_slots):
            if qs == slot_idx:
                self.quick_slots[i] = None
        return item

    # ------------------------------------------------------------------
    # Quick-slot management
    # ------------------------------------------------------------------

    def assign_quick_slot(self, inv_slot_idx: int, qs_idx: int) -> None:
        """Link quick-slot *qs_idx* to inventory slot *inv_slot_idx*."""
        if 0 <= qs_idx < self.QUICK_SLOT_COUNT:
            self.quick_slots[qs_idx] = inv_slot_idx

    def quick_slot_item(self, qs_idx: int) -> "Item | None":
        """Return the item assigned to quick-slot *qs_idx*, or ``None``."""
        if not (0 <= qs_idx < self.QUICK_SLOT_COUNT):
            return None
        inv_slot = self.quick_slots[qs_idx]
        if inv_slot is None:
            return None
        return self._slots[inv_slot]

    # ------------------------------------------------------------------
    # Consumable use
    # ------------------------------------------------------------------

    def use_consumable(self, slot_idx: int, player: "Player") -> bool:
        """Use the consumable assigned to quick-slot *slot_idx*.

        Resolves the linked inventory slot from ``quick_slots[slot_idx]``,
        calls ``item.use(player)``, removes the item, and emits
        ``consumable_used``.

        Returns:
            ``True`` if a consumable was successfully used.
            ``False`` if the quick-slot is unassigned, the inventory slot
            is empty, or the item is not a ``Consumable``.
        """
        from src.inventory.item import Consumable  # noqa: PLC0415

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
        event_bus.emit("consumable_used", {"item": item, "player": player})
        return True
