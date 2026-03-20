"""Unit and integration tests for the PostRound scene.

Covers:
  * Progression commit in __init__: XP award, currency add, save trigger
  * Derived display state: show_level_up, total_loot_value, _xp_before snapshot
  * Audio SFX selection by extraction status
  * None-dependency guards (save_manager, audio_system, xp_system, currency)
  * Legacy sm= construction path
  * Keyboard navigation: K_UP/K_DOWN focus cycling, K_RETURN/K_KP_ENTER activation
  * Mouse navigation: MOUSEMOTION hover focus, MOUSEBUTTONDOWN click activation
  * _activate_button() routing: replace vs replace_all per button index
  * _rarity_color() helper: rarity string/enum → display colour

# Run: pytest tests/scenes/test_post_round_scene.py
"""
from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pygame
import pytest

from src.core.round_summary import RoundSummary
from src.progression.currency import Currency
from src.progression.xp_system import XPSystem
from src.scenes.post_round import _rarity_color, PostRound


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _FakeItem:
    """Minimal item stand-in used in summary construction."""

    def __init__(self, monetary_value: int, rarity: str = "common", name: str = "Stub"):
        self.name = name
        self.monetary_value = monetary_value
        self.rarity = rarity


def _make_summary(**overrides) -> RoundSummary:
    """Build a RoundSummary with sensible defaults."""
    defaults = dict(
        extraction_status="success",
        extracted_items=[],
        xp_earned=100,
        money_earned=500,
        kills=3,
        challenges_completed=1,
        challenges_total=3,
        level_before=2,
    )
    defaults.update(overrides)
    return RoundSummary(**defaults)


