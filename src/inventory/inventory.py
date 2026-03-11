"""Inventory — slot-based item container with quick-slot support."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from src.core import event_bus as _event_bus_module
from src.inventory.item import Consumable, Item

if TYPE_CHECKING:
    from src.entities.player import Player

_QUICK_SLOTS = 4


class Inventory:
    """Slot-based item container.

    The inventory maintains a flat list of optional Item slots plus
    a separate quick-slot mapping (inventory index → quick-slot index).
    """

    def __init__(self, capacity: int = 24) -> None:
        self._slots: list[Optional[Item]] = [None] * capacity
        self._quick_slots: dict[int, int] = {}  # inv_idx → qs_idx

    @property
    def slots(self) -> list[Optional[Item]]:
        return self._slots

    def item_at(self, slot_idx: int) -> Optional[Item]:
        if 0 <= slot_idx < len(self._slots):
            return self._slots[slot_idx]
        return None

    def add_item(self, item: Item) -> Optional[int]:
        """Place *item* in the first empty slot; return the slot index or None."""
        for i, slot in enumerate(self._slots):
            if slot is None:
                self._slots[i] = item
                return i
        return None

    def remove_item(self, slot_idx: int) -> Optional[Item]:
        """Remove and return the item at *slot_idx*."""
        item = self.item_at(slot_idx)
        if item is None:
            return None
        self._slots[slot_idx] = None
        # Remove from quick slots if mapped
        for qs, i in list(self._quick_slots.items()):
            if i == slot_idx:
                del self._quick_slots[qs]
        return item

    def assign_quick_slot(self, inv_slot_idx: int, qs_idx: int) -> None:
        """Map inventory slot *inv_slot_idx* to quick-slot *qs_idx*."""
        if not (0 <= qs_idx < _QUICK_SLOTS):
            return
        # Remove any existing mapping for this qs_idx
        for existing_qs, existing_inv in list(self._quick_slots.items()):
            if existing_qs == qs_idx:
                del self._quick_slots[existing_qs]
                break
        self._quick_slots[qs_idx] = inv_slot_idx

    def quick_slot_item(self, qs_idx: int) -> Optional[Item]:
        """Return the item assigned to quick-slot *qs_idx* or None."""
        inv_slot = self._quick_slots.get(qs_idx)
        if inv_slot is None:
            return None
        return self.item_at(inv_slot)

    def use_consumable(self, slot_idx: int, player: "Player") -> bool:
        """Use the consumable at *slot_idx* on *player*; return True if used."""
        inv_slot = self._slots[slot_idx] if 0 <= slot_idx < len(self._slots) else None
        if inv_slot is None or not isinstance(inv_slot, Consumable):
            return False
        item = inv_slot
        item.use(player)
        item.quantity -= 1
        if item.quantity <= 0:
            self.remove_item(slot_idx)
        return True

    def expand_capacity(self, n: int) -> None:
        """Add *n* extra inventory slots."""
        self._slots.extend([None] * max(0, n))

    def to_save_list(self) -> list[dict]:
        """Serialise inventory for save file."""
        result = []
        for item in self._slots:
            if item is not None:
                result.append({'item_id': item.item_id, 'quantity': item.quantity})
        return result

    @property
    def capacity(self) -> int:
        return len(self._slots)

    def equipped_weapon(self) -> Optional[Item]:
        """Return the first weapon found in inventory, or None."""
        from src.inventory.item import Weapon
        for item in self._slots:
            if isinstance(item, Weapon):
                return item
        return None
