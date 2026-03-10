"""Unit tests for the Entity base class and tilemap collision resolution."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

pygame.init()

from src.entities.base import Entity, resolve_tilemap_collision, _grid


# =====================================================================
# Helpers
# =====================================================================

class FakeTileMap:
    """Minimal tilemap stub for collision testing."""

    def __init__(self, solid_positions: set[tuple[int, int]] | None = None, tile_size: int = 32):
        self.tile_size = tile_size
        self._solid = solid_positions or set()

    def is_solid(self, gx: int, gy: int) -> bool:
        if gx < 0 or gy < 0:
            return True
        return (gx, gy) in self._solid


# =====================================================================
# Entity construction
# =====================================================================

class TestEntityInit:

    def test_default_position(self):
        e = Entity()
        assert e.pos.x == 0.0
        assert e.pos.y == 0.0

    def test_custom_position(self):
        e = Entity(100.5, 200.3)
        assert e.pos.x == 100.5
        assert e.pos.y == 200.3

    def test_default_health(self):
        e = Entity()
        assert e.health == 100
        assert e.max_health == 100

    def test_custom_health(self):
        e = Entity(health=50)
        assert e.health == 50
        assert e.max_health == 50

    def test_alive_on_init(self):
        e = Entity()
        assert e.alive is True

    def test_default_dimensions(self):
        e = Entity()
        assert e.width == 32
        assert e.height == 32

    def test_custom_dimensions(self):
        e = Entity(width=64, height=48)
        assert e.width == 64
        assert e.height == 48

    def test_default_velocity_is_zero(self):
        e = Entity()
        assert e.velocity.x == 0
        assert e.velocity.y == 0

    def test_default_facing_direction(self):
        e = Entity()
        assert e.facing_direction.x == 1
        assert e.facing_direction.y == 0

    def test_sprite_image_created(self):
        e = Entity(width=32, height=32)
        assert e.image is not None
        assert e.image.get_size() == (32, 32)

    def test_rect_initialized_at_position(self):
        e = Entity(100, 200)
        assert e.rect.centerx == 100
        assert e.rect.centery == 200


# =====================================================================
# get_rect
# =====================================================================

class TestGetRect:

    def test_rect_centered_on_pos(self):
        e = Entity(100, 100, width=32, height=32)
        r = e.get_rect()
        assert r.centerx == 100
        assert r.centery == 100
        assert r.width == 32
        assert r.height == 32

    def test_rect_updates_with_position_change(self):
        e = Entity(100, 100)
        e.pos.x = 200
        e.pos.y = 300
        r = e.get_rect()
        assert r.centerx == 200
        assert r.centery == 300

    def test_rect_dimensions_match_entity(self):
        e = Entity(0, 0, width=64, height=48)
        r = e.get_rect()
        assert r.width == 64
        assert r.height == 48


# =====================================================================
# take_damage
# =====================================================================

class TestTakeDamage:

    def test_reduces_health(self):
        e = Entity(health=100)
        e.take_damage(30)
        assert e.health == 70

    def test_returns_actual_damage(self):
        e = Entity(health=100)
        actual = e.take_damage(30)
        assert actual == 30

    def test_caps_at_remaining_health(self):
        e = Entity(health=20)
        actual = e.take_damage(50)
        assert actual == 20
        assert e.health == 0

    def test_kills_at_zero_health(self):
        e = Entity(health=30)
        e.take_damage(30)
        assert e.health == 0
        assert e.alive is False

    def test_overkill_sets_health_to_zero(self):
        e = Entity(health=10)
        e.take_damage(999)
        assert e.health == 0

    def test_no_damage_when_dead(self):
        e = Entity(health=10)
        e.take_damage(10)
        actual = e.take_damage(5)
        assert actual == 0
        assert e.health == 0

    def test_zero_damage_no_effect(self):
        e = Entity(health=100)
        actual = e.take_damage(0)
        assert actual == 0
        assert e.health == 100
        assert e.alive is True

    def test_source_parameter_accepted(self):
        e = Entity(health=100)
        source = Entity(50, 50)
        actual = e.take_damage(10, source=source)
        assert actual == 10

    def test_multiple_hits_accumulate(self):
        e = Entity(health=100)
        e.take_damage(30)
        e.take_damage(30)
        e.take_damage(30)
        assert e.health == 10


# =====================================================================
# _sync_rect
# =====================================================================

class TestSyncRect:

    def test_rect_syncs_with_pos(self):
        e = Entity(100, 100)
        e.pos.x = 500
        e.pos.y = 600
        e._sync_rect()
        assert e.rect.centerx == 500
        assert e.rect.centery == 600


# =====================================================================
# _grid helper
# =====================================================================

class TestGridHelper:

    def test_grid_zero(self):
        assert _grid(0, 32) == 0

    def test_grid_within_tile(self):
        assert _grid(15, 32) == 0

    def test_grid_exact_boundary(self):
        assert _grid(32, 32) == 1

    def test_grid_mid_tile(self):
        assert _grid(48, 32) == 1

    def test_grid_large_value(self):
        assert _grid(320, 32) == 10


# =====================================================================
# resolve_tilemap_collision
# =====================================================================

class TestResolveTilemapCollision:

    def test_no_collision_free_space(self):
        tilemap = FakeTileMap()
        e = Entity(100, 100, width=32, height=32)
        rdx, rdy = resolve_tilemap_collision(e, tilemap, 10, 0)
        assert e.pos.x == pytest.approx(110, abs=1)

    def test_collision_blocks_x_positive(self):
        """Entity cannot move right into a solid tile."""
        # Tile at (4, 3) = pixel (128, 96)
        tilemap = FakeTileMap(solid_positions={(4, 3)})
        e = Entity(100, 100, width=32, height=32)
        resolve_tilemap_collision(e, tilemap, 50, 0)
        # Entity should stop before the solid tile
        assert e.pos.x < 128 + 16

    def test_collision_blocks_x_negative(self):
        """Entity cannot move left into a solid tile."""
        # Tile at (2, 3) = pixel (64, 96)
        tilemap = FakeTileMap(solid_positions={(2, 3)})
        e = Entity(130, 100, width=32, height=32)
        resolve_tilemap_collision(e, tilemap, -50, 0)
        # Entity should stop after the solid tile
        assert e.pos.x > 64

    def test_collision_blocks_y_positive(self):
        """Entity cannot move down into a solid tile."""
        # Tile at (3, 5) = pixel (96, 160)
        tilemap = FakeTileMap(solid_positions={(3, 5)})
        e = Entity(100, 130, width=32, height=32)
        resolve_tilemap_collision(e, tilemap, 0, 50)
        assert e.pos.y < 160 + 16

    def test_collision_blocks_y_negative(self):
        """Entity cannot move up into a solid tile."""
        # Tile at (3, 2) = pixel (96, 64)
        tilemap = FakeTileMap(solid_positions={(3, 2)})
        e = Entity(100, 130, width=32, height=32)
        resolve_tilemap_collision(e, tilemap, 0, -50)
        assert e.pos.y > 64

    def test_no_movement_no_change(self):
        tilemap = FakeTileMap()
        e = Entity(100, 100)
        resolve_tilemap_collision(e, tilemap, 0, 0)
        assert e.pos.x == pytest.approx(100)
        assert e.pos.y == pytest.approx(100)

    def test_diagonal_movement_free(self):
        tilemap = FakeTileMap()
        e = Entity(100, 100)
        resolve_tilemap_collision(e, tilemap, 10, 10)
        assert e.pos.x == pytest.approx(110, abs=1)
        assert e.pos.y == pytest.approx(110, abs=1)

    def test_negative_coordinate_treated_as_solid(self):
        """Moving into negative coordinates should be blocked (boundary)."""
        tilemap = FakeTileMap()
        e = Entity(20, 100, width=32, height=32)
        resolve_tilemap_collision(e, tilemap, -30, 0)
        # Should be pushed back from negative-coordinate tiles
        assert e.pos.x >= 0

    def test_returns_resolved_deltas(self):
        tilemap = FakeTileMap()
        e = Entity(100, 100)
        rdx, rdy = resolve_tilemap_collision(e, tilemap, 5, 7)
        assert rdx == 5
        assert rdy == 7

    def test_returns_zero_on_collision(self):
        tilemap = FakeTileMap(solid_positions={(4, 3)})
        e = Entity(100, 100, width=32, height=32)
        rdx, rdy = resolve_tilemap_collision(e, tilemap, 50, 0)
        assert rdx == 0

    def test_sliding_along_wall(self):
        """X blocked but Y should still move freely."""
        tilemap = FakeTileMap(solid_positions={(4, 3)})
        e = Entity(100, 100, width=32, height=32)
        resolve_tilemap_collision(e, tilemap, 50, 10)
        # Y should have moved
        assert e.pos.y == pytest.approx(110, abs=1)
