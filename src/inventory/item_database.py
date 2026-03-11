"""ItemDatabase — singleton that parses ``data/items.json`` and provides
an ``create(item_id)`` factory.

Design notes:
- The database is loaded once at startup; all subsequent accesses are
  in-memory lookups.
- ``create()`` returns a **deep copy** of the prototype so each Item
  instance in the inventory is independent (equipment state changes on one
  copy never bleed into other copies).
- Importing this module does *not* load the file.  Call
  ``ItemDatabase.get_instance().load()`` (or rely on ``create()``'s lazy load)
  before the game loop starts.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from src.inventory.item import Item, Rarity, make_item

_DEFAULT_ITEMS_PATH = Path("data") / "items.json"


class ItemDatabase:
    """Singleton catalog of every item definition in the game."""

    _instance: "ItemDatabase | None" = None
    _items: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> "ItemDatabase":
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance.__post_init__()
        return cls._instance

    def __post_init__(self) -> None:
        # Per-instance item store (mirrored to the class attr for fixture resets)
        self._items: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, path: str | Path | None = None) -> None:
        """Parse *path* (default: ``data/items.json``) and populate the catalog.

        Calling this method more than once replaces the catalog; it does not
        raise or corrupt state.
        """
        path = Path(path) if path is not None else _DEFAULT_ITEMS_PATH
        with open(path, "r", encoding="utf-8") as fh:
            raw: list[dict[str, Any]] = json.load(fh)

        self._items = {}
        for entry in raw:
            self._items[entry["id"]] = entry

        # Keep class-level attr in sync for singleton-reset fixtures
        ItemDatabase._items = self._items

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def _entry_to_kwargs(entry: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw JSON entry dict into constructor kwargs for make_item."""
        data = copy.deepcopy(entry)
        # Normalise the sprite key
        if "sprite" in data:
            data["sprite_path"] = data.pop("sprite")
        # Convert rarity string → Rarity enum
        data["rarity"] = Rarity[data["rarity"]]
        return data

    def create(self, item_id: str) -> Item:
        """Return a fresh independent Item instance for *item_id*.

        Raises KeyError if the id is not in the catalog.
        """
        try:
            entry = self._items[item_id]
        except KeyError:
            raise KeyError(f"Unknown item id: {item_id!r}")

        kwargs = self._entry_to_kwargs(entry)
        item_type = kwargs.pop("type")
        # Re-inject type as the positional first arg expected by make_item
        return make_item(item_type, type=item_type, **kwargs)

    # ------------------------------------------------------------------
    # Helper queries
    # ------------------------------------------------------------------

    def get_all_by_type(self, item_type: str) -> list[Item]:
        """Return a list of fresh Item instances for all items of *item_type*."""
        return [
            self.create(entry["id"])
            for entry in self._items.values()
            if entry.get("type") == item_type
        ]

    def get_all_by_rarity(self, rarity: Rarity) -> list[Item]:
        """Return a list of fresh Item instances for all items with *rarity*."""
        return [
            self.create(entry["id"])
            for entry in self._items.values()
            if Rarity[entry["rarity"]] == rarity
        ]
