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
from src.scenes.settings_screen import (
    SettingsScreen,
    _res_idx,
    _fps_idx,
    _fmt_action,
    _RESOLUTIONS,
    _FPS_PRESETS,
)


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


# ---------------------------------------------------------------------------
# Module-level helper: _fps_idx
# ---------------------------------------------------------------------------

class TestFpsIdxHelper:
    def test_returns_0_for_30fps(self):
        assert _fps_idx(30) == 0

    def test_returns_1_for_60fps(self):
        assert _fps_idx(60) == 1

    def test_returns_2_for_120fps(self):
        assert _fps_idx(120) == 2

    def test_returns_3_for_144fps(self):
        assert _fps_idx(144) == 3

    def test_returns_4_for_240fps(self):
        assert _fps_idx(240) == 4

    def test_returns_1_for_unknown_fps(self):
        """Unknown FPS defaults to the 60-fps slot (index 1)."""
        assert _fps_idx(999) == 1

    def test_returns_1_for_zero(self):
        assert _fps_idx(0) == 1

    def test_all_presets_round_trip(self):
        for i, fps in enumerate(_FPS_PRESETS):
            assert _fps_idx(fps) == i


# ---------------------------------------------------------------------------
# Module-level helper: _fmt_action
# ---------------------------------------------------------------------------

class TestFmtActionHelper:
    def test_single_word_title_cased(self):
        assert _fmt_action("jump") == "Jump"

    def test_underscore_replaced_by_space(self):
        assert _fmt_action("move_left") == "Move Left"

    def test_two_underscores_become_two_spaces(self):
        assert _fmt_action("move_right") == "Move Right"

    def test_action_with_no_underscore(self):
        assert _fmt_action("reload") == "Reload"

    def test_empty_string_returns_empty_string(self):
        assert _fmt_action("") == ""

    def test_all_actions_produce_non_empty_strings(self):
        from src.constants import KEY_BINDINGS
        for action in KEY_BINDINGS:
            assert _fmt_action(action) != ""


# ---------------------------------------------------------------------------
# Snapshot field initialization
# ---------------------------------------------------------------------------

class TestSettingsScreenSnapshots:
    def test_snap_fps_idx_matches_initial_local_fps_idx(self, ss):
        assert ss._snap_fps_idx == ss._local_fps_idx

    def test_snap_res_idx_matches_initial_local_res_idx(self, ss):
        assert ss._snap_res_idx == ss._local_res_idx

    def test_snap_fullscreen_matches_initial_local_fullscreen(self, ss):
        assert ss._snap_fullscreen == ss._local_fullscreen

    def test_snap_bindings_matches_initial_local_bindings(self, ss):
        assert ss._snap_bindings == ss._local_bindings

    def test_snap_bindings_is_independent_copy(self, ss):
        """Mutating _local_bindings must not affect the snapshot."""
        original_snap = dict(ss._snap_bindings)
        first_action = next(iter(ss._local_bindings))
        ss._local_bindings[first_action] = pygame.K_z
        assert ss._snap_bindings == original_snap

    def test_snap_master_equals_local_master_on_init(self, ss):
        assert ss._snap_master == pytest.approx(ss._local_master)

    def test_snap_music_equals_local_music_on_init(self, ss):
        assert ss._snap_music == pytest.approx(ss._local_music)

    def test_snap_sfx_equals_local_sfx_on_init(self, ss):
        assert ss._snap_sfx == pytest.approx(ss._local_sfx)


# ---------------------------------------------------------------------------
# FPS cycle — modal mode (widgets are available)
# ---------------------------------------------------------------------------

