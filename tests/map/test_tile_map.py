# Run: pytest tests/map/test_tile_map.py
"""Unit and integration tests for TileMap.

Covers:
- baked_minimap creation, dimensions, and per-tile pixel colours
- map_rect pixel dimensions (tiles × tile_size)
- Zone.color read from JSON, and the default when the key is absent
- extraction_rect alignment with TILE_EXTRACTION row in the grid
- Data-driven loading: optional keys use safe defaults, mandatory 'tiles' raises KeyError
- Feature requirement: ≥1 extraction zone, ≥2 named challenge zones in the real map
- Feature requirement: solid tiles are walls; open/extraction tiles allow passage (is_solid)
- Feature requirement: walkability_grid mirrors is_solid results
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pygame
import pytest

from src.map.tile_map import TileMap, TILE_AIR, TILE_SOLID, TILE_EXTRACTION

_ROOT = Path(__file__).resolve().parent.parent.parent
_REAL_MAP = str(_ROOT / "assets" / "maps" / "map_01.json")


# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def small_map_json(tmp_path):
    """10×8 map: solid top/bottom borders, air interior, one extraction tile.

    Tile layout (row, col → tile):
        row 0        — all TILE_SOLID  (ceiling)
        row 1, col 4 — TILE_EXTRACTION
        rows 1-5     — TILE_AIR elsewhere (with solid left/right walls)
        rows 6-7     — all TILE_SOLID  (floor)

    Zones include explicit "color" keys so we can verify color loading.
    """
    tiles: list[list[int]] = []
    for row in range(8):
        if row == 0 or row >= 6:
            tiles.append([TILE_SOLID] * 10)
        else:
            tiles.append([TILE_SOLID] + [TILE_AIR] * 8 + [TILE_SOLID])
    tiles[1][4] = TILE_EXTRACTION

    data = {
        "tile_size": 32,
        "tiles": tiles,
        "player_spawn": [64, 128],
        "extraction_rect": [96, 32, 64, 32],
        "loot_spawns": [[64, 96], [128, 160]],
        "zones": [
            {
                "name": "RED_ZONE",
                "rect": [0, 0, 160, 256],
                "spawn_points": [[64, 128]],
                "enemy_spawns": [{"type": "grunt", "pos": [80, 160]}],
                "music_track": None,
                "color": [200, 50, 50],
            },
            {
                "name": "BLUE_ZONE",
                "rect": [160, 0, 160, 256],
                "spawn_points": [[224, 128]],
                "enemy_spawns": [],
                "music_track": None,
                "color": [50, 50, 200],
            },
        ],
    }
    path = tmp_path / "small_map.json"
    path.write_text(json.dumps(data))
    return str(path)


@pytest.fixture
def minimal_map_json(tmp_path):
    """Bare-minimum map with only the mandatory 'tiles' key."""
    tiles = [[TILE_SOLID] * 5 for _ in range(3)]
    data = {"tiles": tiles}
    path = tmp_path / "minimal.json"
    path.write_text(json.dumps(data))
    return str(path)


@pytest.fixture
def real_map():
    """Load assets/maps/map_01.json — skips the test when the file is absent."""
    if not os.path.exists(_REAL_MAP):
        pytest.skip("Real map not present")
    return TileMap.load(_REAL_MAP)


# ---------------------------------------------------------------------------
# TestBakedMinimap — unit tests for the 1-px-per-tile baked surface
# ---------------------------------------------------------------------------


class TestBakedMinimap:
    """TileMap._bake_minimap() must produce the correct pixel colours."""

    def test_baked_minimap_is_not_none_after_normal_load(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.baked_minimap is not None

    def test_baked_minimap_is_pygame_surface(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert isinstance(tm.baked_minimap, pygame.Surface)

    def test_baked_minimap_width_equals_tile_column_count(self, small_map_json):
        tm = TileMap.load(small_map_json)
        w, _ = tm.baked_minimap.get_size()
        assert w == tm.width  # 10

    def test_baked_minimap_height_equals_tile_row_count(self, small_map_json):
        tm = TileMap.load(small_map_json)
        _, h = tm.baked_minimap.get_size()
        assert h == tm.height  # 8

    def test_solid_tile_pixel_is_dark_blue(self, small_map_json):
        """TILE_SOLID at (col=0, row=0) must be rendered as (35, 50, 70)."""
        tm = TileMap.load(small_map_json)
        colour = tm.baked_minimap.get_at((0, 0))[:3]
        assert colour == (35, 50, 70)

    def test_extraction_tile_pixel_is_green(self, small_map_json):
        """TILE_EXTRACTION at (col=4, row=1) must be rendered as (0, 200, 80)."""
        tm = TileMap.load(small_map_json)
        colour = tm.baked_minimap.get_at((4, 1))[:3]
        assert colour == (0, 200, 80)

    def test_air_tile_pixel_is_dark_background(self, small_map_json):
        """TILE_AIR at (col=1, row=1) must be rendered as (6, 10, 18)."""
        tm = TileMap.load(small_map_json)
        colour = tm.baked_minimap.get_at((1, 1))[:3]
        assert colour == (6, 10, 18)

    def test_entire_solid_row_has_solid_colour(self, small_map_json):
        """Every pixel in the all-solid row 0 must be the solid colour."""
        tm = TileMap.load(small_map_json)
        for col in range(tm.width):
            colour = tm.baked_minimap.get_at((col, 0))[:3]
            assert colour == (35, 50, 70), (
                f"col={col} row=0 expected solid colour, got {colour}"
            )

    def test_baked_minimap_returns_none_for_empty_tile_grid(self, tmp_path):
        """An empty tile grid (height=0) must not crash — returns None."""
        data = {"tiles": []}
        path = tmp_path / "empty.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert tm.baked_minimap is None

    # -- Real-map integration tests --

    def test_real_map_baked_minimap_dimensions_are_100_by_30(self, real_map):
        w, h = real_map.baked_minimap.get_size()
        assert w == 100
        assert h == 30

    def test_real_map_row0_every_pixel_is_solid_colour(self, real_map):
        """Row 0 of the real map is all TILE_SOLID — every minimap pixel must match."""
        for col in range(real_map.width):
            colour = real_map.baked_minimap.get_at((col, 0))[:3]
            assert colour == (35, 50, 70), (
                f"col={col} row=0 expected solid colour, got {colour}"
            )

    def test_real_map_extraction_tiles_row5_cols_80_to_94_are_green(self, real_map):
        """TILE_EXTRACTION tiles sit at row=5, cols=80–94 in the real map."""
        for col in range(80, 95):
            colour = real_map.baked_minimap.get_at((col, 5))[:3]
            assert colour == (0, 200, 80), (
                f"col={col} row=5 expected extraction colour, got {colour}"
            )

    def test_real_map_air_interior_pixel_is_dark_background(self, real_map):
        """Row 1, col 1 is TILE_AIR in the real map interior."""
        colour = real_map.baked_minimap.get_at((1, 1))[:3]
        assert colour == (6, 10, 18)


# ---------------------------------------------------------------------------
# TestMapRect — unit tests for the map_rect property
# ---------------------------------------------------------------------------


class TestMapRect:
    """map_rect must exactly cover width×tile_size by height×tile_size pixels."""

    def test_map_rect_origin_is_zero_zero(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.map_rect.x == 0
        assert tm.map_rect.y == 0

    def test_map_rect_width_equals_tile_columns_times_tile_size(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.map_rect.width == tm.width * tm.tile_size  # 10 × 32 = 320

    def test_map_rect_height_equals_tile_rows_times_tile_size(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.map_rect.height == tm.height * tm.tile_size  # 8 × 32 = 256

    def test_map_rect_is_pygame_rect_instance(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert isinstance(tm.map_rect, pygame.Rect)

    def test_map_rect_equals_expected_value(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.map_rect == pygame.Rect(0, 0, 320, 256)

    # -- Real-map integration tests --

    def test_real_map_rect_is_3200_by_960(self, real_map):
        """100 cols × 32 = 3 200 px wide, 30 rows × 32 = 960 px tall."""
        assert real_map.map_rect == pygame.Rect(0, 0, 3200, 960)


# ---------------------------------------------------------------------------
# TestZoneColors — unit tests for the Zone.color field loaded from JSON
# ---------------------------------------------------------------------------


class TestZoneColors:
    """Zone.color must be read from the JSON 'color' key or default to (60, 120, 180)."""

    def test_zones_have_color_attribute(self, small_map_json):
        tm = TileMap.load(small_map_json)
        for zone in tm.zones:
            assert hasattr(zone, "color"), f"Zone {zone.name!r} missing .color"

    def test_red_zone_color_matches_json(self, small_map_json):
        tm = TileMap.load(small_map_json)
        red = next(z for z in tm.zones if z.name == "RED_ZONE")
        assert red.color == (200, 50, 50)

    def test_blue_zone_color_matches_json(self, small_map_json):
        tm = TileMap.load(small_map_json)
        blue = next(z for z in tm.zones if z.name == "BLUE_ZONE")
        assert blue.color == (50, 50, 200)

    def test_zone_color_defaults_to_blue_when_key_absent(self, tmp_map_json):
        """tmp_map_json zones have no 'color' key → default (60, 120, 180)."""
        tm = TileMap.load(tmp_map_json)
        for zone in tm.zones:
            assert zone.color == (60, 120, 180), (
                f"Zone {zone.name!r} should default to (60, 120, 180), got {zone.color}"
            )

    def test_zone_color_is_a_three_element_tuple(self, small_map_json):
        tm = TileMap.load(small_map_json)
        for zone in tm.zones:
            assert isinstance(zone.color, tuple)
            assert len(zone.color) == 3

    def test_zone_color_components_are_valid_rgb(self, small_map_json):
        tm = TileMap.load(small_map_json)
        for zone in tm.zones:
            for component in zone.color:
                assert isinstance(component, int)
                assert 0 <= component <= 255

    # -- Real-map integration tests --

    def test_real_map_all_zones_have_color_attribute(self, real_map):
        assert len(real_map.zones) >= 1
        for zone in real_map.zones:
            assert hasattr(zone, "color")
            assert len(zone.color) == 3

    def test_real_map_has_three_named_zones(self, real_map):
        names = {z.name for z in real_map.zones}
        assert "HANGAR BAY" in names
        assert "REACTOR CORE" in names
        assert "EXTRACTION PAD" in names


# ---------------------------------------------------------------------------
# TestExtractionRect — alignment between JSON rect and TILE_EXTRACTION tiles
# ---------------------------------------------------------------------------


class TestExtractionRect:
    """extraction_rect must be a pygame.Rect that matches the tile-grid geometry."""

    def test_extraction_rect_is_pygame_rect(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert isinstance(tm.extraction_rect, pygame.Rect)

    def test_extraction_rect_matches_json_values(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.extraction_rect == pygame.Rect(96, 32, 64, 32)

    def test_real_map_extraction_rect_is_not_none(self, real_map):
        assert real_map.extraction_rect is not None

    def test_real_map_extraction_rect_x_aligns_with_column_80(self, real_map):
        """TILE_EXTRACTION starts at col 80 → x = 80 × 32 = 2 560 px."""
        assert real_map.extraction_rect.x == 2560

    def test_real_map_extraction_rect_y_aligns_with_row_5(self, real_map):
        """TILE_EXTRACTION tiles are in row 5 → y = 5 × 32 = 160 px.

        NOTE: This test verifies the intended geometry.  If it fails, the JSON
        field 'extraction_rect' needs updating from y=128 to y=160 to align
        with the actual TILE_EXTRACTION row in the tile grid.
        """
        assert real_map.extraction_rect.y == 160, (
            f"extraction_rect.y should be 160 (row-5 × 32 px), "
            f"got {real_map.extraction_rect.y}. "
            "Update assets/maps/map_01.json: set extraction_rect[1] to 160."
        )

    def test_real_map_grid_contains_at_least_one_extraction_tile(self, real_map):
        """Feature requirement: map must have at least one extraction zone tile."""
        found = any(
            real_map.tiles[r][c] == TILE_EXTRACTION
            for r in range(real_map.height)
            for c in range(real_map.width)
        )
        assert found, "Real map must contain at least one TILE_EXTRACTION tile"


# ---------------------------------------------------------------------------
# TestIsSolid — unit tests verifying solid-tile physics semantics
# ---------------------------------------------------------------------------


class TestIsSolid:
    """Solid tiles must block; air and extraction tiles must pass freely."""

    def test_solid_ceiling_tiles_return_true(self, small_map_json):
        tm = TileMap.load(small_map_json)
        for col in range(tm.width):
            assert tm.is_solid(col, 0), f"Ceiling col {col} should be solid"

    def test_solid_floor_tiles_return_true(self, small_map_json):
        tm = TileMap.load(small_map_json)
        for col in range(tm.width):
            assert tm.is_solid(col, 6), f"Floor col {col} row 6 should be solid"

    def test_air_interior_returns_false(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert not tm.is_solid(1, 1)
        assert not tm.is_solid(5, 3)

    def test_extraction_tile_is_not_solid(self, small_map_json):
        """TILE_EXTRACTION at (4, 1) must be passable for players to stand there."""
        tm = TileMap.load(small_map_json)
        assert not tm.is_solid(4, 1)

    def test_oob_negative_x_is_solid(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.is_solid(-1, 0)

    def test_oob_negative_y_is_solid(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.is_solid(0, -1)

    def test_oob_far_right_is_solid(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.is_solid(9999, 0)

    def test_oob_far_bottom_is_solid(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.is_solid(0, 9999)


# ---------------------------------------------------------------------------
# TestWalkabilityGrid — unit tests verifying the grid mirrors is_solid
# ---------------------------------------------------------------------------


class TestWalkabilityGrid:
    """walkability_grid[r][c] == 0 iff is_solid(c, r); 1 otherwise."""

    def test_grid_row_count_matches_tile_height(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert len(tm.walkability_grid) == tm.height

    def test_grid_column_count_matches_tile_width(self, small_map_json):
        tm = TileMap.load(small_map_json)
        for row in tm.walkability_grid:
            assert len(row) == tm.width

    def test_solid_tiles_have_walkability_zero(self, small_map_json):
        tm = TileMap.load(small_map_json)
        wg = tm.walkability_grid
        for col in range(tm.width):
            assert wg[0][col] == 0, f"Solid ceiling col {col} should be walkability 0"

    def test_air_tiles_have_walkability_one(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.walkability_grid[1][1] == 1
        assert tm.walkability_grid[3][5] == 1

    def test_extraction_tiles_have_walkability_one(self, small_map_json):
        """Players can walk on extraction tiles — they must not block movement."""
        tm = TileMap.load(small_map_json)
        assert tm.walkability_grid[1][4] == 1

    def test_grid_mirrors_is_solid_for_all_cells(self, small_map_json):
        """walkability_grid must be the exact complement of is_solid over the map."""
        tm = TileMap.load(small_map_json)
        wg = tm.walkability_grid
        for row in range(tm.height):
            for col in range(tm.width):
                expected = 0 if tm.is_solid(col, row) else 1
                assert wg[row][col] == expected, (
                    f"Mismatch at ({col}, {row}): "
                    f"is_solid={tm.is_solid(col, row)}, walkability={wg[row][col]}"
                )


# ---------------------------------------------------------------------------
# TestDataDrivenLoad — optional JSON keys fall back to safe defaults
# ---------------------------------------------------------------------------


class TestDataDrivenLoad:
    """New map layouts need zero code changes — only a JSON file is required."""

    def test_minimal_json_loads_without_error(self, minimal_map_json):
        tm = TileMap.load(minimal_map_json)
        assert tm is not None

    def test_tile_size_defaults_to_32_when_absent(self, minimal_map_json):
        tm = TileMap.load(minimal_map_json)
        assert tm.tile_size == 32

    def test_player_spawn_defaults_when_absent(self, minimal_map_json):
        tm = TileMap.load(minimal_map_json)
        # Must not crash; default is (96.0, 832.0) per src/map/tile_map.py
        assert isinstance(tm.player_spawn, tuple)
        assert len(tm.player_spawn) == 2

    def test_loot_spawns_default_to_empty_list(self, minimal_map_json):
        tm = TileMap.load(minimal_map_json)
        assert tm.loot_spawns == []

    def test_zones_default_to_empty_list(self, minimal_map_json):
        tm = TileMap.load(minimal_map_json)
        assert tm.zones == []

    def test_extraction_rect_has_safe_default(self, minimal_map_json):
        tm = TileMap.load(minimal_map_json)
        assert isinstance(tm.extraction_rect, pygame.Rect)

    def test_missing_tiles_key_raises_key_error(self, tmp_path):
        """'tiles' is the one mandatory key — missing it must raise KeyError."""
        data = {"tile_size": 32, "width": 5, "height": 3}
        path = tmp_path / "no_tiles.json"
        path.write_text(json.dumps(data))
        with pytest.raises(KeyError):
            TileMap.load(str(path))

    def test_custom_tile_size_overrides_default(self, tmp_path):
        tiles = [[TILE_SOLID] * 4 for _ in range(3)]
        data = {"tile_size": 16, "tiles": tiles}
        path = tmp_path / "custom_tile_size.json"
        path.write_text(json.dumps(data))
        tm = TileMap.load(str(path))
        assert tm.tile_size == 16

    def test_loot_spawns_loaded_correctly(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert len(tm.loot_spawns) == 2
        assert tm.loot_spawns[0] == (64.0, 96.0)

    def test_player_spawn_loaded_correctly(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert tm.player_spawn == (64.0, 128.0)

    def test_zone_count_matches_json(self, small_map_json):
        tm = TileMap.load(small_map_json)
        assert len(tm.zones) == 2

    def test_zone_rect_is_pygame_rect(self, small_map_json):
        tm = TileMap.load(small_map_json)
        for zone in tm.zones:
            assert isinstance(zone.rect, pygame.Rect)

    def test_zone_spawn_points_loaded(self, small_map_json):
        tm = TileMap.load(small_map_json)
        red = next(z for z in tm.zones if z.name == "RED_ZONE")
        assert red.spawn_points == [(64.0, 128.0)]

    def test_zone_enemy_spawns_loaded(self, small_map_json):
        tm = TileMap.load(small_map_json)
        red = next(z for z in tm.zones if z.name == "RED_ZONE")
        assert len(red.enemy_spawns) == 1
        assert red.enemy_spawns[0]["type"] == "grunt"


# ---------------------------------------------------------------------------
# E2E integration: real map → baked minimap → HUDState → MiniMap render
# ---------------------------------------------------------------------------


class TestFullMiniMapPipeline:
    """End-to-end: load real map, thread baked_minimap through HUDState, render."""

    def test_pipeline_from_real_map_to_minimap_render(self, real_map):
        """The baked surface flows: TileMap → HUDState.tile_surf → MiniMap.draw()."""
        from src.ui.hud_state import HUDState
        from src.ui.mini_map import MiniMap

        tile_surf = real_map.baked_minimap
        assert tile_surf is not None

        state = HUDState(
            map_world_rect=real_map.map_rect,
            player_world_pos=(96.0, 832.0),
            tile_surf=tile_surf,
        )

        mini_rect = pygame.Rect(1064, 16, 180, 180)
        mm = MiniMap(mini_rect)
        mm.update(state)

        surface = pygame.Surface((1280, 720))
        surface.fill((0, 0, 0))
        mm.draw(surface)  # must not raise

        # At least one pixel inside the minimap rect should be non-black
        # because the tile surface was blitted
        found = False
        for y in range(mini_rect.top, mini_rect.bottom, 2):
            for x in range(mini_rect.left, mini_rect.right, 2):
                if surface.get_at((x, y))[:3] != (0, 0, 0):
                    found = True
                    break
            if found:
                break
        assert found, "MiniMap.draw() must write tile pixels inside the minimap rect"
