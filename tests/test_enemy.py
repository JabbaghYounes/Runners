"""Test suite for the Enemy class and FSM AI behaviour."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

pygame.init()

from src.entities.base import Entity
from src.entities.enemy import Enemy, EnemyState, _DISENGAGE_MULTIPLIER
from src.entities.enemy_config import EnemyTierConfig, EnemyTier, load_enemy_tiers
from src.events import EventBus


# =====================================================================
# Helpers & fixtures
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
    """Minimal tilemap stub with configurable solid tiles."""

    def __init__(self, solid_positions: set[tuple[int, int]] | None = None, tile_size: int = 32):
        self.tile_size = tile_size
        self._solid = solid_positions or set()

    def is_solid(self, gx: int, gy: int) -> bool:
        if gx < 0 or gy < 0:
            return True
        return (gx, gy) in self._solid

    def raycast_solid(self, start, end) -> bool:
        """Bresenham check against configured solid tiles."""
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
    """Minimal player stub for enemy AI tests."""

    def __init__(self, x: float = 0.0, y: float = 0.0):
        super().__init__(x, y, health=100)


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def tilemap():
    return FakeTileMap()


@pytest.fixture
def player():
    return FakePlayer(500, 500)


@pytest.fixture
def scout(event_bus):
    return Enemy(
        x=100, y=100,
        tier_config=_scout_config(),
        patrol_path=[[100, 100], [300, 100], [300, 300], [100, 300]],
        event_bus=event_bus,
    )


@pytest.fixture
def enforcer(event_bus):
    return Enemy(
        x=100, y=100,
        tier_config=_enforcer_config(),
        event_bus=event_bus,
    )


# =====================================================================
# Initialisation
# =====================================================================

class TestEnemyInitialisation:

    def test_enemy_initializes_in_idle_state(self, scout):
        assert scout.state == EnemyState.IDLE

    def test_enemy_has_correct_health(self, scout):
        assert scout.health == 50
        assert scout.max_health == 50

    def test_enemy_is_alive_on_init(self, scout):
        assert scout.alive is True

    def test_enemy_loads_tier_stats(self, scout):
        assert scout.speed == 120.0
        assert scout.damage == 8
        assert scout.detection_range == 250.0
        assert scout.attack_range == 200.0
        assert scout.fire_rate == 1.5
        assert scout.xp_reward == 25
        assert scout.loot_table_id == "enemy_scout"


# =====================================================================
# FSM State Transitions
# =====================================================================

class TestFSMTransitions:

    def test_idle_to_patrol_after_delay(self, scout, tilemap):
        """Enemy transitions from IDLE to PATROL after idle_duration."""
        far_player = FakePlayer(9999, 9999)
        # Step time past idle_duration
        scout.update(2.1, tilemap=tilemap, player=far_player)
        assert scout.state == EnemyState.PATROL

    def test_idle_stays_until_duration(self, scout, tilemap):
        far_player = FakePlayer(9999, 9999)
        scout.update(1.0, tilemap=tilemap, player=far_player)
        assert scout.state == EnemyState.IDLE

    def test_patrol_to_detect_on_player_in_range(self, scout, tilemap):
        """Enemy detects player when within detection_range and LOS is clear."""
        # Place player within detection range of the scout at (100, 100)
        close_player = FakePlayer(200, 100)

        # First move to PATROL
        scout._change_state(EnemyState.PATROL)
        scout.update(0.016, tilemap=tilemap, player=close_player)
        assert scout.state == EnemyState.DETECT

    def test_detect_to_attack_after_alert_delay(self, scout, tilemap):
        """After alert_delay in DETECT, enemy transitions to ATTACK."""
        close_player = FakePlayer(200, 100)
        scout._change_state(EnemyState.DETECT)

        # Step slightly past alert_delay
        scout.update(0.6, tilemap=tilemap, player=close_player)
        assert scout.state == EnemyState.ATTACK

    def test_detect_stays_until_delay(self, scout, tilemap):
        close_player = FakePlayer(200, 100)
        scout._change_state(EnemyState.DETECT)
        scout.update(0.3, tilemap=tilemap, player=close_player)
        assert scout.state == EnemyState.DETECT

    def test_attack_to_patrol_when_player_leaves_range(self, scout, tilemap):
        """Enemy returns to PATROL when player moves beyond extended range."""
        # Extended range = detection_range * 1.5 = 375
        far_player = FakePlayer(600, 100)  # 500px away > 375
        scout._change_state(EnemyState.ATTACK)
        scout.update(0.016, tilemap=tilemap, player=far_player)
        assert scout.state == EnemyState.PATROL

    def test_attack_stays_when_player_in_extended_range(self, scout, tilemap):
        """Enemy stays in ATTACK while player within extended range."""
        # Place player at ~350px, within extended range (375)
        player = FakePlayer(440, 100)
        scout._change_state(EnemyState.ATTACK)
        scout.update(0.016, tilemap=tilemap, player=player)
        assert scout.state == EnemyState.ATTACK

    def test_idle_to_detect_on_player_approach(self, scout, tilemap):
        """Even in IDLE, enemy detects a nearby player."""
        close_player = FakePlayer(200, 100)
        scout.update(0.016, tilemap=tilemap, player=close_player)
        assert scout.state == EnemyState.DETECT


# =====================================================================
# Detection
# =====================================================================

class TestDetection:

    def test_detects_player_in_range(self, scout, tilemap):
        player = FakePlayer(200, 100)
        assert scout._can_see_player(player, tilemap) is True

    def test_does_not_detect_player_out_of_range(self, scout, tilemap):
        player = FakePlayer(9999, 9999)
        assert scout._can_see_player(player, tilemap) is False

    def test_does_not_detect_through_walls(self):
        """LOS blocked by a solid tile between enemy and player."""
        # Place a wall between (100,100) and (300,100) — at grid (6, 3) = pixel 192,96
        solid = {(6, 3)}
        tilemap = FakeTileMap(solid_positions=solid)
        bus = EventBus()
        enemy = Enemy(100, 100, _scout_config(), event_bus=bus)
        player = FakePlayer(300, 100)
        assert enemy._can_see_player(player, tilemap) is False

    def test_does_not_detect_dead_player(self, scout, tilemap):
        player = FakePlayer(200, 100)
        player.alive = False
        assert scout._can_see_player(player, tilemap) is False


# =====================================================================
# Movement & Patrol
# =====================================================================

class TestMovement:

    def test_patrol_follows_waypoints(self, scout, tilemap):
        """Enemy moves toward the next waypoint in its patrol path."""
        scout._change_state(EnemyState.PATROL)
        start_pos = pygame.math.Vector2(scout.pos)
        # Run several frames
        far_player = FakePlayer(9999, 9999)
        for _ in range(60):
            scout.update(0.016, tilemap=tilemap, player=far_player)
        # Should have moved from start
        assert scout.pos != start_pos

    def test_patrol_wraps_around_path(self, event_bus):
        """Enemy wraps back to first waypoint after reaching the last."""
        cfg = _scout_config()
        patrol = [[100, 100], [110, 100]]
        enemy = Enemy(100, 100, cfg, patrol_path=patrol, event_bus=event_bus)
        enemy._change_state(EnemyState.PATROL)

        tilemap = FakeTileMap()
        far_player = FakePlayer(9999, 9999)
        # Move for a while so it cycles waypoints
        for _ in range(200):
            enemy.update(0.016, tilemap=tilemap, player=far_player)

        # Should have cycled through patrol_index
        # The important thing is it didn't crash and index is valid
        assert 0 <= enemy._patrol_index < len(enemy._patrol_path)

    def test_enemy_respects_tilemap_collision(self, event_bus):
        """Enemy cannot walk through solid tiles."""
        # Place a wall immediately to the right of the enemy
        solid = {(4, 3)}  # tile at pixel (128, 96)
        tilemap = FakeTileMap(solid_positions=solid)
        cfg = _scout_config()
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)

        # Try to move right toward the wall
        start_x = enemy.pos.x
        enemy._move_toward(pygame.math.Vector2(200, 100), 0.5, tilemap)

        # Should NOT have passed through the wall tile (128px boundary)
        assert enemy.pos.x < 128 + 16  # half-width past the wall


# =====================================================================
# Combat — Taking Damage
# =====================================================================

class TestDamage:

    def test_takes_damage_reduces_health(self, scout):
        scout.take_damage(20)
        assert scout.health == 30

    def test_takes_damage_returns_actual(self, scout):
        actual = scout.take_damage(60)
        assert actual == 50  # capped at remaining health

    def test_dies_at_zero_health(self, scout):
        scout.take_damage(50)
        assert scout.alive is False
        assert scout.state == EnemyState.DEAD

    def test_overkill_caps_health_at_zero(self, scout):
        scout.take_damage(999)
        assert scout.health == 0

    def test_hit_flash_on_damage(self, scout):
        scout.take_damage(10)
        assert scout._hit_flash_timer > 0

    def test_no_damage_when_dead(self, scout):
        scout.take_damage(50)
        actual = scout.take_damage(10)
        assert actual == 0


# =====================================================================
# Combat — Firing Projectiles
# =====================================================================

class TestFiring:

    def test_fires_projectile_in_attack_state(self, scout, tilemap):
        player = FakePlayer(200, 100)
        scout._change_state(EnemyState.ATTACK)
        # Let fire timer accumulate enough
        scout._fire_timer = 10.0
        scout.update(0.016, tilemap=tilemap, player=player)

        assert len(scout.projectile_group) > 0

    def test_projectile_has_correct_damage(self, scout):
        player_pos = pygame.math.Vector2(200, 100)
        proj = scout._fire_projectile(player_pos)
        assert proj.damage == scout.damage

    def test_projectile_owner_is_enemy(self, scout):
        player_pos = pygame.math.Vector2(200, 100)
        proj = scout._fire_projectile(player_pos)
        assert proj.owner is scout

    def test_shot_fired_event_published(self, scout, event_bus):
        events_received = []
        event_bus.subscribe("shot_fired", lambda **kw: events_received.append(kw))

        scout._fire_projectile(pygame.math.Vector2(200, 100))
        assert len(events_received) == 1
        assert events_received[0]["source"] is scout


# =====================================================================
# Death & Events
# =====================================================================

class TestDeath:

    def test_death_publishes_enemy_killed_event(self, scout, event_bus):
        events_received = []
        event_bus.subscribe("enemy_killed", lambda **kw: events_received.append(kw))

        killer = FakePlayer(200, 100)
        scout.take_damage(50, source=killer)

        assert len(events_received) == 1
        ev = events_received[0]
        assert ev["enemy"] is scout
        assert ev["killer"] is killer
        assert ev["xp_reward"] == 25
        assert ev["loot_table_id"] == "enemy_scout"

    def test_death_event_includes_tier_xp(self, enforcer, event_bus):
        events_received = []
        event_bus.subscribe("enemy_killed", lambda **kw: events_received.append(kw))

        enforcer.take_damage(150)
        assert events_received[0]["xp_reward"] == 75

    def test_entity_hit_event_on_damage(self, scout, event_bus):
        events_received = []
        event_bus.subscribe("entity_hit", lambda **kw: events_received.append(kw))

        scout.take_damage(10)
        assert len(events_received) == 1
        assert events_received[0]["target"] is scout
        assert events_received[0]["damage"] == 10

    def test_die_only_fires_once(self, scout, event_bus):
        events_received = []
        event_bus.subscribe("enemy_killed", lambda **kw: events_received.append(kw))

        scout.take_damage(50)
        scout.die()  # second call should be no-op
        assert len(events_received) == 1

    def test_dead_enemy_not_updated(self, scout, tilemap, player):
        scout.take_damage(50)
        old_pos = pygame.math.Vector2(scout.pos)
        scout.update(1.0, tilemap=tilemap, player=player)
        assert scout.pos == old_pos


# =====================================================================
# Tier Comparisons
# =====================================================================

class TestTierComparisons:

    def test_scout_faster_than_enforcer(self):
        assert _scout_config().speed > _enforcer_config().speed

    def test_enforcer_more_health_than_scout(self):
        assert _enforcer_config().health > _scout_config().health

    def test_enforcer_more_damage_than_scout(self):
        assert _enforcer_config().damage > _scout_config().damage

    def test_enforcer_more_xp_than_scout(self):
        assert _enforcer_config().xp_reward > _scout_config().xp_reward

    def test_scout_higher_fire_rate(self):
        assert _scout_config().fire_rate > _enforcer_config().fire_rate


# =====================================================================
# Config Loader
# =====================================================================

class TestConfigLoader:

    def test_load_enemy_tiers_from_json(self):
        tiers = load_enemy_tiers("data/enemies.json")
        assert "scout" in tiers
        assert "enforcer" in tiers

    def test_scout_tier_loads_correct_stats(self):
        tiers = load_enemy_tiers("data/enemies.json")
        scout = tiers["scout"]
        assert scout.health == 50
        assert scout.speed == 120.0
        assert scout.tier == EnemyTier.SCOUT

    def test_enforcer_tier_loads_correct_stats(self):
        tiers = load_enemy_tiers("data/enemies.json")
        enforcer = tiers["enforcer"]
        assert enforcer.health == 150
        assert enforcer.speed == 70.0
        assert enforcer.tier == EnemyTier.ENFORCER


# =====================================================================
# Integration — Multiple Enemies
# =====================================================================

class TestMultipleEnemies:

    def test_multiple_enemies_independent_state(self, event_bus, tilemap):
        """Each enemy maintains its own FSM state independently."""
        e1 = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        e2 = Enemy(800, 800, _scout_config(), event_bus=event_bus)

        close_player = FakePlayer(200, 100)  # close to e1, far from e2

        e1._change_state(EnemyState.PATROL)
        e2._change_state(EnemyState.PATROL)

        e1.update(0.016, tilemap=tilemap, player=close_player)
        e2.update(0.016, tilemap=tilemap, player=close_player)

        # e1 should detect player, e2 should not
        assert e1.state == EnemyState.DETECT
        assert e2.state == EnemyState.PATROL

    def test_enemy_attack_damages_player(self, event_bus, tilemap):
        """Enemy projectile should be able to damage a player entity."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        player = FakePlayer(200, 100)

        proj = enemy._fire_projectile(player.pos)
        # Manually move projectile and check hit
        for _ in range(100):
            proj.update(0.016, tilemap=tilemap)
            if proj.check_hit(player):
                player.take_damage(proj.damage)
                break

        assert player.health < 100