class TestSettingsScreenFpsCycleModal:
    def test_btn_fps_initial_text_matches_local_fps(self, ss):
        expected = str(_FPS_PRESETS[ss._local_fps_idx])
        assert ss._btn_fps.text == expected

    def test_cycle_fps_updates_button_text_to_next_preset(self, ss):
        initial_idx = ss._local_fps_idx
        ss._cycle_fps()
        expected_idx = (initial_idx + 1) % len(_FPS_PRESETS)
        assert ss._btn_fps.text == str(_FPS_PRESETS[expected_idx])

    def test_btn_fps_text_is_numeric_string_after_cycle(self, ss):
        ss._cycle_fps()
        assert ss._btn_fps.text.isdigit()

    def test_cycle_fps_wraps_button_text_back_to_first(self, ss):
        for _ in range(len(_FPS_PRESETS)):
            ss._cycle_fps()
        # After a full cycle, button text reflects the wrapped index
        assert ss._btn_fps.text == str(_FPS_PRESETS[ss._local_fps_idx])

    def test_apply_writes_fps_to_settings_in_modal_mode(self, ss, settings, mock_sm):
        ss._local_fps_idx = 0           # force 30 fps
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert settings.target_fps == _FPS_PRESETS[0]

    def test_apply_fps_matches_idx_after_two_cycles(self, ss, settings, mock_sm):
        initial_idx = ss._local_fps_idx
        ss._cycle_fps()
        ss._cycle_fps()
        expected_idx = (initial_idx + 2) % len(_FPS_PRESETS)
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert settings.target_fps == _FPS_PRESETS[expected_idx]


# ---------------------------------------------------------------------------
# Key binding rows — widget creation and content
# ---------------------------------------------------------------------------

class TestSettingsScreenKeyBindingRows:
    def test_binding_row_button_count_matches_local_bindings(self, ss):
        assert len(ss._btn_binding_rows) == len(ss._local_bindings)

    def test_binding_row_label_count_matches_local_bindings(self, ss):
        assert len(ss._lbl_binding_rows) == len(ss._local_bindings)

    def test_at_least_one_binding_row_created(self, ss):
        assert len(ss._btn_binding_rows) > 0

    def test_each_row_label_text_matches_formatted_action_name(self, ss):
        for i, action in enumerate(ss._local_bindings):
            expected = _fmt_action(action)
            assert ss._lbl_binding_rows[i].text == expected

    def test_each_row_button_text_matches_pygame_key_name(self, ss):
        for i, (action, keycode) in enumerate(ss._local_bindings.items()):
            expected = pygame.key.name(keycode)
            assert ss._btn_binding_rows[i].text == expected

    def test_key_labels_alias_points_to_lbl_binding_rows(self, ss):
        """_key_labels is kept for render compatibility; must alias binding rows."""
        assert ss._key_labels is ss._lbl_binding_rows


# ---------------------------------------------------------------------------
# Rebind FSM — modal mode (clicking a row activates rebind prompt)
# ---------------------------------------------------------------------------

class TestSettingsScreenRebindActivationModal:
    def _first_action_and_index(self, ss):
        action = next(iter(ss._local_bindings))
        return action, 0

    def test_awaiting_action_is_none_before_any_click(self, ss):
        assert ss._awaiting_action is None

    def test_make_rebind_callback_sets_awaiting_action(self, ss):
        action, idx = self._first_action_and_index(ss)
        ss._make_rebind_callback(action, idx)()
        assert ss._awaiting_action == action

    def test_make_rebind_callback_changes_button_text_to_prompt(self, ss):
        action, idx = self._first_action_and_index(ss)
        ss._make_rebind_callback(action, idx)()
        btn_text = ss._btn_binding_rows[idx].text
        # The prompt contains "key" or the ellipsis character
        assert "key" in btn_text.lower() or "\u2026" in btn_text

    def test_keydown_while_awaiting_stores_new_key_in_local_bindings(self, ss):
        action, idx = self._first_action_and_index(ss)
        ss._make_rebind_callback(action, idx)()
        ss.handle_events([_keydown(pygame.K_z)])
        assert ss._local_bindings[action] == pygame.K_z

    def test_keydown_while_awaiting_clears_awaiting_action(self, ss):
        action, idx = self._first_action_and_index(ss)
        ss._make_rebind_callback(action, idx)()
        ss.handle_events([_keydown(pygame.K_z)])
        assert ss._awaiting_action is None

    def test_keydown_while_awaiting_marks_dirty(self, ss):
        action, idx = self._first_action_and_index(ss)
        ss._make_rebind_callback(action, idx)()
        ss.handle_events([_keydown(pygame.K_z)])
        assert ss._dirty is True

    def test_keydown_while_awaiting_updates_row_button_text(self, ss):
        action, idx = self._first_action_and_index(ss)
        ss._make_rebind_callback(action, idx)()
        ss.handle_events([_keydown(pygame.K_z)])
        assert ss._btn_binding_rows[idx].text == pygame.key.name(pygame.K_z)

    def test_esc_while_awaiting_restores_original_button_text(self, ss):
        action, idx = self._first_action_and_index(ss)
        original_key = ss._local_bindings[action]
        ss._make_rebind_callback(action, idx)()    # activates "Press key…"
        ss.handle_events([_keydown(pygame.K_ESCAPE)])
        assert ss._btn_binding_rows[idx].text == pygame.key.name(original_key)

    def test_esc_while_awaiting_clears_awaiting_action(self, ss):
        action, idx = self._first_action_and_index(ss)
        ss._make_rebind_callback(action, idx)()
        ss.handle_events([_keydown(pygame.K_ESCAPE)])
        assert ss._awaiting_action is None

    def test_esc_while_awaiting_does_not_pop(self, ss, mock_sm):
        action, idx = self._first_action_and_index(ss)
        ss._make_rebind_callback(action, idx)()
        ss.handle_events([_keydown(pygame.K_ESCAPE)])
        mock_sm.pop.assert_not_called()


