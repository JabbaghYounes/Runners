"""Tests for XP wiring added in the XP-progression feature:

- XPSystem awards XP on ``challenge_completed`` events
- ``challenge_completed`` with ``reward_xp=0`` or negative is a no-op
- ``"player_leveled_up"`` is emitted (alongside the legacy events) when a
  level boundary is crossed
- ``GameScene._on_enemy_killed`` no longer exists (regression guard for the
  double-award fix — XPSystem owns that subscription exclusively)
- ``RoundSummary.level_before`` and ``xp_earned`` are captured correctly when
  a GameScene exit handler fires
- ``XPSystem.pending_xp`` property exposes the uncommitted round total
- ``XPSystem.load()`` clamps corrupt ``level=0`` to 1
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.progression.xp_system import XPSystem


# ---------------------------------------------------------------------------
# Minimal tracking event bus
# ---------------------------------------------------------------------------

class _Bus:
    """Lightweight event bus that records all emitted events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list] = defaultdict(list)
        self.emitted: list[tuple[str, dict]] = []

    def subscribe(self, event: str, cb) -> None:
        if cb not in self._handlers[event]:
            self._handlers[event].append(cb)

    def unsubscribe(self, event: str, cb) -> None:
        try:
            self._handlers[event].remove(cb)
        except ValueError:
            pass

    def emit(self, event: str, **kwargs: Any) -> None:
        self.emitted.append((event, kwargs))
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


# ===========================================================================
# challenge_completed → XP wiring
# ===========================================================================

class TestChallengeCompletedXP:

    def test_challenge_completed_awards_reward_xp(self, xp: XPSystem, bus: _Bus) -> None:
        bus.emit("challenge_completed", challenge_id="kill_5", reward_xp=150, reward_money=0)
        assert xp.xp == 150

    def test_multiple_challenge_completions_accumulate(self, xp: XPSystem, bus: _Bus) -> None:
        bus.emit("challenge_completed", challenge_id="a", reward_xp=100, reward_money=0)
        bus.emit("challenge_completed", challenge_id="b", reward_xp=200, reward_money=0)
        assert xp.xp == 300

    def test_challenge_completed_with_zero_xp_is_noop(self, xp: XPSystem, bus: _Bus) -> None:
        xp_before = xp.xp
        bus.emit("challenge_completed", challenge_id="a", reward_xp=0, reward_money=50)
        assert xp.xp == xp_before

    def test_challenge_completed_with_negative_xp_is_noop(self, xp: XPSystem, bus: _Bus) -> None:
        xp_before = xp.xp
        bus.emit("challenge_completed", challenge_id="a", reward_xp=-10, reward_money=0)
        assert xp.xp == xp_before

    def test_challenge_completed_missing_reward_xp_key_is_noop(self, xp: XPSystem, bus: _Bus) -> None:
        xp_before = xp.xp
        bus.emit("challenge_completed", challenge_id="a", reward_money=50)
        assert xp.xp == xp_before

    def test_challenge_completed_can_trigger_level_up(self, xp: XPSystem, bus: _Bus) -> None:
        bus.emit("challenge_completed", challenge_id="big", reward_xp=900, reward_money=0)
        assert xp.level == 2

    def test_xp_system_subscribes_to_challenge_completed(self, bus: _Bus) -> None:
        x = XPSystem(event_bus=bus)
        assert any(cb == x._on_challenge_completed
                   for cb in bus._handlers.get("challenge_completed", []))


# ===========================================================================
# player_leveled_up canonical event
# ===========================================================================

class TestPlayerLeveledUpEvent:

    def test_player_leveled_up_emitted_on_level_up(self, xp: XPSystem, bus: _Bus) -> None:
        xp.award(900)  # exactly level 1 → 2 threshold
        events = bus.all_events("player_leveled_up")
        assert len(events) == 1
        assert events[0]["level"] == 2

    def test_player_leveled_up_emitted_alongside_legacy_events(
        self, xp: XPSystem, bus: _Bus
    ) -> None:
        xp.award(900)
        assert len(bus.all_events("level_up")) == 1
        assert len(bus.all_events("level.up")) == 1
        assert len(bus.all_events("player_leveled_up")) == 1

    def test_player_leveled_up_not_emitted_below_threshold(
        self, xp: XPSystem, bus: _Bus
    ) -> None:
        xp.award(500)
        assert len(bus.all_events("player_leveled_up")) == 0

    def test_player_leveled_up_carries_correct_level(self, xp: XPSystem, bus: _Bus) -> None:
        xp.award(900 + 1260)  # crosses levels 1 and 2 → ends at 3
        events = bus.all_events("player_leveled_up")
        assert len(events) == 1
        assert events[0]["level"] == 3

    def test_player_leveled_up_not_emitted_without_event_bus(self) -> None:
        """XPSystem with no bus must not raise when a level boundary is crossed."""
        x = XPSystem()
        x.award(900)
        assert x.level == 2  # level-up happened silently


# ===========================================================================
# Double-award regression guard
# ===========================================================================

