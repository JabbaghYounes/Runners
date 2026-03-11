from typing import Dict, Any

class XPSystem:
    BASE_XP = 900
    SCALE = 1.4

    def __init__(self):
        self.xp: int = 0
        self.level: int = 1
        self._pending_xp: int = 0

    def award(self, amount: int) -> None:
        self._pending_xp += amount
        self.xp += amount
        self._recalculate_level()

    def _recalculate_level(self) -> None:
        while self.xp >= self.xp_to_next_level():
            self.xp -= self.xp_to_next_level()
            self.level += 1

    def xp_to_next_level(self) -> int:
        return int(self.BASE_XP * (self.SCALE ** (self.level - 1)))

    def commit(self) -> None:
        self._pending_xp = 0

    def load(self, data: Dict[str, Any]) -> None:
        self.xp = data.get('xp', 0)
        self.level = data.get('level', 1)

    def to_save_dict(self) -> Dict[str, Any]:
        return {'xp': self.xp, 'level': self.level}
