from __future__ import annotations

from typing import Dict, Any


class XPSystem:
    """Tracks player XP and level, awards XP from game events.

    Subscribes to:
    - ``"enemy_killed"``      — awards ``xp_reward`` from the event payload
    - ``"player_killed"``     — awards ``PVP_KILL_XP`` when killer is player-controlled
    - ``"extraction_success"``— awards ``EXTRACTION_XP`` bonus
    - ``"challenge_completed"``— awards ``reward_xp`` from the challenge payload

    On level-up, emits:
    - ``"level_up"``          (legacy, HUD subscribes)
    - ``"level.up"``          (legacy alias)
    - ``"player_leveled_up"`` (canonical name for external systems)
    """

    def __init__(self, event_bus=None):
        self.xp: int = 0
        self.level: int = 1
        self._pending_xp: int = 0
        self._event_bus = event_bus

        if event_bus is not None:
            event_bus.subscribe("player_killed", self._on_player_killed)
            event_bus.subscribe("enemy_killed", self._on_enemy_killed)
            event_bus.subscribe("extraction_success", self._on_extraction_success)
            event_bus.subscribe("challenge_completed", self._on_challenge_completed)

    # ------------------------------------------------------------------
    # Read-only property
    # ------------------------------------------------------------------

    @property
    def pending_xp(self) -> int:
        """XP accumulated this round, not yet committed (zeroed by commit())."""
        return self._pending_xp

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

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

    def _on_challenge_completed(self, **kwargs: Any) -> None:
        """Award XP when a vendor challenge is completed."""
        reward_xp = kwargs.get("reward_xp", 0)
        if reward_xp <= 0:
            return
        self.award(reward_xp)

    # ------------------------------------------------------------------
    # Core award / level logic
    # ------------------------------------------------------------------

    def award(self, amount: int) -> None:
        """Add *amount* XP, recalculate level, and emit level-up events if needed."""
        self._pending_xp += amount
        self.xp += amount
        old_level = self.level
        self._recalculate_level()
        if self.level > old_level and self._event_bus is not None:
            self._event_bus.emit("level_up", level=self.level)
            self._event_bus.emit("level.up", level=self.level)
            self._event_bus.emit("player_leveled_up", level=self.level)

    def _recalculate_level(self) -> None:
        while self.xp >= self.xp_to_next_level():
            self.xp -= self.xp_to_next_level()
            self.level += 1

    def xp_to_next_level(self) -> int:
        from src.constants import XP_BASE, XP_SCALE
        return int(XP_BASE * (XP_SCALE ** (self.level - 1)))

    def commit(self) -> None:
        """Zero pending XP, finalising the round's awards without re-awarding."""
        self._pending_xp = 0

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self, data: Dict[str, Any]) -> None:
        self.xp = data.get('xp', 0)
        self.level = data.get('level', 1)
        # Guard against corrupt save data (level=0 would cause infinite loop)
        self.level = max(1, self.level)

    def to_save_dict(self) -> Dict[str, Any]:
        return {'xp': self.xp, 'level': self.level}