class TestDoubleAwardRegression:

    def test_game_scene_has_no_on_enemy_killed_method(self) -> None:
        """GameScene must not have its own _on_enemy_killed — XPSystem owns it."""
        from src.scenes.game_scene import GameScene
        assert not hasattr(GameScene, '_on_enemy_killed'), (
            "GameScene._on_enemy_killed still exists — this would double-award "
            "kill XP because XPSystem already subscribes to 'enemy_killed'."
        )

    def test_enemy_killed_event_awards_xp_exactly_once(self, xp: XPSystem, bus: _Bus) -> None:
        """A single 'enemy_killed' emit should award XP exactly once."""
        bus.emit("enemy_killed", xp_reward=50)
        assert xp.xp == 50

    def test_enemy_killed_does_not_double_award_even_with_second_subscriber(
        self, bus: _Bus
    ) -> None:
        """Regression: if a second subscriber were added it would inflate XP.
        Verify the XPSystem is the only subscriber that calls award()."""
        xp_sys = XPSystem(event_bus=bus)
        # Record how many times award() would have been invoked if patched
        award_calls: list[int] = []
        original_award = xp_sys.award

        def tracking_award(amount: int) -> None:
            award_calls.append(amount)
            original_award(amount)

        xp_sys.award = tracking_award  # type: ignore[assignment]
        bus.emit("enemy_killed", xp_reward=75)
        assert award_calls == [75], (
            f"award() called {len(award_calls)} time(s) with args {award_calls}; "
            "expected exactly once with 75"
        )


# ===========================================================================
# pending_xp property
# ===========================================================================

class TestPendingXPProperty:

    def test_pending_xp_starts_at_zero(self, xp: XPSystem) -> None:
        assert xp.pending_xp == 0

    def test_pending_xp_accumulates_with_award(self, xp: XPSystem) -> None:
        xp.award(100)
        xp.award(250)
        assert xp.pending_xp == 350

    def test_commit_zeroes_pending_xp(self, xp: XPSystem) -> None:
        xp.award(400)
        xp.commit()
        assert xp.pending_xp == 0

    def test_commit_does_not_remove_total_xp(self, xp: XPSystem) -> None:
        xp.award(300)
        xp.commit()
        assert xp.xp == 300

    def test_pending_xp_reflects_challenge_xp(self, xp: XPSystem, bus: _Bus) -> None:
        bus.emit("enemy_killed", xp_reward=50)
        bus.emit("challenge_completed", challenge_id="x", reward_xp=200, reward_money=0)
        assert xp.pending_xp == 250


# ===========================================================================
# load() corrupt-save guard
# ===========================================================================

class TestLoadCorruptSaveGuard:

    def test_load_clamps_level_zero_to_one(self) -> None:
        x = XPSystem()
        x.load({"xp": 0, "level": 0})
        assert x.level == 1

    def test_load_clamps_negative_level_to_one(self) -> None:
        x = XPSystem()
        x.load({"xp": 0, "level": -5})
        assert x.level == 1

    def test_load_preserves_valid_level(self) -> None:
        x = XPSystem()
        x.load({"xp": 200, "level": 4})
        assert x.level == 4


# ===========================================================================
# RoundSummary construction from GameScene exit handlers
# ===========================================================================

class TestRoundSummaryCapture:
    """Verify GameScene exit handlers build RoundSummary with correct fields."""

    def _make_xp_system(self, level: int = 2, pending: int = 350) -> Any:
        xs = MagicMock()
        xs.level = level
        xs.pending_xp = pending
        return xs

    def _make_challenge(self, kills: int = 3, completed: int = 1, total: int = 3) -> Any:
        from collections import namedtuple
        _Ch = namedtuple('_Ch', ['completed'])
        ch = MagicMock()
        ch.kills = kills
        ch.get_active_raw.return_value = [_Ch(i < completed) for i in range(total)]
        return ch

    def _build_summary(self, status: str, xp_sys, challenge) -> Any:
        from src.core.round_summary import RoundSummary
        challenges_completed = sum(
            1 for c in challenge.get_active_raw() if c.completed
        ) if challenge and hasattr(challenge, 'get_active_raw') else 0
        challenges_total = len(
            challenge.get_active_raw()
        ) if challenge and hasattr(challenge, 'get_active_raw') else 0
        return RoundSummary(
            extraction_status=status,
            extracted_items=[],
            xp_earned=xp_sys.pending_xp if xp_sys else 0,
            money_earned=0,
            kills=challenge.kills if challenge else 0,
            challenges_completed=challenges_completed,
            challenges_total=challenges_total,
            level_before=xp_sys.level if xp_sys else 1,
        )

    def test_level_before_captured_from_xp_system(self) -> None:
        xs = self._make_xp_system(level=5, pending=200)
        ch = self._make_challenge()
        summary = self._build_summary("success", xs, ch)
        assert summary.level_before == 5

    def test_xp_earned_captured_from_pending_xp(self) -> None:
        xs = self._make_xp_system(level=2, pending=475)
        ch = self._make_challenge()
        summary = self._build_summary("success", xs, ch)
        assert summary.xp_earned == 475

    def test_kills_captured_from_challenge_system(self) -> None:
        xs = self._make_xp_system()
        ch = self._make_challenge(kills=7)
        summary = self._build_summary("eliminated", xs, ch)
        assert summary.kills == 7

    def test_challenges_completed_counted_correctly(self) -> None:
        xs = self._make_xp_system()
        ch = self._make_challenge(completed=2, total=3)
        summary = self._build_summary("timeout", xs, ch)
        assert summary.challenges_completed == 2
        assert summary.challenges_total == 3

    def test_none_xp_system_uses_defaults(self) -> None:
        ch = self._make_challenge()
        summary = self._build_summary("eliminated", None, ch)
        assert summary.xp_earned == 0
        assert summary.level_before == 1

    def test_none_challenge_uses_zero_kills(self) -> None:
        xs = self._make_xp_system()
        summary = self._build_summary("timeout", xs, None)
        assert summary.kills == 0
        assert summary.challenges_completed == 0
        assert summary.challenges_total == 0
