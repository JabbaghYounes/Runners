"""Unit tests for src.scenes.game_scene.GameScene.

GameScene is an intentionally minimal stub; the tests verify its contract:
  - Renders a dark placeholder screen
  - ESC pushes a PauseMenu on top of the stack
  - update() is a no-op (no state change)
"""
from unittest.mock import MagicMock

import pygame
import pytest

from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.scenes.game_scene import GameScene


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_sm():
    return MagicMock(spec=SceneManager)


@pytest.fixture
def game_scene(mock_sm, settings, assets):
    return GameScene(mock_sm, settings, assets)


def _keydown(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestGameSceneConstruction:
    def test_instantiation_does_not_raise(self, game_scene):
        assert game_scene is not None

    def test_stores_scene_manager(self, game_scene, mock_sm):
        assert game_scene._sm is mock_sm

    def test_stores_settings(self, game_scene, settings):
        assert game_scene._settings is settings

    def test_stores_asset_manager(self, game_scene, assets):
        assert game_scene._assets is assets


# ---------------------------------------------------------------------------
# handle_events — ESC key
# ---------------------------------------------------------------------------

class TestGameSceneESC:
    def test_esc_key_pushes_pause_menu(self, game_scene, mock_sm):
        from src.scenes.pause_menu import PauseMenu
        game_scene.handle_events([_keydown(pygame.K_ESCAPE)])
        mock_sm.push.assert_called_once()
        pushed = mock_sm.push.call_args[0][0]
        assert isinstance(pushed, PauseMenu)

    def test_esc_pause_menu_receives_same_settings(self, game_scene, mock_sm, settings):
        game_scene.handle_events([_keydown(pygame.K_ESCAPE)])
        pushed = mock_sm.push.call_args[0][0]
        assert pushed._settings is settings

    def test_esc_pause_menu_receives_same_scene_manager(self, game_scene, mock_sm):
        game_scene.handle_events([_keydown(pygame.K_ESCAPE)])
        pushed = mock_sm.push.call_args[0][0]
        assert pushed._sm is mock_sm

    def test_only_one_push_per_esc_event(self, game_scene, mock_sm):
        """A single ESC event should push exactly one PauseMenu."""
        game_scene.handle_events([_keydown(pygame.K_ESCAPE)])
        assert mock_sm.push.call_count == 1

    def test_non_esc_key_does_not_push(self, game_scene, mock_sm):
        game_scene.handle_events([_keydown(pygame.K_w)])
        mock_sm.push.assert_not_called()

    def test_empty_events_do_not_push(self, game_scene, mock_sm):
        game_scene.handle_events([])
        mock_sm.push.assert_not_called()

    def test_multiple_non_esc_events_do_not_push(self, game_scene, mock_sm):
        events = [
            _keydown(pygame.K_a),
            _keydown(pygame.K_s),
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 100), button=1),
        ]
        game_scene.handle_events(events)
        mock_sm.push.assert_not_called()


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

class TestGameSceneUpdate:
    def test_update_does_not_raise(self, game_scene):
        game_scene.update(0.016)

    def test_update_with_large_dt_does_not_raise(self, game_scene):
        game_scene.update(1.0)

    def test_update_with_zero_dt_does_not_raise(self, game_scene):
        game_scene.update(0.0)

    def test_update_does_not_push_any_scene(self, game_scene, mock_sm):
        game_scene.update(0.016)
        mock_sm.push.assert_not_called()
        mock_sm.pop.assert_not_called()
        mock_sm.replace.assert_not_called()


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

class TestGameSceneRender:
    def test_render_does_not_raise(self, game_scene, screen):
        game_scene.render(screen)

    def test_render_fills_deep_background(self, game_scene, screen):
        from src.constants import BG_DEEP
        game_scene.render(screen)
        assert screen.get_at((0, 0))[:3] == BG_DEEP

    def test_render_after_update_does_not_raise(self, game_scene, screen):
        game_scene.update(0.016)
        game_scene.render(screen)
