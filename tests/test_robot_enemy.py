"""Tests for RobotEnemy — health management, FSM state, and death animation."""
from __future__ import annotations

import pytest

from src.entities.robot_enemy import AIState, RobotEnemy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_robot(**kwargs) -> RobotEnemy:
    """Return a RobotEnemy with sensible defaults, overridable via kwargs."""
    defaults = dict(
        x=100.0,
        y=200.0,
        hp=50,
        patrol_speed=40.0,
        move_speed=80.0,
        aggro_range=200.0,
        attack_range=40.0,
        attack_damage=10,
        attack_cooldown=1.2,
        xp_reward=25,
        loot_table=[{"item_id": "ammo_pistol", "weight": 100}],
        type_id="grunt",
        patrol_waypoints=[(100.0, 200.0), (300.0, 200.0)],
    )
    defaults.update(kwargs)
    return RobotEnemy(**defaults)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestRobotEnemyHealth:
    def test_initial_hp_equals_configured_value(self):
        robot = _make_robot(hp=80)
        assert robot.hp == 80

    def test_max_hp_stored_separately(self):
        robot = _make_robot(hp=80)
        assert robot.max_hp == 80

    def test_take_damage_reduces_hp(self):
        robot = _make_robot(hp=50)
        robot.take_damage(10)
        assert robot.hp == 40

    def test_take_damage_multiple_hits(self):
        robot = _make_robot(hp=50)
        robot.take_damage(15)
        robot.take_damage(15)
        assert robot.hp == 20

    def test_take_damage_does_not_go_below_zero(self):
        robot = _make_robot(hp=10)
        robot.take_damage(999)
        assert robot.hp == 0

    def test_take_damage_returns_remaining_hp(self):
        robot = _make_robot(hp=50)
        remaining = robot.take_damage(20)
        assert remaining == 30

    def test_take_damage_while_dead_does_nothing(self):
        robot = _make_robot(hp=10)
        robot.take_damage(10)           # → DEAD
        result = robot.take_damage(99)  # should be no-op
        assert result == 0
        assert robot.hp == 0

    def test_is_dead_false_when_hp_positive(self):
        robot = _make_robot(hp=50)
        assert robot.is_dead() is False

    def test_is_dead_true_when_hp_zero(self):
        robot = _make_robot(hp=10)
        robot.take_damage(10)
        assert robot.is_dead() is True

    def test_is_dead_true_after_overkill(self):
        robot = _make_robot(hp=10)
        robot.take_damage(9999)
        assert robot.is_dead() is True


# ---------------------------------------------------------------------------
# FSM state
# ---------------------------------------------------------------------------

class TestRobotEnemyState:
    def test_initial_state_is_patrol(self):
        robot = _make_robot()
        assert robot.state == AIState.PATROL

    def test_state_can_be_set_to_aggro(self):
        robot = _make_robot()
        robot.state = AIState.AGGRO
        assert robot.state == AIState.AGGRO

    def test_state_can_be_set_to_attack(self):
        robot = _make_robot()
        robot.state = AIState.ATTACK
        assert robot.state == AIState.ATTACK

    def test_take_damage_to_zero_transitions_to_dead(self):
        robot = _make_robot(hp=20)
        robot.take_damage(20)
        assert robot.state == AIState.DEAD

    def test_take_damage_partial_does_not_transition_to_dead(self):
        robot = _make_robot(hp=20)
        robot.take_damage(10)
        assert robot.state == AIState.PATROL

    def test_take_full_damage_from_aggro_state(self):
        robot = _make_robot(hp=30)
        robot.state = AIState.AGGRO
        robot.take_damage(30)
        assert robot.state == AIState.DEAD


# ---------------------------------------------------------------------------
# Patrol waypoints
# ---------------------------------------------------------------------------

class TestRobotEnemyPatrol:
    def test_waypoints_stored(self):
        wps = [(10.0, 20.0), (30.0, 40.0)]
        robot = _make_robot(patrol_waypoints=wps)
        assert robot.patrol_waypoints == wps

    def test_default_waypoint_is_spawn_position(self):
        robot = _make_robot(x=55.0, y=77.0, patrol_waypoints=None)
        assert robot.patrol_waypoints == [(55.0, 77.0)]

    def test_initial_waypoint_index_is_zero(self):
        robot = _make_robot()
        assert robot.current_waypoint == 0


# ---------------------------------------------------------------------------
# Death animation
# ---------------------------------------------------------------------------

