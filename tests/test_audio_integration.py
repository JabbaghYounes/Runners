"""Integration tests for the audio system end-to-end.

These tests verify that Settings, EventBus, and AudioManager work together
correctly as they would in the actual game loop.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio import (
    MUSIC_REGISTRY,
    SOUND_REGISTRY,
    AudioManager,
    NullSound,
    _FadeState,
)
from src.events import EventBus
from src.settings import Settings


class TestEndToEndGameLoop:
    """Simulate a realistic game loop sequence using all three modules."""

    def test_full_game_session(self):
        """Simulate: load settings → create bus → create audio → play music →
        zone transitions → SFX events → volume changes → stop.
        """
        # 1. Load settings (defaults since no file)
        settings = Settings()
        assert settings.music_volume == pytest.approx(0.7)
        assert settings.sfx_volume == pytest.approx(0.7)

        # 2. Create EventBus
        bus = EventBus()

        # 3. Create AudioManager
        audio = AudioManager(settings, bus, fade_duration=1.0)
        assert audio._enabled  # should init OK in headless mode

        # 4. Simulate game loop frames: player in spawn zone
        for _ in range(60):  # 1 second at 60fps
            audio.update(1 / 60, current_zone="spawn")

        # 5. Fire some events
        bus.publish("shot_fired")
        bus.publish("reload")
        bus.publish("item_picked_up", item_id="medkit")

        # 6. Simulate zone transition to challenge
        audio.update(0.0, current_zone="challenge")
        assert audio._fade_state == _FadeState.FADING_OUT

        # 7. Continue game loop through transition
        for _ in range(120):
            audio.update(1 / 60, current_zone="challenge")

        # The zone should have updated (even if no files — abort at LOADING)
        assert audio._current_zone == "challenge"
        assert audio._fade_state == _FadeState.IDLE

        # 8. Adjust volume mid-game
        audio.set_music_volume(0.3)
        assert settings.music_volume == pytest.approx(0.3)
        audio.set_sfx_volume(0.5)
        assert settings.sfx_volume == pytest.approx(0.5)

        # 9. Extraction events
        bus.publish("extraction_started")
        bus.publish("extraction_complete")

        # 10. Stop music
        audio.stop_music()
        assert audio._current_zone is None
        assert audio._fade_state == _FadeState.IDLE

    def test_settings_persist_volume_changes(self, tmp_path: Path):
        """Volume changes via AudioManager should persist through Settings save/load."""
        settings = Settings()
        bus = EventBus()
        audio = AudioManager(settings, bus)

        audio.set_music_volume(0.4)
        audio.set_sfx_volume(0.2)

        # Save settings
        file = tmp_path / "settings.json"
        settings.save(file)

        # Load fresh and verify
        loaded = Settings.load(file)
        assert loaded.music_volume == pytest.approx(0.4)
        assert loaded.sfx_volume == pytest.approx(0.2)

    def test_eventbus_wiring_complete(self):
        """Verify that creating AudioManager with an EventBus wires all expected events."""
        bus = EventBus()
        settings = Settings()
        audio = AudioManager(settings, bus)

        # Track all SFX calls
        sfx_calls = []
        original_play_sfx = audio.play_sfx

        def tracking_play_sfx(name, volume=None):
            sfx_calls.append(name)
            original_play_sfx(name, volume)

        audio.play_sfx = tracking_play_sfx

        # Re-subscribe with the tracking wrapper
        # We need to test via direct callback invocation
        bus.publish("shot_fired")
        bus.publish("reload")
        bus.publish("item_picked_up")
        bus.publish("extraction_started")
        bus.publish("extraction_complete")
        bus.publish("entity_hit")
        bus.publish("enemy_attack")

        # The original callbacks call the unpatched play_sfx, so we verify
        # the bus has listeners for all expected events
        expected = [
            "shot_fired", "reload", "item_picked_up",
            "extraction_started", "extraction_complete",
            "entity_hit", "enemy_attack",
        ]
        for evt in expected:
            assert evt in bus._listeners
            assert len(bus._listeners[evt]) >= 1

    def test_multiple_zone_transitions_in_sequence(self):
        """Simulate moving through multiple zones over time."""
        settings = Settings()
        audio = AudioManager(settings, event_bus=None, fade_duration=0.5)

        zones = ["spawn", "challenge", "extraction", "spawn"]

        for zone in zones:
            # Start zone
            audio.update(0.0, current_zone=zone)
            # Simulate 2 seconds in zone
            for _ in range(120):
                audio.update(1 / 60, current_zone=zone)
            # Should be settled
            assert audio._fade_state == _FadeState.IDLE
            assert audio._current_zone == zone

    def test_footsteps_during_zone_transition(self):
        """Footsteps should still play during a zone music transition."""
        settings = Settings()
        audio = AudioManager(settings, event_bus=None, fade_duration=1.0)
        audio._current_zone = "spawn"

        # Start zone transition
        audio.update(0.0, current_zone="challenge")
        assert audio._fade_state == _FadeState.FADING_OUT

        # Footsteps should still work during crossfade
        with patch.object(audio, "play_sfx") as mock_play:
            audio._footstep_timer = 0.0
            audio.play_footstep("walk", 0.016)
            mock_play.assert_called_once_with("footstep")

    def test_sfx_events_during_zone_transition(self):
        """SFX events via EventBus should still fire during crossfade."""
        settings = Settings()
        bus = EventBus()
        audio = AudioManager(settings, bus, fade_duration=1.0)
        audio._current_zone = "spawn"

        # Start zone transition
        audio.update(0.0, current_zone="challenge")
        assert audio._fade_state == _FadeState.FADING_OUT

        # Fire SFX event during crossfade
        with patch.object(audio, "play_sfx") as mock_play:
            # Re-subscribe after patching
            audio._event_bus = bus
            audio._subscribe_events()
            bus.publish("shot_fired")
            mock_play.assert_called_with("shoot")


class TestGracefulDegradation:
    """Test that the system handles missing files and bad state gracefully."""

    def test_no_audio_files_no_crash(self):
        """Complete workflow with no audio files should never crash."""
        settings = Settings()
        bus = EventBus()
        audio = AudioManager(settings, bus)

        # All sounds should be NullSound
        for name, snd in audio._sounds.items():
            assert isinstance(snd, NullSound)

        # All operations should be safe
        audio.play_music("spawn")
        audio.play_music("does_not_exist")
        audio.play_sfx("shoot")
        audio.play_sfx("nonexistent")
        audio.play_footstep("walk", 0.016)
        audio.play_footstep("idle", 0.016)
        audio.stop_music()

        bus.publish("shot_fired")
        bus.publish("reload")
        bus.publish("unknown_event")

        for _ in range(60):
            audio.update(1 / 60, current_zone="spawn")

        audio.set_music_volume(0.0)
        audio.set_music_volume(1.0)
        audio.set_sfx_volume(0.0)
        audio.set_sfx_volume(1.0)

    def test_disabled_manager_full_workflow(self):
        """A completely disabled AudioManager should survive a full game session."""
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

        # Full workflow should be no-ops
        mgr.play_music("spawn")
        mgr.update(0.016, "spawn")
        mgr.play_sfx("shoot")
        mgr.play_footstep("walk", 0.016)
        mgr.set_music_volume(0.5)
        mgr.set_sfx_volume(0.5)
        mgr.stop_music()

        # Settings should still be updated
        assert mgr._settings.music_volume == pytest.approx(0.5)
        assert mgr._settings.sfx_volume == pytest.approx(0.5)

    def test_rapid_zone_switches_no_crash(self):
        """Rapidly switching zones every frame should not crash."""
        settings = Settings()
        audio = AudioManager(settings, event_bus=None, fade_duration=0.5)

        zones = ["spawn", "challenge", "extraction", "menu"]
        for i in range(240):
            zone = zones[i % len(zones)]
            audio.update(1 / 60, current_zone=zone)

        # Should end in a valid state
        assert audio._fade_state in (_FadeState.IDLE, _FadeState.FADING_OUT,
                                      _FadeState.LOADING, _FadeState.FADING_IN)

    def test_extreme_dt_values(self):
        """Very large and very small dt values should not crash."""
        settings = Settings()
        audio = AudioManager(settings, event_bus=None)
        audio._current_zone = "spawn"

        # Very large dt (lag spike)
        audio.update(10.0, current_zone="challenge")
        # Very small dt
        audio.update(0.0001, current_zone="challenge")
        # Zero dt
        audio.update(0.0, current_zone="challenge")

    def test_volume_boundary_values(self):
        """Boundary volume values should be handled correctly."""
        settings = Settings()
        audio = AudioManager(settings, event_bus=None)

        for vol in [0.0, 0.001, 0.5, 0.999, 1.0, -0.001, 1.001, -100.0, 100.0]:
            audio.set_music_volume(vol)
            assert 0.0 <= settings.music_volume <= 1.0
            audio.set_sfx_volume(vol)
            assert 0.0 <= settings.sfx_volume <= 1.0


class TestSettingsEventBusAudioInteraction:
    """Test interactions between Settings, EventBus, and AudioManager."""

    def test_settings_shared_reference(self):
        """AudioManager and external code share the same Settings object."""
        settings = Settings()
        audio = AudioManager(settings, event_bus=None)

        # External code changes settings
        settings.sfx_volume = 0.1
        # AudioManager should see the change immediately
        assert audio._settings.sfx_volume == pytest.approx(0.1)

    def test_eventbus_shared_reference(self):
        """AudioManager and game systems share the same EventBus."""
        bus = EventBus()
        settings = Settings()
        audio = AudioManager(settings, bus)

        # Game system publishes event; AudioManager should react
        with patch.object(audio, "play_sfx") as mock_play:
            audio._event_bus = bus
            audio._subscribe_events()
            bus.publish("shot_fired")
            mock_play.assert_called_with("shoot")

    def test_audio_manager_without_eventbus_ignores_events(self):
        """AudioManager created without EventBus should not crash on events."""
        bus = EventBus()
        settings = Settings()
        audio = AudioManager(settings, event_bus=None)

        # Events published to bus should have no effect on AudioManager
        bus.publish("shot_fired")
        bus.publish("reload")
        # No crash expected

    def test_multiple_audio_managers_same_eventbus(self):
        """Multiple AudioManagers on the same EventBus should both respond."""
        bus = EventBus()
        settings1 = Settings()
        settings2 = Settings()
        audio1 = AudioManager(settings1, bus)
        audio2 = AudioManager(settings2, bus)

        # Both should have subscriptions
        assert len(bus._listeners.get("shot_fired", [])) >= 2