# ---------------------------------------------------------------------------
# Fixture: restore src.constants.KEY_BINDINGS after each test that mutates it
# ---------------------------------------------------------------------------

@pytest.fixture()
def restore_key_bindings():
    import src.constants as _C
    original = dict(_C.KEY_BINDINGS)
    yield
    _C.KEY_BINDINGS.clear()
    _C.KEY_BINDINGS.update(original)


# ---------------------------------------------------------------------------
# Apply — FPS and key binding persistence in modal mode
# ---------------------------------------------------------------------------

class TestSettingsScreenApplyFull:
    def test_apply_writes_fps_to_settings(self, ss, settings, mock_sm):
        ss._local_fps_idx = 0           # 30 fps
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert settings.target_fps == _FPS_PRESETS[0]

    def test_apply_writes_key_bindings_to_settings(
        self, ss, settings, mock_sm, restore_key_bindings
    ):
        ss._local_bindings["jump"] = pygame.K_j
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert settings.key_bindings.get("jump") == pygame.K_j

    def test_apply_writes_complete_bindings_dict_to_settings(
        self, ss, settings, mock_sm, restore_key_bindings
    ):
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert settings.key_bindings == ss._local_bindings

    def test_apply_syncs_constants_key_bindings(
        self, ss, settings, mock_sm, restore_key_bindings
    ):
        import src.constants as _C
        ss._local_bindings["jump"] = pygame.K_j
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert _C.KEY_BINDINGS.get("jump") == pygame.K_j

    def test_apply_constants_sync_reflects_all_local_bindings(
        self, ss, settings, mock_sm, restore_key_bindings
    ):
        """Every key in _local_bindings must appear correctly in KEY_BINDINGS."""
        import src.constants as _C
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        for action, keycode in ss._local_bindings.items():
            assert _C.KEY_BINDINGS.get(action) == keycode


# ---------------------------------------------------------------------------
# Apply — restart banner when display settings change
# ---------------------------------------------------------------------------

class TestSettingsScreenApplyDisplayChange:
    def test_no_restart_banner_when_display_unchanged(self, ss, settings, mock_sm):
        ss._local_res_idx = ss._snap_res_idx
        ss._local_fullscreen = ss._snap_fullscreen
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert ss._lbl_restart.text == ""

    def test_restart_banner_shown_when_resolution_changes(self, ss, settings, mock_sm):
        ss._local_res_idx = (ss._snap_res_idx + 1) % len(_RESOLUTIONS)
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert ss._lbl_restart.text != ""

    def test_restart_banner_contains_restart_keyword(self, ss, settings, mock_sm):
        ss._local_res_idx = (ss._snap_res_idx + 1) % len(_RESOLUTIONS)
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert "restart" in ss._lbl_restart.text.lower()

    def test_restart_timer_positive_when_resolution_changes(self, ss, settings, mock_sm):
        ss._local_res_idx = (ss._snap_res_idx + 1) % len(_RESOLUTIONS)
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert ss._restart_timer > 0.0

    def test_restart_timer_is_three_seconds_when_resolution_changes(
        self, ss, settings, mock_sm
    ):
        ss._local_res_idx = (ss._snap_res_idx + 1) % len(_RESOLUTIONS)
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert ss._restart_timer == pytest.approx(3.0)

    def test_restart_banner_shown_when_fullscreen_changes(self, ss, settings, mock_sm):
        ss._local_fullscreen = not ss._snap_fullscreen
        with patch.object(settings, "save"), \
             patch("src.scenes.settings_screen.pygame.display.set_mode"):
            ss._on_apply()
        assert ss._lbl_restart.text != ""


