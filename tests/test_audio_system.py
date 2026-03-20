"""Tests for AudioSystem — fully mocked pygame.mixer.

Every test uses patch.dict(sys.modules, {"pygame": pm}) so that all dynamic
`import pygame` statements inside AudioSystem resolve to our mock object.  No
real audio hardware is required.
"""
import sys
import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
import pytest

from src.core.event_bus import EventBus
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.systems.audio_system import AudioSystem
from src.map.zone import Zone


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_pygame_mock(*, mixer_ok: bool = True, init_raises: bool = False) -> MagicMock:
    """Return a minimal pygame mock for AudioSystem tests."""
    pm = MagicMock()
    pm.mixer.get_init.return_value = mixer_ok
    if init_raises:
        pm.mixer.init.side_effect = Exception("no audio device")
    else:
        pm.mixer.init.return_value = None
    pm.mixer.music = MagicMock()
    return pm


@contextmanager
def _audio_ctx(pm, *, settings=None, sfx_sounds=None):
    """Build an AudioSystem within a patched-pygame context.

    Yields (audio, bus) with sys.modules["pygame"] set to *pm* for the
    duration of the ``with`` block.

    Parameters
    ----------
    pm : MagicMock
        The mock pygame module to inject.
    settings : Settings, optional
        Defaults to ``Settings()`` if omitted.
    sfx_sounds : dict[str, MagicMock | None], optional
        Maps SFX logical name (e.g. ``"shoot"``) to the mock Sound object that
        ``AssetManager.load_sound`` should return for that file.  Names not
        listed get a fresh ``MagicMock()`` automatically.
    """
    if settings is None:
        settings = Settings()

    bus = EventBus()
    am = AssetManager()

    def fake_load_sound(path: str):
        stem = os.path.splitext(os.path.basename(path))[0]
        if sfx_sounds is not None and stem in sfx_sounds:
            return sfx_sounds[stem]
        return MagicMock()

    am.load_sound = fake_load_sound

    with patch.dict(sys.modules, {"pygame": pm}):
        audio = AudioSystem(bus, am, settings)
        yield audio, bus


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInitialisation:
    def test_mixer_ok_true_when_init_succeeds(self):
        pm = _make_pygame_mock(mixer_ok=True)
        with _audio_ctx(pm) as (audio, _):
            assert audio._mixer_ok is True

    def test_mixer_ok_false_when_init_raises(self):
        pm = _make_pygame_mock(mixer_ok=False, init_raises=True)
        with _audio_ctx(pm) as (audio, _):
            assert audio._mixer_ok is False

    def test_apply_volumes_called_during_init(self):
        """set_volume must be called at least once inside __init__."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, _):
            pm.mixer.music.set_volume.assert_called()

    def test_all_sfx_keys_loaded(self):
        """Every SFX logical name is present in _sfx_sounds after init."""
        expected_keys = {
            "shoot", "reload", "footstep", "robot_attack",
            "loot_pickup", "extraction_success", "extraction_fail",
        }
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, _):
            assert set(audio._sfx_sounds.keys()) == expected_keys

    def test_current_track_is_none_at_startup(self):
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, _):
            assert audio._current_track is None


# ---------------------------------------------------------------------------
# Silent fallback — all public methods must be no-ops when mixer is down
# ---------------------------------------------------------------------------

class TestSilentFallback:
    def _unavailable_audio(self, sfx_sounds=None):
        pm = _make_pygame_mock(mixer_ok=False, init_raises=True)
        return pm, sfx_sounds

    def test_play_music_noop(self):
        pm = _make_pygame_mock(mixer_ok=False, init_raises=True)
        with _audio_ctx(pm) as (audio, _):
            audio.play_music("assets/audio/music/zone_alpha.ogg")
        pm.mixer.music.load.assert_not_called()

    def test_play_sfx_noop(self):
        shoot_mock = MagicMock()
        pm = _make_pygame_mock(mixer_ok=False, init_raises=True)
        with _audio_ctx(pm, sfx_sounds={"shoot": shoot_mock}) as (audio, _):
            audio.play_sfx("shoot")
        shoot_mock.play.assert_not_called()

    def test_stop_music_noop(self):
        pm = _make_pygame_mock(mixer_ok=False, init_raises=True)
        with _audio_ctx(pm) as (audio, _):
            pm.mixer.music.stop.reset_mock()
            audio.stop_music()
        pm.mixer.music.stop.assert_not_called()

    def test_apply_volumes_noop(self):
        pm = _make_pygame_mock(mixer_ok=False, init_raises=True)
        with _audio_ctx(pm) as (audio, _):
            pm.mixer.music.set_volume.reset_mock()
            audio.apply_volumes()
        pm.mixer.music.set_volume.assert_not_called()

    def test_update_noop(self):
        pm = _make_pygame_mock(mixer_ok=False, init_raises=True)
        with _audio_ctx(pm) as (audio, _):
            audio.update(1.0, player_is_moving=True)   # must not raise

    def test_all_sfx_events_are_silent(self):
        """EventBus events must not raise when the mixer is unavailable."""
        pm = _make_pygame_mock(mixer_ok=False, init_raises=True)
        with _audio_ctx(pm) as (audio, bus):
            bus.emit("player_shot")
            bus.emit("player_reloaded")
            bus.emit("enemy_attack")
            bus.emit("item_picked_up")
            bus.emit("extraction_success")
            bus.emit("extraction_failed")
        # No assertions needed — the test passes if no exception is raised.


# ---------------------------------------------------------------------------
# Zone music swap
# ---------------------------------------------------------------------------

class TestZoneMusicSwap:
    def test_zone_entered_loads_and_plays_track(self):
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, bus):
            zone = Zone("alpha", (0, 0, 100, 100),
                        music_track="assets/audio/music/zone_alpha.ogg")
            bus.emit("zone_entered", zone=zone)

            pm.mixer.music.load.assert_called_once_with(
                "assets/audio/music/zone_alpha.ogg"
            )
            pm.mixer.music.play.assert_called_once()
            _, kwargs = pm.mixer.music.play.call_args
            assert kwargs.get("loops") == -1

    def test_zone_entered_fades_out_before_loading(self):
        """fadeout(500) must precede load() on every zone switch."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, bus):
            zone = Zone("alpha", (0, 0, 100, 100),
                        music_track="assets/audio/music/zone_alpha.ogg")
            bus.emit("zone_entered", zone=zone)

            pm.mixer.music.fadeout.assert_called_once_with(500)

    def test_same_track_is_not_restarted(self):
        """Emitting zone_entered twice for the same track must not reload."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, bus):
            zone = Zone("alpha", (0, 0, 100, 100),
                        music_track="assets/audio/music/zone_alpha.ogg")
            bus.emit("zone_entered", zone=zone)
            pm.mixer.music.load.reset_mock()
            pm.mixer.music.play.reset_mock()

            bus.emit("zone_entered", zone=zone)   # same zone again

            pm.mixer.music.load.assert_not_called()
            pm.mixer.music.play.assert_not_called()

    def test_different_zone_loads_new_track(self):
        """Crossing into a different zone swaps to the new track."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, bus):
            zone_a = Zone("alpha", (0, 0, 100, 100),
                          music_track="assets/audio/music/zone_alpha.ogg")
            zone_b = Zone("beta", (100, 0, 100, 100),
                          music_track="assets/audio/music/zone_beta.ogg")

            bus.emit("zone_entered", zone=zone_a)
            bus.emit("zone_entered", zone=zone_b)

            assert pm.mixer.music.load.call_count == 2
            last_load_arg = pm.mixer.music.load.call_args[0][0]
            assert last_load_arg == "assets/audio/music/zone_beta.ogg"

    def test_zone_without_track_stops_music(self):
        """A zone with music_track=None causes stop_music() to be called."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, bus):
            zone_music = Zone("alpha", (0, 0, 100, 100),
                              music_track="assets/audio/music/zone_alpha.ogg")
            zone_silent = Zone("void", (100, 0, 100, 100), music_track=None)

            bus.emit("zone_entered", zone=zone_music)
            pm.mixer.music.stop.reset_mock()

            bus.emit("zone_entered", zone=zone_silent)

            pm.mixer.music.stop.assert_called_once()
            assert audio._current_track is None

    def test_zone_entered_with_no_zone_kwarg_is_noop(self):
        """Emitting zone_entered without a zone keyword must not raise."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, bus):
            bus.emit("zone_entered")   # no zone kwarg
            pm.mixer.music.load.assert_not_called()

    def test_current_track_updated_after_play(self):
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, bus):
            track = "assets/audio/music/zone_gamma.ogg"
            zone = Zone("gamma", (0, 0, 100, 100), music_track=track)
            bus.emit("zone_entered", zone=zone)
            assert audio._current_track == track


