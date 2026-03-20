"""Tests for SettingsScreen — volume setter wiring and apply_volumes coupling."""
import pytest
import pygame
from unittest.mock import MagicMock, call

from src.core.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_screen(settings=None, audio=None, on_close=None):
    """Build a SettingsScreen with optional overrides."""
    from src.scenes.settings_screen import SettingsScreen
    if settings is None:
        settings = Settings()
    if audio is None:
        audio = MagicMock()
    return SettingsScreen(settings=settings, audio=audio, on_close=on_close)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_creates_without_error(self):
        screen = _make_screen()
        assert screen is not None

    def test_stores_settings_reference(self):
        s = Settings()
        screen = _make_screen(settings=s)
        assert screen._settings is s

    def test_stores_audio_reference(self):
        audio = MagicMock()
        screen = _make_screen(audio=audio)
        assert screen._audio is audio

    def test_stores_on_close_callable(self):
        cb = MagicMock()
        screen = _make_screen(on_close=cb)
        assert screen._on_close is cb

    def test_on_close_defaults_to_none(self):
        screen = _make_screen()
        assert screen._on_close is None

    def test_not_initialised_on_construction(self):
        """Lazy pygame init must not run until render() is called."""
        screen = _make_screen()
        assert screen._initialised is False


# ---------------------------------------------------------------------------
# Volume setters — Settings mutation + apply_volumes forwarding
# ---------------------------------------------------------------------------

class TestMasterVolumeSetterSetter:
    def test_updates_volume_master_in_settings(self):
        s = Settings()
        screen = _make_screen(settings=s)
        screen._set_master(0.4)
        assert s.volume_master == pytest.approx(0.4)

    def test_calls_apply_volumes_on_audio(self):
        audio = MagicMock()
        screen = _make_screen(audio=audio)
        screen._set_master(0.4)
        audio.apply_volumes.assert_called_once()

    def test_master_set_to_zero_propagates(self):
        s = Settings()
        screen = _make_screen(settings=s)
        screen._set_master(0.0)
        assert s.volume_master == pytest.approx(0.0)

    def test_master_set_to_one_propagates(self):
        s = Settings()
        screen = _make_screen(settings=s)
        screen._set_master(1.0)
        assert s.volume_master == pytest.approx(1.0)


class TestMusicVolumeSetterSetter:
    def test_updates_volume_music_in_settings(self):
        s = Settings()
        screen = _make_screen(settings=s)
        screen._set_music(0.3)
        assert s.volume_music == pytest.approx(0.3)

    def test_calls_apply_volumes_on_audio(self):
        audio = MagicMock()
        screen = _make_screen(audio=audio)
        screen._set_music(0.3)
        audio.apply_volumes.assert_called_once()


class TestSFXVolumeSetterSetter:
    def test_updates_volume_sfx_in_settings(self):
        s = Settings()
        screen = _make_screen(settings=s)
        screen._set_sfx(0.6)
        assert s.volume_sfx == pytest.approx(0.6)

    def test_calls_apply_volumes_on_audio(self):
        audio = MagicMock()
        screen = _make_screen(audio=audio)
        screen._set_sfx(0.6)
        audio.apply_volumes.assert_called_once()


class TestMultipleSliderChanges:
    def test_each_setter_call_triggers_apply_volumes(self):
        audio = MagicMock()
        screen = _make_screen(audio=audio)

        screen._set_master(0.5)
        screen._set_music(0.5)
        screen._set_sfx(0.5)

        assert audio.apply_volumes.call_count == 3

    def test_rapid_master_changes_each_call_apply(self):
        audio = MagicMock()
        screen = _make_screen(audio=audio)

        for v in [0.1, 0.5, 0.9]:
            screen._set_master(v)

        assert audio.apply_volumes.call_count == 3

    def test_settings_reflect_last_change(self):
        s = Settings()
        screen = _make_screen(settings=s)
        screen._set_master(0.2)
        screen._set_master(0.8)
        assert s.volume_master == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Setter independence — changing one field must not affect others
# ---------------------------------------------------------------------------

class TestSetterIndependence:
    def test_set_master_does_not_change_music_or_sfx(self):
        s = Settings()
        screen = _make_screen(settings=s)
        original_music = s.volume_music
        original_sfx   = s.volume_sfx

        screen._set_master(0.3)

        assert s.volume_music == pytest.approx(original_music)
        assert s.volume_sfx   == pytest.approx(original_sfx)

    def test_set_music_does_not_change_master_or_sfx(self):
        s = Settings()
        screen = _make_screen(settings=s)
        original_master = s.volume_master
        original_sfx    = s.volume_sfx

        screen._set_music(0.2)

        assert s.volume_master == pytest.approx(original_master)
        assert s.volume_sfx    == pytest.approx(original_sfx)

    def test_set_sfx_does_not_change_master_or_music(self):
        s = Settings()
        screen = _make_screen(settings=s)
        original_master = s.volume_master
        original_music  = s.volume_music

        screen._set_sfx(0.1)

        assert s.volume_master == pytest.approx(original_master)
        assert s.volume_music  == pytest.approx(original_music)