def _make_post_round(
    summary=None,
    xp_system=None,
    currency=None,
    save_manager=None,
    scene_manager=None,
    audio_system=None,
    **kwargs,
) -> PostRound:
    """Construct a PostRound with sensible defaults for most dependencies."""
    if summary is None:
        summary = _make_summary()
    if xp_system is None:
        xp_sys = XPSystem()
        xp_sys.level = 2
        xp_system = xp_sys
    if currency is None:
        currency = Currency(balance=0)
    if scene_manager is None:
        scene_manager = MagicMock(name="scene_manager")
    return PostRound(
        summary=summary,
        xp_system=xp_system,
        currency=currency,
        save_manager=save_manager,
        scene_manager=scene_manager,
        audio_system=audio_system,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Unit: __init__ — progression commit
# ---------------------------------------------------------------------------

class TestPostRoundInitProgression:
    """PostRound.__init__ commits XP, currency, and save exactly once."""

    def test_xp_awarded_with_correct_amount(self):
        xp_sys = XPSystem()
        summary = _make_summary(xp_earned=250, level_before=1)
        _make_post_round(summary=summary, xp_system=xp_sys)
        # XPSystem stores xp within the current level band; total awarded XP is 250
        assert xp_sys.xp == 250

    def test_xp_not_double_awarded_on_construction(self):
        """Constructing PostRound must award XP exactly once."""
        xp_sys = XPSystem()
        summary = _make_summary(xp_earned=100, level_before=1)
        _make_post_round(summary=summary, xp_system=xp_sys)
        assert xp_sys.xp == 100  # not 200

    def test_level_after_stamped_from_xp_system_after_award(self):
        """summary.level_after reflects xp_system.level AFTER the award."""
        xp_sys = XPSystem()
        xp_sys.level = 3
        summary = _make_summary(level_before=3, xp_earned=0)
        _make_post_round(summary=summary, xp_system=xp_sys)
        assert summary.level_after == 3

    def test_level_after_updated_when_award_causes_level_up(self):
        """Awarding 1000 XP to a level-1 player crosses the 900-XP threshold."""
        xp_sys = XPSystem()
        xp_sys.level = 1
        summary = _make_summary(level_before=1, xp_earned=1000)
        _make_post_round(summary=summary, xp_system=xp_sys)
        assert summary.level_after == 2

    def test_currency_credited_correct_amount(self):
        """currency.add() receives summary.money_earned."""
        currency = Currency(balance=100)
        summary = _make_summary(money_earned=400)
        _make_post_round(summary=summary, currency=currency)
        assert currency.balance == 500  # 100 + 400

    def test_currency_add_called_once_not_per_item(self):
        """A single bulk add(), not one call per extracted item."""
        mock_currency = MagicMock()
        summary = _make_summary(money_earned=300)
        _make_post_round(summary=summary, currency=mock_currency)
        mock_currency.add.assert_called_once_with(300)

    def test_save_called_exactly_once_on_entry(self):
        """save_manager.save() is invoked exactly once on scene construction."""
        mock_save = MagicMock()
        _make_post_round(save_manager=mock_save)
        assert mock_save.save.call_count == 1

    def test_save_receives_xp_system_kwarg(self):
        """save_manager.save() is passed the live xp_system object."""
        mock_save = MagicMock()
        xp_sys = XPSystem()
        _make_post_round(xp_system=xp_sys, save_manager=mock_save)
        _, kwargs = mock_save.save.call_args
        assert kwargs.get("xp_system") is xp_sys

    def test_save_receives_currency_kwarg(self):
        """save_manager.save() is passed the live currency object."""
        mock_save = MagicMock()
        curr = Currency(balance=0)
        _make_post_round(currency=curr, save_manager=mock_save)
        _, kwargs = mock_save.save.call_args
        assert kwargs.get("currency") is curr

    def test_show_level_up_true_when_xp_crosses_level_threshold(self):
        xp_sys = XPSystem()
        xp_sys.level = 1
        summary = _make_summary(level_before=1, xp_earned=1000)  # → level 2
        pr = _make_post_round(summary=summary, xp_system=xp_sys)
        assert pr.show_level_up is True

    def test_show_level_up_false_when_xp_below_threshold(self):
        xp_sys = XPSystem()
        xp_sys.level = 2
        summary = _make_summary(level_before=2, xp_earned=10)  # well below 1260
        pr = _make_post_round(summary=summary, xp_system=xp_sys)
        assert pr.show_level_up is False

    def test_show_level_up_false_when_zero_xp_earned(self):
        """A failed round with xp_earned=0 never shows a level-up notice."""
        xp_sys = XPSystem()
        xp_sys.level = 2
        summary = _make_summary(
            extraction_status="timeout", level_before=2, xp_earned=0, money_earned=0,
        )
        pr = _make_post_round(summary=summary, xp_system=xp_sys)
        assert pr.show_level_up is False

    def test_xp_before_snapshot_taken_before_award(self):
        """_xp_before holds the XP amount BEFORE the award is applied."""
        xp_sys = XPSystem()
        xp_sys.xp = 50
        xp_sys.level = 1
        summary = _make_summary(xp_earned=200)
        pr = _make_post_round(summary=summary, xp_system=xp_sys)
        assert pr._xp_before == 50  # captured before award; after award xp=250

    def test_total_loot_value_computed_from_extracted_items(self):
        items = [_FakeItem(300), _FakeItem(700)]
        summary = _make_summary(extracted_items=items)
        pr = _make_post_round(summary=summary)
        assert pr.total_loot_value == 1000

    def test_total_loot_value_zero_for_empty_items(self):
        summary = _make_summary(extracted_items=[])
        pr = _make_post_round(summary=summary)
        assert pr.total_loot_value == 0

    def test_focused_button_index_starts_at_zero(self):
        pr = _make_post_round()
        assert pr.focused_button_index == 0

    def test_summary_stored_on_instance(self):
        summary = _make_summary(xp_earned=42)
        pr = _make_post_round(summary=summary)
        assert pr.summary is summary

    def test_audio_sfx_played_for_success(self):
        mock_audio = MagicMock()
        summary = _make_summary(extraction_status="success")
        _make_post_round(summary=summary, audio_system=mock_audio)
        mock_audio.play_sfx.assert_called_once_with("extraction_success")

    def test_audio_sfx_played_for_timeout_failure(self):
        mock_audio = MagicMock()
        summary = _make_summary(
            extraction_status="timeout", xp_earned=0, money_earned=0,
        )
        _make_post_round(summary=summary, audio_system=mock_audio)
        mock_audio.play_sfx.assert_called_once_with("extraction_fail")

    def test_audio_sfx_played_for_eliminated_failure(self):
        mock_audio = MagicMock()
        summary = _make_summary(
            extraction_status="eliminated", xp_earned=0, money_earned=0,
        )
        _make_post_round(summary=summary, audio_system=mock_audio)
        mock_audio.play_sfx.assert_called_once_with("extraction_fail")

    def test_no_crash_when_save_manager_is_none(self):
        """save_manager=None must be silently skipped."""
        pr = _make_post_round(save_manager=None)
        assert pr.summary is not None

    def test_no_crash_when_audio_system_is_none(self):
        pr = _make_post_round(audio_system=None)
        assert pr is not None

    def test_no_crash_when_xp_system_is_none(self):
        summary = _make_summary()
        pr = PostRound(
            summary=summary,
            xp_system=None,
            currency=Currency(),
            scene_manager=MagicMock(),
        )
        assert pr.summary is not None

    def test_no_crash_when_currency_is_none(self):
        summary = _make_summary()
        pr = PostRound(
            summary=summary,
            xp_system=XPSystem(),
            currency=None,
            scene_manager=MagicMock(),
        )
        assert pr.summary is not None

    def test_legacy_sm_path_sets_minimal_state(self):
        """Constructing with sm= (legacy) initialises without crashing."""
        sm = MagicMock()
        pr = PostRound(sm=sm, settings=None, assets=None)
        assert pr.summary is None
        assert pr.focused_button_index == 0
        assert pr.show_level_up is False


# ---------------------------------------------------------------------------
# Unit: keyboard navigation
# ---------------------------------------------------------------------------

class TestKeyboardNavigation:
    """handle_events() routes keyboard input to focus management and activation."""

    @staticmethod
    def _keydown(key: int) -> types.SimpleNamespace:
        return types.SimpleNamespace(type=pygame.KEYDOWN, key=key)

    def test_down_key_increments_focus(self):
        pr = _make_post_round()
        pr.focused_button_index = 0
        pr.handle_events([self._keydown(pygame.K_DOWN)])
        assert pr.focused_button_index == 1

    def test_down_key_advances_focus_by_one(self):
        pr = _make_post_round()
        pr.focused_button_index = 1
        pr.handle_events([self._keydown(pygame.K_DOWN)])
        assert pr.focused_button_index == 2

    def test_down_key_wraps_from_last_to_first(self):
        pr = _make_post_round()
        pr.focused_button_index = 2  # last (0-based, 3 buttons)
        pr.handle_events([self._keydown(pygame.K_DOWN)])
        assert pr.focused_button_index == 0

    def test_up_key_decrements_focus(self):
        pr = _make_post_round()
        pr.focused_button_index = 2
        pr.handle_events([self._keydown(pygame.K_UP)])
        assert pr.focused_button_index == 1

    def test_up_key_wraps_from_first_to_last(self):
        pr = _make_post_round()
        pr.focused_button_index = 0
        pr.handle_events([self._keydown(pygame.K_UP)])
        assert pr.focused_button_index == 2

    def test_return_key_activates_focused_button(self):
        sm = MagicMock()
        pr = _make_post_round(scene_manager=sm)
        pr.focused_button_index = 2
        with patch("src.scenes.post_round.MainMenu", return_value=MagicMock()):
            pr.handle_events([self._keydown(pygame.K_RETURN)])
        sm.replace_all.assert_called_once()

    def test_numpad_enter_activates_focused_button(self):
        sm = MagicMock()
        pr = _make_post_round(scene_manager=sm)
        pr.focused_button_index = 2
        with patch("src.scenes.post_round.MainMenu", return_value=MagicMock()):
            pr.handle_events([self._keydown(pygame.K_KP_ENTER)])
        sm.replace_all.assert_called_once()

    def test_empty_event_list_does_not_crash(self):
        pr = _make_post_round()
        pr.handle_events([])
        assert pr.focused_button_index == 0

    def test_unrelated_key_does_not_change_focus(self):
        pr = _make_post_round()
        pr.focused_button_index = 1
        pr.handle_events([self._keydown(pygame.K_SPACE)])
        assert pr.focused_button_index == 1

    def test_multiple_down_presses_accumulate(self):
        pr = _make_post_round()
        pr.focused_button_index = 0
        pr.handle_events([self._keydown(pygame.K_DOWN)])
        pr.handle_events([self._keydown(pygame.K_DOWN)])
        assert pr.focused_button_index == 2

    def test_down_then_up_returns_to_original(self):
        pr = _make_post_round()
        pr.focused_button_index = 1
        pr.handle_events([self._keydown(pygame.K_DOWN)])
        pr.handle_events([self._keydown(pygame.K_UP)])
        assert pr.focused_button_index == 1


# ---------------------------------------------------------------------------
# Unit: mouse navigation
# ---------------------------------------------------------------------------

class TestMouseNavigation:
    """MOUSEMOTION hover focus and MOUSEBUTTONDOWN click routing."""

    # Actual button rects computed from layout constants:
    #   total_w = 3*256 + 2*20 = 808; start_x = (1280 - 808) // 2 = 236
    #   btn[0]: Rect(236, 566, 256, 44)  center ≈ (364, 588)
    #   btn[1]: Rect(512, 566, 256, 44)  center ≈ (640, 588)
    #   btn[2]: Rect(788, 566, 256, 44)  center ≈ (916, 588)
    _BTN_RECTS = [
        pygame.Rect(236, 566, 256, 44),
        pygame.Rect(512, 566, 256, 44),
        pygame.Rect(788, 566, 256, 44),
    ]

    def _pr(self) -> PostRound:
        pr = _make_post_round()
        pr._btn_rects = list(self._BTN_RECTS)
        return pr

    @staticmethod
    def _motion(x: int, y: int) -> types.SimpleNamespace:
        return types.SimpleNamespace(type=pygame.MOUSEMOTION, pos=(x, y))

    @staticmethod
    def _click(x: int, y: int, button: int = 1) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            type=pygame.MOUSEBUTTONDOWN, button=button, pos=(x, y)
        )

    def test_hover_over_first_button_sets_focus_to_zero(self):
        pr = self._pr()
        pr.focused_button_index = 2
        pr.handle_events([self._motion(364, 588)])  # btn[0] center
        assert pr.focused_button_index == 0

    def test_hover_over_second_button_sets_focus_to_one(self):
        pr = self._pr()
        pr.focused_button_index = 0
        pr.handle_events([self._motion(640, 588)])  # btn[1] center
        assert pr.focused_button_index == 1

    def test_hover_over_third_button_sets_focus_to_two(self):
        pr = self._pr()
        pr.focused_button_index = 0
        pr.handle_events([self._motion(916, 588)])  # btn[2] center
        assert pr.focused_button_index == 2

    def test_hover_outside_all_buttons_does_not_change_focus(self):
        pr = self._pr()
        pr.focused_button_index = 1
        pr.handle_events([self._motion(0, 0)])  # far from buttons
        assert pr.focused_button_index == 1

    def test_left_click_on_first_button_calls_replace_all(self):
        pr = self._pr()
        sm = pr._sm
        with patch("src.scenes.post_round.GameScene", return_value=MagicMock()):
            pr.handle_events([self._click(364, 588)])  # btn[0]
        sm.replace_all.assert_called_once()

    def test_left_click_on_second_button_calls_replace(self):
        pr = self._pr()
        sm = pr._sm
        with patch("src.scenes.post_round.HomeBaseScene", return_value=MagicMock()):
            pr.handle_events([self._click(640, 588)])  # btn[1]
        sm.replace.assert_called_once()

    def test_left_click_on_third_button_calls_replace_all(self):
        pr = self._pr()
        sm = pr._sm
        with patch("src.scenes.post_round.MainMenu", return_value=MagicMock()):
            pr.handle_events([self._click(916, 588)])  # btn[2]
        sm.replace_all.assert_called_once()

    def test_right_click_does_not_activate_any_button(self):
        pr = self._pr()
        sm = pr._sm
        pr.handle_events([self._click(364, 588, button=3)])  # right-click on btn[0]
        sm.replace_all.assert_not_called()
        sm.replace.assert_not_called()

    def test_left_click_outside_all_buttons_does_not_activate(self):
        pr = self._pr()
        sm = pr._sm
        pr.handle_events([self._click(0, 0)])
        sm.replace_all.assert_not_called()
        sm.replace.assert_not_called()

    def test_click_updates_focused_index_to_clicked_button(self):
        pr = self._pr()
        pr.focused_button_index = 0
        with patch("src.scenes.post_round.MainMenu", return_value=MagicMock()):
            pr.handle_events([self._click(916, 588)])  # btn[2]
        assert pr.focused_button_index == 2


