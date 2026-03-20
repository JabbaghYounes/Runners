"""Unit and integration tests for GameScene XP wiring.

Covers:
- _build_hud_state() correctly reads level, xp, and xp_to_next from an
  attached XPSystem (and uses safe defaults when XPSystem is None)
- _challenge_counts() delegates to ChallengeSystem.get_active_raw() safely
  and returns (0, 0) when no challenge system is attached
- HUDState XP fields update after an enemy_killed event flows through
  a live XPSystem attached to the scene

Run: pytest tests/scenes/test_game_scene_xp.py
"""
from __future__ import annotations

from collections import namedtuple
from unittest.mock import MagicMock

import pytest

from src.core.event_bus import EventBus
from src.progression.xp_system import XPSystem
from src.ui.hud_state import HUDState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def scene(bus: EventBus):
    """Stub-mode GameScene (no map, no systems) with a live EventBus."""
    from src.scenes.game_scene import GameScene
    return GameScene(event_bus=bus)


# ---------------------------------------------------------------------------
# Helper: named tuple that mimics _ActiveChallenge for _challenge_counts()
# ---------------------------------------------------------------------------

_Ch = namedtuple("_Ch", ["completed"])


# ===========================================================================
# Unit: GameScene._build_hud_state() — XP fields
# ===========================================================================

class TestBuildHUDStateXPFields:
    """_build_hud_state() reads XP data from the attached XPSystem.

    When _xp_system is None the method returns safe defaults so the HUD
    never crashes in tests or stub-mode scenes.
    """

    def test_level_defaults_to_1_when_no_xp_system(self, scene) -> None:
        scene._xp_system = None
        state = scene._build_hud_state()
        assert state.level == 1

    def test_level_reads_from_xp_system_level_attribute(self, scene) -> None:
        mock_xp = MagicMock()
        mock_xp.level = 7
        mock_xp.xp = 300
        mock_xp.xp_to_next_level.return_value = 1764
        scene._xp_system = mock_xp
        state = scene._build_hud_state()
        assert state.level == 7

    def test_xp_defaults_to_0_when_no_xp_system(self, scene) -> None:
        scene._xp_system = None
        state = scene._build_hud_state()
        assert state.xp == 0

    def test_xp_reads_from_xp_system_xp_attribute(self, scene) -> None:
        mock_xp = MagicMock()
        mock_xp.level = 2
        mock_xp.xp = 450
        mock_xp.xp_to_next_level.return_value = 1260
        scene._xp_system = mock_xp
        state = scene._build_hud_state()
        assert state.xp == 450

    def test_xp_to_next_defaults_to_100_when_no_xp_system(self, scene) -> None:
        scene._xp_system = None
        state = scene._build_hud_state()
        assert state.xp_to_next == 100

    def test_xp_to_next_reads_from_xp_system_xp_to_next_level_call(
        self, scene
    ) -> None:
        mock_xp = MagicMock()
        mock_xp.level = 3
        mock_xp.xp = 0
        mock_xp.xp_to_next_level.return_value = 1764
        scene._xp_system = mock_xp
        state = scene._build_hud_state()
        assert state.xp_to_next == 1764

    def test_xp_to_next_is_positive_with_real_xp_system(self, bus) -> None:
        """xp_to_next is always positive — HUD progress bar must never divide by 0."""
        from src.scenes.game_scene import GameScene
        xp = XPSystem(event_bus=bus)
        s = GameScene(event_bus=bus, xp_system=xp)
        state = s._build_hud_state()
        assert state.xp_to_next > 0

    def test_hud_state_level_reflects_xp_system_after_level_up(
        self, bus: EventBus
    ) -> None:
        """Integration: HUDState.level updates after XPSystem levels up."""
        from src.scenes.game_scene import GameScene
        xp = XPSystem(event_bus=bus)
        s = GameScene(event_bus=bus, xp_system=xp)

        assert s._build_hud_state().level == 1

        xp.award(900)   # level 1 → 2

        assert s._build_hud_state().level == 2


# ===========================================================================
# Unit: GameScene._challenge_counts() — safe delegation
# ===========================================================================

