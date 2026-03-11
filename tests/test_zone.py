"""Tests for Zone.contains() and boundary conditions."""
import pytest
import pygame
from src.map.zone import Zone


@pytest.fixture()
def zone():
    return Zone("TEST_ZONE", pygame.Rect(100, 50, 200, 150))


class TestZoneContains:
    def test_point_inside(self, zone):
        assert zone.contains((150, 100))

    def test_point_outside_right(self, zone):
        assert not zone.contains((350, 100))

    def test_point_outside_left(self, zone):
        assert not zone.contains((50, 100))

    def test_point_outside_top(self, zone):
        assert not zone.contains((150, 20))

    def test_point_outside_bottom(self, zone):
        assert not zone.contains((150, 250))

    def test_top_left_corner(self, zone):
        # pygame.Rect.collidepoint: top-left is inside
        assert zone.contains((100, 50))

    def test_bottom_right_outside(self, zone):
        # pygame.Rect.collidepoint: right/bottom edges are outside
        assert not zone.contains((300, 200))

    def test_center_point(self, zone):
        assert zone.contains((200, 125))


class TestZoneDefaults:
    def test_none_spawn_points_defaults_to_empty(self):
        z = Zone("Z", pygame.Rect(0, 0, 100, 100), spawn_points=None)
        assert z.spawn_points == []

    def test_empty_enemy_spawns_by_default(self):
        z = Zone("Z", pygame.Rect(0, 0, 100, 100))
        assert z.enemy_spawns == []

    def test_music_track_none_by_default(self):
        z = Zone("Z", pygame.Rect(0, 0, 100, 100))
        assert z.music_track is None

    def test_name_stored(self):
        z = Zone("MY_ZONE", pygame.Rect(0, 0, 100, 100))
        assert z.name == "MY_ZONE"

    def test_rect_stored(self):
        r = pygame.Rect(10, 20, 300, 400)
        z = Zone("Z", r)
        assert z.rect == r

    def test_spawn_points_stored(self):
        pts = [(10.0, 20.0), (30.0, 40.0)]
        z = Zone("Z", pygame.Rect(0, 0, 100, 100), spawn_points=pts)
        assert z.spawn_points == pts


class TestZoneFromTileMap:
    def test_zones_from_real_map(self, tmp_map_json):
        from src.map.tile_map import TileMap
        tm = TileMap.load(tmp_map_json)
        for zone in tm.zones:
            # All zones should have a name and rect
            assert zone.name
            assert isinstance(zone.rect, pygame.Rect)
            # enemy_spawns comes from JSON
            assert isinstance(zone.enemy_spawns, list)
