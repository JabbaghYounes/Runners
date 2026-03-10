"""End-to-end integration tests for the PvE enemy system.

Tests the complete flow: spawn enemies → FSM AI → detect player → attack →
take damage → die → loot drops → XP events.
"""

from __future__ import annotations

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

pygame.init()

from src.entities.base import Entity
from src.entities.enemy import Enemy, EnemyState
from src.entities.enemy_config import EnemyTierConfig, EnemyTier, load_enemy_tiers
from src.entities.projectile import Projectile
from src.entities.loot_drop import LootDrop
from src.events import EventBus
from src.items import Item, ItemType, Rarity
from src.loot_spawner import LootSpawner, LootTable, LootTableEntry, load_loot_tables
from src.map import TileMap


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


def _enforcer_config() -> EnemyTierConfig:
    return EnemyTierConfig(
        tier=EnemyTier.ENFORCER,
        health=150,
        speed=70.0,
        damage=20,
        detection_range=300.0,
        attack_range=180.0,
        fire_rate=0.8,
        alert_delay=0.8,
        idle_duration=3.0,
        loot_table_id="enemy_enforcer",
        xp_reward=75,
        sprite_key="enemy_enforcer",
    )


class FakeTileMap:
    def __init__(self, solid_positions=None, tile_size=32):
        self.tile_size = tile_size
        self._solid = solid_positions or set()

    def is_solid(self, gx, gy):
        if gx < 0 or gy < 0:
            return True
        return (gx, gy) in self._solid

    def raycast_solid(self, start, end):
        ts = self.tile_size
        x0, y0 = int(start[0]) // ts, int(start[1]) // ts
        x1, y1 = int(end[0]) // ts, int(end[1]) // ts
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        start_tile = (x0, y0)
        while True:
            if (x0, y0) != start_tile:
                if self.is_solid(x0, y0):
                    return True
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
        return False


class FakePlayer(Entity):
    def __init__(self, x=0.0, y=0.0, health=100):
        super().__init__(x, y, health=health)


def _make_loot_tables() -> dict[str, LootTable]:
    return {
        "enemy_scout": LootTable(
            drop_chance=1.0,
            rolls=1,
            items=[
                LootTableEntry("med_kit_small", 50),
                LootTableEntry("ammo_pack_light", 50),
            ],
        ),
        "enemy_enforcer": LootTable(
            drop_chance=1.0,
            rolls=2,
            items=[
                LootTableEntry("med_kit_large", 50),
                LootTableEntry("armor_plate", 50),
            ],
        ),
    }


# =====================================================================
# Happy path E2E: spawn → detect → attack → kill → loot + XP
# =====================================================================