# ---------------------------------------------------------------------------
# Apply — display mode failure recovery
# ---------------------------------------------------------------------------

class TestSettingsScreenApplyDisplayFailure:
    def _apply_with_set_mode_failure(self, ss, settings):
        with patch.object(settings, "save"), \
             patch(
                 "src.scenes.settings_screen.pygame.display.set_mode",
                 side_effect=Exception("unsupported mode"),
             ):
            ss._on_apply()

    def test_no_pop_when_set_mode_raises(self, ss, settings, mock_sm):
        ss._local_res_idx = (ss._snap_res_idx + 1) % len(_RESOLUTIONS)
        self._apply_with_set_mode_failure(ss, settings)
        mock_sm.pop.assert_not_called()

    def test_settings_resolution_reverted_to_original(self, ss, settings, mock_sm):
        original_res = list(settings.resolution)
        ss._local_res_idx = (ss._snap_res_idx + 1) % len(_RESOLUTIONS)
        self._apply_with_set_mode_failure(ss, settings)
        assert settings.resolution == original_res

    def test_settings_fullscreen_reverted_to_original(self, ss, settings, mock_sm):
        original_fs = settings.fullscreen
        ss._local_fullscreen = not ss._snap_fullscreen
        self._apply_with_set_mode_failure(ss, settings)
        assert settings.fullscreen == original_fs

    def test_btn_res_text_reverted_to_original(self, ss, settings, mock_sm):
        original_res = _RESOLUTIONS[ss._snap_res_idx]
        ss._local_res_idx = (ss._snap_res_idx + 1) % len(_RESOLUTIONS)
        self._apply_with_set_mode_failure(ss, settings)
        expected = f"{original_res[0]} \u00d7 {original_res[1]}"
        assert ss._btn_res.text == expected

    def test_btn_fs_text_reverted_to_original(self, ss, settings, mock_sm):
        original_fs = ss._snap_fullscreen
        ss._local_fullscreen = not original_fs
        self._apply_with_set_mode_failure(ss, settings)
        assert ss._btn_fs.text == ("ON" if original_fs else "OFF")

    def test_conflict_label_set_to_nonempty_on_failure(self, ss, settings, mock_sm):
        ss._local_res_idx = (ss._snap_res_idx + 1) % len(_RESOLUTIONS)
        self._apply_with_set_mode_failure(ss, settings)
        assert ss._lbl_conflict.text != ""

    def test_conflict_label_describes_unsupported_mode(self, ss, settings, mock_sm):
        ss._local_res_idx = (ss._snap_res_idx + 1) % len(_RESOLUTIONS)
        self._apply_with_set_mode_failure(ss, settings)
        assert "supported" in ss._lbl_conflict.text.lower()

    def test_conflict_timer_positive_on_failure(self, ss, settings, mock_sm):
        ss._local_res_idx = (ss._snap_res_idx + 1) % len(_RESOLUTIONS)
        self._apply_with_set_mode_failure(ss, settings)
        assert ss._conflict_timer > 0.0


# ---------------------------------------------------------------------------
# Timer update — restart and conflict labels clear after countdown
# ---------------------------------------------------------------------------