# ---------------------------------------------------------------------------
# SFX dispatch — every game event must trigger the correct sound
# ---------------------------------------------------------------------------

class TestSFXDispatch:
    @pytest.mark.parametrize("event_name, sfx_key", [
        ("player_shot",        "shoot"),
        ("player_reloaded",    "reload"),
        ("enemy_attack",       "robot_attack"),
        ("item_picked_up",     "loot_pickup"),
        ("extraction_success", "extraction_success"),
        ("extraction_failed",  "extraction_fail"),
    ])
    def test_event_triggers_correct_sfx(self, event_name, sfx_key):
        mock_sound = MagicMock()
        pm = _make_pygame_mock()
        with _audio_ctx(pm, sfx_sounds={sfx_key: mock_sound}) as (audio, bus):
            bus.emit(event_name)
        mock_sound.play.assert_called_once()

    def test_unknown_sfx_name_is_noop(self):
        """play_sfx() with an unrecognised name must not raise."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, _):
            audio.play_sfx("totally_unknown_sfx_xyz")

    def test_none_sound_in_sfx_dict_is_noop(self):
        """If AssetManager returned None for a sound, play_sfx must not raise."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm, sfx_sounds={"shoot": None}) as (audio, _):
            audio.play_sfx("shoot")   # should not raise