# ---------------------------------------------------------------------------
# Scene protocol compliance
# ---------------------------------------------------------------------------

class TestSceneProtocol:
    def test_update_method_exists_and_accepts_dt(self):
        screen = _make_screen()
        screen.update(1 / 60)   # must not raise

    def test_handle_events_accepts_empty_list(self):
        screen = _make_screen()
        screen.handle_events([])   # must not raise

    def test_render_method_exists(self):
        screen = _make_screen()
        assert callable(getattr(screen, "render", None))


# ---------------------------------------------------------------------------
# Cancel / Discard — snapshot-based restoration
# ---------------------------------------------------------------------------

class TestCancelDiscard:
    def test_discard_reverts_master_volume(self):
        s = Settings()
        original = s.master_volume
        cb = MagicMock()
        screen = _make_screen(settings=s, on_close=cb)
        screen._set_master(0.1)
        assert s.master_volume == pytest.approx(0.1)
        screen._discard_and_pop()
        assert s.master_volume == pytest.approx(original)
        cb.assert_called_once()

    def test_discard_reverts_music_volume(self):
        s = Settings()
        original = s.music_volume
        screen = _make_screen(settings=s, on_close=MagicMock())
        screen._set_music(0.05)
        screen._discard_and_pop()
        assert s.music_volume == pytest.approx(original)

    def test_discard_reverts_sfx_volume(self):
        s = Settings()
        original = s.sfx_volume
        screen = _make_screen(settings=s, on_close=MagicMock())
        screen._set_sfx(0.05)
        screen._discard_and_pop()
        assert s.sfx_volume == pytest.approx(original)

    def test_discard_calls_apply_volumes_to_restore_audio(self):
        audio = MagicMock()
        screen = _make_screen(audio=audio, on_close=MagicMock())
        screen._set_master(0.2)
        audio.apply_volumes.reset_mock()
        screen._discard_and_pop()
        audio.apply_volumes.assert_called_once()

    def test_back_without_changes_does_not_show_confirm(self):
        cb = MagicMock()
        screen = _make_screen(on_close=cb)
        assert not screen._dirty
        screen._on_back()
        cb.assert_called_once()


# ---------------------------------------------------------------------------
# FPS cycling
# ---------------------------------------------------------------------------

class TestFpsCycle:
    def test_cycle_fps_advances_index(self):
        from src.scenes.settings_screen import _FPS_PRESETS
        screen = _make_screen()
        initial = screen._local_fps_idx
        screen._cycle_fps()
        assert screen._local_fps_idx == (initial + 1) % len(_FPS_PRESETS)

    def test_cycle_fps_marks_dirty(self):
        screen = _make_screen()
        assert not screen._dirty
        screen._cycle_fps()
        assert screen._dirty

    def test_cycle_fps_wraps_around(self):
        from src.scenes.settings_screen import _FPS_PRESETS
        screen = _make_screen()
        for _ in range(len(_FPS_PRESETS)):
            screen._cycle_fps()
        assert screen._local_fps_idx == screen._snap_fps_idx

    def test_apply_writes_fps_to_settings(self):
        from src.scenes.settings_screen import _FPS_PRESETS
        s = Settings()
        cb = MagicMock()
        screen = _make_screen(settings=s, on_close=cb)
        screen._local_fps_idx = 0  # 30 fps
        screen._on_apply()
        assert s.target_fps == _FPS_PRESETS[0]

    def test_apply_writes_correct_fps_after_cycles(self):
        from src.scenes.settings_screen import _FPS_PRESETS
        s = Settings()
        cb = MagicMock()
        screen = _make_screen(settings=s, on_close=cb)
        screen._cycle_fps()
        screen._cycle_fps()
        expected = _FPS_PRESETS[screen._local_fps_idx]
        screen._on_apply()
        assert s.target_fps == expected


# ---------------------------------------------------------------------------
# Key rebinding — apply path
# ---------------------------------------------------------------------------

