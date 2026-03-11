from typing import List, Optional
from src.inventory.item import Item

class Inventory:
    def __init__(self, max_slots: int = 24, max_weight: float = 20.0):
        self.max_slots = max_slots
        self.max_weight = max_weight
        self.slots: List[Optional[Item]] = [None] * max_slots
        self._equipped: Optional[Item] = None

    @property
    def total_weight(self) -> float:
        return sum(item.weight for item in self.slots if item is not None)

    @property
    def is_full(self) -> bool:
        return all(slot is not None for slot in self.slots)

    def add(self, item: Item) -> bool:
        if self.total_weight + item.weight > self.max_weight:
            return False
        for i, slot in enumerate(self.slots):
            if slot is None:
                self.slots[i] = item
                return True
        return False

    def remove(self, item: Item) -> bool:
        for i, slot in enumerate(self.slots):
            if slot is item:
                self.slots[i] = None
                return True
        return False

    def equip(self, item: Item) -> None:
        self._equipped = item

    def unequip(self) -> None:
        self._equipped = None

    @property
    def equipped(self) -> Optional[Item]:
        return self._equipped

    def drop(self, item: Item) -> bool:
        return self.remove(item)

    def get_items(self) -> List[Item]:
        return [s for s in self.slots if s is not None]

    def get_consumables(self) -> List[Optional[Item]]:
        return [s for s in self.slots if s is not None and s.type == 'consumable'][:4]
