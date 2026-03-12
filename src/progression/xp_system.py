from typing import Dict, Any

class XPSystem:
    BASE_XP = 900
    SCALE = 1.4

    def __init__(self, event_bus=None):
        self.xp: int = 0
        self.level: int = 1
        self._pending_xp: int = 0
        self._event_bus = event_bus

        if event_bus is not None:
            event_bus.subscribe("player_killed", self._on_player_killed)
            event_bus.subscribe("enemy_killed", self._on_enemy_killed)
            event_bus.subscribe("extraction_success", self._on_extraction_success)

    def _on_player_killed(self, **kwargs: Any) -> None:
        """Award PVP_KILL_XP when the killer is the human player."""
        killer = kwargs.get("killer")
        if killer is None:
            return
        # Only award XP when the killer is player-controlled
        if getattr(killer, "is_player_controlled", False):
            from src.constants import PVP_KILL_XP
            self.award(PVP_KILL_XP)

    def _on_enemy_killed(self, **kwargs: Any) -> None:
        """Award XP based on the enemy's xp_reward when a PvE enemy is killed."""
        xp = kwargs.get("xp_reward", 0)
        if xp:
            self.award(xp)

    def _on_extraction_success(self, **kwargs: Any) -> None:
        """Award bonus XP for a successful extraction."""
        from src.constants import EXTRACTION_XP
        self.award(EXTRACTION_XP)

    def award(self, amount: int) -> None:
        self._pending_xp += amount
        self.xp += amount
        old_level = self.level
        self._recalculate_level()
        if self.level > old_level and self._event_bus is not None:
            self._event_bus.emit("level_up", level=self.level)
            self._event_bus.emit("level.up", level=self.level)

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