class TestRobotEnemyDeathAnimation:
    def test_advance_animation_returns_false_before_duration(self):
        robot = _make_robot()
        robot.state = AIState.DEAD
        # Tiny dt — should not complete
        result = robot.advance_animation(0.01)
        assert result is False

    def test_advance_animation_returns_true_when_done(self):
        robot = _make_robot()
        robot.state = AIState.DEAD
        # Advance past the full death duration (4 frames × 0.15 s = 0.6 s)
        result = robot.advance_animation(1.0)
        assert result is True

    def test_advance_animation_accumulates_time(self):
        robot = _make_robot()
        robot.state = AIState.DEAD
        robot.advance_animation(0.2)
        robot.advance_animation(0.2)
        robot.advance_animation(0.2)
        # Still under 0.6 s
        result = robot.advance_animation(0.1)
        # Cumulative 0.7 s ≥ 0.6 s → True
        assert result is True

    def test_death_timer_resets_on_take_damage_to_zero(self):
        robot = _make_robot(hp=10)
        robot._death_timer = 99.0           # pre-set as if previously dead
        robot.hp = 10                        # restore HP
        robot.state = AIState.PATROL
        robot.take_damage(10)               # kills again → resets timer
        assert robot._death_timer == 0.0


# ---------------------------------------------------------------------------
# Alive flag and rect
# ---------------------------------------------------------------------------

class TestRobotEnemyAliveAndRect:
    def test_alive_true_on_creation(self):
        robot = _make_robot()
        assert robot.alive is True

    def test_rect_reflects_position(self):
        robot = _make_robot(x=10.0, y=20.0)
        r = robot.rect
        assert r.x == 10
        assert r.y == 20

    def test_rect_reflects_dimensions(self):
        robot = _make_robot()
        r = robot.rect
        assert r.width == robot.width
        assert r.height == robot.height

    def test_loot_table_stored(self):
        table = [{"item_id": "medkit_small", "weight": 50}]
        robot = _make_robot(loot_table=table)
        assert robot.loot_table == table

    def test_xp_reward_stored(self):
        robot = _make_robot(xp_reward=99)
        assert robot.xp_reward == 99


# ---------------------------------------------------------------------------
# Coordinate properties and sync_from_rect
# ---------------------------------------------------------------------------

class TestRobotEnemyCoordinates:
    """x/y properties delegate to rect with float accumulation; sync_from_rect
    pulls physics-resolved rect coordinates back into the float backing fields.

    This is the core coordinate contract that lets PhysicsSystem (which writes
    rect) and AISystem (which reads/writes enemy.x via property) stay in sync.
    """

    def test_x_getter_returns_initial_float_value(self):
        robot = _make_robot(x=123.7)
        assert robot.x == pytest.approx(123.7)

    def test_y_getter_returns_initial_float_value(self):
        robot = _make_robot(y=456.3)
        assert robot.y == pytest.approx(456.3)

    def test_setting_x_updates_rect_x_as_truncated_int(self):
        robot = _make_robot(x=0.0)
        robot.x = 73.9
        assert robot.rect.x == 73

    def test_setting_x_preserves_float_precision_in_backing_field(self):
        robot = _make_robot(x=0.0)
        robot.x = 73.9
        assert robot.x == pytest.approx(73.9)

    def test_setting_y_updates_rect_y_as_truncated_int(self):
        robot = _make_robot(y=0.0)
        robot.y = 150.6
        assert robot.rect.y == 150

    def test_setting_y_preserves_float_precision_in_backing_field(self):
        robot = _make_robot(y=0.0)
        robot.y = 150.6
        assert robot.y == pytest.approx(150.6)

    def test_initial_rect_position_matches_constructor_args(self):
        robot = _make_robot(x=64.0, y=128.0)
        assert robot.rect.x == 64
        assert robot.rect.y == 128

    def test_sync_from_rect_updates_x_from_rect(self):
        """sync_from_rect() pulls PhysicsSystem-written rect.x into float x."""
        robot = _make_robot(x=0.0)
        robot.rect.x = 200        # simulate PhysicsSystem moving the rect
        robot.sync_from_rect()
        assert robot.x == pytest.approx(200.0)

    def test_sync_from_rect_updates_y_from_rect(self):
        robot = _make_robot(y=0.0)
        robot.rect.y = 350
        robot.sync_from_rect()
        assert robot.y == pytest.approx(350.0)

    def test_sync_from_rect_does_not_affect_unrelated_attributes(self):
        """sync_from_rect touches only _float_x/_float_y; hp/state unchanged."""
        robot = _make_robot(hp=40)
        robot.state = AIState.AGGRO
        robot.rect.x = 99
        robot.sync_from_rect()
        assert robot.hp == 40
        assert robot.state == AIState.AGGRO

    def test_x_property_round_trip_after_physics_sim(self):
        """Setting x, then sync_from_rect from rect, restores original int value."""
        robot = _make_robot(x=0.0)
        robot.x = 100.9          # float_x = 100.9, rect.x = 100
        robot.sync_from_rect()   # float_x = float(rect.x) = 100.0
        assert robot.x == pytest.approx(100.0)
        assert robot.rect.x == 100
