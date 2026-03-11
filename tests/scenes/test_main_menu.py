"""Unit tests for src.scenes.main_menu.MainMenu.

The SceneManager is replaced with a MagicMock so that navigation callbacks
can be verified without starting a real game loop.
"""
import sys
from unittest.mock import MagicMock, patch

import pygame
import pytest

from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.scenes.main_menu import MainMenu


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_sm():
    return MagicMock(spec=SceneManager)


@pytest.fixture
def menu(mock_sm, settings, assets):
    return MainMenu(mock_sm, settings, assets)


def _keydown(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestMainMenuConstruction:
    def test_instantiation_does_not_raise(self, menu):
        assert menu is not None

    def test_has_exactly_three_buttons(self, menu):
        assert len(menu._buttons) == 3

    def test_button_labels_are_correct(self, menu):
        texts = {btn.text for btn in menu._buttons}
        assert "START GAME" in texts
        assert "SETTINGS" in texts
        assert "EXIT" in texts

    def test_focus_index_starts_at_zero(self, menu):
        assert menu._focus_idx == 0

    def test_first_button_is_focused_on_start(self, menu):
        assert menu._buttons[0]._focused is True

    def test_unfocused_buttons_are_not_focused(self, menu):
        for btn in menu._buttons[1:]:
            assert btn._focused is False


# ---------------------------------------------------------------------------
# Keyboard navigation
# ---------------------------------------------------------------------------

class TestMainMenuKeyboardNav:
    def test_down_arrow_advances_focus_index(self, menu):
        menu.handle_events([_keydown(pygame.K_DOWN)])
        assert menu._focus_idx == 1

    def test_s_key_advances_focus_index(self, menu):
        menu.handle_events([_keydown(pygame.K_s)])
        assert menu._focus_idx == 1

    def test_up_arrow_wraps_to_last_button(self, menu):
        # From index 0, moving up should wrap to the last button.
        menu.handle_events([_keydown(pygame.K_UP)])
        assert menu._focus_idx == len(menu._buttons) - 1

    def test_w_key_wraps_to_last_button(self, menu):
        menu.handle_events([_keydown(pygame.K_w)])
        assert menu._focus_idx == len(menu._buttons) - 1

    def test_down_then_up_returns_to_start(self, menu):
        menu.handle_events([_keydown(pygame.K_DOWN)])
        menu.handle_events([_keydown(pygame.K_UP)])
        assert menu._focus_idx == 0

    def test_down_cycles_through_all_buttons(self, menu):
        n = len(menu._buttons)
        for step in range(n):
            menu.handle_events([_keydown(pygame.K_DOWN)])
        assert menu._focus_idx == 0  # Back to start after full cycle

    def test_focus_moves_to_correct_button(self, menu):
        menu.handle_events([_keydown(pygame.K_DOWN)])
        assert menu._buttons[1]._focused is True
        assert menu._buttons[0]._focused is False

    def test_enter_activates_focused_button_start(self, menu, mock_sm):
        # Focus is on START GAME (index 0); pressing ENTER triggers _on_start.
        from src.scenes.game_scene import GameScene
        menu.handle_events([_keydown(pygame.K_RETURN)])
        mock_sm.replace.assert_called_once()
        passed_scene = mock_sm.replace.call_args[0][0]
        assert isinstance(passed_scene, GameScene)

    def test_space_activates_focused_button(self, menu, mock_sm):
        # Focus on START GAME → SPACE should also trigger.
        from src.scenes.game_scene import GameScene
        menu.handle_events([_keydown(pygame.K_SPACE)])
        mock_sm.replace.assert_called_once()
        passed_scene = mock_sm.replace.call_args[0][0]
        assert isinstance(passed_scene, GameScene)

    def test_enter_on_settings_button_pushes_settings_screen(self, menu, mock_sm):
        from src.scenes.settings_screen import SettingsScreen
        # Move focus to SETTINGS (index 1)
        menu.handle_events([_keydown(pygame.K_DOWN)])
        menu.handle_events([_keydown(pygame.K_RETURN)])
        mock_sm.push.assert_called_once()
        pushed = mock_sm.push.call_args[0][0]
        assert isinstance(pushed, SettingsScreen)


# ---------------------------------------------------------------------------
# Button callbacks
# ---------------------------------------------------------------------------

class TestMainMenuCallbacks:
    def test_on_start_calls_replace_with_game_scene(self, menu, mock_sm):
        from src.scenes.game_scene import GameScene
        menu._on_start()
        mock_sm.replace.assert_called_once()
        assert isinstance(mock_sm.replace.call_args[0][0], GameScene)

    def test_on_settings_calls_push_with_settings_screen(self, menu, mock_sm):
        from src.scenes.settings_screen import SettingsScreen
        menu._on_settings()
        mock_sm.push.assert_called_once()
        assert isinstance(mock_sm.push.call_args[0][0], SettingsScreen)

    def test_on_exit_calls_pygame_quit_and_sys_exit(self, menu):
        with patch("src.scenes.main_menu.pygame.quit") as mock_quit, \
             patch("src.scenes.main_menu.sys.exit") as mock_exit:
            menu._on_exit()
        mock_quit.assert_called_once()
        mock_exit.assert_called_once()

    def test_game_scene_created_with_same_settings(self, menu, mock_sm, settings):
        menu._on_start()
        created = mock_sm.replace.call_args[0][0]
        assert created._settings is settings

    def test_settings_screen_created_with_same_settings(self, menu, mock_sm, settings):
        menu._on_settings()
        created = mock_sm.push.call_args[0][0]
        assert created._settings is settings


# ---------------------------------------------------------------------------
# update / render
# ---------------------------------------------------------------------------

class TestMainMenuFrame:
    def test_update_does_not_raise(self, menu):
        menu.update(0.016)

    def test_update_large_dt_does_not_raise(self, menu):
        menu.update(1.0)

    def test_render_does_not_raise(self, menu, screen):
        menu.render(screen)

    def test_render_fills_background(self, menu, screen):
        """After render(), the screen must not be the default black Surface."""
        from src.constants import BG_DEEP
        menu.render(screen)
        # Sample a corner pixel — should be the deep background colour.
        assert screen.get_at((0, 0))[:3] == BG_DEEP

    def test_update_then_render_does_not_raise(self, menu, screen):
        menu.update(0.016)
        menu.render(screen)
