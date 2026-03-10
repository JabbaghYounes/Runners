"""Unit tests for the LootDrop entity."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

pygame.init()

from src.entities.loot_drop import LootDrop
from src.items import Item, ItemType, Rarity


# =====================================================================
# Helpers
# =====================================================================

def _make_item(item_id: str = "test_item") -> Item:
    return Item(
        id=item_id,
        name="Test Item",
        item_type=ItemType.CONSUMABLE,
        rarity=Rarity.COMMON,
        value=10,
    )


# =====================================================================
# Construction
# =====================================================================

class TestLootDropInit:

    def test_position_set(self):
        drop = LootDrop(100, 200, _make_item())
        assert drop.pos.x == 100
        assert drop.pos.y == 200

    def test_item_stored(self):
        item = _make_item("med_kit")
        drop = LootDrop(0, 0, item)
        assert drop.item is item
        assert drop.item.id == "med_kit"

    def test_dimensions(self):
        drop = LootDrop(0, 0, _make_item())
        assert drop.width == 24
        assert drop.height == 24

    def test_alive_on_init(self):
        drop = LootDrop(0, 0, _make_item())
        assert drop.alive is True

    def test_bob_timer_starts_at_zero(self):
        drop = LootDrop(0, 0, _make_item())
        assert drop._bob_timer == 0.0

    def test_base_y_set(self):
        drop = LootDrop(100, 250, _make_item())
        assert drop._base_y == 250


# =====================================================================
# Bob Animation
# =====================================================================

class TestLootDropBob:

    def test_bob_timer_increments(self):
        drop = LootDrop(0, 100, _make_item())
        drop.update(0.5)
        assert drop._bob_timer == pytest.approx(0.5)

    def test_y_position_oscillates(self):
        """After update, y should differ from base_y due to sin bob."""
        drop = LootDrop(0, 100, _make_item())
        drop.update(0.5)
        # sin(0.5 * 3.0) * 3.0 = sin(1.5) * 3 ≈ 2.99
        assert drop.pos.y != 100

    def test_bob_returns_near_base(self):
        """Bob animation is bounded within ±3 pixels of base_y."""
        import math
        drop = LootDrop(0, 100, _make_item())
        for t in range(100):
            drop.update(0.1)
            assert abs(drop.pos.y - drop._base_y) <= 3.01

    def test_x_position_unchanged_by_bob(self):
        drop = LootDrop(50, 100, _make_item())
        drop.update(1.0)
        assert drop.pos.x == 50

    def test_rect_synced_after_bob(self):
        drop = LootDrop(50, 100, _make_item())
        drop.update(0.5)
        assert drop.rect.centery == pytest.approx(int(drop.pos.y), abs=1)


# =====================================================================
# Pickup range
# =====================================================================

class TestLootDropPickup:

    def test_in_range_close(self):
        drop = LootDrop(100, 100, _make_item())
        player_pos = pygame.math.Vector2(110, 100)
        assert drop.in_pickup_range(player_pos) is True

    def test_in_range_exact_boundary(self):
        drop = LootDrop(100, 100, _make_item())
        player_pos = pygame.math.Vector2(140, 100)  # exactly 40px
        assert drop.in_pickup_range(player_pos) is True

    def test_out_of_range(self):
        drop = LootDrop(100, 100, _make_item())
        player_pos = pygame.math.Vector2(200, 200)  # >40px
        assert drop.in_pickup_range(player_pos) is False

    def test_same_position(self):
        drop = LootDrop(100, 100, _make_item())
        player_pos = pygame.math.Vector2(100, 100)
        assert drop.in_pickup_range(player_pos) is True

    def test_pickup_radius_constant(self):
        assert LootDrop.PICKUP_RADIUS == 40.0

    def test_pickup_range_respects_bob(self):
        """Pickup range should use actual position including bob offset."""
        drop = LootDrop(100, 100, _make_item())
        drop.update(1.0)  # bob changes y
        # Player is near the bobbed position
        player_pos = pygame.math.Vector2(100, drop.pos.y)
        assert drop.in_pickup_range(player_pos) is True
