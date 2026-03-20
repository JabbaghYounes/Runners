"""Unit tests for PostRound scene — src/scenes/post_round.py

Covers:
  - Progression commit on construction (xp_system.award, currency.add, save_manager.save)
  - Audio SFX selection by extraction status
  - Keyboard focus cycling through three action buttons (Down / Up / wrap)
  - Button routing via scene_manager.replace() with correct scene type
  - Level-up callout visibility (show_level_up flag)
  - Total loot value calculation
  - Render smoke tests (no exceptions for all outcome types)
"""
import pygame
import pytest
from unittest.mock import MagicMock, patch

from src.core.round_summary import RoundSummary
from src.scenes.post_round import PostRound


# ── Tiny item stub ─────────────────────────────────────────────────────────────

class _FakeItem:
    def __init__(self, name: str, monetary_value: int, rarity: str = "common"):
        self.name = name
        self.monetary_value = monetary_value
        self.rarity = rarity
        self.icon = None  # populated by AssetManager in production


# ── Summary factory ────────────────────────────────────────────────────────────

def _summary(status="success", xp=200, money=800, kills=3,
             items=None, level_before=2, level_after=0):
    return RoundSummary(
        extraction_status=status,
        extracted_items=items if items is not None else [],
        xp_earned=xp,
        money_earned=money,
        kills=kills,
        challenges_completed=1,
        challenges_total=3,
        level_before=level_before,
        level_after=level_after,
    )


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_xp_system():
    xs = MagicMock()
    xs.level = 3          # value returned by .level AFTER award() is called
    xs.xp = 150
    xs.xp_to_next_level.return_value = 200
    xs.pending_xp = 200
    return xs


@pytest.fixture
def mock_currency():
    cur = MagicMock()
    cur.balance = 5_800
    return cur


@pytest.fixture
def mock_save_manager():
    return MagicMock()


@pytest.fixture
def mock_scene_manager():
    return MagicMock()


@pytest.fixture
def mock_asset_manager(pygame_init):
    am = MagicMock()
    am.load_font.return_value = pygame.font.Font(None, 18)
    am.load_image.return_value = pygame.Surface((48, 48))
    return am


@pytest.fixture
def mock_audio_system():
    return MagicMock()


@pytest.fixture
def blurred_bg(pygame_init):
    surf = pygame.Surface((1280, 720))
    surf.fill((10, 14, 26))
    return surf


@pytest.fixture
def success_summary():
    items = [_FakeItem("Rifle", 600), _FakeItem("Vest", 200)]
    return _summary(status="success", xp=200, money=800, kills=3, items=items, level_before=2)


@pytest.fixture
def timeout_summary():
    return _summary(status="timeout", xp=50, money=0, kills=1, items=[], level_before=2)


@pytest.fixture
def eliminated_summary():
    return _summary(status="eliminated", xp=25, money=0, kills=0, items=[], level_before=2)


# ── Constructor helper ─────────────────────────────────────────────────────────

def _build(summary, blurred_bg, xp_system, currency,
           save_manager, scene_manager, asset_manager, audio_system):
    return PostRound(
        summary=summary,
        blurred_bg=blurred_bg,
        xp_system=xp_system,
        currency=currency,
        save_manager=save_manager,
        scene_manager=scene_manager,
        asset_manager=asset_manager,
        audio_system=audio_system,
    )


# ── Progression commit ─────────────────────────────────────────────────────────

