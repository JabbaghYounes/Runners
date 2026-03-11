import json
import os
from typing import Dict, Optional, List
from src.inventory.item import Item, make_item, Rarity

class ItemDatabase:
    _instance: Optional['ItemDatabase'] = None

    def __init__(self):
        self._items: Dict[str, dict] = {}

    @classmethod
    def instance(cls) -> 'ItemDatabase':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self, path: str) -> None:
        with open(path, 'r') as f:
            raw = json.load(f)
        for item_id, data in raw.items():
            data['item_id'] = item_id
            self._items[item_id] = data

    def create(self, item_id: str) -> Optional[Item]:
        data = self._items.get(item_id)
        if data is None:
            return None
        return make_item(dict(data))

    def get_all_by_type(self, item_type: str) -> List[Item]:
        return [make_item(dict(d)) for d in self._items.values() if d.get('type') == item_type]

    def get_all_by_rarity(self, rarity: str) -> List[Item]:
        return [make_item(dict(d)) for d in self._items.values() if d.get('rarity') == rarity]

    @property
    def item_ids(self) -> List[str]:
        return list(self._items.keys())
