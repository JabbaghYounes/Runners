"""Unit tests for src.scenes.settings_screen.SettingsScreen.

The SceneManager is mocked so pop/push calls can be asserted without a
running game loop.  Settings.save is monkey-patched to prevent disk writes.
"""
from unittest.mock import MagicMock, patch

import pygame
import pytest

from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.scenes.settings_screen import SettingsScreen, _res_idx, _RESOLUTIONS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_sm():
    return MagicMock(spec=SceneManager)


@pytest.fixture
def ss(mock_sm, settings, assets):
    """A freshly constructed SettingsScreen with a mock SceneManager."""
    return SettingsScreen(mock_sm, settings, assets)


def _keydown(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)


# ---------------------------------------------------------------------------
# Module-level helper: _res_idx
# ---------------------------------------------------------------------------

class TestResIdx:
    def test_returns_zero_for_1280x720(self):
        assert _res_idx([1280, 720]) == 0

    def test_returns_one_for_1600x900(self):
        assert _res_idx([1600, 900]) == 1

    def test_returns_two_for_1920x1080(self):
        assert _res_idx([1920, 1080]) == 2

    def test_returns_zero_for_unknown_resolution(self):
        assert _res_idx([1024, 768]) == 0

    def test_float_values_are_handled(self):
        assert _res_idx([1280.0, 720.0]) == 0


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestSettingsScreenConstruction:
    def test_instantiation_does_not_raise(self, ss):
        assert ss is not None

    def test_dirty_flag_false_on_init(self, ss):
        assert ss._dirty is False

    def test_local_master_matches_settings(self, ss, settings):
        assert ss._local_master == pytest.approx(settings.master_volume)

    def test_local_music_matches_settings(self, ss, settings):
        assert ss._local_music == pytest.approx(settings.music_volume)

    def test_local_sfx_matches_settings(self, ss, settings):
        assert ss._local_sfx == pytest.approx(settings.sfx_volume)

    def test_local_fullscreen_matches_settings(self, ss, settings):
        assert ss._local_fullscreen == settings.fullscreen

    def test_local_res_idx_matches_settings(self, ss, settings):
        expected = _res_idx(settings.resolution)
        assert ss._local_res_idx == expected

    def test_confirm_dialog_inactive_on_init(self, ss):
        assert ss._confirm.active is False

    def test_three_sliders_created(self, ss):
        assert len(ss._sliders) == 3


# ---------------------------------------------------------------------------
# Slider callbacks — dirty flag
# ---------------------------------------------------------------------------

class TestSettingsScreenDirtyFlag:
    def test_on_master_sets_dirty(self, ss):
        ss._on_master(0.5)
        assert ss._dirty is True

    def test_on_master_updates_local_value(self, ss):
        ss._on_master(0.3)
        assert ss._local_master == pytest.approx(0.3)

    def test_on_music_sets_dirty(self, ss):
        ss._on_music(0.4)
        assert ss._dirty is True

    def test_on_music_updates_local_value(self, ss):
        ss._on_music(0.2)
        assert ss._local_music == pytest.approx(0.2)

    def test_on_sfx_sets_dirty(self, ss):
        ss._on_sfx(0.9)
        assert ss._dirty is True

    def test_on_sfx_updates_local_value(self, ss):
        ss._on_sfx(0.1)
        assert ss._local_sfx == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# Display controls
# ---------------------------------------------------------------------------

class TestSettingsScreenDisplayControls:
    def test_cycle_resolution_advances_index(self, ss):
        initial = ss._local_res_idx
        ss._cycle_resolution()
        assert ss._local_res_idx == (initial + 1) % len(_RESOLUTIONS)

    def test_cycle_resolution_wraps_around(self, ss):
        ss._local_res_idx = len(_RESOLUTIONS) - 1
        ss._cycle_resolution()
        assert ss._local_res_idx == 0

    def test_cycle_resolution_sets_dirty(self, ss):
        ss._cycle_resolution()
        assert ss._dirty is True

    def test_cycle_resolution_updates_button_text(self, ss):
        ss._local_res_idx = 0
        ss._cycle_resolution()
        expected = _RESOLUTIONS[1]
        assert ss._btn_res.text == f"{expected[0]} × {expected[1]}"

    def test_toggle_fullscreen_flips_flag(self, ss):
        initial = ss._local_fullscreen
        ss._toggle_fullscreen()
        assert ss._local_fullscreen is not initial

    def test_toggle_fullscreen_twice_restores_flag(self, ss):
        initial = ss._local_fullscreen
        ss._toggle_fullscreen()
        ss._toggle_fullscreen()
        assert ss._local_fullscreen == initial

    def test_toggle_fullscreen_sets_dirty(self, ss):
        ss._toggle_fullscreen()
        assert ss._dirty is True

    def test_toggle_fullscreen_updates_button_text_to_on(self, ss):
        ss._local_fullscreen = False
        ss._toggle_fullscreen()
        assert ss._btn_fs.text == "ON"

    def test_toggle_fullscreen_updates_button_text_to_off(self, ss):
        ss._local_fullscreen = True
        ss._toggle_fullscreen()
        assert ss._btn_fs.text == "OFF"


