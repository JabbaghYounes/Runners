"""ItemDatabase — singleton that parses ``data/items.json`` and provides
an ``create(item_id)`` factory.

Design notes:
- The database is loaded once at startup; all subsequent accesses are
  in-memory lookups.
- ``create()`` returns a **deep copy** of the prototype so each Item
  instance in the inventory is independent (equipment state changes on one
  copy never bleed into other copies).
- Importing this module does *not* load the file.  Call
  ``ItemDatabase.instance().load()`` (or rely on ``create()``'s lazy load)
  before the game loop starts.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from src.inventory.item import Item, make_item

_DEFAULT_ITEMS_PATH: Path = Path("data") / "items.json"


class ItemDatabase:
    """Singleton item catalog backed by ``data/items.json``.

    Usage::

        db = ItemDatabase.instance()
        db.load()  # call once at startup
        rifle = db.create("rifle_pulse")
    """

    _instance: ItemDatabase | None = None

    def __init__(self) -> None:
        # Maps item_id → Item prototype.
        self._items: dict[str, Item] = {}
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> ItemDatabase:
        """Return the global singleton instance (creates it if needed)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, path: Path | str | None = None) -> None:
        """Parse the items JSON file and build the prototype cache.

        Args:
            path: Path to items.json.  Defaults to ``data/items.json``.

        Raises:
            FileNotFoundError: If the data file does not exist.
            KeyError: If a required field is missing from an item entry.
        """
        items_path = Path(path) if path is not None else _DEFAULT_ITEMS_PATH

        with items_path.open("r", encoding="utf-8") as fh:
            raw: dict[str, Any] = json.load(fh)

        self._items = {}
        for entry in raw.get("items", []):
            item = self._parse_entry(entry)
            self._items[item.item_id] = item

        self._loaded = True

    def _parse_entry(self, entry: dict[str, Any]) -> Item:
        """Build an Item prototype from a raw JSON dict."""
        return make_item(
            item_id=entry["id"],
            name=entry["name"],
            item_type=entry["type"],
            rarity=entry["rarity"],
            value=int(entry.get("value", 0)),
            weight=float(entry.get("weight", 1.0)),
            sprite=entry.get("sprite", ""),
            stats=entry.get("stats", {}),
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    def create(self, item_id: str) -> Item:
        """Return a fresh :class:`~src.inventory.item.Item` instance for
        *item_id*.

        The returned object is a deep copy of the stored prototype so
        callers are free to mutate it (e.g. attach mods, reduce quantity)
        without affecting the template.

        Args:
            item_id: Identifier matching the ``id`` field in items.json.

        Returns:
            A new Item (or subclass) instance.

        Raises:
            KeyError: If *item_id* is not found in the loaded catalog.
            RuntimeError: If ``load()`` has not been called yet.
        """
        if not self._loaded:
            # Lazy load with default path so simple use-cases don't need
            # an explicit ``load()`` call before the first ``create()``.
            self.load()

        try:
            prototype = self._items[item_id]
        except KeyError:
            raise KeyError(
                f"ItemDatabase: unknown item_id {item_id!r}. "
                f"Available: {sorted(self._items)}"
            ) from None

        return copy.deepcopy(prototype)

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def all_ids(self) -> list[str]:
        """Return a sorted list of all loaded item identifiers."""
        return sorted(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, item_id: str) -> bool:
        return item_id in self._items
