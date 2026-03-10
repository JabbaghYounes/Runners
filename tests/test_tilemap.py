"""Unit tests for TileMap, Camera, Zone, and SpawnPoint."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

pygame.init()

from src.map import TileMap, Camera, Zone, SpawnPoint


# =====================================================================
# TileMap — Loading from JSON
# =====================================================================

class TestTileMapLoad:

    def test_load_map_dimensions(self):
        tilemap = TileMap("data/maps/map_01.json")
        assert tilemap.width == 80
        assert tilemap.height == 60

    def test_load_tile_size(self):
        tilemap = TileMap("data/maps/map_01.json")
        assert tilemap.tile_size == 32

    def test_load_zones(self):
        tilemap = TileMap("data/maps/map_01.json")
        assert len(tilemap.zones) == 3

    def test_zone_names(self):
        tilemap = TileMap("data/maps/map_01.json")
        names = {z.name for z in tilemap.zones}
        assert "spawn_a" in names
        assert "challenge_1" in names
        assert "extract_a" in names

    def test_zone_types(self):
        tilemap = TileMap("data/maps/map_01.json")
        types = {z.zone_type for z in tilemap.zones}
        assert "spawn" in types
        assert "challenge" in types
        assert "extraction" in types

    def test_zone_has_rect(self):
        tilemap = TileMap("data/maps/map_01.json")
        for z in tilemap.zones:
            assert isinstance(z.rect, pygame.Rect)

    def test_zone_metadata_for_challenge(self):
        tilemap = TileMap("data/maps/map_01.json")
        challenge_zones = [z for z in tilemap.zones if z.name == "challenge_1"]
        assert len(challenge_zones) == 1
        assert challenge_zones[0].metadata.get("challenge_id") == "elim_01"

    def test_loads_layers(self):
        tilemap = TileMap("data/maps/map_01.json")
        assert "ground" in tilemap.layers
        assert "walls" in tilemap.layers
        assert "decoration" in tilemap.layers


# =====================================================================
# TileMap — is_solid
# =====================================================================

class TestTileMapCollision:

    def test_negative_x_is_solid(self):
        tilemap = TileMap()
        assert tilemap.is_solid(-1, 0) is True

    def test_negative_y_is_solid(self):
        tilemap = TileMap()
        assert tilemap.is_solid(0, -1) is True

    def test_both_negative_is_solid(self):
        tilemap = TileMap()
        assert tilemap.is_solid(-5, -5) is True

    def test_out_of_bounds_is_solid(self):
        """Querying beyond collision grid boundaries returns True."""
        tilemap = TileMap()
        tilemap.collision = [[0, 0], [0, 0]]
        # Width is 2, so index 5 is out of bounds
        assert tilemap.is_solid(5, 0) is True

    def test_empty_collision_grid_is_solid(self):
        tilemap = TileMap()
        tilemap.collision = []
        assert tilemap.is_solid(0, 0) is True

    def test_non_zero_is_solid(self):
        tilemap = TileMap()
        tilemap.collision = [[0, 1, 0], [0, 0, 0]]
        assert tilemap.is_solid(1, 0) is True

    def test_zero_is_not_solid(self):
        tilemap = TileMap()
        tilemap.collision = [[0, 1, 0], [0, 0, 0]]
        assert tilemap.is_solid(0, 0) is False


# =====================================================================
# TileMap — raycast_solid
# =====================================================================

class TestTileMapRaycast:

    def test_clear_line_of_sight(self):
        tilemap = TileMap()
        tilemap.collision = [[0] * 20 for _ in range(20)]
        tilemap.tile_size = 32
        assert tilemap.raycast_solid((32, 32), (320, 32)) is False

    def test_blocked_by_wall(self):
        tilemap = TileMap()
        tilemap.collision = [[0] * 20 for _ in range(20)]
        tilemap.tile_size = 32
        # Place a wall at grid (5, 1) between start (1,1) and end (10,1)
        tilemap.collision[1][5] = 1
        assert tilemap.raycast_solid((32, 32), (320, 32)) is True

    def test_same_tile_returns_false(self):
        tilemap = TileMap()
        tilemap.collision = [[0] * 5 for _ in range(5)]
        tilemap.tile_size = 32
        assert tilemap.raycast_solid((50, 50), (55, 55)) is False

    def test_adjacent_tiles_clear(self):
        tilemap = TileMap()
        tilemap.collision = [[0] * 5 for _ in range(5)]
        tilemap.tile_size = 32
        assert tilemap.raycast_solid((32, 32), (64, 32)) is False

    def test_diagonal_line_blocked(self):
        tilemap = TileMap()
        tilemap.collision = [[0] * 20 for _ in range(20)]
        tilemap.tile_size = 32
        # Wall on diagonal path
        tilemap.collision[3][3] = 1
        assert tilemap.raycast_solid((32, 32), (160, 160)) is True

    def test_start_tile_not_checked(self):
        """The enemy's own tile should not block LOS."""
        tilemap = TileMap()
        tilemap.collision = [[0] * 5 for _ in range(5)]
        tilemap.tile_size = 32
        # Make start tile solid — should still not block
        tilemap.collision[1][1] = 1
        assert tilemap.raycast_solid((32, 32), (128, 32)) is False


# =====================================================================
# TileMap — get_enemy_spawns
# =====================================================================