# ---------------------------------------------------------------------------
# Volume maths
# ---------------------------------------------------------------------------

class TestVolumeMath:
    def test_music_volume_is_master_times_music_setting(self):
        s = Settings()
        s.volume_master = 0.6
        s.volume_music  = 0.8
        s.volume_sfx    = 1.0

        pm = _make_pygame_mock()
        with _audio_ctx(pm, settings=s) as (audio, _):
            pm.mixer.music.set_volume.reset_mock()
            audio.apply_volumes()

        pm.mixer.music.set_volume.assert_called_once_with(pytest.approx(0.6 * 0.8))

    def test_sfx_volume_is_master_times_sfx_setting(self):
        mock_sound = MagicMock()
        s = Settings()
        s.volume_master = 0.5
        s.volume_sfx    = 0.8
        s.volume_music  = 1.0

        pm = _make_pygame_mock()
        with _audio_ctx(pm, settings=s, sfx_sounds={"shoot": mock_sound}) as (audio, _):
            mock_sound.set_volume.reset_mock()
            audio.apply_volumes()

        mock_sound.set_volume.assert_called_with(pytest.approx(0.5 * 0.8))

    def test_volume_product_clamped_to_one(self):
        """master × music > 1.0 must be clamped to exactly 1.0."""
        s = Settings()
        s.volume_master = 1.5
        s.volume_music  = 1.5

        pm = _make_pygame_mock()
        with _audio_ctx(pm, settings=s) as (audio, _):
            pm.mixer.music.set_volume.reset_mock()
            audio.apply_volumes()

        pm.mixer.music.set_volume.assert_called_once_with(pytest.approx(1.0))

    def test_volume_product_clamped_to_zero(self):
        """master = 0 must produce 0.0 regardless of other sliders."""
        s = Settings()
        s.volume_master = 0.0
        s.volume_music  = 1.0

        pm = _make_pygame_mock()
        with _audio_ctx(pm, settings=s) as (audio, _):
            pm.mixer.music.set_volume.reset_mock()
            audio.apply_volumes()

        pm.mixer.music.set_volume.assert_called_once_with(pytest.approx(0.0))

    def test_zero_master_mutes_sfx_too(self):
        mock_sound = MagicMock()
        s = Settings()
        s.volume_master = 0.0
        s.volume_sfx    = 1.0

        pm = _make_pygame_mock()
        with _audio_ctx(pm, settings=s, sfx_sounds={"shoot": mock_sound}) as (audio, _):
            mock_sound.set_volume.reset_mock()
            audio.apply_volumes()

        mock_sound.set_volume.assert_called_with(pytest.approx(0.0))

    def test_apply_volumes_skips_none_sounds(self):
        """None entries in _sfx_sounds must not cause AttributeError."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm, sfx_sounds={"shoot": None}) as (audio, _):
            audio.apply_volumes()   # must not raise


# ---------------------------------------------------------------------------
# Footstep throttle
# ---------------------------------------------------------------------------

class TestFootstepThrottle:
    _INTERVAL = 0.35   # must match AudioSystem._FOOTSTEP_INTERVAL

    def test_footstep_fires_after_one_interval(self):
        footstep = MagicMock()
        pm = _make_pygame_mock()
        with _audio_ctx(pm, sfx_sounds={"footstep": footstep}) as (audio, _):
            audio.update(self._INTERVAL, player_is_moving=True)
        footstep.play.assert_called_once()

    def test_footstep_does_not_fire_before_interval(self):
        footstep = MagicMock()
        pm = _make_pygame_mock()
        with _audio_ctx(pm, sfx_sounds={"footstep": footstep}) as (audio, _):
            audio.update(self._INTERVAL - 0.01, player_is_moving=True)
        footstep.play.assert_not_called()

    def test_footstep_fires_repeatedly_across_frames(self):
        """Three consecutive interval-length frames → three footstep sounds."""
        footstep = MagicMock()
        pm = _make_pygame_mock()
        with _audio_ctx(pm, sfx_sounds={"footstep": footstep}) as (audio, _):
            for _ in range(3):
                audio.update(self._INTERVAL, player_is_moving=True)
        assert footstep.play.call_count == 3

    def test_timer_resets_to_zero_after_play(self):
        footstep = MagicMock()
        pm = _make_pygame_mock()
        with _audio_ctx(pm, sfx_sounds={"footstep": footstep}) as (audio, _):
            audio.update(self._INTERVAL, player_is_moving=True)
            assert audio._footstep_timer == pytest.approx(0.0)

    def test_timer_resets_when_player_stops(self):
        """Stopping mid-accumulation zeroes the timer so the clock restarts."""
        footstep = MagicMock()
        pm = _make_pygame_mock()
        with _audio_ctx(pm, sfx_sounds={"footstep": footstep}) as (audio, _):
            audio.update(self._INTERVAL * 0.6, player_is_moving=True)   # partial
            audio.update(self._INTERVAL * 0.6, player_is_moving=False)  # stop → reset
            audio.update(self._INTERVAL * 0.6, player_is_moving=True)   # partial again
        footstep.play.assert_not_called()   # never reached full interval consecutively

    def test_no_footstep_while_stationary(self):
        footstep = MagicMock()
        pm = _make_pygame_mock()
        with _audio_ctx(pm, sfx_sounds={"footstep": footstep}) as (audio, _):
            audio.update(1.0, player_is_moving=False)
        footstep.play.assert_not_called()

    def test_footstep_accumulates_across_small_frames(self):
        """Many sub-interval frames should add up to trigger the sound."""
        footstep = MagicMock()
        pm = _make_pygame_mock()
        with _audio_ctx(pm, sfx_sounds={"footstep": footstep}) as (audio, _):
            # 7 × 0.05 = 0.35 s  →  exactly one footstep
            for _ in range(7):
                audio.update(0.05, player_is_moving=True)
        footstep.play.assert_called_once()


# ---------------------------------------------------------------------------
# stop_music
# ---------------------------------------------------------------------------

class TestStopMusic:
    def test_stop_music_calls_pygame_stop(self):
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, bus):
            zone = Zone("alpha", (0, 0, 100, 100),
                        music_track="assets/audio/music/zone_alpha.ogg")
            bus.emit("zone_entered", zone=zone)
            pm.mixer.music.stop.reset_mock()

            audio.stop_music()

            pm.mixer.music.stop.assert_called_once()

    def test_stop_music_clears_current_track(self):
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, bus):
            zone = Zone("alpha", (0, 0, 100, 100),
                        music_track="assets/audio/music/zone_alpha.ogg")
            bus.emit("zone_entered", zone=zone)
            assert audio._current_track is not None

            audio.stop_music()
            assert audio._current_track is None

    def test_play_music_after_stop_reloads_same_track(self):
        """After stop_music(), re-entering the same zone must reload the track."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, bus):
            track = "assets/audio/music/zone_alpha.ogg"
            zone = Zone("alpha", (0, 0, 100, 100), music_track=track)

            bus.emit("zone_entered", zone=zone)
            audio.stop_music()   # clears _current_track
            pm.mixer.music.load.reset_mock()

            bus.emit("zone_entered", zone=zone)

            pm.mixer.music.load.assert_called_once_with(track)


