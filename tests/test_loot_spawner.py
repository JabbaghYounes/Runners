"""Test suite for the LootSpawner and loot table rolling."""

from __future__ import annotations

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

pygame.init()

from src.entities.enemy import Enemy, EnemyState
from src.entities.enemy_config import EnemyTierConfig, EnemyTier
from src.events import EventBus
from src.items import Item, ItemType, Rarity
from src.loot_spawner import LootSpawner, LootTable, LootTableEntry, load_loot_tables


# =====================================================================
# Helpers
# =====================================================================

def _scout_config() -> EnemyTierConfig:
    return EnemyTierConfig(
        tier=EnemyTier.SCOUT,
        health=50,
        speed=120.0,
        damage=8,
        detection_range=250.0,
        attack_range=200.0,
        fire_rate=1.5,
        alert_delay=0.5,
        idle_duration=2.0,
        loot_table_id="enemy_scout",
        xp_reward=25,
        sprite_key="enemy_scout",
    )


def _make_test_tables() -> dict[str, LootTable]:
    return {
        "enemy_scout": LootTable(
            drop_chance=1.0,  # always drop for deterministic tests
            rolls=1,
            items=[
                LootTableEntry("med_kit_small", 50),
                LootTableEntry("ammo_pack_light", 50),
            ],
        ),
        "never_drop": LootTable(
            drop_chance=0.0,
            rolls=1,
            items=[LootTableEntry("item_a", 100)],
        ),
    }


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def loot_group():
    return pygame.sprite.Group()


@pytest.fixture
def spawner(event_bus, loot_group):
    tables = _make_test_tables()
    return LootSpawner(
        event_bus=event_bus,
        loot_tables=tables,
        loot_group=loot_group,
    )


# =====================================================================
# Subscription
# =====================================================================

class TestSubscription:

    def test_loot_spawner_subscribes_to_enemy_killed(self, event_bus, loot_group):
        """Creating a LootSpawner registers a listener on 'enemy_killed'."""
        spawner = LootSpawner(event_bus, _make_test_tables(), loot_group=loot_group)
        assert len(event_bus._listeners.get("enemy_killed", [])) > 0


# =====================================================================
# Loot Rolling
# =====================================================================

class TestLootRolling:

    def test_roll_returns_items_on_success(self, spawner):
        items = spawner.roll_loot("enemy_scout")
        assert len(items) == 1
        assert items[0].id in ("med_kit_small", "ammo_pack_light")

    def test_no_drop_when_chance_fails(self, spawner):
        items = spawner.roll_loot("never_drop")
        assert len(items) == 0

    def test_unknown_table_returns_empty(self, spawner):
        items = spawner.roll_loot("nonexistent_table")
        assert len(items) == 0

    def test_roll_respects_weights(self, spawner):
        """Over many rolls, both items should appear with roughly equal frequency."""
        counts: dict[str, int] = {}
        n = 1000
        for _ in range(n):
            items = spawner.roll_loot("enemy_scout")
            for item in items:
                counts[item.id] = counts.get(item.id, 0) + 1

        # With 50/50 weights and 1000 rolls, each should appear ~500 times.
        # Allow generous margin for randomness.
        assert counts.get("med_kit_small", 0) > 200
        assert counts.get("ammo_pack_light", 0) > 200

    def test_roll_respects_drop_chance(self):
        """With 70% drop chance, roughly 70% of rolls should produce items."""
        tables = {
            "test": LootTable(
                drop_chance=0.7,
                rolls=1,
                items=[LootTableEntry("item_a", 100)],
            ),
        }
        bus = EventBus()
        spawner = LootSpawner(bus, tables)

        drops = 0
        n = 1000
        random.seed(42)
        for _ in range(n):
            if spawner.roll_loot("test"):
                drops += 1

        # Should be roughly 700 ± generous margin
        assert 500 < drops < 900

    def test_multiple_rolls_per_table(self):
        """A table with rolls=3 should return up to 3 items."""
        tables = {
            "multi": LootTable(
                drop_chance=1.0,
                rolls=3,
                items=[LootTableEntry("item_a", 100)],
            ),
        }
        bus = EventBus()
        spawner = LootSpawner(bus, tables)
        items = spawner.roll_loot("multi")
        assert len(items) == 3


# =====================================================================
# Loot Drop Spawning via Event
# =====================================================================

class TestLootDropSpawning:

    def test_enemy_killed_triggers_loot_drop(self, event_bus, loot_group):
        tables = _make_test_tables()
        spawner = LootSpawner(event_bus, tables, loot_group=loot_group)

        enemy = Enemy(500, 500, _scout_config(), event_bus=event_bus)
        enemy.take_damage(50)  # kills the enemy, fires enemy_killed event

        # LootSpawner should have created a LootDrop in the group
        assert len(loot_group) > 0

    def test_loot_drop_created_at_enemy_position(self, event_bus, loot_group):
        tables = _make_test_tables()
        spawner = LootSpawner(event_bus, tables, loot_group=loot_group)

        enemy = Enemy(500, 500, _scout_config(), event_bus=event_bus)
        enemy.take_damage(50)

        for drop in loot_group:
            # Drop should be near the enemy's death position (with random offset)
            assert abs(drop.pos.x - 500) < 32
            assert abs(drop.pos.y - 500) < 32

    def test_loot_drop_has_item(self, event_bus, loot_group):
        tables = _make_test_tables()
        spawner = LootSpawner(event_bus, tables, loot_group=loot_group)

        enemy = Enemy(500, 500, _scout_config(), event_bus=event_bus)
        enemy.take_damage(50)

        for drop in loot_group:
            assert drop.item is not None
            assert drop.item.id in ("med_kit_small", "ammo_pack_light")


# =====================================================================
# JSON Loader
# =====================================================================

class TestLootTableLoader:

    def test_load_loot_tables_from_json(self):
        tables = load_loot_tables("data/loot_tables.json")
        assert "enemy_scout" in tables
        assert "enemy_enforcer" in tables

    def test_scout_table_has_correct_entries(self):
        tables = load_loot_tables("data/loot_tables.json")
        scout = tables["enemy_scout"]
        assert scout.drop_chance == 0.7
        assert scout.rolls == 1
        assert len(scout.items) == 4

    def test_enforcer_table_has_correct_entries(self):
        tables = load_loot_tables("data/loot_tables.json")
        enforcer = tables["enemy_enforcer"]
        assert enforcer.drop_chance == 0.9
        assert enforcer.rolls == 2
        assert len(enforcer.items) == 6
