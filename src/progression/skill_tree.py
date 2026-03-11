import json
from typing import Dict, List, Any, Set

class SkillTree:
    def __init__(self):
        self._nodes: Dict[str, dict] = {}
        self._unlocked: Set[str] = set()

    def load(self, path: str) -> None:
        with open(path, 'r') as f:
            data = json.load(f)
        for node in data.get('nodes', []):
            self._nodes[node['id']] = node

    def can_unlock(self, node_id: str) -> bool:
        node = self._nodes.get(node_id)
        if node is None:
            return False
        return all(req in self._unlocked for req in node.get('requires', []))

    def unlock(self, node_id: str) -> bool:
        if node_id in self._unlocked or not self.can_unlock(node_id):
            return False
        self._unlocked.add(node_id)
        return True

    def get_stat_bonuses(self) -> Dict[str, float]:
        bonuses: Dict[str, float] = {}
        for node_id in self._unlocked:
            node = self._nodes.get(node_id, {})
            for k, v in node.get('stat_bonus', {}).items():
                bonuses[k] = bonuses.get(k, 0.0) + v
        return bonuses

    def load_state(self, data: dict) -> None:
        self._unlocked = set(data.get('unlocked', []))

    def to_save_dict(self) -> dict:
        return {'unlocked': list(self._unlocked)}