class TestKeyRebindApply:
    def _make_keydown(self, key: int) -> "pygame.event.Event":
        return pygame.event.Event(
            pygame.KEYDOWN,
            {"key": key, "mod": 0, "unicode": "", "scancode": 0},
        )

    def test_rebind_stores_new_key_in_local_bindings(self):
        screen = _make_screen()
        screen._awaiting_action = "jump"
        screen.handle_events([self._make_keydown(pygame.K_j)])
        assert screen._local_bindings["jump"] == pygame.K_j

    def test_awaiting_action_cleared_after_rebind(self):
        screen = _make_screen()
        screen._awaiting_action = "jump"
        screen.handle_events([self._make_keydown(pygame.K_j)])
        assert screen._awaiting_action is None

    def test_rebind_marks_dirty(self):
        screen = _make_screen()
        assert not screen._dirty
        screen._awaiting_action = "jump"
        screen.handle_events([self._make_keydown(pygame.K_j)])
        assert screen._dirty

    def test_apply_writes_bindings_to_settings(self):
        s = Settings()
        cb = MagicMock()
        screen = _make_screen(settings=s, on_close=cb)
        screen._local_bindings["jump"] = pygame.K_j
        screen._on_apply()
        assert s.key_bindings.get("jump") == pygame.K_j

    def test_apply_syncs_constants_key_bindings(self):
        import src.constants as _C
        s = Settings()
        cb = MagicMock()
        screen = _make_screen(settings=s, on_close=cb)
        screen._local_bindings["jump"] = pygame.K_j
        screen._on_apply()
        assert _C.KEY_BINDINGS.get("jump") == pygame.K_j

    def test_apply_calls_on_close(self):
        cb = MagicMock()
        screen = _make_screen(on_close=cb)
        screen._on_apply()
        cb.assert_called_once()


# ---------------------------------------------------------------------------
# ESC cancels rebind without triggering BACK
# ---------------------------------------------------------------------------

class TestEscCancelsRebind:
    def _make_keydown(self, key: int) -> "pygame.event.Event":
        return pygame.event.Event(
            pygame.KEYDOWN,
            {"key": key, "mod": 0, "unicode": "", "scancode": 0},
        )

    def test_esc_clears_awaiting_action(self):
        screen = _make_screen()
        screen._awaiting_action = "jump"
        screen.handle_events([self._make_keydown(pygame.K_ESCAPE)])
        assert screen._awaiting_action is None

    def test_esc_does_not_trigger_on_close(self):
        cb = MagicMock()
        screen = _make_screen(on_close=cb)
        screen._awaiting_action = "jump"
        screen.handle_events([self._make_keydown(pygame.K_ESCAPE)])
        cb.assert_not_called()

    def test_esc_does_not_mark_dirty(self):
        screen = _make_screen()
        assert not screen._dirty
        screen._awaiting_action = "jump"
        screen.handle_events([self._make_keydown(pygame.K_ESCAPE)])
        assert not screen._dirty


# ---------------------------------------------------------------------------
# Duplicate key binding conflict
# ---------------------------------------------------------------------------

class TestDuplicateBindingConflict:
    def _make_keydown(self, key: int) -> "pygame.event.Event":
        return pygame.event.Event(
            pygame.KEYDOWN,
            {"key": key, "mod": 0, "unicode": "", "scancode": 0},
        )

    def test_rebinding_to_used_key_stores_new_binding(self):
        screen = _make_screen()
        actions = list(screen._local_bindings.keys())
        action_a, action_b = actions[0], actions[1]
        key_b = screen._local_bindings[action_b]

        screen._awaiting_action = action_a
        screen.handle_events([self._make_keydown(key_b)])

        assert screen._local_bindings[action_a] == key_b

    def test_rebinding_to_used_key_swaps_conflicting_action(self):
        screen = _make_screen()
        actions = list(screen._local_bindings.keys())
        action_a, action_b = actions[0], actions[1]
        old_key_a = screen._local_bindings[action_a]
        key_b = screen._local_bindings[action_b]

        screen._awaiting_action = action_a
        screen.handle_events([self._make_keydown(key_b)])

        # action_b should now hold action_a's old key
        assert screen._local_bindings[action_b] == old_key_a

    def test_conflict_sets_lbl_text(self):
        screen = _make_screen()
        # Trigger init so _lbl_conflict is created
        screen.handle_events([])
        actions = list(screen._local_bindings.keys())
        action_a, action_b = actions[0], actions[1]
        key_b = screen._local_bindings[action_b]

        screen._awaiting_action = action_a
        screen.handle_events([self._make_keydown(key_b)])

        if screen._lbl_conflict is not None:
            assert screen._lbl_conflict.text != ""

    def test_conflict_timer_ticks_to_zero(self):
        screen = _make_screen()
        screen.handle_events([])
        actions = list(screen._local_bindings.keys())
        action_a, action_b = actions[0], actions[1]
        key_b = screen._local_bindings[action_b]

        screen._awaiting_action = action_a
        screen.handle_events([self._make_keydown(key_b)])

        if screen._conflict_timer > 0.0:
            screen.update(3.0)   # advance past timer
            assert screen._conflict_timer == 0.0
            if screen._lbl_conflict is not None:
                assert screen._lbl_conflict.text == ""
