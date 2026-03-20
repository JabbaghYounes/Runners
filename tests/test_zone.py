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


# ---------------------------------------------------------------------------
# Zone.color — new field added in the tile-map feature
# ---------------------------------------------------------------------------


class TestZoneColor:
    """Zone.color must default to blue and accept any RGB triple."""

    def test_default_color_is_blue(self):
        z = Zone("Z", pygame.Rect(0, 0, 100, 100))
        assert z.color == (60, 120, 180)

    def test_custom_color_is_stored(self):
        z = Zone("Z", pygame.Rect(0, 0, 100, 100), color=(255, 0, 0))
        assert z.color == (255, 0, 0)

    def test_color_is_a_three_element_tuple(self):
        z = Zone("Z", pygame.Rect(0, 0, 100, 100), color=(128, 64, 32))
        assert isinstance(z.color, tuple)
        assert len(z.color) == 3

    def test_color_components_are_integers(self):
        z = Zone("Z", pygame.Rect(0, 0, 100, 100), color=(10, 20, 30))
        for component in z.color:
            assert isinstance(component, int)

    def test_two_zones_with_different_colors_do_not_share_state(self):
        z1 = Zone("A", pygame.Rect(0, 0, 100, 100), color=(255, 0, 0))
        z2 = Zone("B", pygame.Rect(0, 0, 100, 100), color=(0, 0, 255))
        assert z1.color != z2.color

    def test_color_survives_round_trip_through_tile_map_json(self, tmp_path):
        """Verify color is preserved when TileMap loads a zone with an explicit color."""
        import json
        from src.map.tile_map import TileMap
        tiles = [[1] * 5 for _ in range(3)]
        data = {
            "tiles": tiles,
            "zones": [
                {
                    "name": "CUSTOM",
                    "rect": [0, 0, 160, 96],
                    "color": [180, 80, 60],
                }
            ],
        }
        path = tmp_path / "color_map.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert tm.zones[0].color == (180, 80, 60)

    def test_color_uses_default_when_json_key_absent(self, tmp_path):
        """When JSON zone has no 'color' key, Zone.color must be the default."""
        import json
        from src.map.tile_map import TileMap
        tiles = [[1] * 5 for _ in range(3)]
        data = {
            "tiles": tiles,
            "zones": [{"name": "NO_COLOR", "rect": [0, 0, 160, 96]}],
        }
        path = tmp_path / "no_color_map.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert tm.zones[0].color == (60, 120, 180)