class TestHappyPathE2E:

    def test_full_enemy_lifecycle(self):
        """Complete lifecycle: idle → patrol → detect → attack → take damage → die → loot + XP."""
        event_bus = EventBus()
        tilemap = FakeTileMap()
        loot_group = pygame.sprite.Group()
        enemy_group = pygame.sprite.Group()

        # Track events
        xp_events = []
        kill_events = []
        hit_events = []
        event_bus.subscribe("enemy_killed", lambda **kw: kill_events.append(kw))
        event_bus.subscribe("entity_hit", lambda **kw: hit_events.append(kw))

        # Wire up loot spawner
        spawner = LootSpawner(event_bus, _make_loot_tables(), loot_group=loot_group)

        # Create scout enemy
        config = _scout_config()
        patrol = [[100, 100], [300, 100]]
        enemy = Enemy(100, 100, config, patrol_path=patrol, event_bus=event_bus)
        enemy_group.add(enemy)

        # Phase 1: IDLE
        far_player = FakePlayer(9999, 9999)
        assert enemy.state == EnemyState.IDLE
        enemy.update(0.5, tilemap=tilemap, player=far_player)
        assert enemy.state == EnemyState.IDLE  # still under idle_duration

        # Phase 2: IDLE → PATROL
        enemy.update(2.0, tilemap=tilemap, player=far_player)
        assert enemy.state == EnemyState.PATROL

        # Phase 3: PATROL → DETECT (player approaches)
        close_player = FakePlayer(200, 100)
        enemy.update(0.016, tilemap=tilemap, player=close_player)
        assert enemy.state == EnemyState.DETECT

        # Phase 4: DETECT → ATTACK (alert delay passes)
        enemy.update(0.6, tilemap=tilemap, player=close_player)
        assert enemy.state == EnemyState.ATTACK

        # Phase 5: ATTACK — enemy fires projectiles
        enemy._fire_timer = 10.0  # ensure ready to fire
        enemy.update(0.016, tilemap=tilemap, player=close_player)
        assert len(enemy.projectile_group) > 0

        # Phase 6: Player damages enemy
        actual = enemy.take_damage(30, source=close_player)
        assert actual == 30
        assert enemy.health == 20
        assert len(hit_events) == 1

        # Phase 7: Kill the enemy
        enemy.take_damage(20, source=close_player)
        assert enemy.alive is False
        assert enemy.state == EnemyState.DEAD

        # Verify events
        assert len(kill_events) == 1
        assert kill_events[0]["xp_reward"] == 25
        assert kill_events[0]["killer"] is close_player
        assert kill_events[0]["loot_table_id"] == "enemy_scout"

        # Verify loot dropped
        assert len(loot_group) > 0
        for drop in loot_group:
            assert isinstance(drop, LootDrop)
            assert drop.item is not None

        # Verify enemy removed from group
        assert enemy not in enemy_group

    def test_enforcer_full_lifecycle(self):
        """Enforcer: higher health, more damage, drops 2 loot items."""
        event_bus = EventBus()
        tilemap = FakeTileMap()
        loot_group = pygame.sprite.Group()
        kill_events = []
        event_bus.subscribe("enemy_killed", lambda **kw: kill_events.append(kw))

        spawner = LootSpawner(event_bus, _make_loot_tables(), loot_group=loot_group)

        config = _enforcer_config()
        enemy = Enemy(100, 100, config, event_bus=event_bus)
        assert enemy.health == 150

        killer = FakePlayer(200, 100)
        # Multi-hit to kill
        enemy.take_damage(50, source=killer)
        assert enemy.health == 100
        enemy.take_damage(50, source=killer)
        assert enemy.health == 50
        enemy.take_damage(50, source=killer)
        assert enemy.alive is False

        assert kill_events[0]["xp_reward"] == 75
        # Enforcer table has rolls=2, so should get 2 drops
        assert len(loot_group) == 2


# =====================================================================
# Multi-enemy scenarios
# =====================================================================

class TestMultiEnemyIntegration:

    def test_multiple_enemies_independent_lifecycle(self):
        """Two enemies with independent FSM states."""
        event_bus = EventBus()
        tilemap = FakeTileMap()
        kill_events = []
        event_bus.subscribe("enemy_killed", lambda **kw: kill_events.append(kw))

        e1 = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        e2 = Enemy(800, 800, _enforcer_config(), event_bus=event_bus)

        # Player near e1, far from e2
        player = FakePlayer(200, 100)
        e1._change_state(EnemyState.PATROL)
        e2._change_state(EnemyState.PATROL)

        e1.update(0.016, tilemap=tilemap, player=player)
        e2.update(0.016, tilemap=tilemap, player=player)

        assert e1.state == EnemyState.DETECT
        assert e2.state == EnemyState.PATROL

        # Kill e1
        e1.take_damage(50, source=player)
        assert e1.alive is False
        assert e2.alive is True

        assert len(kill_events) == 1
        assert kill_events[0]["xp_reward"] == 25

    def test_enemy_group_update_loop(self):
        """Simulate a gameplay update loop with multiple enemies."""
        event_bus = EventBus()
        tilemap = FakeTileMap()
        enemy_group = pygame.sprite.Group()

        for i in range(5):
            cfg = _scout_config() if i % 2 == 0 else _enforcer_config()
            e = Enemy(100 + i * 200, 100, cfg, event_bus=event_bus)
            enemy_group.add(e)

        far_player = FakePlayer(9999, 9999)

        # Run 60 frames
        for _ in range(60):
            for enemy in enemy_group:
                enemy.update(0.016, tilemap=tilemap, player=far_player)

        # All should still be alive (no player in range)
        for enemy in enemy_group:
            assert enemy.alive is True

    def test_kill_all_enemies(self):
        """Kill all enemies and verify all produce events."""
        event_bus = EventBus()
        kill_events = []
        event_bus.subscribe("enemy_killed", lambda **kw: kill_events.append(kw))

        enemies = [
            Enemy(100, 100, _scout_config(), event_bus=event_bus),
            Enemy(200, 200, _scout_config(), event_bus=event_bus),
            Enemy(300, 300, _enforcer_config(), event_bus=event_bus),
        ]
        killer = FakePlayer(0, 0)
        for e in enemies:
            e.take_damage(e.health, source=killer)

        assert len(kill_events) == 3
        xp_total = sum(ev["xp_reward"] for ev in kill_events)
        assert xp_total == 25 + 25 + 75


