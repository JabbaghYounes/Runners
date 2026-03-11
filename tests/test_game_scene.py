"""Integration tests for GameScene — zone detection and audio forwarding.

AudioSystem is replaced with a MagicMock so no real pygame mixer is required.
pygame itself is patched at the module level to avoid display requirements.
"""
import sys
from unittest.mock import MagicMock, patch
import pytest

from src.core.event_bus import EventBus
from src.core.settings import Settings
from src.map.zone import Zone


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_scene(zones=None):
    """Return (scene, bus, mock_audio) with a freshly constructed GameScene."""
    from src.scenes.game_scene import GameScene

    bus = EventBus()
    audio = MagicMock()
    settings = Settings()
    scene = GameScene(event_bus=bus, audio=audio, settings=settings, zones=zones)
    return scene, bus, audio


def _set_player_pos(scene, x: int, y: int) -> None:
    """Directly place the stub player at world coords (x, y)."""
    scene._player.rect.x = x
    scene._player.rect.y = y
    scene._player.rect.center = (x, y)


# ---------------------------------------------------------------------------
# Zone detection — zone_entered event
# ---------------------------------------------------------------------------

class TestZoneDetection:
    def test_zone_entered_emitted_when_player_enters_zone(self):
        zone = Zone("alpha", (0, 0, 640, 720))
        scene, bus, _ = _make_scene(zones=[zone])

        received = []
        bus.subscribe("zone_entered", lambda zone, **_: received.append(zone))

        _set_player_pos(scene, 100, 100)
        scene.update(0.0)

        assert received == [zone]

    def test_zone_entered_not_emitted_for_same_zone_on_repeated_update(self):
        zone = Zone("alpha", (0, 0, 1280, 720))
        scene, bus, _ = _make_scene(zones=[zone])

        received = []
        bus.subscribe("zone_entered", lambda **kw: received.append(kw))

        _set_player_pos(scene, 100, 100)
        scene.update(0.0)
        scene.update(0.0)   # player still in same zone

        assert len(received) == 1

    def test_zone_entered_emitted_on_zone_cross(self):
        zone_a = Zone("alpha", (0,   0, 200, 720))
        zone_b = Zone("beta",  (200, 0, 200, 720))
        scene, bus, _ = _make_scene(zones=[zone_a, zone_b])

        names = []
        bus.subscribe("zone_entered", lambda zone, **_: names.append(zone.name))

        _set_player_pos(scene, 100, 360)
        scene.update(0.0)   # enters alpha

        _set_player_pos(scene, 300, 360)
        scene.update(0.0)   # enters beta

        assert names == ["alpha", "beta"]

    def test_no_zone_entered_when_player_outside_all_zones(self):
        zone = Zone("alpha", (500, 500, 100, 100))
        scene, bus, _ = _make_scene(zones=[zone])

        received = []
        bus.subscribe("zone_entered", lambda **kw: received.append(kw))

        _set_player_pos(scene, 0, 0)   # far from zone
        scene.update(0.0)

        assert received == []

    def test_zone_entered_after_leaving_then_re_entering(self):
        """Leaving a zone and re-entering should fire the event again."""
        zone_a = Zone("alpha", (0,   0, 200, 720))
        zone_b = Zone("beta",  (200, 0, 200, 720))
        scene, bus, _ = _make_scene(zones=[zone_a, zone_b])

        names = []
        bus.subscribe("zone_entered", lambda zone, **_: names.append(zone.name))

        _set_player_pos(scene, 100, 360)
        scene.update(0.0)   # → alpha

        _set_player_pos(scene, 300, 360)
        scene.update(0.0)   # → beta

        _set_player_pos(scene, 100, 360)
        scene.update(0.0)   # → alpha again

        assert names == ["alpha", "beta", "alpha"]

    def test_prev_zone_updated_after_transition(self):
        zone_a = Zone("alpha", (0,   0, 200, 720))
        zone_b = Zone("beta",  (200, 0, 200, 720))
        scene, _, _ = _make_scene(zones=[zone_a, zone_b])

        _set_player_pos(scene, 100, 360)
        scene.update(0.0)
        assert scene._prev_zone is zone_a

        _set_player_pos(scene, 300, 360)
        scene.update(0.0)
        assert scene._prev_zone is zone_b

    def test_prev_zone_stays_none_when_player_outside_all_zones(self):
        zone = Zone("alpha", (500, 500, 100, 100))
        scene, _, _ = _make_scene(zones=[zone])

        _set_player_pos(scene, 0, 0)
        scene.update(0.0)

        assert scene._prev_zone is None

    def test_zone_priority_first_zone_wins(self):
        """When zones overlap, the first matching zone wins."""
        zone_a = Zone("alpha", (0, 0, 400, 400))
        zone_b = Zone("beta",  (0, 0, 400, 400))   # identical rect
        scene, bus, _ = _make_scene(zones=[zone_a, zone_b])

        received = []
        bus.subscribe("zone_entered", lambda zone, **_: received.append(zone.name))

        _set_player_pos(scene, 200, 200)
        scene.update(0.0)

        assert received == ["alpha"]


