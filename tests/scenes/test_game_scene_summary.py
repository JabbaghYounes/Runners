"""Tests for GameScene kill tracking and round-summary building.

Covers:
  * _round_kills and _round_kill_xp accumulation via _on_enemy_killed()
  * _build_summary("success"): EXTRACTION_XP bonus, kill XP, inventory items,
    loot_value_bonus, level_before snapshot
  * _build_summary("timeout") and ("eliminated"): all stats zeroed out
  * _on_player_dead() idempotency guard (_dead_handled flag)
  * Integration: _on_extract / _on_extract_failed / _on_player_dead each call
    sm.replace() with the correct PostRound containing the right summary type

# Run: pytest tests/scenes/test_game_scene_summary.py
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.core.event_bus import EventBus
from src.core.round_summary import RoundSummary
from src.scenes.game_scene import GameScene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeXPSystem:
    """Minimal stand-in for XPSystem used in summary-building tests."""

    def __init__(self, level: int = 1, xp: int = 0) -> None:
        self.level = level
        self.xp = xp

    def award(self, amount: int) -> None:
        self.xp += amount

    def xp_to_next_level(self) -> int:
        return 900


class _FakeInventoryItem:
    """Item stand-in with monetary_value and value attributes."""

    def __init__(self, name: str, monetary_value: int) -> None:
        self.name = name
        self.monetary_value = monetary_value
        self.value = monetary_value


class _FakeInventory:
    """Inventory stand-in with a get_items() method."""

    def __init__(self, items: list) -> None:
        self._items = items

    def get_items(self) -> list:
        return list(self._items)


def _make_game_scene(
    xp_system=None,
    challenge=None,
    loot_value_bonus: float = 0.0,
) -> GameScene:
    """Create a stub-mode GameScene (sm=None → _init_stub)."""
    scene = GameScene()  # sm=None → always stub mode
    if xp_system is not None:
        scene._xp_system = xp_system
    scene.loot_value_bonus = loot_value_bonus
    scene._challenge = challenge
    return scene


# ---------------------------------------------------------------------------
# Unit: kill tracking — _on_enemy_killed()
# ---------------------------------------------------------------------------

class TestKillTracking:
    """_on_enemy_killed() accumulates round kills and XP correctly."""

    def test_initial_round_kills_is_zero(self):
        scene = _make_game_scene()
        assert scene._round_kills == 0

    def test_initial_round_kill_xp_is_zero(self):
        scene = _make_game_scene()
        assert scene._round_kill_xp == 0

    def test_single_enemy_killed_increments_kills_to_one(self):
        scene = _make_game_scene()
        scene._on_enemy_killed(xp_reward=50)
        assert scene._round_kills == 1

    def test_multiple_kills_accumulated_in_order(self):
        scene = _make_game_scene()
        scene._on_enemy_killed(xp_reward=50)
        scene._on_enemy_killed(xp_reward=50)
        scene._on_enemy_killed(xp_reward=50)
        assert scene._round_kills == 3

    def test_single_kill_xp_accumulated(self):
        scene = _make_game_scene()
        scene._on_enemy_killed(xp_reward=75)
        assert scene._round_kill_xp == 75

    def test_multiple_xp_rewards_summed(self):
        scene = _make_game_scene()
        scene._on_enemy_killed(xp_reward=50)
        scene._on_enemy_killed(xp_reward=100)
        assert scene._round_kill_xp == 150

    def test_enemy_killed_with_no_xp_reward_adds_zero_kill_xp(self):
        scene = _make_game_scene()
        scene._on_enemy_killed()  # no xp_reward kwarg → defaults to 0
        assert scene._round_kill_xp == 0
        assert scene._round_kills == 1

    def test_enemy_killed_with_zero_xp_reward_adds_zero(self):
        scene = _make_game_scene()
        scene._on_enemy_killed(xp_reward=0)
        assert scene._round_kill_xp == 0
        assert scene._round_kills == 1

    def test_kills_and_xp_tracked_independently(self):
        """Kills without XP and kills with XP each increment their own counter."""
        scene = _make_game_scene()
        scene._on_enemy_killed(xp_reward=100)
        scene._on_enemy_killed()  # no xp_reward
        assert scene._round_kills == 2
        assert scene._round_kill_xp == 100

    def test_ten_kills_all_with_xp(self):
        scene = _make_game_scene()
        for _ in range(10):
            scene._on_enemy_killed(xp_reward=25)
        assert scene._round_kills == 10
        assert scene._round_kill_xp == 250


# ---------------------------------------------------------------------------
# Unit: _build_summary("success")
# ---------------------------------------------------------------------------

class TestBuildSummarySuccess:
    """_build_summary("success") produces a fully populated RoundSummary."""

    def test_returns_round_summary_instance(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        result = scene._build_summary("success")
        assert isinstance(result, RoundSummary)

    def test_extraction_status_is_success(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        s = scene._build_summary("success")
        assert s.extraction_status == "success"

    def test_xp_earned_includes_extraction_xp_bonus(self):
        from src.constants import EXTRACTION_XP
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._round_kill_xp = 0
        s = scene._build_summary("success")
        assert s.xp_earned == EXTRACTION_XP

    def test_xp_earned_adds_kill_xp_to_extraction_xp(self):
        from src.constants import EXTRACTION_XP
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._round_kill_xp = 150
        s = scene._build_summary("success")
        assert s.xp_earned == EXTRACTION_XP + 150

    def test_kills_field_equals_round_kills(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._round_kills = 5
        s = scene._build_summary("success")
        assert s.kills == 5

    def test_zero_kills_reported(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._round_kills = 0
        s = scene._build_summary("success")
        assert s.kills == 0

    def test_level_before_read_from_xp_system(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=4))
        s = scene._build_summary("success")
        assert s.level_before == 4

    def test_level_before_defaults_to_one_when_no_xp_system(self):
        scene = _make_game_scene()  # _xp_system is None
        s = scene._build_summary("success")
        assert s.level_before == 1

    def test_money_earned_sums_item_monetary_values(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        items = [
            _FakeInventoryItem("Rifle", 500),
            _FakeInventoryItem("Vest", 200),
        ]
        scene.player.inventory = _FakeInventory(items)
        s = scene._build_summary("success")
        assert s.money_earned == 700  # no loot bonus

    def test_money_earned_applies_loot_value_bonus(self):
        scene = _make_game_scene(
            xp_system=_FakeXPSystem(level=1),
            loot_value_bonus=0.5,  # 50% bonus
        )
        scene.player.inventory = _FakeInventory([_FakeInventoryItem("Gold", 1000)])
        s = scene._build_summary("success")
        assert s.money_earned == 1500  # 1000 * (1 + 0.5)

    def test_money_earned_with_no_bonus(self):
        scene = _make_game_scene(
            xp_system=_FakeXPSystem(level=1),
            loot_value_bonus=0.0,
        )
        scene.player.inventory = _FakeInventory([_FakeInventoryItem("Grenade", 200)])
        s = scene._build_summary("success")
        assert s.money_earned == 200

    def test_extracted_items_from_player_inventory(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        items = [_FakeInventoryItem("Rifle", 500), _FakeInventoryItem("Med Kit", 100)]
        scene.player.inventory = _FakeInventory(items)
        s = scene._build_summary("success")
        assert len(s.extracted_items) == 2

    def test_empty_inventory_returns_empty_items_list(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene.player.inventory = _FakeInventory([])
        s = scene._build_summary("success")
        assert s.extracted_items == []

    def test_challenges_zero_when_no_challenge_system(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._challenge = None
        s = scene._build_summary("success")
        assert s.challenges_completed == 0
        assert s.challenges_total == 0


# ---------------------------------------------------------------------------
# Unit: _build_summary("timeout") and ("eliminated")
# ---------------------------------------------------------------------------

class TestBuildSummaryFailed:
    """Failed extractions zero out XP, money, and items."""

    def test_timeout_sets_correct_status(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        s = scene._build_summary("timeout")
        assert s.extraction_status == "timeout"

    def test_timeout_xp_earned_is_zero_despite_kills(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._round_kill_xp = 999  # kills happened, but extraction failed
        s = scene._build_summary("timeout")
        assert s.xp_earned == 0

    def test_timeout_money_earned_is_zero(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene.player.inventory = _FakeInventory([_FakeInventoryItem("Loot", 9999)])
        s = scene._build_summary("timeout")
        assert s.money_earned == 0

    def test_timeout_extracted_items_is_empty_list(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene.player.inventory = _FakeInventory([_FakeInventoryItem("Rifle", 500)])
        s = scene._build_summary("timeout")
        assert s.extracted_items == []

    def test_timeout_still_reports_kill_count(self):
        """Kill count is preserved even on timeout — it's shown on the screen."""
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._round_kills = 4
        s = scene._build_summary("timeout")
        assert s.kills == 4

    def test_eliminated_sets_correct_status(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        s = scene._build_summary("eliminated")
        assert s.extraction_status == "eliminated"

    def test_eliminated_xp_earned_is_zero(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._round_kill_xp = 500
        s = scene._build_summary("eliminated")
        assert s.xp_earned == 0

    def test_eliminated_money_earned_is_zero(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        s = scene._build_summary("eliminated")
        assert s.money_earned == 0

    def test_eliminated_extracted_items_is_empty(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene.player.inventory = _FakeInventory([_FakeInventoryItem("Armor", 800)])
        s = scene._build_summary("eliminated")
        assert s.extracted_items == []

    def test_timeout_level_before_still_reads_from_xp_system(self):
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=3))
        s = scene._build_summary("timeout")
        assert s.level_before == 3


# ---------------------------------------------------------------------------
# Unit: _on_player_dead() idempotency
# ---------------------------------------------------------------------------

class TestOnPlayerDeadIdempotency:
    """_on_player_dead() must fire sm.replace() at most once per round."""

    def test_dead_handled_flag_starts_false(self):
        scene = _make_game_scene()
        assert scene._dead_handled is False

    def test_dead_handled_flag_set_true_after_first_call(self):
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_player_dead()
        assert scene._dead_handled is True

    def test_replace_called_once_on_first_death(self):
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_player_dead()
        assert sm.replace.call_count == 1

    def test_replace_not_called_again_on_second_death(self):
        """Repeated _on_player_dead() calls must not re-trigger navigation."""
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_player_dead()
            scene._on_player_dead()
        assert sm.replace.call_count == 1

    def test_third_death_call_still_ignored(self):
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_player_dead()
            scene._on_player_dead()
            scene._on_player_dead()
        assert sm.replace.call_count == 1


# ---------------------------------------------------------------------------
# Integration: event handlers trigger correct scene transitions
# ---------------------------------------------------------------------------

class TestEventHandlerIntegration:
    """_on_extract, _on_extract_failed, _on_player_dead each call sm.replace()
    and produce a PostRound scene with the matching extraction_status."""

    def test_on_extract_calls_sm_replace(self):
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_extract()
        sm.replace.assert_called_once()

    def test_on_extract_passes_post_round_scene_to_replace(self):
        from src.scenes.post_round import PostRound
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_extract()
        new_scene = sm.replace.call_args[0][0]
        assert isinstance(new_scene, PostRound)

    def test_on_extract_builds_success_summary(self):
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_extract()
        new_scene = sm.replace.call_args[0][0]
        assert new_scene.summary.extraction_status == "success"

    def test_on_extract_failed_calls_sm_replace(self):
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_extract_failed()
        sm.replace.assert_called_once()

    def test_on_extract_failed_builds_timeout_summary(self):
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_extract_failed()
        new_scene = sm.replace.call_args[0][0]
        assert new_scene.summary.extraction_status == "timeout"

    def test_on_player_dead_builds_eliminated_summary(self):
        from src.scenes.post_round import PostRound
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_player_dead()
        new_scene = sm.replace.call_args[0][0]
        assert isinstance(new_scene, PostRound)
        assert new_scene.summary.extraction_status == "eliminated"

    def test_on_extract_summary_includes_extraction_xp(self):
        from src.constants import EXTRACTION_XP
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        scene._round_kill_xp = 0
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_extract()
        new_scene = sm.replace.call_args[0][0]
        assert new_scene.summary.xp_earned == EXTRACTION_XP

    def test_on_extract_summary_reflects_kill_count(self):
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        scene._round_kills = 7
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_extract()
        new_scene = sm.replace.call_args[0][0]
        assert new_scene.summary.kills == 7

    def test_on_extract_failed_summary_has_zero_xp(self):
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        scene._round_kill_xp = 999  # irrelevant on timeout
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_extract_failed()
        new_scene = sm.replace.call_args[0][0]
        assert new_scene.summary.xp_earned == 0

    def test_on_player_dead_summary_has_zero_money(self):
        sm = MagicMock()
        scene = _make_game_scene(xp_system=_FakeXPSystem(level=1))
        scene._sm = sm
        with patch("src.save.save_manager.SaveManager.save"):
            scene._on_player_dead()
        new_scene = sm.replace.call_args[0][0]
        assert new_scene.summary.money_earned == 0
