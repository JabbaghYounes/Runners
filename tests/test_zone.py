"""Tests for Zone — contains() geometry and music_track field."""
import pytest
from src.map.zone import Zone


# ---------------------------------------------------------------------------
# contains() — boundary and interior checks
# ---------------------------------------------------------------------------

class TestContains:
    def setup_method(self):
        # Zone covers x ∈ [10, 110)  y ∈ [20, 100)
        self.zone = Zone("test", (10, 20, 100, 80))

    def test_point_inside_returns_true(self):
        assert self.zone.contains((50, 60)) is True

    def test_top_left_corner_is_inclusive(self):
        assert self.zone.contains((10, 20)) is True

    def test_right_edge_is_exclusive(self):
        # x == rect.x + rect.width  →  outside
        assert self.zone.contains((110, 50)) is False

    def test_bottom_edge_is_exclusive(self):
        # y == rect.y + rect.height  →  outside
        assert self.zone.contains((50, 100)) is False

    def test_one_pixel_inside_right_edge(self):
        assert self.zone.contains((109, 50)) is True

    def test_one_pixel_inside_bottom_edge(self):
        assert self.zone.contains((50, 99)) is True

    def test_point_above_zone(self):
        assert self.zone.contains((50, 19)) is False

    def test_point_left_of_zone(self):
        assert self.zone.contains((9, 60)) is False

    def test_point_far_outside(self):
        assert self.zone.contains((0, 0)) is False

    def test_point_on_x_axis_only_inside(self):
        # x is inside but y is outside
        assert self.zone.contains((50, 200)) is False

    def test_zero_sized_zone_contains_nothing(self):
        z = Zone("empty", (50, 50, 0, 0))
        assert z.contains((50, 50)) is False


# ---------------------------------------------------------------------------
# music_track field
# ---------------------------------------------------------------------------

class TestMusicTrack:
    def test_default_music_track_is_none(self):
        z = Zone("silent", (0, 0, 100, 100))
        assert z.music_track is None

    def test_music_track_set_in_constructor(self):
        path = "assets/audio/music/zone_alpha.ogg"
        z = Zone("alpha", (0, 0, 100, 100), music_track=path)
        assert z.music_track == path

    def test_music_track_can_be_reassigned(self):
        z = Zone("alpha", (0, 0, 100, 100), music_track="old.ogg")
        z.music_track = "new.ogg"
        assert z.music_track == "new.ogg"


# ---------------------------------------------------------------------------
# spawn_points field
# ---------------------------------------------------------------------------

class TestSpawnPoints:
    def test_default_spawn_points_empty(self):
        z = Zone("alpha", (0, 0, 100, 100))
        assert z.spawn_points == []

    def test_spawn_points_set_in_constructor(self):
        pts = [(10, 10), (50, 50), (90, 90)]
        z = Zone("alpha", (0, 0, 100, 100), spawn_points=pts)
        assert z.spawn_points == pts

    def test_default_spawn_lists_are_independent(self):
        """Two separately constructed Zones must not share the default list."""
        z1 = Zone("a", (0, 0, 100, 100))
        z2 = Zone("b", (0, 0, 100, 100))
        z1.spawn_points.append((1, 1))
        assert z2.spawn_points == []


# ---------------------------------------------------------------------------
# name and rect fields
# ---------------------------------------------------------------------------

class TestNameAndRect:
    def test_name_stored(self):
        z = Zone("zone_gamma", (0, 0, 100, 100))
        assert z.name == "zone_gamma"

    def test_rect_stored(self):
        rect = (5, 10, 200, 150)
        z = Zone("r", rect)
        assert z.rect == rect
