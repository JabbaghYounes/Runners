"""Tests for the Minimap widget — coordinate conversion, markers, rendering."""

from __future__ import annotations

import pygame
import pytest

from src.map import Zone
from src.ui.minimap import Minimap


# ======================================================================
# Helpers
# ======================================================================


def make_zone(name: str, x: int, y: int, w: int = 128, h: int = 128) -> Zone:
    return Zone(name=name, zone_type="extraction", rect=pygame.Rect(x, y, w, h))


# ======================================================================
# Coordinate conversion
# ======================================================================


class TestMinimapCoordinates:
    """Test world-to-minimap coordinate conversion."""

    @pytest.fixture
    def minimap(self):
        mm = Minimap(screen_width=1280, screen_height=720)
        mm.set_map_size(2560, 1920)
        return mm

    def test_origin_maps_to_minimap_topleft(self, minimap):
        mx, my = minimap._world_to_minimap(0, 0)
        assert mx == minimap._x
        assert my == minimap._y

    def test_max_maps_to_minimap_bottomright(self, minimap):
        mx, my = minimap._world_to_minimap(2560, 1920)
        # Should be clamped to minimap bounds (SIZE - 1)
        assert mx <= minimap._x + minimap.SIZE
        assert my <= minimap._y + minimap.SIZE

    def test_center_maps_to_minimap_center(self, minimap):
        mx, my = minimap._world_to_minimap(1280, 960)
        expected_mx = minimap._x + minimap.SIZE // 2
        expected_my = minimap._y + minimap.SIZE // 2
        assert mx == expected_mx
        assert my == expected_my

    def test_negative_coords_clamped(self, minimap):
        mx, my = minimap._world_to_minimap(-100, -100)
        assert mx >= minimap._x
        assert my >= minimap._y

    def test_beyond_map_coords_clamped(self, minimap):
        mx, my = minimap._world_to_minimap(10000, 10000)
        assert mx <= minimap._x + minimap.SIZE - 1
        assert my <= minimap._y + minimap.SIZE - 1


# ======================================================================
# Map size and state
# ======================================================================


class TestMinimapState:
    @pytest.fixture
    def minimap(self):
        return Minimap(screen_width=1280, screen_height=720)

    def test_default_dimensions(self, minimap):
        assert minimap.SIZE == 160
        assert minimap.MARGIN == 16

    def test_set_map_size(self, minimap):
        minimap.set_map_size(5000, 4000)
        assert minimap._map_w == 5000
        assert minimap._map_h == 4000

    def test_set_map_size_minimum_of_one(self, minimap):
        minimap.set_map_size(0, 0)
        assert minimap._map_w == 1
        assert minimap._map_h == 1

    def test_set_player_pos_vector(self, minimap):
        pos = pygame.math.Vector2(100, 200)
        minimap.set_player_pos(pos)
        assert minimap._player_pos == (100.0, 200.0)

    def test_set_player_pos_tuple(self, minimap):
        minimap.set_player_pos((300, 400))
        assert minimap._player_pos == (300.0, 400.0)

    def test_set_extraction_zones(self, minimap):
        zones = [make_zone("a", 100, 100), make_zone("b", 500, 500)]
        minimap.set_extraction_zones(zones)
        assert len(minimap._extraction_zones) == 2

    def test_set_extraction_zones_makes_copy(self, minimap):
        zones = [make_zone("a", 100, 100)]
        minimap.set_extraction_zones(zones)
        zones.append(make_zone("b", 500, 500))
        # Original list mutated, but minimap's copy should not be
        assert len(minimap._extraction_zones) == 1

    def test_set_extracting(self, minimap):
        minimap.set_extracting(True)
        assert minimap._is_extracting
        minimap.set_extracting(False)
        assert not minimap._is_extracting

    def test_update_advances_anim_time(self, minimap):
        minimap.update(0.5)
        assert minimap._anim_time == pytest.approx(0.5)


# ======================================================================
# Rendering
# ======================================================================


class TestMinimapRendering:
    @pytest.fixture
    def surface(self):
        return pygame.Surface((1280, 720))

    @pytest.fixture
    def minimap(self):
        mm = Minimap(screen_width=1280, screen_height=720)
        mm.set_map_size(2560, 1920)
        return mm

    def test_draw_empty_no_crash(self, minimap, surface):
        minimap.draw(surface)

    def test_draw_with_player_pos(self, minimap, surface):
        minimap.set_player_pos((500, 500))
        minimap.draw(surface)

    def test_draw_with_extraction_zones(self, minimap, surface):
        zones = [make_zone("a", 200, 200), make_zone("b", 1000, 1000)]
        minimap.set_extraction_zones(zones)
        minimap.draw(surface)

    def test_draw_with_extracting_pulse(self, minimap, surface):
        zones = [make_zone("a", 200, 200)]
        minimap.set_extraction_zones(zones)
        minimap.set_extracting(True)
        minimap.update(1.0)
        minimap.draw(surface)

    def test_draw_extraction_marker_at_zone_center(self, minimap, surface):
        zone = make_zone("test", 1280, 960, 128, 128)
        minimap.set_extraction_zones([zone])
        minimap.draw(surface)

    def test_draw_multiple_frames_no_crash(self, minimap, surface):
        zones = [make_zone("a", 200, 200)]
        minimap.set_extraction_zones(zones)
        minimap.set_player_pos((200, 200))
        for _ in range(30):
            minimap.update(0.016)
            minimap.draw(surface)

    def test_draw_with_zone_at_map_edge(self, minimap, surface):
        """Zone at the very edge of the map should still render."""
        zone = make_zone("edge", 2432, 1792, 128, 128)
        minimap.set_extraction_zones([zone])
        minimap.draw(surface)

    def test_draw_with_zone_outside_map(self, minimap, surface):
        """Zone beyond map boundaries should be clamped and not crash."""
        zone = make_zone("far", 5000, 5000, 128, 128)
        minimap.set_extraction_zones([zone])
        minimap.draw(surface)


# ======================================================================
# Position (screen placement)
# ======================================================================


class TestMinimapPosition:
    def test_positioned_bottom_right(self):
        mm = Minimap(screen_width=1280, screen_height=720)
        expected_x = 1280 - 160 - 16
        expected_y = 720 - 160 - 16
        assert mm._x == expected_x
        assert mm._y == expected_y

    def test_different_screen_size(self):
        mm = Minimap(screen_width=800, screen_height=600)
        assert mm._x == 800 - 160 - 16
        assert mm._y == 600 - 160 - 16
