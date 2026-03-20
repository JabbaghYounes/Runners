"""Unit tests for src.scenes.pause_menu.PauseMenu.

# Run: pytest tests/scenes/test_pause_menu.py

Covers:
  - Construction and initial state
  - RESUME (button + ESC key) → sm.pop()
  - RESTART → shows confirm dialog → sm.replace_all(GameScene)
  - EXIT TO MENU → shows confirm dialog → sm.replace_all(MainMenu)
  - Confirm dialogs swallow events while active
  - update / render smoke tests
"""
from unittest.mock import MagicMock

import pygame
import pytest

# Ensure pygame (including pygame.font) is initialised before any fixture
# or test in this module attempts to construct UI widgets.
pygame.init()
pygame.display.set_mode((1, 1))

from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.scenes.pause_menu import PauseMenu


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_sm():
    return MagicMock(spec=SceneManager)


@pytest.fixture
def pause_menu(mock_sm, settings, assets):
    return PauseMenu(mock_sm, settings, assets)


def _keydown(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)


def _click_at(x, y):
    return [
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=1),
        pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x, y), button=1),
    ]


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestPauseMenuConstruction:
    def test_instantiation_does_not_raise(self, pause_menu):
        assert pause_menu is not None

    def test_stores_scene_manager(self, pause_menu, mock_sm):
        assert pause_menu._sm is mock_sm

    def test_stores_settings(self, pause_menu, settings):
        assert pause_menu._settings is settings

    def test_restart_confirm_inactive_on_init(self, pause_menu):
        assert pause_menu._confirm_restart.active is False

    def test_exit_confirm_inactive_on_init(self, pause_menu):
        assert pause_menu._confirm_exit.active is False

    def test_vignette_surface_created(self, pause_menu):
        assert pause_menu._vignette is not None
        assert isinstance(pause_menu._vignette, pygame.Surface)

    def test_vignette_covers_full_screen(self, pause_menu):
        from src.constants import SCREEN_W, SCREEN_H
        w, h = pause_menu._vignette.get_size()
        assert w == SCREEN_W
        assert h == SCREEN_H


# ---------------------------------------------------------------------------
# RESUME
# ---------------------------------------------------------------------------

class TestPauseMenuResume:
    def test_on_resume_calls_pop(self, pause_menu, mock_sm):
        pause_menu._on_resume()
        mock_sm.pop.assert_called_once()

    def test_esc_key_calls_pop(self, pause_menu, mock_sm):
        pause_menu.handle_events([_keydown(pygame.K_ESCAPE)])
        mock_sm.pop.assert_called_once()

    def test_esc_key_does_not_pop_when_restart_confirm_active(self, pause_menu, mock_sm):
        pause_menu._confirm_restart.show((1280, 720))
        pause_menu.handle_events([_keydown(pygame.K_ESCAPE)])
        mock_sm.pop.assert_not_called()

    def test_esc_key_does_not_pop_when_exit_confirm_active(self, pause_menu, mock_sm):
        pause_menu._confirm_exit.show((1280, 720))
        pause_menu.handle_events([_keydown(pygame.K_ESCAPE)])
        mock_sm.pop.assert_not_called()


# ---------------------------------------------------------------------------
# RESTART
# ---------------------------------------------------------------------------

class TestPauseMenuRestart:
    def test_on_restart_shows_confirm_dialog(self, pause_menu):
        pause_menu._on_restart()
        assert pause_menu._confirm_restart.active is True

    def test_on_restart_does_not_immediately_replace(self, pause_menu, mock_sm):
        pause_menu._on_restart()
        mock_sm.replace.assert_not_called()

    def test_on_restart_confirmed_calls_replace_all_with_game_scene(self, pause_menu, mock_sm):
        from src.scenes.game_scene import GameScene
        pause_menu._on_restart_confirmed()
        mock_sm.replace_all.assert_called_once()
        replaced = mock_sm.replace_all.call_args[0][0]
        assert isinstance(replaced, GameScene)

    def test_on_restart_confirmed_hides_dialog(self, pause_menu):
        pause_menu._confirm_restart.show((1280, 720))
        pause_menu._on_restart_confirmed()
        assert pause_menu._confirm_restart.active is False

    def test_restart_game_scene_has_same_settings(self, pause_menu, mock_sm, settings):
        pause_menu._on_restart_confirmed()
        created = mock_sm.replace_all.call_args[0][0]
        assert created._settings is settings

    def test_restart_game_scene_has_same_scene_manager(self, pause_menu, mock_sm):
        pause_menu._on_restart_confirmed()
        created = mock_sm.replace_all.call_args[0][0]
        assert created._sm is mock_sm


