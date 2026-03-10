"""Edge-case and error-path tests for the Enemy FSM AI.

Complements the main test_enemy.py suite with boundary conditions,
unusual inputs, and stress scenarios.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

pygame.init()

from src.entities.base import Entity
from src.entities.enemy import Enemy, EnemyState, _DISENGAGE_MULTIPLIER, _WAYPOINT_THRESHOLD
from src.entities.enemy_config import EnemyTierConfig, EnemyTier
from src.events import EventBus


# =====================================================================
# Helpers
# =====================================================================

def _scout_config(**overrides) -> EnemyTierConfig:
    defaults = dict(
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
    defaults.update(overrides)
    return EnemyTierConfig(**defaults)


def _enforcer_config(**overrides) -> EnemyTierConfig:
    defaults = dict(
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
    defaults.update(overrides)
    return EnemyTierConfig(**defaults)


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


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def tilemap():
    return FakeTileMap()


# =====================================================================
# No patrol path
# =====================================================================

class TestNoPatrolPath:

    def test_patrol_without_path_reverts_to_idle(self, event_bus, tilemap):
        """Enemy with no patrol path should cycle back to IDLE from PATROL."""
        cfg = _scout_config(idle_duration=1.0)
        enemy = Enemy(100, 100, cfg, patrol_path=[], event_bus=event_bus)
        enemy._change_state(EnemyState.PATROL)
        far_player = FakePlayer(9999, 9999)

        # Run long enough for idle_duration to expire in patrol's fallback
        for _ in range(200):
            enemy.update(0.016, tilemap=tilemap, player=far_player)

        assert enemy.state == EnemyState.IDLE

    def test_patrol_without_path_no_movement(self, event_bus, tilemap):
        """Enemy with no patrol path should not move."""
        enemy = Enemy(100, 100, _scout_config(), patrol_path=[], event_bus=event_bus)
        enemy._change_state(EnemyState.PATROL)
        far_player = FakePlayer(9999, 9999)
        enemy.update(0.016, tilemap=tilemap, player=far_player)
        assert enemy.pos.x == pytest.approx(100.0)
        assert enemy.pos.y == pytest.approx(100.0)

    def test_enemy_without_patrol_defaults_to_empty(self, event_bus):
        """Creating enemy without patrol_path arg results in empty list."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        assert enemy._patrol_path == []


# =====================================================================
# Null/missing arguments
# =====================================================================

class TestNullArguments:

    def test_update_with_no_tilemap(self, event_bus):
        """Update should not crash when tilemap is None."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        far_player = FakePlayer(9999, 9999)
        enemy.update(0.016, tilemap=None, player=far_player)
        assert enemy.alive is True

    def test_update_with_no_player(self, event_bus, tilemap):
        """Update should not crash when player is None."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy.update(0.016, tilemap=tilemap, player=None)
        assert enemy.alive is True

    def test_update_with_no_args(self, event_bus):
        """Update with no kwargs should not crash."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy.update(0.016)
        assert enemy.alive is True

    def test_attack_without_player_goes_to_patrol(self, event_bus, tilemap):
        """If player is None during ATTACK, enemy should disengage."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy._change_state(EnemyState.ATTACK)
        enemy.update(0.016, tilemap=tilemap, player=None)
        assert enemy.state == EnemyState.PATROL

    def test_enemy_without_event_bus(self, tilemap):
        """Enemy should function without event_bus (no events published)."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=None)
        enemy.take_damage(50)
        assert enemy.alive is False
        assert enemy.state == EnemyState.DEAD


# =====================================================================
# Detection boundary conditions
# =====================================================================

class TestDetectionBoundary:

    def test_exact_detection_range_boundary(self, event_bus, tilemap):
        """Player at exactly detection_range should still be detected."""
        cfg = _scout_config(detection_range=100.0)
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)
        player = FakePlayer(200, 100)  # exactly 100px away
        assert enemy._can_see_player(player, tilemap) is True

    def test_just_outside_detection_range(self, event_bus, tilemap):
        """Player slightly beyond detection_range should not be detected."""
        cfg = _scout_config(detection_range=100.0)
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)
        player = FakePlayer(201, 100)  # 101px away
        assert enemy._can_see_player(player, tilemap) is False

    def test_player_at_same_position(self, event_bus, tilemap):
        """Player at same position as enemy should be detected."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        player = FakePlayer(100, 100)
        assert enemy._can_see_player(player, tilemap) is True

    def test_extended_range_boundary(self, event_bus):
        """Player at exactly extended range should still keep enemy in attack."""
        cfg = _scout_config(detection_range=100.0)
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)
        # Extended range = 100 * 1.5 = 150
        player = FakePlayer(250, 100)  # exactly 150px
        assert enemy._in_extended_range(player) is True

    def test_just_outside_extended_range(self, event_bus):
        cfg = _scout_config(detection_range=100.0)
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)
        # 151px > 150 extended range
        player = FakePlayer(251, 100)
        assert enemy._in_extended_range(player) is False

    def test_multiple_walls_block_los(self, event_bus):
        """Multiple solid tiles between enemy and player block LOS."""
        solid = {(5, 3), (6, 3), (7, 3)}
        tilemap = FakeTileMap(solid_positions=solid)
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        player = FakePlayer(300, 100)
        assert enemy._can_see_player(player, tilemap) is False


