"""Tests for SettingsScreen — volume setter wiring and apply_volumes coupling."""
import pytest
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
