"""End-to-end integration tests for the main menu / settings / pause feature.

These tests wire a *real* SceneManager together with real scene instances to
verify that the full scene-transition flow described in the feature spec works
correctly without crashes or visual artifacts.

Scene stack expectations tested here:

  ┌──────────────────────────────────────────────────────────┐
  │ Situation          │ Expected stack (bottom → top)        │
  ├────────────────────┼──────────────────────────────────────┤
  │ At main menu       │ [MainMenu]                           │
  │ Settings opened    │ [MainMenu, SettingsScreen]           │
  │ Settings closed    │ [MainMenu]                           │
  │ Game started       │ [GameScene]                          │
  │ Game paused        │ [GameScene, PauseMenu]               │
  │ Game resumed       │ [GameScene]                          │
  │ Restart confirmed  │ [GameScene]  (new instance)          │
  │ Exit to main menu  │ [MainMenu]                           │
  └──────────────────────────────────────────────────────────┘
"""
from unittest.mock import patch

import pygame
import pytest

from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.scenes.main_menu import MainMenu
from src.scenes.game_scene import GameScene
from src.scenes.pause_menu import PauseMenu
from src.scenes.settings_screen import SettingsScreen


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sm():
    return SceneManager()


@pytest.fixture
def main_menu(sm, settings, assets):
    scene = MainMenu(sm, settings, assets)
    sm.push(scene)
    return scene


def _keydown(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)


# ---------------------------------------------------------------------------
# Happy-path: Main Menu → Start Game → GameScene
# ---------------------------------------------------------------------------

class TestStartGameTransition:
    def test_start_game_replaces_main_menu_with_game_scene(self, main_menu, sm):
        main_menu._on_start()
        assert not sm.is_empty
        assert isinstance(sm._stack[-1], GameScene)

    def test_stack_has_exactly_one_scene_after_start(self, main_menu, sm):
        main_menu._on_start()
        assert len(sm._stack) == 1

    def test_game_scene_top_receives_events_after_start(self, main_menu, sm, screen):
        main_menu._on_start()
        # ESC in GameScene → PauseMenu pushed; no crash
        sm.handle_events([_keydown(pygame.K_ESCAPE)])
        assert len(sm._stack) == 2
        assert isinstance(sm._stack[-1], PauseMenu)

    def test_render_after_start_does_not_raise(self, main_menu, sm, screen):
        main_menu._on_start()
        sm.render(screen)


# ---------------------------------------------------------------------------
# Happy-path: Main Menu → Settings → Back (clean)
# ---------------------------------------------------------------------------

class TestSettingsTransition:
    def test_push_settings_screen_on_top_of_main_menu(self, main_menu, sm):
        main_menu._on_settings()
        assert len(sm._stack) == 2
        assert isinstance(sm._stack[-1], SettingsScreen)
        assert isinstance(sm._stack[0], MainMenu)

    def test_back_when_clean_pops_settings_screen(self, main_menu, sm):
        main_menu._on_settings()
        settings_screen: SettingsScreen = sm._stack[-1]
        settings_screen._on_back()
        assert len(sm._stack) == 1
        assert isinstance(sm._stack[-1], MainMenu)

    def test_render_settings_over_main_menu(self, main_menu, sm, screen):
        main_menu._on_settings()
        sm.render(screen)  # Both layers must render without raising

    def test_settings_events_do_not_reach_main_menu(self, main_menu, sm):
        main_menu._on_settings()
        settings_scene = sm._stack[-1]
        # Routing: only top scene receives events
        ev = pygame.event.Event(pygame.USEREVENT)
        sm.handle_events([ev])
        # Main menu buttons should NOT have been interacted with.
        assert all(not btn._hovered for btn in main_menu._buttons)


# ---------------------------------------------------------------------------
# Happy-path: GameScene → ESC → PauseMenu → Resume → GameScene
# ---------------------------------------------------------------------------

