"""Home base hub — upgradeable facility system.

Design notes:
- Facility definitions are loaded from data/home_base.json at construction.
  No stats are hard-coded.
- upgrade() takes a Currency instance directly; HomeBase never owns currency.
- get_round_bonuses() aggregates all active facility bonuses:
    - extra_hp, extra_slots: additive (summed across all facilities)
    - loot_value_bonus: takes the maximum value (additive compounding would be
      too aggressive since facilities share bonus types)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class HomeBase:
    """Manages upgradeable home base facilities.

    Each facility has a current level (0 = not built) and up to max_level
    upgrades. Upgrading costs currency and grants a permanent per-round bonus.
    """

    def __init__(self, definitions_path: str = "data/home_base.json") -> None:
        self._defs: dict[str, dict] = {}   # facility_id -> definition
        self._levels: dict[str, int] = {}  # facility_id -> current level
        self._load_definitions(definitions_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_definitions(self, path: str) -> None:
        """Load facility definitions from JSON and initialise all levels to 0."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for facility in data["facilities"]:
            fid = facility["id"]
            self._defs[fid] = facility
            self._levels[fid] = 0

    def _def(self, facility_id: str) -> dict:
        if facility_id not in self._defs:
            raise KeyError(f"Unknown facility: {facility_id!r}")
        return self._defs[facility_id]

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    @property
    def facility_ids(self) -> list[str]:
        """Ordered list of all facility identifiers."""
        return list(self._defs.keys())

    def current_level(self, facility_id: str) -> int:
        """Current upgrade level (0 = not built yet)."""
        return self._levels.get(facility_id, 0)

    def max_level(self, facility_id: str) -> int:
        """Maximum upgrade level for this facility."""
        return self._def(facility_id)["max_level"]

    def is_maxed(self, facility_id: str) -> bool:
        """True if the facility is at maximum level."""
        return self.current_level(facility_id) >= self.max_level(facility_id)

    def upgrade_cost(self, facility_id: str) -> Optional[int]:
        """Return the currency cost for the next upgrade level, or None if maxed."""
        if self.is_maxed(facility_id):
            return None
        lvl = self.current_level(facility_id)
        return self._def(facility_id)["levels"][lvl]["cost"]

    def can_upgrade(self, facility_id: str, currency) -> bool:
        """True if the facility is not maxed and the player can afford the upgrade."""
        cost = self.upgrade_cost(facility_id)
        if cost is None:
            return False
        return currency.balance >= cost

    # ------------------------------------------------------------------
    # Public mutation API
    # ------------------------------------------------------------------

    def upgrade(self, facility_id: str, currency) -> bool:
        """Attempt to purchase the next upgrade level.

        Deducts the cost from *currency* and increments the level.

        Returns:
            True on success; False if maxed or insufficient funds.
        """
        cost = self.upgrade_cost(facility_id)
        if cost is None:
            return False
        if not currency.spend(cost):
            return False
        self._levels[facility_id] += 1
        return True

    # ------------------------------------------------------------------
    # Display data
    # ------------------------------------------------------------------

    def get_facility_display(self, facility_id: str) -> dict:
        """Return a display-ready dict for the given facility.

        Keys:
            id, name, level, max_level, cost (None if maxed),
            bonus_description (next level bonus text),
            current_bonus_description (current level bonus text or "Not built").
        """
        fdef = self._def(facility_id)
        lvl = self.current_level(facility_id)
        cost = self.upgrade_cost(facility_id)

        levels = fdef["levels"]
        next_desc = levels[lvl]["description"] if not self.is_maxed(facility_id) else "MAX"
        current_desc = levels[lvl - 1]["description"] if lvl > 0 else "Not built"

        return {
            "id": facility_id,
            "name": fdef["name"],
            "level": lvl,
            "max_level": fdef["max_level"],
            "cost": cost,
            "bonus_description": next_desc,
            "current_bonus_description": current_desc,
        }

    # ------------------------------------------------------------------
    # Round bonus aggregation
    # ------------------------------------------------------------------

    def get_round_bonuses(self) -> dict:
        """Compute aggregate per-round bonuses from all facility levels.

        Additive bonus types (extra_hp, extra_slots) are summed across all
        facilities at their current level. The loot_value_bonus uses the
        maximum value rather than summing to avoid aggressive compounding.

        Returns:
            dict with keys: "extra_hp" (int), "extra_slots" (int),
            "loot_value_bonus" (float).  All default to 0 / 0.0 when
            no upgrades are purchased.
        """
        bonuses: dict = {
            "extra_hp": 0,
            "extra_slots": 0,
            "loot_value_bonus": 0.0,
        }

        for fid in self.facility_ids:
            lvl = self.current_level(fid)
            if lvl == 0:
                continue
            # Level is 1-based index into the levels array
            level_data = self._def(fid)["levels"][lvl - 1]
            bonus_type = level_data["bonus_type"]
            bonus_value = level_data["bonus_value"]

            if bonus_type in ("extra_hp", "extra_slots"):
                bonuses[bonus_type] += bonus_value
            elif bonus_type == "loot_value_bonus":
                bonuses["loot_value_bonus"] = max(
                    bonuses["loot_value_bonus"], bonus_value
                )
            else:
                # Unknown bonus type — accumulate additively
                bonuses[bonus_type] = bonuses.get(bonus_type, 0) + bonus_value

        return bonuses

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def to_save_dict(self) -> dict:
        """Return a flat dict of facility_id → current_level for JSON saving."""
        return dict(self._levels)

    def from_save_dict(self, data: dict) -> None:
        """Restore facility levels from a save dict.

        Unknown keys are silently ignored.
        Levels are clamped to [0, max_level] to guard against corrupt saves.
        """
        for fid, lvl in data.items():
            if fid not in self._levels:
                continue  # ignore unknown facilities
            self._levels[fid] = max(0, min(int(lvl), self.max_level(fid)))