# =====================================================================
# Projectile → Enemy damage flow
# =====================================================================

class TestProjectileEnemyIntegration:

    def test_player_projectile_hits_enemy(self):
        """Player-fired projectile damages enemy on collision."""
        event_bus = EventBus()
        tilemap = FakeTileMap()
        hit_events = []
        event_bus.subscribe("entity_hit", lambda **kw: hit_events.append(kw))

        player = FakePlayer(0, 100)
        enemy = Enemy(200, 100, _scout_config(), event_bus=event_bus)

        # Fire projectile from player toward enemy
        direction = enemy.pos - player.pos
        proj = Projectile(
            x=player.pos.x, y=player.pos.y,
            direction=direction, speed=1000.0,
            damage=25, owner=player,
        )

        # Simulate frames
        for _ in range(100):
            proj.update(0.016, tilemap=tilemap)
            if proj.check_hit(enemy):
                enemy.take_damage(proj.damage, source=player)
                break

        assert enemy.health < 50
        assert len(hit_events) > 0

    def test_enemy_projectile_hits_player(self):
        """Enemy-fired projectile damages player on collision."""
        event_bus = EventBus()
        tilemap = FakeTileMap()

        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        player = FakePlayer(200, 100)

        proj = enemy._fire_projectile(player.pos)

        for _ in range(100):
            proj.update(0.016, tilemap=tilemap)
            if proj.check_hit(player):
                player.take_damage(proj.damage, source=enemy)
                break

        assert player.health < 100

    def test_enemy_projectile_does_not_hit_self(self):
        """Enemy-fired projectile should not hit the enemy that fired it."""
        event_bus = EventBus()
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        proj = enemy._fire_projectile(pygame.math.Vector2(200, 100))
        assert proj.check_hit(enemy) is False

    def test_player_projectile_does_not_hit_player(self):
        """Player-fired projectile should not hit the player that fired it."""
        player = FakePlayer(100, 100)
        direction = pygame.math.Vector2(1, 0)
        proj = Projectile(100, 100, direction, damage=10, owner=player)
        assert proj.check_hit(player) is False


# =====================================================================
# Loot spawner integration
# =====================================================================