# ---------------------------------------------------------------------------
# AssetManager path contract — load_sound must receive relative paths
# ---------------------------------------------------------------------------

class TestLoadSoundPaths:
    def test_sfx_loaded_with_relative_paths(self):
        """_load_sfx must pass AssetManager-relative paths (not absolute OS paths)."""
        from unittest.mock import patch

        recorded_paths: list[str] = []

        pm = _make_pygame_mock()
        bus = EventBus()
        am = AssetManager()
        am.load_sound = lambda path: recorded_paths.append(path) or MagicMock()

        with patch.dict(sys.modules, {"pygame": pm}):
            AudioSystem(bus, am, Settings())

        assert recorded_paths, "load_sound was never called"
        for path in recorded_paths:
            assert not path.startswith('/'), (
                f"load_sound received absolute path; expected relative: {path!r}"
            )
            assert path.startswith('sfx/'), (
                f"Expected 'sfx/' prefix for SFX asset, got: {path!r}"
            )


# ---------------------------------------------------------------------------
# set_volume() — legacy three-argument volume setter
# ---------------------------------------------------------------------------

class TestSetVolumeMethod:
    def test_set_volume_updates_music_channel(self):
        """set_volume(master, music, sfx) must call pygame.mixer.music.set_volume(master*music)."""
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, _):
            pm.mixer.music.set_volume.reset_mock()
            audio.set_volume(0.5, 0.8, 1.0)
        pm.mixer.music.set_volume.assert_called_once_with(pytest.approx(0.5 * 0.8))

    def test_set_volume_noop_when_mixer_unavailable(self):
        pm = _make_pygame_mock(mixer_ok=False, init_raises=True)
        with _audio_ctx(pm) as (audio, _):
            pm.mixer.music.set_volume.reset_mock()
            audio.set_volume(0.5, 0.8, 1.0)
        pm.mixer.music.set_volume.assert_not_called()

    def test_set_volume_zero_master_silences_music(self):
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, _):
            pm.mixer.music.set_volume.reset_mock()
            audio.set_volume(0.0, 1.0, 1.0)
        pm.mixer.music.set_volume.assert_called_once_with(pytest.approx(0.0))

    def test_set_volume_full_master_and_music(self):
        pm = _make_pygame_mock()
        with _audio_ctx(pm) as (audio, _):
            pm.mixer.music.set_volume.reset_mock()
            audio.set_volume(1.0, 1.0, 1.0)
        pm.mixer.music.set_volume.assert_called_once_with(pytest.approx(1.0))