# ---------------------------------------------------------------------------
# Back / Discard
# ---------------------------------------------------------------------------

class TestSettingsScreenBack:
    def test_on_back_when_clean_pops_scene(self, ss, mock_sm):
        assert not ss._dirty
        ss._on_back()
        mock_sm.pop.assert_called_once()

    def test_on_back_when_dirty_shows_confirm_dialog(self, ss):
        ss._dirty = True
        ss._on_back()
        assert ss._confirm.active is True

    def test_on_back_when_dirty_does_not_pop(self, ss, mock_sm):
        ss._dirty = True
        ss._on_back()
        mock_sm.pop.assert_not_called()

    def test_esc_key_triggers_back_when_clean(self, ss, mock_sm):
        ss.handle_events([_keydown(pygame.K_ESCAPE)])
        mock_sm.pop.assert_called_once()

    def test_esc_key_shows_confirm_dialog_when_dirty(self, ss):
        ss._dirty = True
        ss.handle_events([_keydown(pygame.K_ESCAPE)])
        assert ss._confirm.active is True

    def test_discard_and_pop_hides_dialog_and_pops(self, ss, mock_sm):
        ss._dirty = True
        ss._on_back()                    # Opens dialog
        ss._discard_and_pop()
        assert ss._confirm.active is False
        mock_sm.pop.assert_called_once()


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

class TestSettingsScreenApply:
    def test_apply_writes_master_volume_to_settings(self, ss, mock_sm):
        ss._local_master = 0.25
        with patch.object(ss._settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert ss._settings.master_volume == pytest.approx(0.25)

    def test_apply_writes_music_volume_to_settings(self, ss, mock_sm):
        ss._local_music = 0.15
        with patch.object(ss._settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert ss._settings.music_volume == pytest.approx(0.15)

    def test_apply_writes_sfx_volume_to_settings(self, ss, mock_sm):
        ss._local_sfx = 0.65
        with patch.object(ss._settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert ss._settings.sfx_volume == pytest.approx(0.65)

    def test_apply_writes_resolution_to_settings(self, ss, mock_sm):
        ss._local_res_idx = 2          # 1920 × 1080
        with patch.object(ss._settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert ss._settings.resolution == [1920, 1080]

    def test_apply_writes_fullscreen_to_settings(self, ss, mock_sm):
        ss._local_fullscreen = True
        with patch.object(ss._settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert ss._settings.fullscreen is True

    def test_apply_calls_pop(self, ss, mock_sm):
        with patch.object(ss._settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        mock_sm.pop.assert_called_once()

    def test_apply_calls_settings_save(self, ss, mock_sm):
        with patch.object(ss._settings, "save") as mock_save, \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# update / render
# ---------------------------------------------------------------------------

class TestSettingsScreenFrame:
    def test_update_does_not_raise(self, ss):
        ss.update(0.016)

    def test_render_does_not_raise(self, ss, screen):
        ss.render(screen)

    def test_render_with_active_confirm_does_not_raise(self, ss, screen):
        ss._dirty = True
        ss._on_back()                   # Activates the confirm dialog
        ss.render(screen)

    def test_confirm_dialog_swallows_events_while_active(self, ss, mock_sm):
        """When the confirm dialog is active, ESC should not pop the scene."""
        ss._dirty = True
        ss._on_back()                   # Opens confirm
        ss.handle_events([_keydown(pygame.K_ESCAPE)])
        mock_sm.pop.assert_not_called()