class TestSettingsScreenTimers:
    def test_restart_timer_decrements_by_dt(self, ss):
        ss._restart_timer = 2.0
        ss.update(0.5)
        assert ss._restart_timer == pytest.approx(1.5)

    def test_restart_timer_clamps_to_zero_on_large_dt(self, ss):
        ss._restart_timer = 0.1
        ss.update(100.0)
        assert ss._restart_timer == 0.0

    def test_restart_timer_never_goes_negative(self, ss):
        ss._restart_timer = 1.0
        ss.update(9999.0)
        assert ss._restart_timer >= 0.0

    def test_restart_label_clears_when_timer_hits_zero(self, ss):
        ss._restart_timer = 0.01
        ss._lbl_restart.text = "Restart may be needed"
        ss.update(1.0)
        assert ss._lbl_restart.text == ""

    def test_restart_label_not_cleared_while_timer_active(self, ss):
        ss._restart_timer = 2.0
        ss._lbl_restart.text = "Restart may be needed"
        ss.update(0.5)
        # Timer still running (1.5 s left) — label must be unchanged
        assert ss._lbl_restart.text == "Restart may be needed"

    def test_conflict_timer_decrements_by_dt(self, ss):
        ss._conflict_timer = 1.5
        ss.update(0.5)
        assert ss._conflict_timer == pytest.approx(1.0)

    def test_conflict_timer_clamps_to_zero_on_large_dt(self, ss):
        ss._conflict_timer = 0.1
        ss.update(100.0)
        assert ss._conflict_timer == 0.0

    def test_conflict_timer_never_goes_negative(self, ss):
        ss._conflict_timer = 1.0
        ss.update(9999.0)
        assert ss._conflict_timer >= 0.0

    def test_conflict_label_clears_when_timer_hits_zero(self, ss):
        ss._conflict_timer = 0.01
        ss._lbl_conflict.text = "Key conflict!"
        ss.update(1.0)
        assert ss._lbl_conflict.text == ""

    def test_conflict_label_not_cleared_while_timer_active(self, ss):
        ss._conflict_timer = 2.0
        ss._lbl_conflict.text = "Key conflict!"
        ss.update(0.5)
        assert ss._lbl_conflict.text == "Key conflict!"

    def test_timers_are_independent(self, ss):
        """Advancing the conflict timer must not touch the restart timer."""
        ss._conflict_timer = 0.1
        ss._restart_timer = 5.0
        ss.update(1.0)
        assert ss._conflict_timer == 0.0
        assert ss._restart_timer == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# Scene lifecycle hooks
# ---------------------------------------------------------------------------

class TestSettingsScreenLifecycle:
    def test_is_instance_of_base_scene(self, ss):
        from src.scenes.base_scene import BaseScene
        assert isinstance(ss, BaseScene)

    def test_on_enter_does_not_raise(self, ss):
        ss.on_enter()

    def test_on_exit_does_not_raise(self, ss):
        ss.on_exit()

    def test_on_pause_does_not_raise(self, ss):
        ss.on_pause()

    def test_on_resume_does_not_raise(self, ss):
        ss.on_resume()

    def test_lazy_init_flag_true_after_first_render(self, ss):
        # ss is in modal mode so _ensure_init() was called in __init__
        assert ss._initialised is True

    def test_standalone_mode_not_initialised_until_render(self, screen):
        """In standalone mode, _initialised must stay False until render/events."""
        from src.core.settings import Settings
        sc = SettingsScreen(settings=Settings())
        assert sc._initialised is False
        sc.render(screen)
        assert sc._initialised is True


# ---------------------------------------------------------------------------
# Render — extra smoke tests
# ---------------------------------------------------------------------------

class TestSettingsScreenRenderExtra:
    def test_render_while_awaiting_rebind_does_not_raise(self, ss, screen):
        ss._awaiting_action = "jump"
        ss.render(screen)

    def test_render_is_idempotent(self, ss, screen):
        """Two consecutive renders must not raise or corrupt widget state."""
        ss.render(screen)
        ss.render(screen)

    def test_render_after_cycle_fps_does_not_raise(self, ss, screen):
        ss._cycle_fps()
        ss.render(screen)

    def test_render_after_rebind_does_not_raise(self, ss, screen):
        action = next(iter(ss._local_bindings))
        ss._make_rebind_callback(action, 0)()
        ss.handle_events([_keydown(pygame.K_z)])
        ss.render(screen)

    def test_render_with_active_conflict_label_does_not_raise(self, ss, screen):
        ss._lbl_conflict.text = "Key conflict!"
        ss._conflict_timer = 2.0
        ss.render(screen)

    def test_render_with_active_restart_label_does_not_raise(self, ss, screen):
        ss._lbl_restart.text = "Restart may be needed"
        ss._restart_timer = 3.0
        ss.render(screen)
