"""HomeBase -- manages facility upgrade levels and round-start bonuses.

Supports two constructor styles:
1. HomeBase(defs_path)           -- loads from JSON, currency passed to upgrade()
2. HomeBase(currency, data_path) -- injects currency at init
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.progression.currency import Currency

_DEFAULT_HOME_BASE_PATH: Path = Path("data") / "home_base.json"


class HomeBase:
    """Tracks facility upgrade levels."""

    def __init__(
        self,
        first_arg: "Currency | str | Path | None" = None,
        data_path: "Path | str | None" = None,
    ) -> None:
        # Determine constructor mode
        if isinstance(first_arg, Currency):
            self._currency = first_arg
            self._data_path = Path(data_path) if data_path else _DEFAULT_HOME_BASE_PATH
        elif isinstance(first_arg, (str, Path)):
            self._currency = None
            self._data_path = Path(first_arg)
        else:
            self._currency = None
            self._data_path = Path(data_path) if data_path else _DEFAULT_HOME_BASE_PATH

        self._level_data: dict[str, list[dict[str, Any]]] = {}
        self._facility_meta: dict[str, dict[str, Any]] = {}
        self._levels: dict[str, int] = {}
        self._bonus_types: set[str] = set()

        if self._data_path.exists():
            self._load()

    def _load(self) -> None:
        with self._data_path.open("r", encoding="utf-8") as fh:
            raw: dict[str, Any] = json.load(fh)

        for facility in raw.get("facilities", []):
            fid = facility["id"]
            self._facility_meta[fid] = {
                "name": facility["name"],
                "description": facility.get("description", ""),
                "icon": facility.get("icon", ""),
                "max_level": facility["max_level"],
            }
            self._level_data[fid] = facility["levels"]
            self._levels[fid] = 0
            # Track all bonus types for get_round_bonuses
            for level_entry in facility["levels"]:
                bt = level_entry.get("bonus_type")
                if bt:
                    self._bonus_types.add(bt)

    # ------------------------------------------------------------------
    # Upgrade
    # ------------------------------------------------------------------

    def upgrade(self, facility_id: str, currency: "Currency | None" = None,
                event_bus=None) -> bool:
        cur = currency or self._currency
        if facility_id not in self._levels:
            return False

        current = self._levels[facility_id]
        max_lvl = self._facility_meta[facility_id]["max_level"]

        if current >= max_lvl:
            return False

        next_level_entry = self._level_data[facility_id][current]
        cost: int = next_level_entry["cost"]

        if cur is None:
            return False
        if not cur.spend(cost):
            return False

        self._levels[facility_id] = current + 1
        if event_bus is not None:
            event_bus.emit("currency_spent", amount=cost, new_balance=cur.balance)
        return True

    def can_upgrade(self, facility_id: str, currency: "Currency | None" = None) -> bool:
        cur = currency or self._currency
        if facility_id not in self._levels:
            return False
        current = self._levels[facility_id]
        max_lvl = self._facility_meta[facility_id]["max_level"]
        if current >= max_lvl:
            return False
        if cur is None:
            return False
        cost = self._level_data[facility_id][current]["cost"]
        return cur.balance >= cost

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def current_level(self, facility_id: str) -> int:
        return self._levels.get(facility_id, 0)

    # Alias
    def get_level(self, facility_id: str) -> int:
        return self.current_level(facility_id)

    def max_level(self, facility_id: str) -> int:
        if facility_id not in self._facility_meta:
            raise KeyError(f"Unknown facility: {facility_id!r}")
        return self._facility_meta[facility_id]["max_level"]

    def is_maxed(self, facility_id: str) -> bool:
        if facility_id not in self._levels:
            return False
        return self._levels[facility_id] >= self._facility_meta[facility_id]["max_level"]

    def upgrade_cost(self, facility_id: str) -> "int | None":
        if facility_id not in self._level_data:
            raise KeyError(f"Unknown facility: {facility_id!r}")
        current = self._levels.get(facility_id, 0)
        levels = self._level_data[facility_id]
        if current >= len(levels):
            return None
        return levels[current]["cost"]

    def get_next_level_data(self, facility_id: str) -> "dict[str, Any] | None":
        if facility_id not in self._levels:
            return None
        current = self._levels[facility_id]
        levels = self._level_data.get(facility_id, [])
        if current >= len(levels):
            return None
        return levels[current]

    def get_current_level_data(self, facility_id: str) -> "dict[str, Any] | None":
        if facility_id not in self._levels:
            return None
        current = self._levels[facility_id]
        if current == 0:
            return None
        levels = self._level_data.get(facility_id, [])
        if current - 1 >= len(levels):
            return None
        return levels[current - 1]

    def get_facility_meta(self, facility_id: str) -> dict[str, Any]:
        return self._facility_meta.get(facility_id, {})

    def get_facility_display(self, facility_id: str) -> dict[str, Any]:
        """Return display-ready dict for a facility."""
        meta = self._facility_meta[facility_id]
        current = self._levels[facility_id]
        max_lvl = meta["max_level"]
        levels = self._level_data[facility_id]

        # Current bonus description
        if current == 0:
            current_bonus = "Not built"
        else:
            current_bonus = levels[current - 1].get("description", "")

        # Next level
        if current >= max_lvl:
            bonus_desc = "MAX"
            cost = None
        else:
            bonus_desc = levels[current].get("description", "")
            cost = levels[current]["cost"]

        return {
            "id": facility_id,
            "name": meta["name"],
            "level": current,
            "max_level": max_lvl,
            "cost": cost,
            "bonus_description": bonus_desc,
            "current_bonus_description": current_bonus,
        }

    @property
    def facility_ids(self) -> list[str]:
        return list(self._levels.keys())

    def get_round_bonuses(self) -> dict[str, Any]:
        """Returns all bonus types, defaulting unknown to 0."""
        # Initialize all known types to 0
        bonuses: dict[str, Any] = {bt: 0 for bt in self._bonus_types}
        for fid, current_level in self._levels.items():
            if current_level == 0:
                continue
            level_entry = self._level_data[fid][current_level - 1]
            bonus_type: str = level_entry["bonus_type"]
            bonus_value = level_entry["bonus_value"]
            bonuses[bonus_type] = bonuses.get(bonus_type, 0) + bonus_value
        return bonuses

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_save_dict(self) -> dict[str, int]:
        return dict(self._levels)

    def from_save_dict(self, data: dict[str, Any]) -> None:
        for fid, level in data.items():
            if fid in self._levels:
                max_lvl = self._facility_meta[fid]["max_level"]
                self._levels[fid] = max(0, min(int(level), max_lvl))

    def get_all_bonuses(self) -> dict[str, Any]:
        """Alias for get_round_bonuses."""
        return self.get_round_bonuses()

    def get_bonus(self, bonus_type: str) -> float:
        """Return the current value for a single bonus type."""
        bonuses = self.get_round_bonuses()
        return float(bonuses.get(bonus_type, 0))

    # Legacy compat
    def get_facilities(self) -> list[dict]:
        return list(self._facility_meta.values())

    def load_state(self, data: dict) -> None:
        self.from_save_dict(data.get('facilities', data))
