"""Integration and E2E tests for the XP award event pipeline.

Covers the wiring introduced by the XP-progression feature:
- ChallengeSystem completing a challenge → emits 'challenge_completed'
  → XPSystem._on_challenge_completed awards reward_xp
- Kill-type and loot-type challenges both route XP to XPSystem
- Challenge completion can cross a level threshold (triggers level-up events)
- Both 'level_up' (HUD) and 'player_leveled_up' (canonical) are emitted on level-up
- XPSystem._on_player_killed awards PVP_KILL_XP only to a player-controlled killer
- E2E: kill → challenge completes → level up → HUD banner timer set

Run: pytest tests/systems/test_challenge_xp_integration.py
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import pytest

from src.progression.xp_system import XPSystem
from src.systems.challenge_system import ChallengeSystem
from src.constants import PVP_KILL_XP


# ---------------------------------------------------------------------------
# Minimal tracking event bus (synchronous, records all emitted events)
# ---------------------------------------------------------------------------

class _Bus:
    """Lightweight synchronous event bus that supports nested emits."""

    def __init__(self) -> None:
        self._handlers: dict[str, list] = defaultdict(list)
        self.emitted: list[tuple[str, dict]] = []

    def subscribe(self, event: str, cb: Any) -> None:
        if cb not in self._handlers[event]:
            self._handlers[event].append(cb)

    def unsubscribe(self, event: str, cb: Any) -> None:
        try:
            self._handlers[event].remove(cb)
        except ValueError:
            pass

    def emit(self, event: str, **kwargs: Any) -> None:
        self.emitted.append((event, kwargs))
        # Snapshot handlers so nested emits do not corrupt iteration
        for cb in list(self._handlers[event]):
            cb(**kwargs)

    def all_events(self, name: str) -> list[dict]:
        return [p for e, p in self.emitted if e == name]


@pytest.fixture
def bus() -> _Bus:
    return _Bus()


@pytest.fixture
def xp(bus: _Bus) -> XPSystem:
    return XPSystem(event_bus=bus)


# ---------------------------------------------------------------------------
# Reusable challenge pool definitions
# ---------------------------------------------------------------------------

_KILL_3 = {
    "id": "kill_3",
    "description": "Eliminate 3 enemies",
    "criteria_type": "enemy_killed",
    "target": 3,
    "zone_filter": None,
    "reward_xp": 150,
    "reward_money": 100,
}

_LOOT_5 = {
    "id": "loot_5",
    "description": "Pick up 5 items",
    "criteria_type": "item_picked_up",
    "target": 5,
    "zone_filter": None,
    "reward_xp": 200,
    "reward_money": 50,
}

_LEVEL_UP = {
    "id": "level_up_reward",
    "description": "Complete one kill for a full level's worth of XP",
    "criteria_type": "enemy_killed",
    "target": 1,
    "zone_filter": None,
    "reward_xp": 900,   # exactly the level-1 → level-2 threshold (XP_BASE = 900)
    "reward_money": 0,
}

_ZERO_XP = {
    "id": "no_xp",
    "description": "Challenge that grants no XP",
    "criteria_type": "enemy_killed",
    "target": 1,
    "zone_filter": None,
    "reward_xp": 0,
    "reward_money": 500,
}


def _make_challenge(bus: _Bus, pool: list) -> ChallengeSystem:
    """Instantiate a ChallengeSystem with a deterministic test pool."""
    cs = ChallengeSystem(bus, rng_seed=42)
    cs.load_pool_from_list(pool)
    return cs


# ===========================================================================
# Integration: ChallengeSystem → EventBus → XPSystem XP awards
# ===========================================================================

class TestChallengeSystemXPWiring:
    """Real ChallengeSystem and real XPSystem share one bus; verify XP flow."""

    def test_kill_challenge_awards_reward_xp_on_completion(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """Completing a kill-type challenge via 3 enemy_killed events awards XP."""
        _make_challenge(bus, [_KILL_3])
        for _ in range(3):
            bus.emit("enemy_killed", xp_reward=0, enemy=None, x=0, y=0)
        assert xp.xp == _KILL_3["reward_xp"]

    def test_loot_challenge_awards_reward_xp_on_completion(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """Completing an item-pickup challenge awards XP."""
        _make_challenge(bus, [_LOOT_5])
        for _ in range(5):
            bus.emit("item_picked_up", item=None, x=0, y=0)
        assert xp.xp == _LOOT_5["reward_xp"]

    def test_challenge_xp_accumulates_with_per_kill_xp(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """Both per-kill XP and challenge-completion XP are added together."""
        _make_challenge(bus, [_KILL_3])
        per_kill = 25
        for _ in range(3):
            bus.emit("enemy_killed", xp_reward=per_kill, enemy=None, x=0, y=0)
        expected = 3 * per_kill + _KILL_3["reward_xp"]
        assert xp.xp == expected

    def test_challenge_completion_emits_challenge_completed_event(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """ChallengeSystem emits 'challenge_completed' with the correct payload."""
        _make_challenge(bus, [_KILL_3])
        for _ in range(3):
            bus.emit("enemy_killed", xp_reward=0, enemy=None, x=0, y=0)
        events = bus.all_events("challenge_completed")
        assert len(events) == 1
        assert events[0]["challenge_id"] == "kill_3"
        assert events[0]["reward_xp"] == _KILL_3["reward_xp"]

    def test_challenge_xp_crosses_level_threshold(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """A 900-XP challenge reward advances level 1 → 2."""
        _make_challenge(bus, [_LEVEL_UP])
        assert xp.level == 1
        bus.emit("enemy_killed", xp_reward=0, enemy=None, x=0, y=0)
        assert xp.level == 2

    def test_challenge_level_up_emits_player_leveled_up_event(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """Level-up triggered by challenge emits the canonical 'player_leveled_up'."""
        _make_challenge(bus, [_LEVEL_UP])
        bus.emit("enemy_killed", xp_reward=0, enemy=None, x=0, y=0)
        events = bus.all_events("player_leveled_up")
        assert len(events) == 1
        assert events[0]["level"] == 2

    def test_challenge_level_up_emits_both_legacy_and_canonical_events(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """All three level-up event names are emitted so both old and new subscribers fire."""
        _make_challenge(bus, [_LEVEL_UP])
        bus.emit("enemy_killed", xp_reward=0, enemy=None, x=0, y=0)
        assert len(bus.all_events("level_up")) == 1
        assert len(bus.all_events("level.up")) == 1
        assert len(bus.all_events("player_leveled_up")) == 1

    def test_challenge_with_zero_xp_reward_does_not_change_xp(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """XPSystem's guard skips award when reward_xp <= 0 — no XP change."""
        _make_challenge(bus, [_ZERO_XP])
        xp_before = xp.xp
        bus.emit("enemy_killed", xp_reward=0, enemy=None, x=0, y=0)
        # Challenge completes but reward_xp=0 → XPSystem returns early
        assert xp.xp == xp_before

    def test_challenge_xp_is_included_in_pending_xp(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """Challenge reward XP accumulates in pending_xp for end-of-round capture."""
        _make_challenge(bus, [_KILL_3])
        for _ in range(3):
            bus.emit("enemy_killed", xp_reward=0, enemy=None, x=0, y=0)
        assert xp.pending_xp == _KILL_3["reward_xp"]

    def test_multiple_challenge_types_accumulate_xp_independently(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """Kill and loot challenges each award their own XP; both are summed."""
        _make_challenge(bus, [_KILL_3, _LOOT_5])  # 2 active (min(3, 2) = 2)
        for _ in range(3):
            bus.emit("enemy_killed", xp_reward=0, enemy=None, x=0, y=0)
        for _ in range(5):
            bus.emit("item_picked_up", item=None, x=0, y=0)
        expected = _KILL_3["reward_xp"] + _LOOT_5["reward_xp"]
        assert xp.xp == expected


# ===========================================================================
# Unit: XPSystem._on_player_killed — PvP kill XP
# ===========================================================================

class TestPvPKillXP:
    """XPSystem awards PVP_KILL_XP only when the killer is player-controlled."""

    class _PlayerKiller:
        is_player_controlled = True

    class _AIKiller:
        is_player_controlled = False

    def test_player_controlled_killer_awards_pvp_kill_xp(
        self, xp: XPSystem, bus: _Bus
    ) -> None:
        bus.emit("player_killed", killer=self._PlayerKiller(), victim=None)
        assert xp.xp == PVP_KILL_XP

    def test_non_player_killer_awards_nothing(
        self, xp: XPSystem, bus: _Bus
    ) -> None:
        xp_before = xp.xp
        bus.emit("player_killed", killer=self._AIKiller(), victim=None)
        assert xp.xp == xp_before

    def test_no_killer_field_awards_nothing(
        self, xp: XPSystem, bus: _Bus
    ) -> None:
        xp_before = xp.xp
        bus.emit("player_killed", victim=None)   # no 'killer' kwarg
        assert xp.xp == xp_before

    def test_multiple_pvp_kills_accumulate_xp(
        self, xp: XPSystem, bus: _Bus
    ) -> None:
        for _ in range(3):
            bus.emit("player_killed", killer=self._PlayerKiller(), victim=None)
        assert xp.xp == 3 * PVP_KILL_XP

    def test_pvp_kill_xp_constant_is_positive(self) -> None:
        assert PVP_KILL_XP > 0


# ===========================================================================
# End-to-end: kill → challenge completes → level up → HUD banner set
# ===========================================================================

class TestChallengeXPEndToEnd:

    def test_kill_challenge_completion_triggers_hud_level_up_banner(
        self, bus: _Bus, pygame_init
    ) -> None:
        """E2E: enemy_killed → ChallengeSystem completes → 900 XP awarded
        → XPSystem levels up → emits 'level_up' → HUD banner timer is set.

        This exercises the full synchronous chain across three systems sharing
        one event bus with no mocks involved.
        """
        from src.ui.hud import HUD

        xp = XPSystem(event_bus=bus)
        hud = HUD(bus)
        _make_challenge(bus, [_LEVEL_UP])

        assert hud._levelup_banner_timer == pytest.approx(0.0)

        # One kill: challenge completes, 900 XP awarded, level 1 → 2, HUD notified
        bus.emit("enemy_killed", xp_reward=0, enemy=None, x=0, y=0)

        assert xp.level == 2
        assert hud._levelup_banner_timer > 0.0

    def test_full_round_earn_then_commit_preserves_xp(
        self, bus: _Bus, xp: XPSystem
    ) -> None:
        """E2E: earn XP via kills and a challenge, then commit at round end.

        After commit():
        - pending_xp is zeroed  (round finalised)
        - total xp is unchanged (not re-applied or lost)
        - level is unchanged    (commit() has no side-effects on level)
        """
        _make_challenge(bus, [_KILL_3])

        # 3 kills: 50 XP each + 150 challenge reward = 300 XP total
        for _ in range(3):
            bus.emit("enemy_killed", xp_reward=50, enemy=None, x=0, y=0)

        expected_total = 3 * 50 + _KILL_3["reward_xp"]
        assert xp.pending_xp == expected_total
        assert xp.xp == expected_total

        level_before = xp.level
        total_before = xp.xp

        xp.commit()

        assert xp.pending_xp == 0
        assert xp.xp == total_before   # XP not lost
        assert xp.level == level_before  # commit() does not alter level