class TestTileMapEnemySpawns:

    def test_returns_spawn_list(self):
        tilemap = TileMap("data/maps/map_01.json")
        spawns = tilemap.get_enemy_spawns()
        assert isinstance(spawns, list)
        assert len(spawns) == 8

    def test_spawn_has_pos(self):
        tilemap = TileMap("data/maps/map_01.json")
        spawns = tilemap.get_enemy_spawns()
        for spawn in spawns:
            assert "pos" in spawn
            assert len(spawn["pos"]) == 2

    def test_spawn_has_tier(self):
        tilemap = TileMap("data/maps/map_01.json")
        spawns = tilemap.get_enemy_spawns()
        for spawn in spawns:
            assert "tier" in spawn
            assert spawn["tier"] in ("scout", "enforcer")

    def test_spawn_has_patrol_path(self):
        tilemap = TileMap("data/maps/map_01.json")
        spawns = tilemap.get_enemy_spawns()
        for spawn in spawns:
            assert "patrol_path" in spawn
            assert len(spawn["patrol_path"]) >= 2

    def test_returns_copy(self):
        """get_enemy_spawns should return a copy, not the internal list."""
        tilemap = TileMap("data/maps/map_01.json")
        spawns1 = tilemap.get_enemy_spawns()
        spawns2 = tilemap.get_enemy_spawns()
        assert spawns1 is not spawns2

    def test_tier_distribution(self):
        """Map has 5 scouts and 3 enforcers."""
        tilemap = TileMap("data/maps/map_01.json")
        spawns = tilemap.get_enemy_spawns()
        scouts = [s for s in spawns if s["tier"] == "scout"]
        enforcers = [s for s in spawns if s["tier"] == "enforcer"]
        assert len(scouts) == 5
        assert len(enforcers) == 3

    def test_empty_map_returns_empty(self):
        tilemap = TileMap()
        assert tilemap.get_enemy_spawns() == []


# =====================================================================
# TileMap — init without path
# =====================================================================

class TestTileMapEmpty:

    def test_default_tile_size(self):
        tilemap = TileMap()
        assert tilemap.tile_size == 32

    def test_default_dimensions_zero(self):
        tilemap = TileMap()
        assert tilemap.width == 0
        assert tilemap.height == 0

    def test_empty_collision(self):
        tilemap = TileMap()
        assert tilemap.collision == []

    def test_empty_zones(self):
        tilemap = TileMap()
        assert tilemap.zones == []


# =====================================================================
# Camera
# =====================================================================

class TestCamera:

    def test_initial_offset_zero(self):
        cam = Camera(1280, 720)
        assert cam.offset.x == 0
        assert cam.offset.y == 0

    def test_world_to_screen_no_offset(self):
        cam = Camera(1280, 720)
        screen = cam.world_to_screen(pygame.math.Vector2(100, 200))
        assert screen.x == 100
        assert screen.y == 200

    def test_world_to_screen_with_offset(self):
        cam = Camera(1280, 720)
        cam.offset = pygame.math.Vector2(50, 100)
        screen = cam.world_to_screen(pygame.math.Vector2(150, 300))
        assert screen.x == 100
        assert screen.y == 200

    def test_screen_to_world_no_offset(self):
        cam = Camera(1280, 720)
        world = cam.screen_to_world(pygame.math.Vector2(100, 200))
        assert world.x == 100
        assert world.y == 200

    def test_screen_to_world_with_offset(self):
        cam = Camera(1280, 720)
        cam.offset = pygame.math.Vector2(50, 100)
        world = cam.screen_to_world(pygame.math.Vector2(100, 200))
        assert world.x == 150
        assert world.y == 300

    def test_world_screen_roundtrip(self):
        cam = Camera(1280, 720)
        cam.offset = pygame.math.Vector2(123, 456)
        original = pygame.math.Vector2(500, 600)
        screen = cam.world_to_screen(original)
        result = cam.screen_to_world(screen)
        assert result.x == pytest.approx(original.x)
        assert result.y == pytest.approx(original.y)

    def test_update_moves_toward_target(self):
        cam = Camera(1280, 720)
        target = pygame.math.Vector2(1000, 1000)
        cam.update(target, 1.0)
        # Camera should have moved toward centering on target
        assert cam.offset.x > 0
        assert cam.offset.y > 0

    def test_update_lerp_smoothing(self):
        """Camera should not immediately snap to target."""
        cam = Camera(1280, 720)
        target = pygame.math.Vector2(1000, 1000)
        cam.update(target, 0.016)  # single frame
        expected_x = 1000 - 1280 / 2  # target offset
        # Should be between 0 and target offset (not snapped)
        assert 0 < cam.offset.x < expected_x


# =====================================================================
# Zone dataclass
# =====================================================================

class TestZone:

    def test_zone_creation(self):
        z = Zone("test_zone", "spawn", pygame.Rect(0, 0, 100, 100))
        assert z.name == "test_zone"
        assert z.zone_type == "spawn"

    def test_zone_metadata_default(self):
        z = Zone("z", "spawn", pygame.Rect(0, 0, 1, 1))
        assert z.metadata == {}

    def test_zone_metadata_custom(self):
        z = Zone("z", "challenge", pygame.Rect(0, 0, 1, 1), metadata={"challenge_id": "c1"})
        assert z.metadata["challenge_id"] == "c1"


# =====================================================================
# SpawnPoint dataclass
# =====================================================================

class TestSpawnPoint:

    def test_spawn_point_creation(self):
        sp = SpawnPoint(pos=(100, 200), entity_type="enemy")
        assert sp.pos == (100, 200)
        assert sp.entity_type == "enemy"

    def test_spawn_point_metadata(self):
        sp = SpawnPoint(pos=(0, 0), entity_type="enemy", metadata={"tier": "scout"})
        assert sp.metadata["tier"] == "scout"
