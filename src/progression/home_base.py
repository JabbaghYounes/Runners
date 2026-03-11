"""HomeBase — manages facility upgrade levels and round-start bonuses.

Design notes:
- Constructor receives a ``Currency`` reference so upgrade cost deductions
  go through the same single-truth ledger used everywhere else.
- ``upgrade()`` never raises on insufficient funds — it returns ``False``
  and leaves all state unchanged so callers can react gracefully.
- ``get_round_bonuses()`` aggregates all facility bonuses into a flat dict
  that ``GameScene`` applies to the player at round start.
- Facility state (current levels) is serialised/deserialised via
  ``to_save_dict()`` / ``from_save_dict()`` rather than going through JSON
  again, so ``SaveManager`` just stores the dict it receives.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.progression.currency import Currency

_DEFAULT_HOME_BASE_PATH: Path = Path("data") / "home_base.json"


class HomeBase:
    """Tracks facility upgrade levels and deducts upgrade costs from
    ``Currency``.

    Args:
        currency:  The shared :class:`~src.progression.currency.Currency`
                   instance.
        data_path: Path to ``data/home_base.json``.  Defaults to that path.
    """

    def __init__(
        self,
        currency: Currency,
        data_path: Path | str | None = None,
    ) -> None:
        self._currency = currency
        self._data_path = Path(data_path) if data_path else _DEFAULT_HOME_BASE_PATH

        # Maps facility_id → list of level dicts (index = level - 1).
        self._level_data: dict[str, list[dict[str, Any]]] = {}
        # Maps facility_id → dict with metadata (name, description, max_level).
        self._facility_meta: dict[str, dict[str, Any]] = {}
        # Maps facility_id → current level (0 = not yet purchased).
        self._levels: dict[str, int] = {}

        self._load()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Parse data/home_base.json and initialise all facilities at level 0."""
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upgrade(self, facility_id: str) -> bool:
        """Attempt to upgrade *facility_id* to the next level.

        Deducts the upgrade cost from ``Currency`` if the player can afford
        it and the facility is not already at max level.

        Args:
            facility_id: ID of the facility to upgrade (e.g. ``"armory"``).

        Returns:
            ``True`` if the upgrade succeeded.
            ``False`` if the facility is maxed out, unknown, or the player
            cannot afford it (no state is mutated in this case).
        """
        if facility_id not in self._levels:
            return False

        current = self._levels[facility_id]
        max_lvl = self._facility_meta[facility_id]["max_level"]

        if current >= max_lvl:
            return False

        next_level_entry = self._level_data[facility_id][current]  # index = next level - 1
        cost: int = next_level_entry["cost"]

        if not self._currency.spend(cost):
            return False

        self._levels[facility_id] = current + 1
        return True

    def get_level(self, facility_id: str) -> int:
        """Return the current upgrade level of *facility_id* (0 if unknown)."""
        return self._levels.get(facility_id, 0)

    def get_next_level_data(self, facility_id: str) -> dict[str, Any] | None:
        """Return the next-level dict for *facility_id*, or None if maxed/unknown."""
        if facility_id not in self._levels:
            return None
        current = self._levels[facility_id]
        levels = self._level_data.get(facility_id, [])
        if current >= len(levels):
            return None
        return levels[current]

    def get_current_level_data(self, facility_id: str) -> dict[str, Any] | None:
        """Return the current level dict for *facility_id*, or None if at 0/unknown."""
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
        """Return display metadata for *facility_id* (name, description, icon, max_level)."""
        return self._facility_meta.get(facility_id, {})

    def facility_ids(self) -> list[str]:
        """Return a list of all facility IDs in definition order."""
        return list(self._levels.keys())

    def get_round_bonuses(self) -> dict[str, Any]:
        """Aggregate all active facility bonuses into a flat dict.

        The dict is consumed by ``GameScene`` to modify player stats at
        round start.  Keys match the ``bonus_type`` strings defined in
        ``data/home_base.json``.

        Returns:
            A dict such as::

                {
                    "weapon_damage_percent": 10,
                    "starting_health_bonus": 45,
                    "inventory_slots_bonus": 4,
                    "xp_gain_percent": 20,
                }

            Values accumulate (bonuses at each level are the *total* bonus
            for that level, not a delta).  Only facilities at level > 0
            contribute.
        """
        bonuses: dict[str, Any] = {}
        for fid, current_level in self._levels.items():
            if current_level == 0:
                continue
            level_entry = self._level_data[fid][current_level - 1]
            bonus_type: str = level_entry["bonus_type"]
            bonus_value = level_entry["bonus_value"]
            # In case multiple facilities share a bonus type, accumulate.
            bonuses[bonus_type] = bonuses.get(bonus_type, 0) + bonus_value
        return bonuses

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_save_dict(self) -> dict[str, int]:
        """Return a dict of facility_id → level suitable for the save file."""
        return dict(self._levels)

    def from_save_dict(self, data: dict[str, int]) -> None:
        """Restore facility levels from a previously saved dict.

        Unknown facility IDs in *data* are silently ignored so that removing
        a facility from the data file does not crash on an old save.

        Args:
            data: Mapping of facility_id → level (as stored in save.json).
        """
        for fid, level in data.items():
            if fid in self._levels:
                max_lvl = self._facility_meta[fid]["max_level"]
                self._levels[fid] = max(0, min(int(level), max_lvl))
