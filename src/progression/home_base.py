"""Home base hub — upgradeable facility system.

Design notes:
- Facility definitions are loaded from a JSON file; no hard-coding.
- Levels start at 0 (not built).
- `get_round_bonuses` aggregates additive stat bonuses from all facilities.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional


class HomeBase:
    def __init__(self, definitions_path: Optional[str] = None) -> None:
        self._defs: dict[str, dict] = {}
        self._levels: dict[str, int] = {}
        self._load_definitions(definitions_path)

    def _load_definitions(self, path: Optional[str]) -> None:
        """Load facility definitions from JSON and initialise all levels to 0."""
        if path is None:
            return
        try:
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
            for facility in data.get('facilities', []):
                fid = facility['id']
                self._defs[fid] = facility
                self._levels[fid] = 0
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            pass

    def _def(self, facility_id: str) -> dict:
        if facility_id not in self._defs:
            raise KeyError(f'Unknown facility: {facility_id}')
        return self._defs[facility_id]

    def facility_ids(self) -> list[str]:
        """Ordered list of all facility identifiers."""
        return list(self._defs.keys())

    def current_level(self, facility_id: str) -> int:
        """Current upgrade level (0 = not built yet)."""
        return self._levels.get(facility_id, 0)

    def max_level(self, facility_id: str) -> int:
        """Maximum upgrade level for this facility."""
        return self._def(facility_id).get('max_level', 5)

    def is_maxed(self, facility_id: str) -> bool:
        """True if the facility is at maximum level."""
        return self.current_level(facility_id) >= self.max_level(facility_id)

    def upgrade_cost(self, facility_id: str) -> Optional[int]:
        """Return the currency cost for the next upgrade level, or None if maxed."""
        if self.is_maxed(facility_id):
            return None
        lvl = self.current_level(facility_id)
        levels = self._def(facility_id).get('levels', [])
        if lvl < len(levels):
            return levels[lvl].get('cost', 0)
        return None

    def can_upgrade(self, facility_id: str, currency: object) -> bool:
        """True if the facility is not maxed and the player can afford the upgrade."""
        cost = self.upgrade_cost(facility_id)
        if cost is None:
            return False
        return currency.balance >= cost

    def upgrade(self, facility_id: str, currency: object) -> None:
        """Attempt to purchase the next upgrade level.

        Deducts the cost from *currency* and increments the level.
        """
        cost = self.upgrade_cost(facility_id)
        if cost is None:
            return
        currency.spend(cost)
        self._levels[facility_id] = self.current_level(facility_id) + 1

    def get_facility_display(self, facility_id: str) -> dict:
        """Return a display-ready dict for the given facility.

        Keys: id, name, level, max_level, cost (None if maxed), description
        """
        fdef = self._def(facility_id)
        lvl = self.current_level(facility_id)
        cost = self.upgrade_cost(facility_id)
        levels = fdef.get('levels', [])
        next_desc = levels[lvl].get('description', 'MAX') if lvl < len(levels) else 'MAX'
        current_desc = levels[lvl - 1].get('description', 'Not built') if lvl > 0 else 'Not built'
        return {
            'id': facility_id,
            'name': fdef.get('name', facility_id),
            'level': lvl,
            'max_level': fdef.get('max_level', 5),
            'cost': cost,
            'description': next_desc,
            'current_description': current_desc,
        }

    def get_round_bonuses(self) -> dict[str, float]:
        """Compute aggregate per-round bonuses from all facility levels.

        Additive bonus types (extra_hp, extra_slots) are summed.
        """
        bonuses: dict[str, float] = {}
        for fid in self.facility_ids():
            lvl = self.current_level(fid)
            if lvl <= 0:
                continue
            fdef = self._def(fid)
            levels = fdef.get('levels', [])
            level_data = levels[min(lvl - 1, len(levels) - 1)] if levels else {}
            bonus_type = level_data.get('bonus_type')
            bonus_value = level_data.get('bonus_value', 0)
            if bonus_type:
                bonuses[bonus_type] = bonuses.get(bonus_type, 0) + bonus_value
        return bonuses

    def to_save_dict(self) -> dict[str, int]:
        """Return a flat dict of facility_id → current_level for JSON saving."""
        return dict(self._levels)

    def from_save_dict(self, data: dict) -> None:
        """Restore facility levels from a save dict.

        Unknown keys are silently ignored.
        Levels are clamped to [0, max_level].
        """
        for fid, lvl in data.items():
            if fid in self._levels:
                self._levels[fid] = max(0, min(int(lvl), self.max_level(fid)))