# ---------------------------------------------------------------------------
# Initialisation without settings (settings=None)
# ---------------------------------------------------------------------------

class TestInitialisationWithoutSettings:
    """AudioSystem(bus, assets, None) must behave correctly: no volumes applied
    during __init__, but all other functionality works normally."""

    def _make_audio_no_settings(self, pm):
        bus = EventBus()
        am = AssetManager()
        am.load_sound = lambda path: MagicMock()
        with patch.dict(sys.modules, {"pygame": pm}):
            audio = AudioSystem(bus, am, None)
        return audio, bus

    def test_settings_attribute_is_none(self):
        pm = _make_pygame_mock()
        audio, _ = self._make_audio_no_settings(pm)
        assert audio._settings is None

    def test_apply_volumes_is_noop_when_settings_is_none(self):
        pm = _make_pygame_mock()
        audio, _ = self._make_audio_no_settings(pm)
        pm.mixer.music.set_volume.reset_mock()
        with patch.dict(sys.modules, {"pygame": pm}):
            audio.apply_volumes()
        pm.mixer.music.set_volume.assert_not_called()

    def test_sfx_sounds_all_loaded_without_settings(self):
        """All SFX keys must be present even when no Settings object is given."""
        pm = _make_pygame_mock()
        audio, _ = self._make_audio_no_settings(pm)
        expected_keys = {
            "shoot", "reload", "footstep", "robot_attack",
            "loot_pickup", "extraction_success", "extraction_fail",
        }
        assert set(audio._sfx_sounds.keys()) == expected_keys

    def test_sfx_events_fire_without_settings(self):
        """SFX must play from bus events even when settings=None."""
        mock_sound = MagicMock()
        pm = _make_pygame_mock()
        bus = EventBus()
        am = AssetManager()
        am.load_sound = lambda path: mock_sound
        with patch.dict(sys.modules, {"pygame": pm}):
            AudioSystem(bus, am, None)
            bus.emit("player_shot")
        mock_sound.play.assert_called()

    def test_mixer_ok_still_true_without_settings(self):
        pm = _make_pygame_mock(mixer_ok=True)
        audio, _ = self._make_audio_no_settings(pm)
        assert audio._mixer_ok is True


