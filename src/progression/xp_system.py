"""XP and levelling system."""
from __future__ import annotations


# XP thresholds per level (index = level-1, value = total XP needed)
_XP_TABLE = [
    0, 100, 250, 500, 900, 1400, 2100, 3000, 4200, 5800,
]


class XPSystem:
    """Tracks player XP and level.

    Attributes:
        xp: Total accumulated XP.
        level: Current player level (1-based).
    """

    def __init__(self) -> None:
        self.xp: int = 0
        self.level: int = 1

    def award(self, amount: int) -> None:
        """Add *amount* XP and advance level if threshold crossed."""
        if amount <= 0:
            return
        self.xp += amount
        self._recalculate_level()

    def _recalculate_level(self) -> None:
        for lvl, threshold in enumerate(_XP_TABLE, start=1):
            if self.xp < threshold:
                self.level = max(1, lvl - 1)
                return
        self.level = len(_XP_TABLE)

    def xp_to_next_level(self) -> int:
        """Return XP needed to reach the next level, or 0 if maxed."""
        idx = self.level  # next level index in table (0-based)
        if idx >= len(_XP_TABLE):
            return 0
        return max(0, _XP_TABLE[idx] - self.xp)

    def commit(self) -> None:
        """Finalise XP at end of round (no-op; level already updated live)."""

    def load(self, data: dict) -> None:
        """Restore state from a save dict like {'level': 3, 'xp': 500}."""
        self.xp = int(data.get("xp", 0))
        self.level = int(data.get("level", 1))
        self._recalculate_level()

    def to_save_dict(self) -> dict:
        return {"level": self.level, "xp": self.xp}
