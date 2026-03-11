import json
import os
from typing import Dict, Any, List, Optional

class EnemyDatabase:
    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}

    def load(self, path: str) -> None:
        with open(path, 'r') as f:
            self._data = json.load(f)

    def create(self, type_id: str):
        from src.entities.robot_enemy import RobotEnemy
        data = self._data.get(type_id)
        if data is None:
            data = self._data.get('grunt', {})
        enemy = RobotEnemy(0, 0, type_id=type_id)
        enemy.hp = data.get('hp', 60)
        enemy.max_hp = enemy.hp
        enemy.speed = float(data.get('speed', 80))
        enemy.aggro_range = float(data.get('aggro_range', 200))
        enemy.attack_range = float(data.get('attack_range', 60))
        enemy.attack_damage = data.get('damage', 10)
        enemy.xp_reward = data.get('xp_reward', 50)
        enemy.loot_table = data.get('loot_table', [])
        return enemy

    def get_loot_table(self, type_id: str) -> List[Dict[str, Any]]:
        return self._data.get(type_id, {}).get('loot_table', [])

    @property
    def type_ids(self) -> List[str]:
        return list(self._data.keys())