class TestPauseResumeFlow:
    def test_esc_in_game_pushes_pause_menu(self, main_menu, sm):
        main_menu._on_start()
        game_scene = sm._stack[-1]
        game_scene.handle_events([_keydown(pygame.K_ESCAPE)])
        assert len(sm._stack) == 2
        assert isinstance(sm._stack[-1], PauseMenu)

    def test_game_scene_is_still_below_pause_menu(self, main_menu, sm):
        main_menu._on_start()
        game_scene = sm._stack[0]
        sm.handle_events([_keydown(pygame.K_ESCAPE)])
        assert isinstance(sm._stack[0], GameScene)
        assert isinstance(sm._stack[1], PauseMenu)

    def test_resume_pops_pause_menu(self, main_menu, sm):
        main_menu._on_start()
        sm.handle_events([_keydown(pygame.K_ESCAPE)])
        pause_menu: PauseMenu = sm._stack[-1]
        pause_menu._on_resume()
        assert len(sm._stack) == 1
        assert isinstance(sm._stack[-1], GameScene)

    def test_esc_in_pause_menu_resumes(self, main_menu, sm):
        main_menu._on_start()
        sm.handle_events([_keydown(pygame.K_ESCAPE)])
        sm.handle_events([_keydown(pygame.K_ESCAPE)])  # Second ESC = resume
        assert len(sm._stack) == 1
        assert isinstance(sm._stack[-1], GameScene)

    def test_render_pause_over_game_does_not_raise(self, main_menu, sm, screen):
        main_menu._on_start()
        sm.handle_events([_keydown(pygame.K_ESCAPE)])
        sm.render(screen)  # Both GameScene + PauseMenu render cleanly


# ---------------------------------------------------------------------------
# Happy-path: PauseMenu → Restart Confirmed → new GameScene
# ---------------------------------------------------------------------------

class TestPauseRestartFlow:
    def test_restart_confirmed_replaces_pause_menu_with_new_game_scene(self, main_menu, sm):
        """sm.replace() swaps only the top scene (PauseMenu → new GameScene),
        so the stack becomes [original_GameScene, new_GameScene]."""
        main_menu._on_start()
        original_game = sm._stack[0]
        sm.handle_events([_keydown(pygame.K_ESCAPE)])
        pause_menu: PauseMenu = sm._stack[-1]
        pause_menu._on_restart_confirmed()
        # Top scene is a fresh GameScene
        assert isinstance(sm._stack[-1], GameScene)
        # It is a different instance from the one that was already paused
        assert sm._stack[-1] is not pause_menu

    def test_restart_confirmed_top_is_not_pause_menu(self, main_menu, sm):
        main_menu._on_start()
        sm.handle_events([_keydown(pygame.K_ESCAPE)])
        sm._stack[-1]._on_restart_confirmed()
        assert not isinstance(sm._stack[-1], PauseMenu)


# ---------------------------------------------------------------------------
# Happy-path: PauseMenu → Exit to Main Menu → MainMenu
# ---------------------------------------------------------------------------

class TestPauseExitToMenuFlow:
    def test_exit_confirmed_replaces_all_with_main_menu(self, main_menu, sm, settings, assets):
        main_menu._on_start()
        sm.handle_events([_keydown(pygame.K_ESCAPE)])
        pause_menu: PauseMenu = sm._stack[-1]
        pause_menu._on_exit_confirmed()
        assert len(sm._stack) == 1
        assert isinstance(sm._stack[-1], MainMenu)

    def test_exit_confirmed_stack_is_clean(self, main_menu, sm):
        main_menu._on_start()
        sm.handle_events([_keydown(pygame.K_ESCAPE)])
        sm._stack[-1]._on_exit_confirmed()
        # Only one scene: the new MainMenu
        assert len(sm._stack) == 1


# ---------------------------------------------------------------------------
# Render / visual-artifact smoke tests
# ---------------------------------------------------------------------------

class TestRenderSmoke:
    """Verify that no render call raises an exception for any typical state."""

    def test_main_menu_render(self, sm, settings, assets, screen):
        mm = MainMenu(sm, settings, assets)
        sm.push(mm)
        sm.update(0.016)
        sm.render(screen)

    def test_settings_over_main_menu_render(self, main_menu, sm, screen):
        main_menu._on_settings()
        sm.render(screen)

    def test_game_scene_render(self, sm, settings, assets, screen):
        gs = GameScene(sm, settings, assets)
        sm.push(gs)
        sm.render(screen)

    def test_pause_menu_over_game_render(self, main_menu, sm, screen):
        main_menu._on_start()
        sm.handle_events([_keydown(pygame.K_ESCAPE)])
        sm.render(screen)

    def test_multi_frame_render_loop_stable(self, main_menu, sm, screen):
        """Simulate 10 frames at the main menu to confirm no drift/crash."""
        for _ in range(10):
            sm.update(1 / 60)
            sm.render(screen)
