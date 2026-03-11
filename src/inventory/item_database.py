"""ItemDatabase — parses data/items.json and creates Item instances."""
from __future__ import annotations
import json
import os
from typing import Optional

from src.inventory.item import Item, make_item

_DEFAULT_DATA_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'data', 'items.json'
)


class ItemDatabase:
    """Singleton-ish item catalog loaded from data/items.json."""

    _catalog: dict[str, dict] = {}
    _loaded: bool = False

    @classmethod
    def _ensure_loaded(cls, path: str = _DEFAULT_DATA_PATH) -> None:
        if cls._loaded:
            return
        try:
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
            for entry in data:
                cls._catalog[entry['id']] = entry
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            pass
        cls._loaded = True

    def create(self, item_id: str) -> Optional[Item]:
        """Create an Item instance from the catalog."""
        self._ensure_loaded()
        entry = self._catalog.get(item_id)
        if entry is None:
            return None
        return make_item(
            item_id=item_id,
            item_type=entry.get('type', 'item'),
            name=entry.get('name', item_id),
            rarity=entry.get('rarity', 'common'),
            value=entry.get('value'),
            stats=entry.get('stats', {}),
        )
