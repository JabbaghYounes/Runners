"""ItemDatabase -- singleton that parses items.json and provides create() factory."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from src.inventory.item import Item, make_item

_DEFAULT_ITEMS_PATH: Path = Path("data") / "items.json"


class ItemDatabase:
    """Singleton item catalog backed by items.json."""

    _instance: "ItemDatabase | None" = None

    def __init__(self) -> None:
        self._items: dict[str, Item] = {}
        self._raw: dict[str, dict] = {}
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> "ItemDatabase":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # Legacy alias
    @classmethod
    def get_instance(cls) -> "ItemDatabase":
        return cls.instance()

    def reload(self) -> None:
        """Reload the item database from disk."""
        self._loaded = False
        self.load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, path: "Path | str | None" = None) -> None:
        items_path = Path(path) if path is not None else _DEFAULT_ITEMS_PATH

        with items_path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)

        self._items = {}
        self._raw = {}

        # Support both list format [{"id": ...}, ...] and dict format {"item_id": {...}, ...}
        if isinstance(raw, list):
            entries = raw
        elif isinstance(raw, dict) and "items" in raw:
            entries = raw["items"]
        elif isinstance(raw, dict):
            entries = []
            for key, val in raw.items():
                if isinstance(val, dict):
                    val = dict(val)
                    if "id" not in val:
                        val["id"] = key
                    entries.append(val)
        else:
            entries = []

        for entry in entries:
            item = self._parse_entry(entry)
            self._items[item.item_id] = item
            self._raw[item.item_id] = entry

        self._loaded = True

    def load_additional(self, path: "Path | str") -> None:
        """Merge entries from *path* into the existing catalog without clearing it.

        If the file does not exist or cannot be parsed, the method silently
        returns so that missing optional data files never crash the game.
        """
        try:
            items_path = Path(path)
            with items_path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return  # silently ignore missing/corrupt files

        if isinstance(raw, list):
            entries = raw
        elif isinstance(raw, dict) and "items" in raw:
            entries = raw["items"]
        elif isinstance(raw, dict):
            entries = []
            for key, val in raw.items():
                if isinstance(val, dict):
                    val = dict(val)
                    if "id" not in val:
                        val["id"] = key
                    entries.append(val)
        else:
            entries = []

        for entry in entries:
            item = self._parse_entry(entry)
            self._items[item.item_id] = item
            self._raw[item.item_id] = entry

    def _parse_entry(self, entry: dict[str, Any]) -> Item:
        # Collect known extra kwargs, filtering out None values
        extra: dict[str, Any] = {}
        _EXTRA_KEYS = (
            "damage", "fire_rate", "magazine_size", "mod_slots",
            "armor_rating", "armor_value", "slot_type",
            "consumable_type", "heal_amount",
            "buff_type", "buff_value", "buff_duration",
            "defense", "slot", "effect_type", "effect_value",
            "compatible_weapons", "stat_delta",
        )
        for k in _EXTRA_KEYS:
            v = entry.get(k)
            if v is not None:
                extra[k] = v

        return make_item(
            item_id=entry.get("id", entry.get("item_id", "")),
            name=entry.get("name", ""),
            item_type=entry.get("type", "misc"),
            rarity=entry.get("rarity", "COMMON"),
            value=int(entry.get("value", entry.get("base_value", 0))),
            weight=float(entry.get("weight", 1.0)),
            sprite=entry.get("sprite", ""),
            stats=entry.get("stats", {}),
            **extra,
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    def create(self, item_id: str) -> Item:
        if not self._loaded:
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
        return sorted(self._items)

    @property
    def item_ids(self) -> list[str]:
        return list(self._items.keys())

    def get_all_by_type(self, item_type: str) -> list[Item]:
        return [copy.deepcopy(i) for i in self._items.values() if getattr(i, 'type', '') == item_type]

    def get_all_by_rarity(self, rarity) -> list[Item]:
        """Get all items of the given rarity. Accepts string or Rarity enum."""
        from src.inventory.item import Rarity
        if isinstance(rarity, str):
            target = Rarity.from_str(rarity)
        elif isinstance(rarity, Rarity):
            target = rarity
        else:
            target = rarity
        return [copy.deepcopy(i) for i in self._items.values() if getattr(i, 'rarity', None) == target]

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, item_id: str) -> bool:
        return item_id in self._items


# Module-level singleton for convenience
item_database = ItemDatabase.instance()