# ---------------------------------------------------------------------------
# Unit: _activate_button() routing
# ---------------------------------------------------------------------------

class TestActivateButton:
    """_activate_button(index) routes to the correct scene-manager method."""

    def test_button_0_calls_replace_all(self):
        sm = MagicMock()
        pr = _make_post_round(scene_manager=sm)
        with patch("src.scenes.post_round.GameScene", return_value=MagicMock()):
            pr._activate_button(0)
        sm.replace_all.assert_called_once()

    def test_button_0_does_not_call_replace(self):
        sm = MagicMock()
        pr = _make_post_round(scene_manager=sm)
        with patch("src.scenes.post_round.GameScene", return_value=MagicMock()):
            pr._activate_button(0)
        sm.replace.assert_not_called()

    def test_button_1_calls_replace(self):
        sm = MagicMock()
        pr = _make_post_round(scene_manager=sm)
        with patch("src.scenes.post_round.HomeBaseScene", return_value=MagicMock()):
            pr._activate_button(1)
        sm.replace.assert_called_once()

    def test_button_1_does_not_call_replace_all(self):
        sm = MagicMock()
        pr = _make_post_round(scene_manager=sm)
        with patch("src.scenes.post_round.HomeBaseScene", return_value=MagicMock()):
            pr._activate_button(1)
        sm.replace_all.assert_not_called()

    def test_button_2_calls_replace_all(self):
        sm = MagicMock()
        pr = _make_post_round(scene_manager=sm)
        with patch("src.scenes.post_round.MainMenu", return_value=MagicMock()):
            pr._activate_button(2)
        sm.replace_all.assert_called_once()

    def test_button_2_does_not_call_replace(self):
        sm = MagicMock()
        pr = _make_post_round(scene_manager=sm)
        with patch("src.scenes.post_round.MainMenu", return_value=MagicMock()):
            pr._activate_button(2)
        sm.replace.assert_not_called()

    def test_no_crash_when_scene_manager_is_none(self):
        """_activate_button() with sm=None must return immediately without error."""
        pr = PostRound(
            summary=_make_summary(),
            scene_manager=None,
            xp_system=None,
            currency=None,
        )
        pr._activate_button(0)  # must not raise

    def test_button_0_passes_fresh_game_scene_to_replace_all(self):
        """replace_all receives the GameScene instance returned by the constructor."""
        sm = MagicMock()
        pr = _make_post_round(scene_manager=sm)
        mock_gs = MagicMock(name="GameSceneInstance")
        with patch("src.scenes.post_round.GameScene", return_value=mock_gs):
            pr._activate_button(0)
        sm.replace_all.assert_called_once_with(mock_gs)


