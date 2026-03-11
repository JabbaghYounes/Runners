"""JSON-backed item catalog with a factory method.

``ItemDatabase`` is a singleton that parses ``data/items.json`` once on
first access and returns fresh ``Item`` instances on demand via
``create(item_id)``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from src.inventory.item import Consumable, Item

# Resolved relative to this file: src/inventory/ → project root → data/
_DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "items.json"
)


class ItemDatabase:
    """Singleton item factory.

    Usage::

        from src.inventory.item_database import item_database
        medkit = item_database.create("medkit_small")
    """

    _instance: "ItemDatabase | None" = None

    def __new__(cls) -> "ItemDatabase":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._raw: dict[str, Any] = {}
            cls._instance._loaded = False
        return cls._instance

    # ------------------------------------------------------------------
    # Internal loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Parse items.json into memory (idempotent)."""
        if self._loaded:
            return
        path = os.path.abspath(_DATA_PATH)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self._raw = data.get("items", {})
        self._loaded = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, item_id: str) -> Item:
        """Return a fresh ``Item`` instance for *item_id*.

        Raises:
            KeyError: If *item_id* is not present in items.json.
        """
        self._load()
        if item_id not in self._raw:
            raise KeyError(f"Unknown item ID: {item_id!r}")
        raw = self._raw[item_id]
        item_type = raw.get("type", "consumable")

        if item_type == "consumable":
            return Consumable(
                id=raw["id"],
                name=raw["name"],
                rarity=raw.get("rarity", "common"),
                sprite_key=raw.get("sprite_key", ""),
                value=int(raw.get("value", 0)),
                consumable_type=raw.get("consumable_type", "heal"),
                heal_amount=int(raw.get("heal_amount", 0)),
                buff_type=raw.get("buff_type") or None,
                buff_value=float(raw.get("buff_value", 0)),
                buff_duration=float(raw.get("buff_duration", 0)),
                buff_icon_key=raw.get("buff_icon_key", raw.get("sprite_key", "")),
            )

        # Fallback for future Weapon / Armor / Attachment types.
        return Item(
            id=raw["id"],
            name=raw["name"],
            rarity=raw.get("rarity", "common"),
            sprite_key=raw.get("sprite_key", ""),
            value=int(raw.get("value", 0)),
        )

    def all_ids(self) -> list[str]:
        """Return every item ID defined in items.json."""
        self._load()
        return list(self._raw.keys())

    def reload(self) -> None:
        """Force a reload from disk (useful in tests and tooling)."""
        self._loaded = False
        self._raw = {}
        self._load()


# Module-level singleton.
item_database = ItemDatabase()