class TestProgressionCommit:

    def test_xp_award_called_once_with_correct_amount(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        _build(success_summary, blurred_bg, mock_xp_system, mock_currency,
               mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        mock_xp_system.award.assert_called_once_with(success_summary.xp_earned)

    def test_currency_add_called_once_with_correct_amount(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        _build(success_summary, blurred_bg, mock_xp_system, mock_currency,
               mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        mock_currency.add.assert_called_once_with(success_summary.money_earned)

    def test_save_called_exactly_once(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        _build(success_summary, blurred_bg, mock_xp_system, mock_currency,
               mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        assert mock_save_manager.save.call_count == 1

    def test_level_after_set_to_xp_system_level_post_award(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        scene = _build(success_summary, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        assert scene.summary.level_after == mock_xp_system.level

    def test_progression_not_applied_again_on_update(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        scene = _build(success_summary, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)
        scene.update(0.016)
        scene.update(0.016)

        mock_xp_system.award.assert_called_once()
        mock_currency.add.assert_called_once()
        assert mock_save_manager.save.call_count == 1

    def test_timeout_awards_zero_money(
        self, timeout_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        _build(timeout_summary, blurred_bg, mock_xp_system, mock_currency,
               mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        mock_currency.add.assert_called_once_with(0)

    def test_eliminated_awards_zero_money(
        self, eliminated_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        _build(eliminated_summary, blurred_bg, mock_xp_system, mock_currency,
               mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        mock_currency.add.assert_called_once_with(0)

    def test_timeout_extracted_items_is_empty(
        self, timeout_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        scene = _build(timeout_summary, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        assert scene.summary.extracted_items == []

    def test_eliminated_extracted_items_is_empty(
        self, eliminated_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        scene = _build(eliminated_summary, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        assert scene.summary.extracted_items == []


# ── Audio SFX ─────────────────────────────────────────────────────────────────

class TestAudioSfx:

    def _make(self, summary, blurred_bg, mock_xp_system, mock_currency,
              mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system):
        return _build(summary, blurred_bg, mock_xp_system, mock_currency,
                      mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

    def test_success_plays_extraction_success_sfx(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        self._make(success_summary, blurred_bg, mock_xp_system, mock_currency,
                   mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        mock_audio_system.play_sfx.assert_called_once_with("extraction_success")

    def test_timeout_plays_extraction_fail_sfx(
        self, timeout_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        self._make(timeout_summary, blurred_bg, mock_xp_system, mock_currency,
                   mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        mock_audio_system.play_sfx.assert_called_once_with("extraction_fail")

    def test_eliminated_plays_extraction_fail_sfx(
        self, eliminated_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        self._make(eliminated_summary, blurred_bg, mock_xp_system, mock_currency,
                   mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        mock_audio_system.play_sfx.assert_called_once_with("extraction_fail")

    def test_audio_played_exactly_once(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        self._make(success_summary, blurred_bg, mock_xp_system, mock_currency,
                   mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

        assert mock_audio_system.play_sfx.call_count == 1


# ── Keyboard focus cycling ─────────────────────────────────────────────────────

class TestKeyboardFocus:

    @pytest.fixture
    def scene(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        return _build(success_summary, blurred_bg, mock_xp_system, mock_currency,
                      mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

    @staticmethod
    def _key(key_const):
        return pygame.event.Event(
            pygame.KEYDOWN,
            {"key": key_const, "mod": 0, "unicode": "", "scancode": 0},
        )

    def test_initial_focus_is_zero(self, scene):
        assert scene.focused_button_index == 0

    def test_down_advances_focus_to_1(self, scene):
        scene.handle_events([self._key(pygame.K_DOWN)])
        assert scene.focused_button_index == 1

    def test_down_twice_advances_focus_to_2(self, scene):
        scene.handle_events([self._key(pygame.K_DOWN)])
        scene.handle_events([self._key(pygame.K_DOWN)])
        assert scene.focused_button_index == 2

    def test_down_from_last_wraps_to_0(self, scene):
        scene.focused_button_index = 2
        scene.handle_events([self._key(pygame.K_DOWN)])
        assert scene.focused_button_index == 0

    def test_up_from_first_wraps_to_last(self, scene):
        scene.focused_button_index = 0
        scene.handle_events([self._key(pygame.K_UP)])
        assert scene.focused_button_index == 2

    def test_up_from_2_moves_to_1(self, scene):
        scene.focused_button_index = 2
        scene.handle_events([self._key(pygame.K_UP)])
        assert scene.focused_button_index == 1

    def test_up_from_1_moves_to_0(self, scene):
        scene.focused_button_index = 1
        scene.handle_events([self._key(pygame.K_UP)])
        assert scene.focused_button_index == 0

    def test_up_then_down_returns_to_original(self, scene):
        original = scene.focused_button_index
        scene.handle_events([self._key(pygame.K_UP)])
        scene.handle_events([self._key(pygame.K_DOWN)])
        assert scene.focused_button_index == original

    def test_unrelated_key_does_not_change_focus(self, scene):
        scene.focused_button_index = 1
        scene.handle_events([self._key(pygame.K_SPACE)])
        assert scene.focused_button_index == 1

    def test_three_downs_complete_full_cycle(self, scene):
        start = scene.focused_button_index
        for _ in range(3):
            scene.handle_events([self._key(pygame.K_DOWN)])
        assert scene.focused_button_index == start


# ── Button routing ─────────────────────────────────────────────────────────────

class TestButtonRouting:

    @pytest.fixture
    def scene(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        return _build(success_summary, blurred_bg, mock_xp_system, mock_currency,
                      mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

    @staticmethod
    def _enter():
        return pygame.event.Event(
            pygame.KEYDOWN,
            {"key": pygame.K_RETURN, "mod": 0, "unicode": "\r", "scancode": 0},
        )

    def test_queue_next_round_calls_replace(self, scene, mock_scene_manager):
        """Button 0 — QUEUE NEXT ROUND — must call scene_manager.replace_all."""
        scene.focused_button_index = 0
        with patch("src.scenes.post_round.GameScene"):
            scene.handle_events([self._enter()])
        mock_scene_manager.replace_all.assert_called_once()

    def test_queue_next_round_passes_game_scene_instance(self, scene, mock_scene_manager):
        scene.focused_button_index = 0
        with patch("src.scenes.post_round.GameScene") as MockGameScene:
            scene.handle_events([self._enter()])
        assert MockGameScene.called

    def test_go_to_home_base_calls_replace(self, scene, mock_scene_manager):
        """Button 1 — GO TO HOME BASE — must call scene_manager.replace."""
        scene.focused_button_index = 1
        with patch("src.scenes.post_round.HomeBaseScene"):
            scene.handle_events([self._enter()])
        mock_scene_manager.replace.assert_called_once()

    def test_go_to_home_base_passes_home_base_scene_instance(self, scene, mock_scene_manager):
        scene.focused_button_index = 1
        with patch("src.scenes.post_round.HomeBaseScene") as MockHomeBase:
            scene.handle_events([self._enter()])
        assert MockHomeBase.called

    def test_exit_to_main_menu_calls_replace(self, scene, mock_scene_manager):
        """Button 2 — EXIT TO MAIN MENU — must call scene_manager.replace_all."""
        scene.focused_button_index = 2
        with patch("src.scenes.post_round.MainMenu"):
            scene.handle_events([self._enter()])
        mock_scene_manager.replace_all.assert_called_once()

    def test_exit_to_main_menu_passes_main_menu_instance(self, scene, mock_scene_manager):
        scene.focused_button_index = 2
        with patch("src.scenes.post_round.MainMenu") as MockMainMenu:
            scene.handle_events([self._enter()])
        assert MockMainMenu.called

    def test_navigation_alone_does_not_trigger_replace(self, scene, mock_scene_manager):
        down = pygame.event.Event(
            pygame.KEYDOWN,
            {"key": pygame.K_DOWN, "mod": 0, "unicode": "", "scancode": 0},
        )
        scene.handle_events([down])
        mock_scene_manager.replace.assert_not_called()

    def test_replace_receives_a_scene_object(self, scene, mock_scene_manager):
        scene.focused_button_index = 0
        with patch("src.scenes.post_round.GameScene") as MockGameScene:
            scene.handle_events([self._enter()])
        passed = mock_scene_manager.replace_all.call_args[0][0]
        assert passed is MockGameScene.return_value


# ── Level-up callout ───────────────────────────────────────────────────────────

class TestLevelUpCallout:

    def _make_scene(
        self, level_before, awarded_level,
        blurred_bg, mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        mock_xp_system.level = awarded_level
        s = _summary(status="success", level_before=level_before)
        return _build(s, blurred_bg, mock_xp_system, mock_currency,
                      mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)

    def test_show_level_up_true_when_level_increased(
        self, blurred_bg, mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        scene = self._make_scene(
            2, 3, blurred_bg, mock_xp_system, mock_currency, mock_save_manager,
            mock_scene_manager, mock_asset_manager, mock_audio_system,
        )
        assert scene.show_level_up is True

    def test_show_level_up_false_when_level_unchanged(
        self, blurred_bg, mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        scene = self._make_scene(
            3, 3, blurred_bg, mock_xp_system, mock_currency, mock_save_manager,
            mock_scene_manager, mock_asset_manager, mock_audio_system,
        )
        assert scene.show_level_up is False

    def test_show_level_up_false_on_failed_extraction(
        self, blurred_bg, mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        mock_xp_system.level = 2  # no level gain
        s = _summary(status="timeout", xp=10, money=0, level_before=2)
        scene = _build(s, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)
        assert scene.show_level_up is False


# ── Loot grid total value ──────────────────────────────────────────────────────

class TestLootGrid:

    def test_total_loot_value_is_sum_of_item_monetary_values(
        self, blurred_bg, mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        items = [_FakeItem("Rifle", 600), _FakeItem("Vest", 200), _FakeItem("Meds", 150)]
        s = _summary(status="success", money=950, items=items)
        scene = _build(s, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)
        assert scene.total_loot_value == 950

    def test_total_loot_value_zero_when_no_items(
        self, blurred_bg, mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        s = _summary(status="timeout", money=0, items=[])
        scene = _build(s, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)
        assert scene.total_loot_value == 0

    def test_total_loot_value_equals_sum_of_all_item_values(
        self, blurred_bg, mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system,
    ):
        items = [_FakeItem(f"item_{i}", (i + 1) * 100) for i in range(5)]
        expected = sum(i.monetary_value for i in items)
        s = _summary(status="success", money=expected, items=items)
        scene = _build(s, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)
        assert scene.total_loot_value == expected


# ── Render smoke tests ─────────────────────────────────────────────────────────

class TestRender:
    """Ensure render() never raises regardless of outcome type or animation state."""

    def test_render_success_no_exception(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system, screen,
    ):
        scene = _build(success_summary, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)
        scene.render(screen)

    def test_render_timeout_no_exception(
        self, timeout_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system, screen,
    ):
        scene = _build(timeout_summary, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)
        scene.render(screen)

    def test_render_eliminated_no_exception(
        self, eliminated_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system, screen,
    ):
        scene = _build(eliminated_summary, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)
        scene.render(screen)

    def test_render_after_several_updates_no_exception(
        self, success_summary, blurred_bg,
        mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system, screen,
    ):
        scene = _build(success_summary, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)
        for _ in range(60):
            scene.update(1 / 60)
        scene.render(screen)

    def test_render_with_level_up_no_exception(
        self, blurred_bg, mock_xp_system, mock_currency, mock_save_manager,
        mock_scene_manager, mock_asset_manager, mock_audio_system, screen,
    ):
        mock_xp_system.level = 4
        s = _summary(status="success", level_before=3)
        scene = _build(s, blurred_bg, mock_xp_system, mock_currency,
                       mock_save_manager, mock_scene_manager, mock_asset_manager, mock_audio_system)
        for _ in range(90):
            scene.update(1 / 60)
        scene.render(screen)