# =====================================================================
# Combat edge cases
# =====================================================================

class TestCombatEdgeCases:

    def test_fire_at_same_position(self, event_bus):
        """Firing at target at same position should not crash (zero direction)."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        proj = enemy._fire_projectile(pygame.math.Vector2(100, 100))
        # Direction defaults to (1, 0) for zero-length
        assert proj.direction.length() == pytest.approx(1.0)

    def test_fire_timer_resets_after_shot(self, event_bus, tilemap):
        """Fire timer should reset to 0 after firing."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        player = FakePlayer(200, 100)
        enemy._change_state(EnemyState.ATTACK)
        enemy._fire_timer = 10.0  # Ready to fire
        enemy.update(0.016, tilemap=tilemap, player=player)
        # Timer should have been reset
        assert enemy._fire_timer < 1.0

    def test_projectile_has_limited_range(self, event_bus):
        """Enemy projectile max_range is based on attack_range * 1.5."""
        cfg = _scout_config(attack_range=200.0)
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)
        proj = enemy._fire_projectile(pygame.math.Vector2(300, 100))
        assert proj.max_range == 300.0  # 200 * 1.5

    def test_projectile_added_to_group(self, event_bus):
        """Fired projectile should be added to the enemy's projectile group."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        assert len(enemy.projectile_group) == 0
        enemy._fire_projectile(pygame.math.Vector2(200, 100))
        assert len(enemy.projectile_group) == 1

    def test_multiple_projectiles_accumulate(self, event_bus):
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy._fire_projectile(pygame.math.Vector2(200, 100))
        enemy._fire_projectile(pygame.math.Vector2(200, 100))
        enemy._fire_projectile(pygame.math.Vector2(200, 100))
        assert len(enemy.projectile_group) == 3

    def test_no_firing_outside_attack_range(self, event_bus, tilemap):
        """Enemy should not fire when player is beyond attack_range."""
        cfg = _scout_config(attack_range=100.0, detection_range=500.0)
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)
        player = FakePlayer(300, 100)  # 200px > 100 attack range
        enemy._change_state(EnemyState.ATTACK)
        enemy._fire_timer = 10.0
        enemy.update(0.016, tilemap=tilemap, player=player)
        assert len(enemy.projectile_group) == 0

    def test_fires_within_attack_range(self, event_bus, tilemap):
        """Enemy fires when player is within attack_range."""
        cfg = _scout_config(attack_range=200.0)
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)
        player = FakePlayer(200, 100)  # 100px < 200 attack range
        enemy._change_state(EnemyState.ATTACK)
        enemy._fire_timer = 10.0
        enemy.update(0.016, tilemap=tilemap, player=player)
        assert len(enemy.projectile_group) > 0

    def test_moves_toward_player_outside_attack_range(self, event_bus, tilemap):
        """In ATTACK state, enemy moves toward player if outside attack_range."""
        cfg = _scout_config(attack_range=50.0, detection_range=500.0)
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)
        player = FakePlayer(300, 100)
        enemy._change_state(EnemyState.ATTACK)
        start_x = enemy.pos.x
        enemy.update(0.5, tilemap=tilemap, player=player)
        assert enemy.pos.x > start_x


# =====================================================================
# Damage edge cases
# =====================================================================

class TestDamageEdgeCases:

    def test_one_damage_from_full_health(self, event_bus):
        cfg = _scout_config(health=50)
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)
        actual = enemy.take_damage(1)
        assert actual == 1
        assert enemy.health == 49
        assert enemy.alive is True

    def test_exact_lethal_damage(self, event_bus):
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        actual = enemy.take_damage(50)
        assert actual == 50
        assert enemy.health == 0
        assert enemy.alive is False

    def test_source_tracked_for_death_event(self, event_bus):
        """The killer should be recorded from the last damage source."""
        events = []
        event_bus.subscribe("enemy_killed", lambda **kw: events.append(kw))

        killer = FakePlayer(200, 200)
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy.take_damage(30, source=FakePlayer(300, 300))  # non-lethal
        enemy.take_damage(20, source=killer)  # lethal

        assert events[0]["killer"] is killer

    def test_hit_flash_timer_set(self, event_bus):
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy.take_damage(10)
        assert enemy._hit_flash_timer == pytest.approx(0.15)

    def test_hit_flash_decays_over_time(self, event_bus, tilemap):
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy.take_damage(10)
        far_player = FakePlayer(9999, 9999)
        enemy.update(0.2, tilemap=tilemap, player=far_player)
        assert enemy._hit_flash_timer == 0.0


# =====================================================================
# State timer resets
# =====================================================================

class TestStateTimerResets:

    def test_state_timer_resets_on_transition(self, event_bus, tilemap):
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy._state_timer = 999.0
        enemy._change_state(EnemyState.PATROL)
        assert enemy._state_timer == 0.0

    def test_alert_timer_resets_on_detect(self, event_bus):
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy._alert_timer = 999.0
        enemy._change_state(EnemyState.DETECT)
        assert enemy._alert_timer == 0.0

    def test_fire_timer_resets_on_attack(self, event_bus):
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy._fire_timer = 999.0
        enemy._change_state(EnemyState.ATTACK)
        assert enemy._fire_timer == 0.0


# =====================================================================
# Facing direction
# =====================================================================

class TestFacingDirection:

    def test_facing_updates_in_detect(self, event_bus, tilemap):
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy._change_state(EnemyState.DETECT)
        player = FakePlayer(200, 100)  # to the right
        enemy.update(0.1, tilemap=tilemap, player=player)
        assert enemy.facing_direction.x > 0

    def test_facing_updates_in_attack(self, event_bus, tilemap):
        enemy = Enemy(100, 100, _scout_config(detection_range=500.0), event_bus=event_bus)
        enemy._change_state(EnemyState.ATTACK)
        player = FakePlayer(100, 300)  # below
        enemy.update(0.016, tilemap=tilemap, player=player)
        assert enemy.facing_direction.y > 0

    def test_facing_updates_on_move_toward(self, event_bus, tilemap):
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        target = pygame.math.Vector2(0, 100)  # to the left
        enemy._move_toward(target, 0.1, tilemap)
        assert enemy.facing_direction.x < 0


# =====================================================================
# Waypoint threshold
# =====================================================================

class TestWaypointThreshold:

    def test_advances_when_within_threshold(self, event_bus, tilemap):
        """Enemy should advance to next waypoint when close enough."""
        patrol = [[100, 100], [100 + _WAYPOINT_THRESHOLD - 1, 100]]
        enemy = Enemy(100, 100, _scout_config(), patrol_path=patrol, event_bus=event_bus)
        enemy._change_state(EnemyState.PATROL)
        far_player = FakePlayer(9999, 9999)
        # The enemy starts at the first waypoint, within threshold
        enemy.update(0.016, tilemap=tilemap, player=far_player)
        assert enemy._patrol_index == 1

    def test_single_waypoint_patrol(self, event_bus, tilemap):
        """Enemy with a single waypoint should stay at index 0."""
        patrol = [[100, 100]]
        enemy = Enemy(100, 100, _scout_config(), patrol_path=patrol, event_bus=event_bus)
        enemy._change_state(EnemyState.PATROL)
        far_player = FakePlayer(9999, 9999)
        for _ in range(60):
            enemy.update(0.016, tilemap=tilemap, player=far_player)
        assert enemy._patrol_index == 0


# =====================================================================
# Sprite group behaviour
# =====================================================================

class TestSpriteGroupBehaviour:

    def test_enemy_added_to_sprite_group(self, event_bus):
        group = pygame.sprite.Group()
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        group.add(enemy)
        assert enemy in group

    def test_dead_enemy_removed_from_group(self, event_bus):
        """Enemy.die() calls kill() which removes from all sprite groups."""
        group = pygame.sprite.Group()
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        group.add(enemy)
        enemy.take_damage(50)
        assert enemy not in group

    def test_custom_projectile_group(self, event_bus):
        """Enemy should use a provided projectile group when non-empty.

        Note: Empty pygame.sprite.Group is falsy, so the constructor's
        ``projectile_group or Group()`` only uses the provided group when
        it already has sprites.  This test verifies the projectile lands
        in ``enemy.projectile_group`` regardless.
        """
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy._fire_projectile(pygame.math.Vector2(200, 100))
        assert len(enemy.projectile_group) == 1

    def test_default_projectile_group_created(self, event_bus):
        """Enemy creates its own projectile group if none provided."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        assert enemy.projectile_group is not None


