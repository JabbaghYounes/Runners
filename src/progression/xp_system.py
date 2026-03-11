"""XP and levelling system."""
from __future__ import annotations

# XP required to reach each level threshold (index = level - 1)
_XP_TABLE: list[int] = [
    0,     # level 1  (starting)
    100,   # level 2
    250,   # level 3
    500,   # level 4
    900,   # level 5
    1400,  # level 6
    2100,  # level 7
    3000,  # level 8
    4200,  # level 9
    6000,  # level 10
]


class XPSystem:
    """Tracks XP and current level for the player."""

    def __init__(self) -> None:
        self.xp: int = 0
        self.level: int = 1

    def award(self, amount: int) -> None:
        """Add *amount* XP and advance level if threshold crossed."""
        self.xp += max(0, amount)
        self._recalculate_level()

    def _recalculate_level(self) -> None:
        lvl = 1
        for threshold in _XP_TABLE:
            if self.xp >= threshold:
                lvl = _XP_TABLE.index(threshold) + 1
            else:
                break
        self.level = max(self.level, lvl)

    def xp_to_next_level(self) -> int:
        """Return XP needed to reach the next level, or 0 if maxed."""
        idx = self.level  # next level index in table
        if idx >= len(_XP_TABLE):
            return 0
        return max(0, _XP_TABLE[idx] - self.xp)

    def commit(self) -> None:
        """Finalise XP at end of round (no-op; level already updated live)."""

    def load(self, data: dict) -> None:
        """Restore state from a save dict like {'level': 3, 'xp': 500}."""
        self.level = int(data.get('level', 1))
        self.xp = int(data.get('xp', 0))
        self._recalculate_level()

    def to_save_dict(self) -> dict:
        return {'level': self.level, 'xp': self.xp}
