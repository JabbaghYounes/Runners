"""Tests for TileMap loading, is_solid(), and walkability_grid.

Run: pytest tests/test_tile_map.py
"""
from __future__ import annotations

import json
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


# ---------------------------------------------------------------------------
# player_spawns — new multi-point list field
# ---------------------------------------------------------------------------


class TestPlayerSpawns:
    """TileMap.player_spawns is a list of (x, y) tuples for the new spawn format."""

    def test_player_spawns_attribute_exists(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        assert hasattr(tm, "player_spawns")

    def test_player_spawns_is_a_list(self, tmp_map_json):
        tm = TileMap.load(tmp_map_json)
        assert isinstance(tm.player_spawns, list)

    def test_legacy_player_spawn_key_produces_one_element_list(self, tmp_path):
        """JSON with only 'player_spawn' (singular) produces a one-element player_spawns list."""
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "player_spawn": [64.0, 64.0],
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [],
        }
        path = tmp_path / "legacy.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert tm.player_spawns == [(64.0, 64.0)]

    def test_legacy_player_spawn_preserves_scalar_player_spawn(self, tmp_path):
        """The legacy scalar player_spawn attribute still points at the first spawn."""
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "player_spawn": [96.0, 128.0],
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [],
        }
        path = tmp_path / "legacy2.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert tm.player_spawn == (96.0, 128.0)

    def test_multi_point_player_spawns_loaded_correctly(self, tmp_path):
        """JSON with 'player_spawns' (list) populates all spawn points."""
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "player_spawns": [[32.0, 64.0], [96.0, 64.0], [160.0, 64.0]],
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [],
        }
        path = tmp_path / "multi.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert tm.player_spawns == [(32.0, 64.0), (96.0, 64.0), (160.0, 64.0)]

    def test_multi_point_scalar_player_spawn_points_at_first(self, tmp_path):
        """Legacy scalar player_spawn always points at the first entry."""
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "player_spawns": [[100.0, 200.0], [300.0, 400.0]],
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [],
        }
        path = tmp_path / "multi2.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert tm.player_spawn == (100.0, 200.0)

    def test_missing_both_spawn_keys_falls_back_to_default(self, tmp_path):
        """When both 'player_spawn' and 'player_spawns' are absent, a safe default is used."""
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [],
        }
        path = tmp_path / "nokey.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert isinstance(tm.player_spawns, list)
        assert len(tm.player_spawns) >= 1

    def test_player_spawns_values_are_float_tuples(self, tmp_path):
        """Each entry in player_spawns is a tuple of two floats."""
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "player_spawns": [[64, 128]],  # JSON integers, not floats
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [],
        }
        path = tmp_path / "intspawns.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        x, y = tm.player_spawns[0]
        assert isinstance(x, float)
        assert isinstance(y, float)


# ---------------------------------------------------------------------------
# Zone pvp_bot_spawns loading
# ---------------------------------------------------------------------------


class TestZonePvpBotSpawns:
    """TileMap.load() parses pvp_bot_spawns per zone from JSON."""

    def test_zone_pvp_bot_spawns_attribute_exists(self, tmp_path):
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "player_spawn": [64, 64],
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [{
                "name": "TEST_ZONE",
                "rect": [0, 0, 128, 128],
                "spawn_points": [],
                "enemy_spawns": [],
                "pvp_bot_spawns": [[32.0, 64.0], [96.0, 64.0]],
                "music_track": None,
            }],
        }
        path = tmp_path / "pvp_zone.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert hasattr(tm.zones[0], "pvp_bot_spawns")

    def test_zone_pvp_bot_spawns_values_loaded_correctly(self, tmp_path):
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "player_spawn": [64, 64],
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [{
                "name": "TEST_ZONE",
                "rect": [0, 0, 128, 128],
                "spawn_points": [],
                "enemy_spawns": [],
                "pvp_bot_spawns": [[32.0, 64.0], [96.0, 64.0]],
                "music_track": None,
            }],
        }
        path = tmp_path / "pvp_zone2.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert tm.zones[0].pvp_bot_spawns == [(32.0, 64.0), (96.0, 64.0)]

    def test_zone_without_pvp_bot_spawns_key_defaults_to_empty_list(self, tmp_path):
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "player_spawn": [64, 64],
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [{
                "name": "NO_BOT_ZONE",
                "rect": [0, 0, 128, 128],
                "spawn_points": [],
                "enemy_spawns": [],
                "music_track": None,
                # no pvp_bot_spawns key at all
            }],
        }
        path = tmp_path / "no_pvp.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert tm.zones[0].pvp_bot_spawns == []

    def test_pvp_bot_spawn_values_are_float_tuples(self, tmp_path):
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "player_spawn": [64, 64],
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [{
                "name": "Z",
                "rect": [0, 0, 128, 128],
                "spawn_points": [],
                "enemy_spawns": [],
                "pvp_bot_spawns": [[50, 75]],  # JSON integers
                "music_track": None,
            }],
        }
        path = tmp_path / "intpvp.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        x, y = tm.zones[0].pvp_bot_spawns[0]
        assert isinstance(x, float)
        assert isinstance(y, float)

    def test_multiple_zones_each_carry_their_own_pvp_bot_spawns(self, tmp_path):
        tiles = [[1] * 4 for _ in range(4)]
        data = {
            "tile_size": 32, "width": 4, "height": 4, "tiles": tiles,
            "player_spawn": [64, 64],
            "extraction_rect": [0, 0, 32, 32],
            "loot_spawns": [],
            "zones": [
                {
                    "name": "ZONE_A",
                    "rect": [0, 0, 128, 128],
                    "spawn_points": [],
                    "enemy_spawns": [],
                    "pvp_bot_spawns": [[10.0, 20.0]],
                    "music_track": None,
                },
                {
                    "name": "ZONE_B",
                    "rect": [128, 0, 128, 128],
                    "spawn_points": [],
                    "enemy_spawns": [],
                    "pvp_bot_spawns": [[30.0, 40.0], [50.0, 60.0]],
                    "music_track": None,
                },
            ],
        }
        path = tmp_path / "multi_zone.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert len(tm.zones[0].pvp_bot_spawns) == 1
        assert len(tm.zones[1].pvp_bot_spawns) == 2


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