# ---------------------------------------------------------------------------
# EventBus subscriptions — AudioSystem must register all expected handlers
# ---------------------------------------------------------------------------

class TestEventBusSubscriptions:
    """After construction, every game event AudioSystem handles must have
    at least one listener registered on the EventBus."""

    def _bus_after_audio_init(self):
        pm = _make_pygame_mock()
        bus = EventBus()
        am = AssetManager()
        am.load_sound = lambda path: MagicMock()
        with patch.dict(sys.modules, {"pygame": pm}):
            AudioSystem(bus, am, Settings())
        return bus

    def test_zone_entered_has_subscriber(self):
        assert self._bus_after_audio_init().listener_count("zone_entered") >= 1

    def test_player_shot_has_subscriber(self):
        assert self._bus_after_audio_init().listener_count("player_shot") >= 1

    def test_player_reloaded_has_subscriber(self):
        assert self._bus_after_audio_init().listener_count("player_reloaded") >= 1

    def test_enemy_attack_has_subscriber(self):
        assert self._bus_after_audio_init().listener_count("enemy_attack") >= 1

    def test_item_picked_up_has_subscriber(self):
        assert self._bus_after_audio_init().listener_count("item_picked_up") >= 1

    def test_extraction_success_has_subscriber(self):
        assert self._bus_after_audio_init().listener_count("extraction_success") >= 1

    def test_extraction_failed_has_subscriber(self):
        assert self._bus_after_audio_init().listener_count("extraction_failed") >= 1