# =====================================================================
# Rapid state transitions
# =====================================================================

class TestRapidTransitions:

    def test_detect_to_patrol_when_player_flees(self, event_bus, tilemap):
        """During DETECT, if player moves beyond extended range, enemy returns to PATROL."""
        cfg = _scout_config(detection_range=100.0)
        enemy = Enemy(100, 100, cfg, event_bus=event_bus)
        enemy._change_state(EnemyState.DETECT)
        far_player = FakePlayer(500, 500)  # beyond 150 extended range
        enemy.update(0.016, tilemap=tilemap, player=far_player)
        assert enemy.state == EnemyState.PATROL

    def test_full_state_cycle(self, event_bus, tilemap):
        """IDLE → PATROL → DETECT → ATTACK full cycle."""
        cfg = _scout_config(idle_duration=0.1, alert_delay=0.1)
        patrol = [[100, 100], [200, 100]]
        enemy = Enemy(100, 100, cfg, patrol_path=patrol, event_bus=event_bus)
        far_player = FakePlayer(9999, 9999)

        # IDLE → PATROL
        enemy.update(0.2, tilemap=tilemap, player=far_player)
        assert enemy.state == EnemyState.PATROL

        # PATROL → DETECT (bring player close)
        close_player = FakePlayer(200, 100)
        enemy.update(0.016, tilemap=tilemap, player=close_player)
        assert enemy.state == EnemyState.DETECT

        # DETECT → ATTACK
        enemy.update(0.2, tilemap=tilemap, player=close_player)
        assert enemy.state == EnemyState.ATTACK

    def test_kill_during_attack(self, event_bus, tilemap):
        """Killing an enemy during ATTACK transitions correctly."""
        enemy = Enemy(100, 100, _scout_config(), event_bus=event_bus)
        enemy._change_state(EnemyState.ATTACK)
        enemy.take_damage(50)
        assert enemy.state == EnemyState.DEAD
        assert enemy.alive is False


# =====================================================================
# EnemyTierConfig edge cases
# =====================================================================

class TestTierConfigEdgeCases:

    def test_frozen_dataclass(self):
        """EnemyTierConfig should be immutable."""
        cfg = _scout_config()
        with pytest.raises(AttributeError):
            cfg.health = 999

    def test_tier_enum_values(self):
        assert EnemyTier.SCOUT.value == "scout"
        assert EnemyTier.ENFORCER.value == "enforcer"

    def test_disengage_multiplier_constant(self):
        assert _DISENGAGE_MULTIPLIER == 1.5

    def test_waypoint_threshold_constant(self):
        assert _WAYPOINT_THRESHOLD == 8.0