# ---------------------------------------------------------------------------
# EXIT TO MENU
# ---------------------------------------------------------------------------

class TestPauseMenuExitToMenu:
    def test_on_exit_shows_exit_confirm_dialog(self, pause_menu):
        pause_menu._on_exit()
        assert pause_menu._confirm_exit.active is True

    def test_on_exit_does_not_immediately_replace_all(self, pause_menu, mock_sm):
        pause_menu._on_exit()
        mock_sm.replace_all.assert_not_called()

    def test_on_exit_confirmed_calls_replace_all_with_main_menu(self, pause_menu, mock_sm):
        from src.scenes.main_menu import MainMenu
        pause_menu._on_exit_confirmed()
        mock_sm.replace_all.assert_called_once()
        replaced = mock_sm.replace_all.call_args[0][0]
        assert isinstance(replaced, MainMenu)

    def test_on_exit_confirmed_hides_dialog(self, pause_menu):
        pause_menu._confirm_exit.show((1280, 720))
        pause_menu._on_exit_confirmed()
        assert pause_menu._confirm_exit.active is False

    def test_exit_main_menu_has_same_settings(self, pause_menu, mock_sm, settings):
        pause_menu._on_exit_confirmed()
        created = mock_sm.replace_all.call_args[0][0]
        assert created._settings is settings

    def test_exit_main_menu_has_same_scene_manager(self, pause_menu, mock_sm):
        pause_menu._on_exit_confirmed()
        created = mock_sm.replace_all.call_args[0][0]
        assert created._sm is mock_sm


# ---------------------------------------------------------------------------
# Confirm dialog event-swallowing
# ---------------------------------------------------------------------------

class TestPauseMenuConfirmDialogs:
    def test_restart_dialog_swallows_resume_button_click(self, pause_menu, mock_sm):
        """While the restart confirm dialog is active, clicking the RESUME
        button coordinates should not call pop()."""
        pause_menu._confirm_restart.show((1280, 720))
        # Click somewhere other than the confirm dialog buttons — the dialog
        # should still swallow the event.
        pause_menu.handle_events(_click_at(640, 10))
        mock_sm.pop.assert_not_called()

    def test_exit_dialog_swallows_events(self, pause_menu, mock_sm):
        pause_menu._confirm_exit.show((1280, 720))
        pause_menu.handle_events(_click_at(100, 100))
        mock_sm.pop.assert_not_called()
        mock_sm.replace_all.assert_not_called()

    def test_no_dialog_active_escape_resumes(self, pause_menu, mock_sm):
        assert not pause_menu._confirm_restart.active
        assert not pause_menu._confirm_exit.active
        pause_menu.handle_events([_keydown(pygame.K_ESCAPE)])
        mock_sm.pop.assert_called_once()


# ---------------------------------------------------------------------------
# update / render
# ---------------------------------------------------------------------------

class TestPauseMenuFrame:
    def test_update_does_not_raise(self, pause_menu):
        pause_menu.update(0.016)

    def test_update_does_not_affect_scene_manager(self, pause_menu, mock_sm):
        pause_menu.update(0.016)
        mock_sm.pop.assert_not_called()
        mock_sm.push.assert_not_called()

    def test_render_does_not_raise(self, pause_menu, screen):
        pause_menu.render(screen)

    def test_render_with_restart_confirm_active(self, pause_menu, screen):
        pause_menu._confirm_restart.show((1280, 720))
        pause_menu.render(screen)

    def test_render_with_exit_confirm_active(self, pause_menu, screen):
        pause_menu._confirm_exit.show((1280, 720))
        pause_menu.render(screen)

    def test_update_then_render_does_not_raise(self, pause_menu, screen):
        pause_menu.update(0.016)
        pause_menu.render(screen)
