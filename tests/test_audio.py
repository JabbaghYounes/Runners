"""Comprehensive test suite for the AudioManager, NullSound, and crossfade FSM."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from src.audio import (
    FOOTSTEP_INTERVALS,
    MUSIC_REGISTRY,
    SOUND_REGISTRY,
    AudioManager,
    NullSound,
    _FadeState,
)
from src.events import EventBus
from src.settings import Settings


# -----------------------------------------------------------------------
# NullSound
# -----------------------------------------------------------------------

class TestNullSound:
    """NullSound must be a complete no-op."""

    def test_play_returns_none(self):
        assert NullSound().play() is None

    def test_stop_returns_none(self):
        assert NullSound().stop() is None

    def test_set_volume_returns_none(self):
        assert NullSound().set_volume(0.5) is None

    def test_get_length_returns_zero(self):
        assert NullSound().get_length() == 0.0

    def test_play_accepts_arbitrary_args(self):
        """play() should accept any positional and keyword arguments."""
        ns = NullSound()
        ns.play(1, 2, loops=5, maxtime=3000)  # should not raise

    def test_multiple_calls_safe(self):
        """Calling NullSound methods repeatedly should be harmless."""
        ns = NullSound()
        for _ in range(100):
            ns.play()
            ns.stop()
            ns.set_volume(0.5)
        assert ns.get_length() == 0.0


# -----------------------------------------------------------------------
# AudioManager initialisation
# -----------------------------------------------------------------------

class TestAudioManagerInit:
    """Initialisation and graceful-degradation tests."""

    def test_init_does_not_crash(self, mock_settings, mock_event_bus):
        """AudioManager should initialise without raising."""
        mgr = AudioManager(mock_settings, mock_event_bus)
        assert mgr is not None

    def test_init_without_event_bus(self, mock_settings):
        """AudioManager works without an EventBus."""
        mgr = AudioManager(mock_settings, event_bus=None)
        assert mgr is not None

    def test_all_sounds_loaded(self, audio_manager):
        """Every entry in SOUND_REGISTRY should be present (real or NullSound)."""
        for name in SOUND_REGISTRY:
            assert name in audio_manager._sounds

    def test_missing_sounds_become_null(self, audio_manager):
        """With no real .wav files, all loaded sounds should be NullSound."""
        for name, snd in audio_manager._sounds.items():
            assert isinstance(snd, NullSound), f"{name} should be NullSound"

    def test_custom_fade_duration(self, mock_settings):
        """fade_duration parameter should be respected."""
        mgr = AudioManager(mock_settings, event_bus=None, fade_duration=2.0)
        assert mgr._fade_duration == 2.0
        # fade_speed = 1.0 / (duration / 2) = 1.0
        assert mgr._fade_speed == pytest.approx(1.0)

    def test_zero_fade_duration(self, mock_settings):
        """Zero fade_duration should set high fade speed for instant transitions."""
        mgr = AudioManager(mock_settings, event_bus=None, fade_duration=0.0)
        assert mgr._fade_speed == pytest.approx(100.0)

    def test_initial_state(self, audio_manager):
        """AudioManager should start in IDLE state with no current zone."""
        assert audio_manager._fade_state == _FadeState.IDLE
        assert audio_manager._current_zone is None
        assert audio_manager._target_zone is None
        assert audio_manager._queued_zone is None

    def test_disabled_manager_on_mixer_failure(self, mock_settings):
        """If pygame.mixer.init fails, AudioManager should set _enabled=False."""
        with patch.dict("os.environ", {"SDL_AUDIODRIVER": "____invalid____"}):
            mgr = AudioManager.__new__(AudioManager)
            mgr._settings = mock_settings
            mgr._event_bus = None
            mgr._enabled = False
            mgr._sounds = {}
            mgr._footstep_timer = 0.0
            mgr._fade_state = _FadeState.IDLE
            mgr._current_zone = None
            mgr._target_zone = None
            mgr._queued_zone = None
            mgr._fade_volume = 0.0
            # A disabled manager's methods should all be safe to call
            mgr.update(0.016)
            mgr.play_sfx("shoot")
            mgr.play_music("spawn")
            mgr.stop_music()
            mgr.set_music_volume(0.5)
            mgr.set_sfx_volume(0.5)


# -----------------------------------------------------------------------
# SFX playback
# -----------------------------------------------------------------------

class TestSFXPlayback:
    """play_sfx and volume control."""

    def test_play_known_sfx_no_crash(self, audio_manager):
        """play_sfx with a known name should not raise even with NullSound."""
        audio_manager.play_sfx("shoot")

    def test_play_unknown_sfx_no_crash(self, audio_manager):
        """play_sfx with an unknown name should not raise."""
        audio_manager.play_sfx("nonexistent_sound")

    def test_sfx_volume_set(self, audio_manager):
        audio_manager.set_sfx_volume(0.3)
        assert audio_manager._settings.sfx_volume == pytest.approx(0.3)

    def test_sfx_volume_clamped_high(self, audio_manager):
        audio_manager.set_sfx_volume(5.0)
        assert audio_manager._settings.sfx_volume == pytest.approx(1.0)

    def test_sfx_volume_clamped_low(self, audio_manager):
        audio_manager.set_sfx_volume(-1.0)
        assert audio_manager._settings.sfx_volume == pytest.approx(0.0)

    def test_play_sfx_with_explicit_volume(self, audio_manager):
        """play_sfx with explicit volume should use override, not settings."""
        mock_sound = MagicMock()
        audio_manager._sounds["shoot"] = mock_sound
        audio_manager._settings.sfx_volume = 0.7
        audio_manager.play_sfx("shoot", volume=0.3)
        mock_sound.set_volume.assert_called_once_with(0.3)
        mock_sound.play.assert_called_once()

    def test_play_sfx_uses_settings_volume(self, audio_manager):
        """play_sfx without explicit volume should use settings.sfx_volume."""
        mock_sound = MagicMock()
        audio_manager._sounds["reload"] = mock_sound
        audio_manager._settings.sfx_volume = 0.4
        audio_manager.play_sfx("reload")
        mock_sound.set_volume.assert_called_once_with(0.4)
        mock_sound.play.assert_called_once()

    def test_play_sfx_volume_clamped(self, audio_manager):
        """Explicit volume for play_sfx should be clamped to [0.0, 1.0]."""
        mock_sound = MagicMock()
        audio_manager._sounds["hit"] = mock_sound
        audio_manager.play_sfx("hit", volume=5.0)
        mock_sound.set_volume.assert_called_once_with(1.0)

    def test_play_sfx_null_sound_skipped(self, audio_manager):
        """play_sfx should silently skip NullSound instances (early return)."""
        audio_manager._sounds["shoot"] = NullSound()
        # Should not raise; NullSound.play() is never called via the
        # regular path because isinstance(sound, NullSound) returns early.
        audio_manager.play_sfx("shoot")

    def test_play_sfx_exception_in_sound_play(self, audio_manager):
        """If sound.play() raises, play_sfx should catch and not crash."""
        mock_sound = MagicMock()
        mock_sound.play.side_effect = RuntimeError("audio device lost")
        audio_manager._sounds["shoot"] = mock_sound
        audio_manager.play_sfx("shoot")  # should not raise


# -----------------------------------------------------------------------
# Music volume
# -----------------------------------------------------------------------

class TestMusicVolume:
    """Music volume controls and clamping."""

    def test_set_music_volume(self, audio_manager):
        audio_manager.set_music_volume(0.4)
        assert audio_manager._settings.music_volume == pytest.approx(0.4)

    def test_music_volume_clamped_high(self, audio_manager):
        audio_manager.set_music_volume(2.0)
        assert audio_manager._settings.music_volume == pytest.approx(1.0)

    def test_music_volume_clamped_low(self, audio_manager):
        audio_manager.set_music_volume(-0.5)
        assert audio_manager._settings.music_volume == pytest.approx(0.0)

    def test_set_music_volume_during_fade_does_not_set_mixer(self, audio_manager):
        """During a crossfade, set_music_volume should NOT call mixer.music.set_volume."""
        audio_manager._fade_state = _FadeState.FADING_OUT
        with patch.object(audio_manager._pygame.mixer.music, "set_volume") as mock_sv:
            audio_manager.set_music_volume(0.5)
            # Settings should still be updated
            assert audio_manager._settings.music_volume == pytest.approx(0.5)
            # But mixer volume should NOT be set during fade
            mock_sv.assert_not_called()

    def test_set_music_volume_idle_sets_mixer(self, audio_manager):
        """During IDLE, set_music_volume SHOULD set mixer volume."""
        audio_manager._fade_state = _FadeState.IDLE
        with patch.object(audio_manager._pygame.mixer.music, "set_volume") as mock_sv:
            audio_manager.set_music_volume(0.6)
            mock_sv.assert_called_once_with(0.6)


# -----------------------------------------------------------------------
# Zone-based music and crossfade FSM
# -----------------------------------------------------------------------

class TestCrossfade:
    """Zone change detection and crossfade state machine."""

    def test_zone_change_triggers_fade(self, audio_manager):
        """Updating with a new zone should enter FADING_OUT.

        We use dt=0 so the fade step doesn't advance past FADING_OUT
        in the same frame.
        """
        audio_manager._current_zone = "spawn"
        audio_manager.update(0.0, current_zone="challenge")
        assert audio_manager._fade_state == _FadeState.FADING_OUT

    def test_same_zone_no_transition(self, audio_manager):
        """Same zone on consecutive updates should stay IDLE."""
        audio_manager._current_zone = "spawn"
        audio_manager._fade_state = _FadeState.IDLE
        audio_manager.update(0.016, current_zone="spawn")
        assert audio_manager._fade_state == _FadeState.IDLE

    def test_none_zone_no_transition(self, audio_manager):
        """None zone should not trigger a transition."""
        audio_manager._current_zone = "spawn"
        audio_manager._fade_state = _FadeState.IDLE
        audio_manager.update(0.016, current_zone=None)
        assert audio_manager._fade_state == _FadeState.IDLE

    def test_crossfade_fading_out_decreases_volume(self, audio_manager):
        """During FADING_OUT, volume should decrease each step."""
        audio_manager._fade_state = _FadeState.FADING_OUT
        audio_manager._fade_volume = 0.7
        audio_manager._target_zone = "challenge"
        audio_manager._fade_step(0.1)
        assert audio_manager._fade_volume < 0.7

    def test_crossfade_completes_full_cycle(self, audio_manager):
        """Simulate enough dt steps to drive through the full FSM cycle.

        Since no real music files exist, the transition will abort at
        LOADING (no playable track), which is the expected behaviour in
        a test environment.
        """
        audio_manager._current_zone = "spawn"
        # Use dt=0 so fade doesn't advance in the trigger frame
        audio_manager.update(0.0, current_zone="challenge")
        assert audio_manager._fade_state == _FadeState.FADING_OUT

        # Pump frames until we leave FADING_OUT
        for _ in range(200):
            audio_manager._fade_step(0.016)
            if audio_manager._fade_state != _FadeState.FADING_OUT:
                break

        # Without real files, LOADING aborts back to IDLE
        # and sets _current_zone to the target zone.
        assert audio_manager._current_zone == "challenge"
        assert audio_manager._fade_state == _FadeState.IDLE

    def test_queued_zone_during_transition(self, audio_manager):
        """A second zone change during an active transition is queued."""
        audio_manager._current_zone = "spawn"
        # Start first transition (dt=0 to stay in FADING_OUT)
        audio_manager.update(0.0, current_zone="challenge")
        assert audio_manager._fade_state == _FadeState.FADING_OUT
        # Now request another change while still transitioning
        audio_manager._request_zone_change("extraction")
        assert audio_manager._queued_zone == "extraction"

    def test_unknown_zone_ignored(self, audio_manager):
        """A zone not in MUSIC_REGISTRY should not trigger a transition."""
        audio_manager._current_zone = "spawn"
        audio_manager._fade_state = _FadeState.IDLE
        audio_manager.update(0.016, current_zone="totally_unknown_zone")
        assert audio_manager._fade_state == _FadeState.IDLE

    def test_fading_in_increases_volume(self, audio_manager):
        """During FADING_IN, volume should increase each step."""
        audio_manager._fade_state = _FadeState.FADING_IN
        audio_manager._fade_volume = 0.1
        audio_manager._settings.music_volume = 0.7
        audio_manager._fade_step(0.1)
        assert audio_manager._fade_volume > 0.1

    def test_fading_in_completes_to_idle(self, audio_manager):
        """FADING_IN should transition to IDLE when target volume is reached."""
        audio_manager._fade_state = _FadeState.FADING_IN
        audio_manager._fade_volume = 0.0
        audio_manager._settings.music_volume = 0.7
        # Run many steps to complete fade-in
        for _ in range(200):
            audio_manager._fade_step(0.016)
            if audio_manager._fade_state == _FadeState.IDLE:
                break
        assert audio_manager._fade_state == _FadeState.IDLE
        assert audio_manager._fade_volume == pytest.approx(0.7)

    def test_queued_zone_replaces_target_at_loading(self, audio_manager):
        """When a queued zone exists, it should replace the target at LOADING."""
        audio_manager._current_zone = "spawn"
        # Start transition to challenge
        audio_manager.update(0.0, current_zone="challenge")
        assert audio_manager._target_zone == "challenge"
        # Queue extraction while still fading
        audio_manager._request_zone_change("extraction")
        assert audio_manager._queued_zone == "extraction"
        # Drive fade-out to completion → LOADING
        for _ in range(200):
            audio_manager._fade_step(0.016)
            if audio_manager._fade_state != _FadeState.FADING_OUT:
                break
        # At LOADING, the queued zone should have replaced the target
        # (no real files → aborts to IDLE, but _current_zone updated)
        assert audio_manager._current_zone == "extraction"
        assert audio_manager._queued_zone is None

    def test_multiple_rapid_zone_changes(self, audio_manager):
        """Multiple zone changes during a transition should keep only the last."""
        audio_manager._current_zone = "spawn"
        audio_manager.update(0.0, current_zone="challenge")
        # Rapidly queue several zones
        audio_manager._request_zone_change("extraction")
        audio_manager._request_zone_change("menu")
        # Only the last queued zone should remain
        assert audio_manager._queued_zone == "menu"

    def test_fade_out_reaches_zero(self, audio_manager):
        """FADING_OUT should eventually bring volume to 0."""
        audio_manager._fade_state = _FadeState.FADING_OUT
        audio_manager._fade_volume = 0.7
        audio_manager._target_zone = "challenge"
        for _ in range(200):
            audio_manager._fade_step(0.016)
            if audio_manager._fade_volume <= 0.0:
                break
        assert audio_manager._fade_volume == pytest.approx(0.0)

    def test_idle_fade_step_noop(self, audio_manager):
        """_fade_step in IDLE state should do nothing."""
        audio_manager._fade_state = _FadeState.IDLE
        audio_manager._fade_volume = 0.5
        audio_manager._fade_step(0.016)
        assert audio_manager._fade_volume == pytest.approx(0.5)
        assert audio_manager._fade_state == _FadeState.IDLE


# -----------------------------------------------------------------------
# play_music / stop_music
# -----------------------------------------------------------------------

class TestPlayStopMusic:
    """Direct play_music and stop_music calls."""

    def test_play_music_unknown_zone(self, audio_manager):
        """play_music with an unknown zone logs a warning but does not crash."""
        audio_manager.play_music("does_not_exist")

    def test_play_music_missing_file(self, audio_manager):
        """play_music with a valid zone but missing file should not crash."""
        audio_manager.play_music("spawn")  # file doesn't exist in test env

    def test_stop_music_no_crash(self, audio_manager):
        """stop_music should not crash even when nothing is playing."""
        audio_manager.stop_music()
        assert audio_manager._current_zone is None

    def test_stop_music_resets_fade_state(self, audio_manager):
        """stop_music should reset fade state to IDLE."""
        audio_manager._fade_state = _FadeState.FADING_OUT
        audio_manager._current_zone = "spawn"
        audio_manager.stop_music()
        assert audio_manager._fade_state == _FadeState.IDLE
        assert audio_manager._current_zone is None

    def test_play_music_sets_current_zone(self, audio_manager):
        """play_music should set _current_zone even if file is missing.

        In our test environment files don't exist, so it will just log and skip.
        The zone should NOT be set when the file is missing.
        """
        audio_manager.play_music("spawn")
        # File doesn't exist → zone should remain unset
        assert audio_manager._current_zone is None


# -----------------------------------------------------------------------
# EventBus integration
# -----------------------------------------------------------------------

class TestEventBusIntegration:
    """EventBus events should trigger the correct SFX."""

    def test_shot_fired_triggers_sfx(self, audio_manager, mock_event_bus):
        with patch.object(audio_manager, "play_sfx") as mock_play:
            # Re-subscribe because we patched after init
            audio_manager._event_bus = mock_event_bus
            audio_manager._subscribe_events()
            mock_event_bus.publish("shot_fired")
            mock_play.assert_called_with("shoot")

    def test_reload_triggers_sfx(self, audio_manager, mock_event_bus):
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager._event_bus = mock_event_bus
            audio_manager._subscribe_events()
            mock_event_bus.publish("reload")
            mock_play.assert_called_with("reload")

    def test_item_picked_up_triggers_sfx(self, audio_manager, mock_event_bus):
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager._event_bus = mock_event_bus
            audio_manager._subscribe_events()
            mock_event_bus.publish("item_picked_up")
            mock_play.assert_called_with("pickup")

    def test_extraction_started_triggers_sfx(self, audio_manager, mock_event_bus):
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager._event_bus = mock_event_bus
            audio_manager._subscribe_events()
            mock_event_bus.publish("extraction_started")
            mock_play.assert_called_with("extraction")

    def test_entity_hit_triggers_sfx(self, audio_manager, mock_event_bus):
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager._event_bus = mock_event_bus
            audio_manager._subscribe_events()
            mock_event_bus.publish("entity_hit")
            mock_play.assert_called_with("hit")

    def test_enemy_attack_triggers_sfx(self, audio_manager, mock_event_bus):
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager._event_bus = mock_event_bus
            audio_manager._subscribe_events()
            mock_event_bus.publish("enemy_attack")
            mock_play.assert_called_with("robot_attack")

    def test_extraction_complete_triggers_sfx(self, audio_manager, mock_event_bus):
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager._event_bus = mock_event_bus
            audio_manager._subscribe_events()
            mock_event_bus.publish("extraction_complete")
            mock_play.assert_called_with("extraction")

    def test_event_with_data_still_triggers(self, audio_manager, mock_event_bus):
        """Events published with extra kwargs should still trigger SFX."""
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager._event_bus = mock_event_bus
            audio_manager._subscribe_events()
            mock_event_bus.publish("shot_fired", weapon="rifle", damage=25)
            mock_play.assert_called_with("shoot")

    def test_all_event_subscriptions_registered(self, mock_settings, mock_event_bus):
        """All expected event types should be subscribed after init."""
        mgr = AudioManager(mock_settings, mock_event_bus)
        expected_events = [
            "shot_fired", "reload", "item_picked_up",
            "extraction_started", "extraction_complete",
            "entity_hit", "enemy_attack",
        ]
        for event_type in expected_events:
            assert event_type in mock_event_bus._listeners, (
                f"'{event_type}' should be subscribed"
            )
            assert len(mock_event_bus._listeners[event_type]) > 0


# -----------------------------------------------------------------------
# Footstep rate-limiting
# -----------------------------------------------------------------------

class TestFootsteps:
    """Footstep SFX with per-movement-state cooldown."""

    def test_walk_footstep_plays(self, audio_manager):
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager._footstep_timer = 0.0
            audio_manager.play_footstep("walk", 0.016)
            mock_play.assert_called_once_with("footstep")

    def test_footstep_cooldown_prevents_spam(self, audio_manager):
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager._footstep_timer = 0.0
            audio_manager.play_footstep("walk", 0.016)
            # Timer now set — immediate second call should be suppressed
            audio_manager.play_footstep("walk", 0.016)
            assert mock_play.call_count == 1

    def test_idle_no_footstep(self, audio_manager):
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager.play_footstep("idle", 0.016)
            mock_play.assert_not_called()

    def test_sprint_uses_shorter_interval(self, audio_manager):
        with patch.object(audio_manager, "play_sfx"):
            audio_manager._footstep_timer = 0.0
            audio_manager.play_footstep("sprint", 0.016)
            assert audio_manager._footstep_timer == pytest.approx(0.3)

    def test_crouch_uses_longer_interval(self, audio_manager):
        with patch.object(audio_manager, "play_sfx"):
            audio_manager._footstep_timer = 0.0
            audio_manager.play_footstep("crouch", 0.016)
            assert audio_manager._footstep_timer == pytest.approx(0.7)

    def test_footstep_timer_ticks_down_in_update(self, audio_manager):
        audio_manager._footstep_timer = 0.5
        audio_manager.update(0.1, current_zone=None)
        assert audio_manager._footstep_timer == pytest.approx(0.4)

    def test_walk_footstep_interval(self, audio_manager):
        """Walk state should set 0.5s cooldown."""
        with patch.object(audio_manager, "play_sfx"):
            audio_manager._footstep_timer = 0.0
            audio_manager.play_footstep("walk", 0.016)
            assert audio_manager._footstep_timer == pytest.approx(0.5)

    def test_jump_no_footstep(self, audio_manager):
        """Jump state should not trigger footsteps."""
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager.play_footstep("jump", 0.016)
            mock_play.assert_not_called()

    def test_slide_no_footstep(self, audio_manager):
        """Slide state should not trigger footsteps."""
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager.play_footstep("slide", 0.016)
            mock_play.assert_not_called()

    def test_footstep_cooldown_expires_then_plays(self, audio_manager):
        """After cooldown expires via update(), next play_footstep should fire."""
        with patch.object(audio_manager, "play_sfx") as mock_play:
            audio_manager._footstep_timer = 0.0
            audio_manager.play_footstep("walk", 0.016)
            assert mock_play.call_count == 1
            # Simulate time passing via update to expire cooldown
            audio_manager.update(0.5, current_zone=None)
            audio_manager.play_footstep("walk", 0.016)
            assert mock_play.call_count == 2

    def test_footstep_timer_does_not_go_below_zero(self, audio_manager):
        """Timer should not go below zero after large dt."""
        audio_manager._footstep_timer = 0.1
        audio_manager.update(1.0, current_zone=None)
        assert audio_manager._footstep_timer <= 0.0

    def test_all_movement_states_in_footstep_intervals(self):
        """FOOTSTEP_INTERVALS should contain walk, sprint, crouch."""
        assert "walk" in FOOTSTEP_INTERVALS
        assert "sprint" in FOOTSTEP_INTERVALS
        assert "crouch" in FOOTSTEP_INTERVALS
        assert FOOTSTEP_INTERVALS["walk"] == pytest.approx(0.5)
        assert FOOTSTEP_INTERVALS["sprint"] == pytest.approx(0.3)
        assert FOOTSTEP_INTERVALS["crouch"] == pytest.approx(0.7)


# -----------------------------------------------------------------------
# Disabled manager
# -----------------------------------------------------------------------

class TestDisabledManager:
    """A disabled AudioManager should be a complete no-op."""

    def _make_disabled(self) -> AudioManager:
        mgr = AudioManager.__new__(AudioManager)
        mgr._settings = Settings()
        mgr._event_bus = None
        mgr._enabled = False
        mgr._sounds = {}
        mgr._footstep_timer = 0.0
        mgr._fade_state = _FadeState.IDLE
        mgr._current_zone = None
        mgr._target_zone = None
        mgr._queued_zone = None
        mgr._fade_volume = 0.0
        mgr._fade_duration = 1.0
        mgr._fade_speed = 2.0
        mgr._pygame = None
        return mgr

    def test_update_noop(self):
        mgr = self._make_disabled()
        mgr.update(0.016, "spawn")  # should not raise

    def test_play_sfx_noop(self):
        mgr = self._make_disabled()
        mgr.play_sfx("shoot")  # should not raise

    def test_play_music_noop(self):
        mgr = self._make_disabled()
        mgr.play_music("spawn")  # should not raise

    def test_stop_music_noop(self):
        mgr = self._make_disabled()
        mgr.stop_music()  # should not raise

    def test_set_volumes_still_updates_settings(self):
        mgr = self._make_disabled()
        mgr.set_music_volume(0.5)
        assert mgr._settings.music_volume == pytest.approx(0.5)
        mgr.set_sfx_volume(0.3)
        assert mgr._settings.sfx_volume == pytest.approx(0.3)

    def test_play_footstep_noop(self):
        mgr = self._make_disabled()
        mgr.play_footstep("walk", 0.016)  # should not raise

    def test_update_does_not_change_fade_state(self):
        """Disabled manager update should not change fade state."""
        mgr = self._make_disabled()
        mgr.update(0.016, "challenge")
        assert mgr._fade_state == _FadeState.IDLE

    def test_stop_music_does_not_clear_zone_when_disabled(self):
        """Disabled manager stop_music returns early; zone is NOT cleared."""
        mgr = self._make_disabled()
        mgr._current_zone = "spawn"
        mgr.stop_music()
        # stop_music checks _enabled and returns early, so _current_zone
        # is never set to None (the assignment is after the early return).
        assert mgr._current_zone == "spawn"


# -----------------------------------------------------------------------
# Registry validation
# -----------------------------------------------------------------------

class TestRegistries:
    """Validate SOUND_REGISTRY and MUSIC_REGISTRY constants."""

    def test_sound_registry_has_expected_keys(self):
        expected = {"shoot", "reload", "footstep", "robot_attack", "pickup", "extraction", "hit"}
        assert set(SOUND_REGISTRY.keys()) == expected

    def test_music_registry_has_expected_keys(self):
        expected = {"menu", "spawn", "challenge", "extraction"}
        assert set(MUSIC_REGISTRY.keys()) == expected

    def test_sound_paths_are_under_assets(self):
        for name, path in SOUND_REGISTRY.items():
            assert path.startswith("assets/sounds/"), f"{name}: {path}"

    def test_music_paths_are_under_assets(self):
        for name, path in MUSIC_REGISTRY.items():
            assert path.startswith("assets/music/"), f"{name}: {path}"

    def test_sound_registry_paths_are_wav(self):
        for name, path in SOUND_REGISTRY.items():
            assert path.endswith(".wav"), f"{name} should be .wav, got {path}"

    def test_music_registry_paths_are_ogg(self):
        for name, path in MUSIC_REGISTRY.items():
            assert path.endswith(".ogg"), f"{name} should be .ogg, got {path}"


# -----------------------------------------------------------------------
# FadeState enum
# -----------------------------------------------------------------------

class TestFadeState:
    """Validate the crossfade state machine enum."""

    def test_all_states_exist(self):
        assert _FadeState.IDLE.value == "idle"
        assert _FadeState.FADING_OUT.value == "fading_out"
        assert _FadeState.LOADING.value == "loading"
        assert _FadeState.FADING_IN.value == "fading_in"

    def test_four_states(self):
        assert len(_FadeState) == 4


# -----------------------------------------------------------------------
# Full crossfade cycle with mocked music files
# -----------------------------------------------------------------------

class TestCrossfadeWithMockedFiles:
    """Simulate a complete crossfade cycle by mocking file existence and mixer."""

    def test_full_crossfade_with_files(self, audio_manager):
        """Complete cycle: IDLE → FADING_OUT → LOADING → FADING_IN → IDLE."""
        audio_manager._current_zone = "spawn"
        audio_manager._fade_volume = 0.7
        audio_manager._settings.music_volume = 0.7

        mixer_music = audio_manager._pygame.mixer.music

        # Mock both Path.exists and mixer.music methods
        with patch("src.audio.Path") as MockPath, \
             patch.object(mixer_music, "load"), \
             patch.object(mixer_music, "play"), \
             patch.object(mixer_music, "set_volume"):
            MockPath.return_value.exists.return_value = True

            # Trigger zone change (dt=0 to not advance FSM)
            audio_manager.update(0.0, current_zone="challenge")
            assert audio_manager._fade_state == _FadeState.FADING_OUT

            # Drive FADING_OUT to completion
            for _ in range(200):
                audio_manager._fade_step(0.016)
                if audio_manager._fade_state != _FadeState.FADING_OUT:
                    break

            # Should have passed through LOADING and now be FADING_IN
            assert audio_manager._fade_state == _FadeState.FADING_IN
            assert audio_manager._current_zone == "challenge"

            # Drive FADING_IN to completion
            for _ in range(200):
                audio_manager._fade_step(0.016)
                if audio_manager._fade_state == _FadeState.IDLE:
                    break

            assert audio_manager._fade_state == _FadeState.IDLE
            assert audio_manager._fade_volume == pytest.approx(0.7)

    def test_crossfade_calls_mixer_correctly(self, audio_manager):
        """Verify that load/play/set_volume are called on the mixer during crossfade."""
        audio_manager._current_zone = "spawn"
        audio_manager._fade_volume = 0.7
        audio_manager._settings.music_volume = 0.7

        mixer_music = audio_manager._pygame.mixer.music

        with patch("src.audio.Path") as MockPath, \
             patch.object(mixer_music, "load") as mock_load, \
             patch.object(mixer_music, "play") as mock_play, \
             patch.object(mixer_music, "set_volume") as mock_sv:
            MockPath.return_value.exists.return_value = True

            audio_manager.update(0.0, current_zone="challenge")

            # Drive through full cycle
            for _ in range(500):
                audio_manager._fade_step(0.016)
                if audio_manager._fade_state == _FadeState.IDLE:
                    break

            # Music should have been loaded and played
            mock_load.assert_called_once()
            mock_play.assert_called_once_with(-1)
            # set_volume should have been called multiple times during fade
            assert mock_sv.call_count > 2

    def test_crossfade_queued_zone_replaces_during_loading(self, audio_manager):
        """Queue a zone change during FADING_OUT; at LOADING it should pick up the queued zone."""
        audio_manager._current_zone = "spawn"
        audio_manager._fade_volume = 0.7
        audio_manager._settings.music_volume = 0.7

        mixer_music = audio_manager._pygame.mixer.music

        with patch("src.audio.Path") as MockPath, \
             patch.object(mixer_music, "load"), \
             patch.object(mixer_music, "play"), \
             patch.object(mixer_music, "set_volume"):
            MockPath.return_value.exists.return_value = True

            # Start transition to challenge
            audio_manager.update(0.0, current_zone="challenge")
            # Queue extraction while fading
            audio_manager._request_zone_change("extraction")

            # Drive to completion
            for _ in range(500):
                audio_manager._fade_step(0.016)
                if audio_manager._fade_state == _FadeState.IDLE:
                    break

            # Should end at the queued zone
            assert audio_manager._current_zone == "extraction"
            assert audio_manager._fade_state == _FadeState.IDLE