# ---------------------------------------------------------------------------
# Unit: _rarity_color() helper
# ---------------------------------------------------------------------------

class TestRarityColor:
    """Module-level _rarity_color() maps item rarity to a display colour."""

    def test_common_rarity_returns_text_primary(self):
        from src.constants import TEXT_PRIMARY
        item = types.SimpleNamespace(rarity="common")
        assert _rarity_color(item) == TEXT_PRIMARY

    def test_uncommon_rarity_returns_accent_green(self):
        from src.constants import ACCENT_GREEN
        item = types.SimpleNamespace(rarity="uncommon")
        assert _rarity_color(item) == ACCENT_GREEN

    def test_rare_rarity_returns_accent_cyan(self):
        from src.constants import ACCENT_CYAN
        item = types.SimpleNamespace(rarity="rare")
        assert _rarity_color(item) == ACCENT_CYAN

    def test_epic_rarity_returns_accent_magenta(self):
        from src.constants import ACCENT_MAGENTA
        item = types.SimpleNamespace(rarity="epic")
        assert _rarity_color(item) == ACCENT_MAGENTA

    def test_legendary_rarity_returns_amber(self):
        item = types.SimpleNamespace(rarity="legendary")
        assert _rarity_color(item) == (255, 184, 0)

    def test_none_rarity_returns_text_primary(self):
        from src.constants import TEXT_PRIMARY
        item = types.SimpleNamespace(rarity=None)
        assert _rarity_color(item) == TEXT_PRIMARY

    def test_missing_rarity_attribute_returns_text_primary(self):
        from src.constants import TEXT_PRIMARY
        item = types.SimpleNamespace()  # no .rarity attr
        assert _rarity_color(item) == TEXT_PRIMARY

    def test_unknown_rarity_string_returns_text_primary(self):
        from src.constants import TEXT_PRIMARY
        item = types.SimpleNamespace(rarity="godlike")
        assert _rarity_color(item) == TEXT_PRIMARY

    def test_rarity_enum_uncommon_returns_accent_green(self):
        """Rarity enum instances are resolved via their .value attribute."""
        from src.constants import ACCENT_GREEN
        from src.inventory.item import Rarity
        item = types.SimpleNamespace(rarity=Rarity.UNCOMMON)
        assert _rarity_color(item) == ACCENT_GREEN

    def test_rarity_enum_legendary_returns_amber(self):
        from src.inventory.item import Rarity
        item = types.SimpleNamespace(rarity=Rarity.LEGENDARY)
        assert _rarity_color(item) == (255, 184, 0)

    def test_rarity_enum_rare_returns_accent_cyan(self):
        from src.constants import ACCENT_CYAN
        from src.inventory.item import Rarity
        item = types.SimpleNamespace(rarity=Rarity.RARE)
        assert _rarity_color(item) == ACCENT_CYAN