# ---------------------------------------------------------------------------
# Audio forwarding — audio.update() called every frame
# ---------------------------------------------------------------------------

class TestAudioForwarding:
    def test_audio_update_called_each_frame(self):
        zone = Zone("alpha", (0, 0, 1280, 720))
        scene, _, audio = _make_scene(zones=[zone])

        scene.update(1 / 60)

        audio.update.assert_called_once()

    def test_audio_update_receives_correct_dt(self):
        zone = Zone("alpha", (0, 0, 1280, 720))
        scene, _, audio = _make_scene(zones=[zone])

        scene.update(0.016)

        args, kwargs = audio.update.call_args
        dt_received = args[0] if args else kwargs.get("dt")
        assert dt_received == pytest.approx(0.016)

    def test_audio_update_called_multiple_times(self):
        zone = Zone("alpha", (0, 0, 1280, 720))
        scene, _, audio = _make_scene(zones=[zone])

        scene.update(0.016)
        scene.update(0.016)
        scene.update(0.016)

        assert audio.update.call_count == 3

    def test_player_is_moving_true_when_velocity_nonzero(self):
        zone = Zone("alpha", (0, 0, 1280, 720))
        scene, _, audio = _make_scene(zones=[zone])

        _set_player_pos(scene, 640, 360)
        scene._player.velocity_x = 200.0
        scene._player.velocity_y = 0.0

        scene.update(0.016)

        _, kwargs = audio.update.call_args
        assert kwargs.get("player_is_moving") is True

    def test_player_is_moving_false_when_velocity_zero(self):
        zone = Zone("alpha", (0, 0, 1280, 720))
        scene, _, audio = _make_scene(zones=[zone])

        _set_player_pos(scene, 640, 360)
        scene._player.velocity_x = 0.0
        scene._player.velocity_y = 0.0

        scene.update(0.016)

        _, kwargs = audio.update.call_args
        assert kwargs.get("player_is_moving") is False

    def test_player_is_moving_true_when_only_y_velocity_nonzero(self):
        zone = Zone("alpha", (0, 0, 1280, 720))
        scene, _, audio = _make_scene(zones=[zone])

        _set_player_pos(scene, 640, 360)
        scene._player.velocity_x = 0.0
        scene._player.velocity_y = -200.0

        scene.update(0.016)

        _, kwargs = audio.update.call_args
        assert kwargs.get("player_is_moving") is True

    def test_audio_update_called_last_in_frame(self):
        """audio.update must still be called even when a zone event fires."""
        zone_a = Zone("alpha", (0,   0, 200, 720))
        zone_b = Zone("beta",  (200, 0, 200, 720))
        scene, bus, audio = _make_scene(zones=[zone_a, zone_b])

        _set_player_pos(scene, 100, 360)
        scene.update(0.016)  # zone enters alpha
        audio_call_count_after_first = audio.update.call_count

        _set_player_pos(scene, 300, 360)
        scene.update(0.016)  # zone changes to beta
        audio_call_count_after_second = audio.update.call_count

        # audio.update must be called on every frame regardless of zone events
        assert audio_call_count_after_first == 1
        assert audio_call_count_after_second == 2


# ---------------------------------------------------------------------------
# Default zones — _default_zones() smoke test
# ---------------------------------------------------------------------------

class TestDefaultZones:
    def test_scene_creates_three_default_zones_when_none_provided(self):
        scene, _, _ = _make_scene(zones=None)
        assert len(scene._zones) == 3

    def test_default_zones_have_music_tracks(self):
        scene, _, _ = _make_scene(zones=None)
        for zone in scene._zones:
            assert zone.music_track is not None

    def test_default_zones_cover_full_width(self):
        """The three default zones together should span 1280 pixels."""
        scene, _, _ = _make_scene(zones=None)
        total_width = sum(z.rect[2] for z in scene._zones)
        assert total_width == 1280


# ---------------------------------------------------------------------------
# _zone_for_player helper
# ---------------------------------------------------------------------------

class TestZoneForPlayer:
    def test_returns_none_when_no_zones(self):
        scene, _, _ = _make_scene(zones=[])
        _set_player_pos(scene, 100, 100)
        assert scene._zone_for_player() is None

    def test_returns_matching_zone(self):
        zone = Zone("alpha", (0, 0, 500, 500))
        scene, _, _ = _make_scene(zones=[zone])
        _set_player_pos(scene, 100, 100)
        assert scene._zone_for_player() is zone

    def test_returns_none_when_player_outside_all(self):
        zone = Zone("alpha", (200, 200, 100, 100))
        scene, _, _ = _make_scene(zones=[zone])
        _set_player_pos(scene, 0, 0)
        assert scene._zone_for_player() is None
