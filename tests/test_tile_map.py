"""Tests for TileMap loading, is_solid(), and walkability_grid."""
import pytest
import pygame
from src.map.tile_map import TileMap


class TestTileMapLoad:
    def test_tile_size(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        assert tm.tile_size == 32

    def test_dimensions(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        assert tm.width == 10
        assert tm.height == 8

    def test_player_spawn(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        assert tm.player_spawn == (64.0, 128.0)

    def test_extraction_rect_populated(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        assert tm.extraction_rect is not None
        assert isinstance(tm.extraction_rect, pygame.Rect)
        assert tm.extraction_rect.width == 64

    def test_zones_count(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        assert len(tm.zones) >= 3

    def test_zone_names(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        names = [z.name for z in tm.zones]
        assert "ZONE_A" in names
        assert "ZONE_B" in names


class TestIsSolid:
    def test_ceiling_is_solid(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        # Row 0 is all solid
        for col in range(tm.width):
            assert tm.is_solid(col, 0), f"col {col} row 0 should be solid"

    def test_interior_air_not_solid(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        # Row 1-5, col 1-8 are air (0)
        assert not tm.is_solid(1, 1)
        assert not tm.is_solid(5, 3)

    def test_ground_is_solid(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        for col in range(tm.width):
            assert tm.is_solid(col, 7), f"bottom row col {col} should be solid"

    def test_out_of_bounds_is_solid(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        assert tm.is_solid(-1, 0)
        assert tm.is_solid(0, -1)
        assert tm.is_solid(999, 0)
        assert tm.is_solid(0, 999)

    def test_extraction_tile_not_solid(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        # tiles[1][4] == 2 (extraction) — not solid
        assert not tm.is_solid(4, 1)


class TestWalkabilityGrid:
    def test_grid_shape(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        wg = tm.walkability_grid
        assert len(wg) == tm.height
        for row in wg:
            assert len(row) == tm.width

    def test_solid_tiles_not_walkable(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        wg = tm.walkability_grid
        # Row 0 is solid → walkability 0
        for col in range(tm.width):
            assert wg[0][col] == 0, f"solid ceiling col {col} should have walkability 0"

    def test_air_tiles_walkable(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        wg = tm.walkability_grid
        assert wg[1][1] == 1


class TestTileMapFromRealMap:
    """Smoke-test against the actual game map."""

    def test_real_map_loads(self):
        import os
        _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        map_path = os.path.join(_ROOT, 'assets', 'maps', 'map_01.json')
        if not os.path.exists(map_path):
            pytest.skip("Real map not present")
        tm = TileMap.load(map_path)
        assert tm.tile_size == 32
        assert tm.width == 100
        assert tm.height == 30
        assert len(tm.zones) == 3
        assert tm.extraction_rect is not None

    def test_real_map_three_zone_names(self):
        import os
        _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        map_path = os.path.join(_ROOT, 'assets', 'maps', 'map_01.json')
        if not os.path.exists(map_path):
            pytest.skip("Real map not present")
        tm = TileMap.load(map_path)
        names = [z.name for z in tm.zones]
        assert "HANGAR BAY" in names
        assert "REACTOR CORE" in names
        assert "EXTRACTION PAD" in names