# ---------------------------------------------------------------------------
# Integration: full progression pipeline
# ---------------------------------------------------------------------------

class TestProgressionIntegration:
    """End-to-end tests: real XPSystem + Currency + mocked SaveManager."""

    def test_success_round_credits_xp_and_currency_correctly(self):
        xp_sys = XPSystem()
        xp_sys.level = 1
        curr = Currency(balance=0)
        mock_save = MagicMock()
        summary = _make_summary(xp_earned=150, money_earned=500, level_before=1)
        _make_post_round(
            summary=summary,
            xp_system=xp_sys,
            currency=curr,
            save_manager=mock_save,
        )
        assert xp_sys.xp == 150
        assert curr.balance == 500
        mock_save.save.assert_called_once()

    def test_failed_round_leaves_xp_and_currency_unchanged(self):
        """A timeout with xp_earned=0 and money_earned=0 leaves balances intact."""
        xp_sys = XPSystem()
        xp_sys.level = 2
        curr = Currency(balance=1000)
        mock_save = MagicMock()
        summary = _make_summary(
            extraction_status="timeout",
            xp_earned=0,
            money_earned=0,
            level_before=2,
        )
        _make_post_round(
            summary=summary,
            xp_system=xp_sys,
            currency=curr,
            save_manager=mock_save,
        )
        assert xp_sys.xp == 0  # no XP added
        assert curr.balance == 1000  # unchanged
        mock_save.save.assert_called_once()  # save still triggered

    def test_multi_level_xp_jump_reflected_in_level_after(self):
        """Awarding 2500 XP from level 1 crosses two thresholds (→ level 3)."""
        xp_sys = XPSystem()
        xp_sys.level = 1
        summary = _make_summary(xp_earned=2500, level_before=1)
        _make_post_round(summary=summary, xp_system=xp_sys)
        assert summary.level_after == 3

    def test_multi_level_jump_sets_show_level_up(self):
        xp_sys = XPSystem()
        xp_sys.level = 1
        summary = _make_summary(xp_earned=2500, level_before=1)
        pr = _make_post_round(summary=summary, xp_system=xp_sys)
        assert pr.show_level_up is True

    def test_single_level_up_sets_show_level_up(self):
        xp_sys = XPSystem()
        xp_sys.level = 1
        summary = _make_summary(xp_earned=1000, level_before=1)  # → level 2
        pr = _make_post_round(summary=summary, xp_system=xp_sys)
        assert pr.show_level_up is True
        assert summary.level_after == 2

    def test_eliminated_round_awards_zero_xp(self):
        xp_sys = XPSystem()
        xp_sys.level = 1
        curr = Currency(balance=500)
        summary = _make_summary(
            extraction_status="eliminated",
            xp_earned=0,
            money_earned=0,
            level_before=1,
        )
        _make_post_round(summary=summary, xp_system=xp_sys, currency=curr)
        assert xp_sys.xp == 0
        assert curr.balance == 500