class TestLootSpawnerIntegration:

    def test_loot_spawner_reacts_to_enemy_death(self):
        """LootSpawner creates drops when enemy is killed."""
        event_bus = EventBus()
        loot_group = pygame.sprite.Group()
        spawner = LootSpawner(event_bus, _make_loot_tables(), loot_group=loot_group)

        enemy = Enemy(500, 500, _scout_config(), event_bus=event_bus)
        enemy.take_damage(50)

        assert len(loot_group) > 0

    def test_loot_drops_near_enemy_death_position(self):
        """Loot drops spawn near the enemy's position."""
        event_bus = EventBus()
        loot_group = pygame.sprite.Group()
        spawner = LootSpawner(event_bus, _make_loot_tables(), loot_group=loot_group)

        enemy = Enemy(500, 500, _scout_config(), event_bus=event_bus)
        enemy.take_damage(50)

        for drop in loot_group:
            assert abs(drop.pos.x - 500) < 32
            assert abs(drop.pos.y - 500) < 32

    def test_loot_item_has_valid_fields(self):
        """Dropped items should have valid Item fields."""
        event_bus = EventBus()
        loot_group = pygame.sprite.Group()
        spawner = LootSpawner(event_bus, _make_loot_tables(), loot_group=loot_group)

        enemy = Enemy(500, 500, _scout_config(), event_bus=event_bus)
        enemy.take_damage(50)

        for drop in loot_group:
            assert isinstance(drop.item, Item)
            assert drop.item.id != ""
            assert drop.item.name != ""

    def test_enforcer_drops_more_loot_than_scout(self):
        """Enforcer loot table has 2 rolls, scout has 1."""
        event_bus = EventBus()
        scout_loot = pygame.sprite.Group()
        enforcer_loot = pygame.sprite.Group()

        s_spawner = LootSpawner(EventBus(), _make_loot_tables(), loot_group=scout_loot)
        e_spawner = LootSpawner(EventBus(), _make_loot_tables(), loot_group=enforcer_loot)

        # We need to route events through the correct bus
        scout_bus = EventBus()
        LootSpawner(scout_bus, _make_loot_tables(), loot_group=scout_loot)
        enforcer_bus = EventBus()
        LootSpawner(enforcer_bus, _make_loot_tables(), loot_group=enforcer_loot)

        scout = Enemy(100, 100, _scout_config(), event_bus=scout_bus)
        enforcer = Enemy(200, 200, _enforcer_config(), event_bus=enforcer_bus)

        scout.take_damage(50)
        enforcer.take_damage(150)

        assert len(enforcer_loot) > len(scout_loot)

    def test_loot_drop_pickup_range(self):
        """Player can pick up loot when within pickup radius."""
        event_bus = EventBus()
        loot_group = pygame.sprite.Group()
        spawner = LootSpawner(event_bus, _make_loot_tables(), loot_group=loot_group)

        enemy = Enemy(500, 500, _scout_config(), event_bus=event_bus)
        enemy.take_damage(50)

        player_pos = pygame.math.Vector2(500, 500)
        for drop in loot_group:
            assert drop.in_pickup_range(player_pos) is True


# =====================================================================
# Map data → enemy spawning integration
# =====================================================================

class TestMapSpawnIntegration:

    def test_spawn_enemies_from_map_data(self):
        """Load enemy spawns from map JSON and create Enemy instances."""
        tilemap = TileMap("data/maps/map_01.json")
        tiers = load_enemy_tiers("data/enemies.json")
        event_bus = EventBus()
        enemy_group = pygame.sprite.Group()

        spawns = tilemap.get_enemy_spawns()
        for spawn in spawns:
            tier_config = tiers[spawn["tier"]]
            patrol_path = spawn.get("patrol_path", [])
            enemy = Enemy(
                x=spawn["pos"][0],
                y=spawn["pos"][1],
                tier_config=tier_config,
                patrol_path=patrol_path,
                event_bus=event_bus,
            )
            enemy_group.add(enemy)

        assert len(enemy_group) == 8

    def test_spawned_enemies_have_correct_tiers(self):
        """Spawned enemies should match their tier config from the map."""
        tilemap = TileMap("data/maps/map_01.json")
        tiers = load_enemy_tiers("data/enemies.json")
        event_bus = EventBus()

        enemies = []
        for spawn in tilemap.get_enemy_spawns():
            tier_config = tiers[spawn["tier"]]
            enemy = Enemy(
                x=spawn["pos"][0], y=spawn["pos"][1],
                tier_config=tier_config, event_bus=event_bus,
            )
            enemies.append((spawn["tier"], enemy))

        for tier_name, enemy in enemies:
            if tier_name == "scout":
                assert enemy.health == 50
                assert enemy.speed == 120.0
            elif tier_name == "enforcer":
                assert enemy.health == 150
                assert enemy.speed == 70.0

    def test_spawned_enemies_at_correct_positions(self):
        tilemap = TileMap("data/maps/map_01.json")
        tiers = load_enemy_tiers("data/enemies.json")
        event_bus = EventBus()

        spawns = tilemap.get_enemy_spawns()
        for spawn in spawns:
            enemy = Enemy(
                x=spawn["pos"][0], y=spawn["pos"][1],
                tier_config=tiers[spawn["tier"]], event_bus=event_bus,
            )
            assert enemy.pos.x == spawn["pos"][0]
            assert enemy.pos.y == spawn["pos"][1]

    def test_spawned_enemies_have_patrol_paths(self):
        tilemap = TileMap("data/maps/map_01.json")
        tiers = load_enemy_tiers("data/enemies.json")
        event_bus = EventBus()

        for spawn in tilemap.get_enemy_spawns():
            enemy = Enemy(
                x=spawn["pos"][0], y=spawn["pos"][1],
                tier_config=tiers[spawn["tier"]],
                patrol_path=spawn.get("patrol_path", []),
                event_bus=event_bus,
            )
            assert len(enemy._patrol_path) >= 2


