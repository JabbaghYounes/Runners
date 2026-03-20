# Run: pytest tests/scenes/test_game_scene_audio.py
"""Integration tests for GameScene audio wiring.

Verifies:
  - on_exit() calls audio.stop_music() so music does not bleed across scenes
  - on_exit() is safe when _audio is None (no scene manager was given)
  - An AudioSystem injected via the constructor is never silently replaced
  - Stub-mode update() still forwards dt and player_is_moving to the audio ref
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from src.core.event_bus import EventBus
from src.core.settings import Settings
from src.map.zone import Zone
from src.scenes.game_scene import GameScene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_scene(audio=None, zones=None):
    """Return a stub-mode GameScene (no scene manager, no real assets)."""
    bus = EventBus()
    settings = Settings()
    scene = GameScene(
        event_bus=bus,
        audio=audio,
        settings=settings,
        zones=zones if zones is not None else [],
    )
    return scene, bus


def _set_player_pos(scene, x, y):
    scene._player.rect.x = x
    scene._player.rect.y = y
    scene._player.rect.center = (x, y)


# ---------------------------------------------------------------------------
# on_exit — music must stop when the scene is torn down
# ---------------------------------------------------------------------------

class TestGameSceneOnExit:
    def test_on_exit_calls_stop_music(self):
        audio = MagicMock()
        scene, _ = _stub_scene(audio=audio)
        scene.on_exit()
        audio.stop_music.assert_called_once()

    def test_on_exit_is_safe_when_audio_is_none(self):
        """on_exit() must not raise when no audio system was injected."""
        scene, _ = _stub_scene(audio=None)
        scene.on_exit()   # must not raise

    def test_stop_music_not_called_before_on_exit(self):
        audio = MagicMock()
        scene, _ = _stub_scene(audio=audio)
        audio.stop_music.assert_not_called()

    def test_on_exit_called_twice_calls_stop_music_twice(self):
        """Calling on_exit more than once is safe and idempotent per call."""
        audio = MagicMock()
        scene, _ = _stub_scene(audio=audio)
        scene.on_exit()
        scene.on_exit()
        assert audio.stop_music.call_count == 2

    def test_on_exit_stop_music_called_even_with_zones(self):
        """Zones being present must not prevent stop_music from running."""
        audio = MagicMock()
        zone = Zone("alpha", (0, 0, 1280, 720), music_track="music/alpha.ogg")
        scene, _ = _stub_scene(audio=audio, zones=[zone])
        scene.on_exit()
        audio.stop_music.assert_called_once()


# ---------------------------------------------------------------------------
# AudioSystem injection — injected instance must never be replaced
# ---------------------------------------------------------------------------

class TestGameSceneAudioInjection:
    def test_injected_audio_reference_is_preserved_in_stub_mode(self):
        """The object passed as audio= must remain scene._audio after init."""
        audio = MagicMock()
        scene, _ = _stub_scene(audio=audio)
        assert scene._audio is audio

    def test_audio_none_stored_when_not_provided(self):
        scene, _ = _stub_scene(audio=None)
        assert scene._audio is None

    def test_two_scenes_with_different_audio_refs_stay_independent(self):
        audio_a = MagicMock()
        audio_b = MagicMock()
        scene_a, _ = _stub_scene(audio=audio_a)
        scene_b, _ = _stub_scene(audio=audio_b)
        assert scene_a._audio is audio_a
        assert scene_b._audio is audio_b
        assert scene_a._audio is not scene_b._audio

    def test_injected_audio_receives_update_call_per_frame(self):
        """audio.update() must be called on every scene.update() tick."""
        zone = Zone("alpha", (0, 0, 1280, 720))
        audio = MagicMock()
        scene, _ = _stub_scene(audio=audio, zones=[zone])
        scene.update(0.016)
        audio.update.assert_called_once()

    def test_audio_update_receives_correct_dt(self):
        zone = Zone("alpha", (0, 0, 1280, 720))
        audio = MagicMock()
        scene, _ = _stub_scene(audio=audio, zones=[zone])
        scene.update(0.025)
        _, kwargs = audio.update.call_args
        dt_received = audio.update.call_args[0][0] if audio.update.call_args[0] else kwargs.get("dt")
        assert dt_received == pytest.approx(0.025)

    def test_player_moving_flag_forwarded_to_audio_update(self):
        zone = Zone("alpha", (0, 0, 1280, 720))
        audio = MagicMock()
        scene, _ = _stub_scene(audio=audio, zones=[zone])
        _set_player_pos(scene, 640, 360)
        scene._player.velocity_x = 150.0
        scene._player.velocity_y = 0.0
        scene.update(0.016)
        _, kwargs = audio.update.call_args
        assert kwargs.get("player_is_moving") is True

    def test_player_stationary_flag_forwarded_to_audio_update(self):
        zone = Zone("alpha", (0, 0, 1280, 720))
        audio = MagicMock()
        scene, _ = _stub_scene(audio=audio, zones=[zone])
        _set_player_pos(scene, 640, 360)
        scene._player.velocity_x = 0.0
        scene._player.velocity_y = 0.0
        scene.update(0.016)
        _, kwargs = audio.update.call_args
        assert kwargs.get("player_is_moving") is False
