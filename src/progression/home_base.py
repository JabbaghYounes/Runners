import json
from typing import Dict, Any, List

class HomeBase:
    def __init__(self):
        self._facilities: Dict[str, dict] = {}

    def load(self, path: str) -> None:
        with open(path, 'r') as f:
            data = json.load(f)
        for fac in data.get('facilities', []):
            self._facilities[fac['id']] = dict(fac)

    def upgrade(self, facility_id: str, currency: Any) -> bool:
        fac = self._facilities.get(facility_id)
        if not fac:
            return False
        level = fac.get('level', 0)
        costs = fac.get('upgrade_cost', [])
        if level >= len(costs):
            return False
        cost = costs[level]
        if not currency.spend(cost):
            return False
        fac['level'] = level + 1
        return True

    def get_round_bonuses(self) -> Dict[str, float]:
        bonuses: Dict[str, float] = {}
        for fac in self._facilities.values():
            level = fac.get('level', 0)
            if level == 0:
                continue
            bpl = fac.get('bonus_per_level', {})
            for k, v in bpl.items():
                bonuses[k] = bonuses.get(k, 0.0) + v * level
        return bonuses

    def get_facilities(self) -> List[dict]:
        return list(self._facilities.values())

    def load_state(self, data: dict) -> None:
        for fac_id, state in data.get('facilities', {}).items():
            if fac_id in self._facilities:
                self._facilities[fac_id].update(state)

    def to_save_dict(self) -> dict:
        return {'facilities': {fid: {'level': f.get('level', 0)}
                               for fid, f in self._facilities.items()}}
