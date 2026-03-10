"""Unit tests for the Projectile entity."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

pygame.init()

from src.entities.base import Entity
from src.entities.projectile import Projectile


# =====================================================================
# Helpers
# =====================================================================

class FakeTileMap:
    """Minimal tilemap stub for projectile testing."""

    def __init__(self, solid_positions: set[tuple[int, int]] | None = None, tile_size: int = 32):
        self.tile_size = tile_size
        self._solid = solid_positions or set()

    def is_solid(self, gx: int, gy: int) -> bool:
        if gx < 0 or gy < 0:
            return True
        return (gx, gy) in self._solid


# =====================================================================
# Construction
# =====================================================================

class TestProjectileInit:

    def test_position_set(self):
        p = Projectile(100, 200, pygame.math.Vector2(1, 0))
        assert p.pos.x == 100
        assert p.pos.y == 200

    def test_direction_normalized(self):
        p = Projectile(0, 0, pygame.math.Vector2(3, 4))
        assert p.direction.length() == pytest.approx(1.0)

    def test_zero_direction_defaults_to_right(self):
        p = Projectile(0, 0, pygame.math.Vector2(0, 0))
        assert p.direction.x == 1
        assert p.direction.y == 0

    def test_default_speed(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0))
        assert p.speed == 600.0

    def test_custom_speed(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=400.0)
        assert p.speed == 400.0

    def test_default_damage(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0))
        assert p.damage == 10

    def test_custom_damage(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), damage=25)
        assert p.damage == 25

    def test_owner_set(self):
        owner = Entity(0, 0)
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), owner=owner)
        assert p.owner is owner

    def test_no_owner_by_default(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0))
        assert p.owner is None

    def test_max_range_default(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0))
        assert p.max_range == 800.0

    def test_custom_max_range(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), max_range=300.0)
        assert p.max_range == 300.0

    def test_distance_travelled_starts_at_zero(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0))
        assert p._distance_travelled == 0.0

    def test_alive_on_init(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0))
        assert p.alive is True

    def test_small_dimensions(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0))
        assert p.width == 8
        assert p.height == 8


# =====================================================================
# Movement
# =====================================================================

class TestProjectileMovement:

    def test_moves_in_direction(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=100.0)
        p.update(1.0)
        assert p.pos.x == pytest.approx(100.0)
        assert p.pos.y == pytest.approx(0.0)

    def test_moves_diagonally(self):
        direction = pygame.math.Vector2(1, 1)
        p = Projectile(0, 0, direction, speed=100.0)
        p.update(1.0)
        # Normalized (1,1) is ~(0.707, 0.707), so distance is 100
        assert p.pos.x > 0
        assert p.pos.y > 0

    def test_moves_negative_direction(self):
        p = Projectile(100, 100, pygame.math.Vector2(-1, 0), speed=50.0)
        p.update(1.0)
        assert p.pos.x == pytest.approx(50.0)

    def test_distance_accumulated(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=100.0)
        p.update(0.5)
        assert p._distance_travelled == pytest.approx(50.0)

    def test_multiple_updates_accumulate(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=100.0)
        p.update(0.5)
        p.update(0.5)
        assert p._distance_travelled == pytest.approx(100.0)

    def test_no_movement_when_dead(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=100.0)
        p.alive = False
        p.update(1.0)
        assert p.pos.x == pytest.approx(0.0)

    def test_rect_synced_after_update(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=100.0)
        p.update(1.0)
        assert p.rect.centerx == pytest.approx(100, abs=1)


# =====================================================================
# Max range destruction
# =====================================================================

class TestProjectileMaxRange:

    def test_destroyed_at_max_range(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=1000.0, max_range=100.0)
        p.update(0.2)  # 200 pixels > 100 max_range
        assert p.alive is False

    def test_survives_under_max_range(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=100.0, max_range=800.0)
        p.update(0.5)  # 50 pixels < 800 max_range
        assert p.alive is True

    def test_exact_max_range(self):
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=100.0, max_range=100.0)
        p.update(1.0)  # exactly 100 pixels
        assert p.alive is False

    def test_killed_removed_from_group(self):
        group = pygame.sprite.Group()
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=1000.0, max_range=100.0)
        group.add(p)
        p.update(0.2)
        assert p not in group


# =====================================================================
# Tilemap collision
# =====================================================================

class TestProjectileTilemapCollision:

    def test_destroyed_on_solid_tile(self):
        tilemap = FakeTileMap(solid_positions={(10, 0)})
        p = Projectile(300, 10, pygame.math.Vector2(1, 0), speed=1000.0)
        # Move to pixel ~320 which is tile (10, 0)
        p.update(0.03, tilemap=tilemap)
        assert p.alive is False

    def test_survives_on_empty_tile(self):
        tilemap = FakeTileMap()
        p = Projectile(100, 100, pygame.math.Vector2(1, 0), speed=100.0)
        p.update(0.1, tilemap=tilemap)
        assert p.alive is True

    def test_removed_from_group_on_wall_hit(self):
        tilemap = FakeTileMap(solid_positions={(10, 0)})
        group = pygame.sprite.Group()
        p = Projectile(300, 10, pygame.math.Vector2(1, 0), speed=1000.0)
        group.add(p)
        p.update(0.03, tilemap=tilemap)
        assert p not in group

    def test_no_tilemap_skips_collision_check(self):
        p = Projectile(100, 100, pygame.math.Vector2(1, 0), speed=100.0)
        p.update(0.1, tilemap=None)
        assert p.alive is True


# =====================================================================
# check_hit
# =====================================================================

class TestProjectileCheckHit:

    def test_hits_non_owner_overlapping(self):
        target = Entity(10, 10, width=32, height=32)
        p = Projectile(10, 10, pygame.math.Vector2(1, 0))
        assert p.check_hit(target) is True

    def test_does_not_hit_owner(self):
        owner = Entity(10, 10, width=32, height=32)
        p = Projectile(10, 10, pygame.math.Vector2(1, 0), owner=owner)
        assert p.check_hit(owner) is False

    def test_does_not_hit_when_dead(self):
        target = Entity(10, 10, width=32, height=32)
        p = Projectile(10, 10, pygame.math.Vector2(1, 0))
        p.alive = False
        assert p.check_hit(target) is False

    def test_does_not_hit_non_overlapping(self):
        target = Entity(9999, 9999, width=32, height=32)
        p = Projectile(0, 0, pygame.math.Vector2(1, 0))
        assert p.check_hit(target) is False

    def test_hits_different_entity_not_owner(self):
        owner = Entity(0, 0)
        target = Entity(10, 10, width=32, height=32)
        p = Projectile(10, 10, pygame.math.Vector2(1, 0), owner=owner)
        assert p.check_hit(target) is True

    def test_hit_after_movement(self):
        """Projectile can hit a target after moving toward it."""
        target = Entity(200, 0, width=32, height=32)
        p = Projectile(0, 0, pygame.math.Vector2(1, 0), speed=1000.0)
        hit = False
        for _ in range(50):
            p.update(0.016)
            if p.check_hit(target):
                hit = True
                break
        assert hit is True