# =====================================================================
# Full system integration with real data
# =====================================================================

class TestFullSystemIntegration:

    def test_full_system_with_real_data(self):
        """E2E test using real JSON data files: map, enemy tiers, loot tables."""
        # Load real data
        tilemap = TileMap("data/maps/map_01.json")
        tiers = load_enemy_tiers("data/enemies.json")
        loot_tables = load_loot_tables("data/loot_tables.json")

        event_bus = EventBus()
        enemy_group = pygame.sprite.Group()
        loot_group = pygame.sprite.Group()

        # Wire systems
        spawner = LootSpawner(event_bus, loot_tables, loot_group=loot_group)

        kill_events = []
        event_bus.subscribe("enemy_killed", lambda **kw: kill_events.append(kw))

        # Spawn all enemies from map
        spawns = tilemap.get_enemy_spawns()
        for spawn in spawns:
            tier_config = tiers[spawn["tier"]]
            enemy = Enemy(
                x=spawn["pos"][0], y=spawn["pos"][1],
                tier_config=tier_config,
                patrol_path=spawn.get("patrol_path", []),
                event_bus=event_bus,
            )
            enemy_group.add(enemy)

        assert len(enemy_group) == 8

        # Kill the first scout
        player = FakePlayer(320, 480)
        first_enemy = list(enemy_group)[0]
        first_enemy.take_damage(first_enemy.health, source=player)

        assert len(kill_events) == 1
        assert kill_events[0]["loot_table_id"] in ("enemy_scout", "enemy_enforcer")
        # Loot should have been spawned (with 70% or 90% chance — may or may not drop)
        # The important thing is no errors occurred
        assert len(enemy_group) == 7

    def test_xp_accumulation_across_kills(self):
        """Track cumulative XP from killing multiple enemies."""
        event_bus = EventBus()
        xp_total = [0]

        def on_kill(**kw):
            xp_total[0] += kw.get("xp_reward", 0)

        event_bus.subscribe("enemy_killed", on_kill)

        killer = FakePlayer(0, 0)

        # Kill 2 scouts (25 XP each) and 1 enforcer (75 XP)
        for cfg in [_scout_config(), _scout_config(), _enforcer_config()]:
            enemy = Enemy(100, 100, cfg, event_bus=event_bus)
            enemy.take_damage(cfg.health, source=killer)

        assert xp_total[0] == 125  # 25 + 25 + 75

    def test_wall_blocks_enemy_attack(self):
        """Enemy cannot detect/attack player through a wall."""
        solid = {(5, 3), (6, 3)}
        tilemap = FakeTileMap(solid_positions=solid)
        event_bus = EventBus()

        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy._change_state(EnemyState.PATROL)

        # Player behind the wall
        player = FakePlayer(300, 100)
        enemy.update(0.016, tilemap=tilemap, player=player)

        # Should NOT detect through wall
        assert enemy.state == EnemyState.PATROL

    def test_projectile_destroyed_by_wall(self):
        """Projectile stops on tilemap collision."""
        solid = {(5, 3)}
        tilemap = FakeTileMap(solid_positions=solid)
        event_bus = EventBus()

        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        proj = enemy._fire_projectile(pygame.math.Vector2(300, 100))

        for _ in range(200):
            proj.update(0.016, tilemap=tilemap)
            if not proj.alive:
                break

        assert proj.alive is False