class TestChallengeCounts:
    """_challenge_counts() returns (completed, total) and handles None safely."""

    def test_returns_zero_zero_when_no_challenge_system(self, scene) -> None:
        scene._challenge = None
        completed, total = scene._challenge_counts()
        assert completed == 0
        assert total == 0

    def test_completed_count_is_correct(self, scene) -> None:
        mock_ch = MagicMock()
        mock_ch.get_active_raw.return_value = [
            _Ch(True), _Ch(False), _Ch(True),
        ]
        scene._challenge = mock_ch
        completed, total = scene._challenge_counts()
        assert completed == 2

    def test_total_count_equals_number_of_active_challenges(self, scene) -> None:
        mock_ch = MagicMock()
        mock_ch.get_active_raw.return_value = [
            _Ch(True), _Ch(False), _Ch(False),
        ]
        scene._challenge = mock_ch
        completed, total = scene._challenge_counts()
        assert total == 3

    def test_returns_zero_completed_when_none_are_done(self, scene) -> None:
        mock_ch = MagicMock()
        mock_ch.get_active_raw.return_value = [
            _Ch(False), _Ch(False), _Ch(False),
        ]
        scene._challenge = mock_ch
        completed, total = scene._challenge_counts()
        assert completed == 0
        assert total == 3

    def test_returns_all_completed_when_every_challenge_is_done(
        self, scene
    ) -> None:
        mock_ch = MagicMock()
        mock_ch.get_active_raw.return_value = [
            _Ch(True), _Ch(True), _Ch(True),
        ]
        scene._challenge = mock_ch
        completed, total = scene._challenge_counts()
        assert completed == 3
        assert total == 3


# ===========================================================================
# Integration: live XPSystem attached to GameScene — HUDState reflects events
# ===========================================================================

class TestGameSceneXPLiveIntegration:
    """GameScene with a real XPSystem: verify HUDState XP values after events."""

    def test_hud_state_xp_increases_after_enemy_killed_event(
        self, bus: EventBus
    ) -> None:
        from src.scenes.game_scene import GameScene
        xp = XPSystem(event_bus=bus)
        s = GameScene(event_bus=bus, xp_system=xp)

        assert s._build_hud_state().xp == 0

        bus.emit("enemy_killed", xp_reward=100, enemy=None, x=0, y=0)

        assert s._build_hud_state().xp == 100

    def test_hud_state_xp_to_next_matches_xp_system_curve(
        self, bus: EventBus
    ) -> None:
        """xp_to_next in HUDState equals XPSystem.xp_to_next_level() output."""
        from src.scenes.game_scene import GameScene
        xp = XPSystem(event_bus=bus)
        s = GameScene(event_bus=bus, xp_system=xp)
        state = s._build_hud_state()
        # Level 1: int(900 * 1.4 ** 0) = 900
        assert state.xp_to_next == xp.xp_to_next_level()

    def test_hud_state_xp_to_next_updates_after_level_up(
        self, bus: EventBus
    ) -> None:
        """xp_to_next in HUDState increases at higher levels (the XP curve scales)."""
        from src.scenes.game_scene import GameScene
        xp = XPSystem(event_bus=bus)
        s = GameScene(event_bus=bus, xp_system=xp)

        xp_to_next_lv1 = s._build_hud_state().xp_to_next

        xp.award(900)   # level up to 2

        xp_to_next_lv2 = s._build_hud_state().xp_to_next

        # Level 2 requires more XP than level 1 (scaled curve)
        assert xp_to_next_lv2 > xp_to_next_lv1

    def test_pending_xp_matches_total_kill_xp_before_commit(
        self, bus: EventBus
    ) -> None:
        """pending_xp tracks all XP earned this round for RoundSummary capture."""
        from src.scenes.game_scene import GameScene
        xp = XPSystem(event_bus=bus)
        s = GameScene(event_bus=bus, xp_system=xp)

        bus.emit("enemy_killed", xp_reward=50, enemy=None, x=0, y=0)
        bus.emit("enemy_killed", xp_reward=75, enemy=None, x=0, y=0)

        assert s._xp_system.pending_xp == 125
