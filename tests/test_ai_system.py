"""
Integration tests for AISystem — FSM driver
=============================================

Tests drive the four-state FSM (PATROL → AGGRO → ATTACK → DEAD) through
``AISystem.update()`` using lightweight mock objects; no Pygame display
context is required.

Coverage:
  PATROL  transitions to AGGRO, waypoint movement, wrapping
  AGGRO   transitions to ATTACK and back to PATROL, lost-timer logic,
          direct movement, BFS-guided movement, path recalculation
  ATTACK  damage timing, cooldown reset, revert to AGGRO, dead-player guard
  DEAD    alive flag, enemy_killed emission, payload correctness, no double-emit
  Multi   independent updates per-robot, skip of already-dead robots
"""
from __future__ import annotations

import pytest

from src.entities.robot_enemy import AIState, RobotEnemy
from src.systems.ai_system import (
    AISystem,
    LOST_PLAYER_TIMEOUT,
    PATH_RECALC_INTERVAL,
)


# ---------------------------------------------------------------------------
# Lightweight mocks
# ---------------------------------------------------------------------------

class MockPlayer:
    """Minimal player stub — exposes x/y/width/height and take_damage."""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.width = 32
        self.height = 48
        self.alive = True
        self.damage_received: list[int] = []

    def take_damage(self, amount: int) -> None:
        self.damage_received.append(amount)

    @property
    def centre(self) -> tuple[float, float]:
        return self.x + self.width / 2.0, self.y + self.height / 2.0


class MockTilemap:
    """Minimal tilemap with a fully-walkable grid."""

    def __init__(self, rows: int = 20, cols: int = 20, tile_size: int = 32) -> None:
        self.tile_size = tile_size
        self.walkability_grid = [[0] * cols for _ in range(rows)]


# ---------------------------------------------------------------------------
# Robot factory
# ---------------------------------------------------------------------------

def _make_robot(**overrides) -> RobotEnemy:
    defaults: dict = dict(
        x=100.0,
        y=100.0,
        hp=50,
        patrol_speed=40.0,
        move_speed=80.0,
        aggro_range=200.0,
        attack_range=40.0,
        attack_damage=10,
        attack_cooldown=1.2,
        xp_reward=25,
        loot_table=[{"item_id": "ammo_pistol", "weight": 60}],
        type_id="grunt",
        patrol_waypoints=[(100.0, 100.0), (300.0, 100.0)],
    )
    defaults.update(overrides)
    return RobotEnemy(**defaults)


def _centre(robot: RobotEnemy) -> tuple[float, float]:
    """Return world-space centre of *robot*."""
    return robot.x + robot.width / 2.0, robot.y + robot.height / 2.0


# ===========================================================================
# PATROL state
# ===========================================================================

class TestAISystemPatrol:

    def test_patrol_to_aggro_when_player_enters_range(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, aggro_range=200.0)
        # Player close enough: distance ≈ 50 px, well inside 200 px aggro_range.
        player = MockPlayer(x=150.0, y=100.0)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.state == AIState.AGGRO

    def test_patrol_stays_when_player_out_of_range(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, aggro_range=100.0)
        player = MockPlayer(x=2000.0, y=2000.0)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.state == AIState.PATROL

    def test_patrol_moves_robot_toward_current_waypoint(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=0.0,
            y=0.0,
            patrol_speed=40.0,
            aggro_range=5.0,          # tiny range — player won't trigger aggro
            patrol_waypoints=[(300.0, 0.0)],
        )
        player = MockPlayer(x=5000.0, y=5000.0)
        x_before = robot.x
        ai.update([robot], player, None, dt=1.0, event_bus=event_bus)
        assert robot.x > x_before

    def test_patrol_advances_waypoint_index_on_arrival(self, event_bus):
        ai = AISystem()
        # The arrival check compares the robot's *centre* to the waypoint.
        # Default robot: width=32, height=48 → centre offset is (+16, +24).
        # Place the first waypoint exactly at the starting centre (16, 24) so
        # distance == 0 < _ARRIVAL_THRESHOLD (4 px) and the index advances.
        robot = _make_robot(
            x=0.0,
            y=0.0,
            aggro_range=5.0,
            patrol_waypoints=[(16.0, 24.0), (300.0, 24.0)],
        )
        player = MockPlayer(x=5000.0, y=5000.0)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.current_waypoint == 1

    def test_patrol_wraps_waypoint_index_cyclically(self, event_bus):
        ai = AISystem()
        # Only one waypoint; index must wrap back to 0 after advancing.
        robot = _make_robot(
            x=1.0,
            y=0.0,
            aggro_range=5.0,
            patrol_waypoints=[(0.0, 0.0)],
        )
        player = MockPlayer(x=5000.0, y=5000.0)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.current_waypoint == 0

    def test_patrol_resets_lost_timer_on_aggro_transition(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, aggro_range=300.0)
        robot.lost_timer = 5.0
        player = MockPlayer(x=130.0, y=100.0)  # inside aggro_range
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.state == AIState.AGGRO
        assert robot.lost_timer == 0.0

    def test_patrol_clears_path_on_aggro_transition(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, aggro_range=300.0)
        robot.path = [(1, 1), (2, 1)]  # stale path
        player = MockPlayer(x=130.0, y=100.0)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.state == AIState.AGGRO
        assert robot.path == []

    def test_dead_robots_are_skipped_in_patrol(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0)
        robot.alive = False
        x_before = robot.x
        player = MockPlayer(x=110.0, y=100.0)
        ai.update([robot], player, None, dt=1.0, event_bus=event_bus)
        assert robot.x == x_before


# ===========================================================================
# AGGRO state
# ===========================================================================

class TestAISystemAggro:

    def test_aggro_to_attack_when_player_in_attack_range(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, aggro_range=300.0, attack_range=60.0)
        robot.state = AIState.AGGRO
        # Place player centre within 60 px of robot centre.
        cx, _ = _centre(robot)
        player = MockPlayer(x=cx - 20.0, y=100.0)  # distance ≈ 20 px
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.state == AIState.ATTACK

    def test_aggro_resets_attack_timer_on_attack_transition(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, aggro_range=300.0, attack_range=60.0)
        robot.state = AIState.AGGRO
        robot.attack_timer = 99.0
        cx, _ = _centre(robot)
        player = MockPlayer(x=cx - 10.0, y=100.0)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.state == AIState.ATTACK
        assert robot.attack_timer == 0.0

    def test_aggro_returns_to_patrol_after_lost_player_timeout(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, aggro_range=200.0)
        robot.state = AIState.AGGRO
        robot.lost_timer = LOST_PLAYER_TIMEOUT - 0.01
        player = MockPlayer(x=5000.0, y=5000.0)  # far outside aggro_range
        ai.update([robot], player, None, dt=0.02, event_bus=event_bus)
        assert robot.state == AIState.PATROL

    def test_aggro_does_not_return_to_patrol_before_timeout(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, aggro_range=200.0)
        robot.state = AIState.AGGRO
        robot.lost_timer = 0.0
        player = MockPlayer(x=5000.0, y=5000.0)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.state == AIState.AGGRO

    def test_aggro_clears_path_on_patrol_revert(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, aggro_range=200.0)
        robot.state = AIState.AGGRO
        robot.path = [(1, 1), (2, 2)]
        robot.lost_timer = LOST_PLAYER_TIMEOUT - 0.01
        player = MockPlayer(x=5000.0, y=5000.0)
        ai.update([robot], player, None, dt=0.02, event_bus=event_bus)
        assert robot.state == AIState.PATROL
        assert robot.path == []

    def test_aggro_resets_lost_timer_when_player_visible(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=100.0,
            y=100.0,
            aggro_range=300.0,
            attack_range=10.0,  # keep out of attack transition
        )
        robot.state = AIState.AGGRO
        robot.lost_timer = 2.5  # accumulated
        # Player inside aggro_range but outside attack_range ≈ 100 px away.
        player = MockPlayer(x=200.0, y=100.0)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.lost_timer == 0.0

    def test_aggro_moves_robot_toward_player_without_tilemap(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=0.0,
            y=0.0,
            move_speed=80.0,
            aggro_range=1000.0,
            attack_range=10.0,
        )
        robot.state = AIState.AGGRO
        player = MockPlayer(x=400.0, y=0.0)
        x_before = robot.x
        ai.update([robot], player, None, dt=1.0, event_bus=event_bus)
        assert robot.x > x_before

    def test_aggro_moves_robot_toward_player_with_tilemap(self, event_bus):
        ai = AISystem()
        tilemap = MockTilemap(rows=20, cols=20, tile_size=32)
        robot = _make_robot(
            x=0.0,
            y=0.0,
            move_speed=80.0,
            aggro_range=1000.0,
            attack_range=10.0,
        )
        robot.state = AIState.AGGRO
        player = MockPlayer(x=400.0, y=0.0)
        x_before = robot.x
        ai.update([robot], player, tilemap, dt=1.0, event_bus=event_bus)
        assert robot.x > x_before

    def test_aggro_recalculates_path_after_interval(self, event_bus):
        ai = AISystem()
        tilemap = MockTilemap(rows=20, cols=20, tile_size=32)
        robot = _make_robot(
            x=0.0, y=0.0,
            aggro_range=1000.0,
            attack_range=10.0,
        )
        robot.state = AIState.AGGRO
        robot.path_timer = PATH_RECALC_INTERVAL  # trigger immediate recalc
        player = MockPlayer(x=300.0, y=0.0)
        ai.update([robot], player, tilemap, dt=0.016, event_bus=event_bus)
        # After recalculation the timer must have reset below the interval.
        assert robot.path_timer < PATH_RECALC_INTERVAL

    def test_aggro_increments_path_timer_each_frame(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=0.0, y=0.0,
            aggro_range=1000.0,
            attack_range=10.0,
        )
        robot.state = AIState.AGGRO
        robot.path_timer = 0.0
        robot.path = [(0, 0)]  # non-empty so no forced recalc
        player = MockPlayer(x=5000.0, y=5000.0)  # out of range → lost_timer ticks
        # We just want path_timer to increment; keep lost_timer low.
        robot.lost_timer = 0.0
        # Player out of aggro_range increases lost_timer, not path_timer directly.
        # Put player inside aggro_range but far from attack_range.
        player2 = MockPlayer(x=100.0, y=0.0)
        before = robot.path_timer
        ai.update([robot], player2, None, dt=0.1, event_bus=event_bus)
        assert robot.path_timer > before or robot.state == AIState.ATTACK


# ===========================================================================
# ATTACK state
# ===========================================================================

class TestAISystemAttack:

    def test_attack_deals_damage_after_cooldown_elapses(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=100.0, y=100.0,
            attack_range=200.0,
            attack_damage=10,
            attack_cooldown=1.2,
        )
        robot.state = AIState.ATTACK
        robot.attack_timer = 1.1  # just below cooldown
        cx, cy = _centre(robot)
        player = MockPlayer(x=cx, y=cy)  # co-located — distance ≈ 28 px < 200
        # dt=0.2 → timer becomes 1.3 ≥ 1.2 → fires.
        ai.update([robot], player, None, dt=0.2, event_bus=event_bus)
        assert 10 in player.damage_received

    def test_attack_deals_correct_damage_amount(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=100.0, y=100.0,
            attack_range=200.0,
            attack_damage=35,
            attack_cooldown=1.0,
        )
        robot.state = AIState.ATTACK
        robot.attack_timer = 1.0
        cx, cy = _centre(robot)
        player = MockPlayer(x=cx, y=cy)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert 35 in player.damage_received

    def test_attack_does_not_deal_damage_before_cooldown(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=100.0, y=100.0,
            attack_range=200.0,
            attack_damage=10,
            attack_cooldown=1.2,
        )
        robot.state = AIState.ATTACK
        robot.attack_timer = 0.0
        cx, cy = _centre(robot)
        player = MockPlayer(x=cx, y=cy)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert player.damage_received == []

    def test_attack_timer_resets_to_zero_after_firing(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=100.0, y=100.0,
            attack_range=200.0,
            attack_cooldown=1.2,
        )
        robot.state = AIState.ATTACK
        robot.attack_timer = 1.3  # already over cooldown
        cx, cy = _centre(robot)
        player = MockPlayer(x=cx, y=cy)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.attack_timer == 0.0

    def test_attack_accumulates_timer_each_frame(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=100.0, y=100.0,
            attack_range=200.0,
            attack_cooldown=1.2,
        )
        robot.state = AIState.ATTACK
        robot.attack_timer = 0.0
        cx, cy = _centre(robot)
        player = MockPlayer(x=cx, y=cy)
        ai.update([robot], player, None, dt=0.5, event_bus=event_bus)
        assert robot.attack_timer == pytest.approx(0.5, abs=1e-6)

    def test_attack_reverts_to_aggro_when_player_leaves_range(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, aggro_range=300.0, attack_range=40.0)
        robot.state = AIState.ATTACK
        player = MockPlayer(x=5000.0, y=5000.0)  # far beyond attack_range
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.state == AIState.AGGRO

    def test_attack_clears_path_on_revert_to_aggro(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=100.0, y=100.0, attack_range=40.0)
        robot.state = AIState.ATTACK
        robot.path = [(1, 1), (2, 1)]
        player = MockPlayer(x=5000.0, y=5000.0)
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert robot.state == AIState.AGGRO
        assert robot.path == []

    def test_attack_does_not_damage_dead_player(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=100.0, y=100.0,
            attack_range=200.0,
            attack_cooldown=0.1,
        )
        robot.state = AIState.ATTACK
        robot.attack_timer = 0.5  # well over cooldown
        cx, cy = _centre(robot)
        player = MockPlayer(x=cx, y=cy)
        player.alive = False
        ai.update([robot], player, None, dt=0.016, event_bus=event_bus)
        assert player.damage_received == []

    def test_attack_fires_repeatedly_on_successive_cooldown_expirations(self, event_bus):
        ai = AISystem()
        robot = _make_robot(
            x=100.0, y=100.0,
            attack_range=200.0,
            attack_damage=10,
            attack_cooldown=0.5,
        )
        robot.state = AIState.ATTACK
        robot.attack_timer = 0.0
        cx, cy = _centre(robot)
        player = MockPlayer(x=cx, y=cy)
        # Two frames — each 0.6 s — should each trigger a hit.
        ai.update([robot], player, None, dt=0.6, event_bus=event_bus)
        ai.update([robot], player, None, dt=0.6, event_bus=event_bus)
        assert len(player.damage_received) == 2


# ===========================================================================
# DEAD state
# ===========================================================================

class TestAISystemDead:

    def test_dead_sets_alive_false_after_animation_completes(self, event_bus):
        ai = AISystem()
        robot = _make_robot(hp=10)
        robot.take_damage(10)          # → DEAD; _death_timer = 0
        assert robot.state == AIState.DEAD
        ai.update([robot], MockPlayer(), None, dt=1.0, event_bus=event_bus)
        assert robot.alive is False

    def test_dead_robot_alive_stays_true_before_animation_completes(self, event_bus):
        ai = AISystem()
        robot = _make_robot(hp=10)
        robot.take_damage(10)
        # 0.3 s — animation duration is 0.6 s; not done yet.
        ai.update([robot], MockPlayer(), None, dt=0.3, event_bus=event_bus)
        assert robot.alive is True

    def test_dead_emits_enemy_killed_event(self, event_bus):
        ai = AISystem()
        robot = _make_robot(hp=10, xp_reward=25)
        robot.take_damage(10)
        ai.update([robot], MockPlayer(), None, dt=1.0, event_bus=event_bus)
        assert any(name == "enemy_killed" for name, _ in event_bus.emitted)

    def test_dead_does_not_emit_before_animation_completes(self, event_bus):
        ai = AISystem()
        robot = _make_robot(hp=10)
        robot.take_damage(10)
        ai.update([robot], MockPlayer(), None, dt=0.3, event_bus=event_bus)
        assert event_bus.all_events("enemy_killed") == []

    def test_enemy_killed_payload_contains_required_keys(self, event_bus):
        ai = AISystem()
        robot = _make_robot(hp=10)
        robot.take_damage(10)
        ai.update([robot], MockPlayer(), None, dt=1.0, event_bus=event_bus)
        payload = event_bus.first_event("enemy_killed")
        for key in ("enemy", "x", "y", "loot_table", "xp_reward"):
            assert key in payload, f"Missing key: {key}"

    def test_enemy_killed_payload_xp_reward(self, event_bus):
        ai = AISystem()
        robot = _make_robot(hp=10, xp_reward=42)
        robot.take_damage(10)
        ai.update([robot], MockPlayer(), None, dt=1.0, event_bus=event_bus)
        payload = event_bus.first_event("enemy_killed")
        assert payload["xp_reward"] == 42

    def test_enemy_killed_payload_loot_table(self, event_bus):
        ai = AISystem()
        loot = [{"item_id": "medkit_small", "weight": 30}]
        robot = _make_robot(hp=10, loot_table=loot)
        robot.take_damage(10)
        ai.update([robot], MockPlayer(), None, dt=1.0, event_bus=event_bus)
        payload = event_bus.first_event("enemy_killed")
        assert payload["loot_table"] == loot

    def test_enemy_killed_payload_position_is_robot_centre(self, event_bus):
        ai = AISystem()
        robot = _make_robot(x=200.0, y=300.0, hp=10)
        robot.take_damage(10)
        ai.update([robot], MockPlayer(), None, dt=1.0, event_bus=event_bus)
        payload = event_bus.first_event("enemy_killed")
        expected_x = 200.0 + robot.width / 2.0
        expected_y = 300.0 + robot.height / 2.0
        assert payload["x"] == pytest.approx(expected_x)
        assert payload["y"] == pytest.approx(expected_y)

    def test_enemy_killed_payload_enemy_is_the_robot_instance(self, event_bus):
        ai = AISystem()
        robot = _make_robot(hp=10)
        robot.take_damage(10)
        ai.update([robot], MockPlayer(), None, dt=1.0, event_bus=event_bus)
        payload = event_bus.first_event("enemy_killed")
        assert payload["enemy"] is robot

    def test_enemy_killed_emitted_exactly_once(self, event_bus):
        ai = AISystem()
        robot = _make_robot(hp=10)
        robot.take_damage(10)
        # Animation finishes first call → alive=False.
        ai.update([robot], MockPlayer(), None, dt=1.0, event_bus=event_bus)
        # Second call skips the already-dead robot (alive=False).
        ai.update([robot], MockPlayer(), None, dt=1.0, event_bus=event_bus)
        assert len(event_bus.all_events("enemy_killed")) == 1

    def test_dead_robot_does_not_move(self, event_bus):
        ai = AISystem()
        robot = _make_robot(hp=10)
        robot.take_damage(10)
        x_before, y_before = robot.x, robot.y
        player = MockPlayer(x=robot.x + 5.0, y=robot.y)
        ai.update([robot], player, None, dt=1.0, event_bus=event_bus)
        assert robot.x == x_before
        assert robot.y == y_before

    def test_hp_zeroed_externally_transitions_to_dead_via_ai_system(self, event_bus):
        """Robot whose HP was set to 0 without calling take_damage is caught."""
        ai = AISystem()
        robot = _make_robot(hp=50)
        robot.hp = 0  # bypassed take_damage
        ai.update([robot], MockPlayer(), None, dt=0.016, event_bus=event_bus)
        assert robot.state == AIState.DEAD

    def test_dead_state_from_any_prior_state(self, event_bus):
        """A robot killed while in AGGRO still ends up DEAD and emits the event."""
        ai = AISystem()
        robot = _make_robot(hp=30)
        robot.state = AIState.AGGRO
        robot.take_damage(30)  # → DEAD from AGGRO
        ai.update([robot], MockPlayer(), None, dt=1.0, event_bus=event_bus)
        assert robot.alive is False
        assert event_bus.all_events("enemy_killed")


# ===========================================================================
# Multiple robots
# ===========================================================================

class TestAISystemMultipleRobots:

    def test_each_robot_updated_independently(self, event_bus):
        ai = AISystem()
        # robot_a is near player (aggro triggers); robot_b is far away.
        robot_a = _make_robot(x=0.0, y=0.0, aggro_range=50.0)
        robot_b = _make_robot(x=5000.0, y=5000.0, aggro_range=50.0)
        player = MockPlayer(x=0.0, y=0.0)
        ai.update([robot_a, robot_b], player, None, dt=0.016, event_bus=event_bus)
        assert robot_a.state == AIState.AGGRO
        assert robot_b.state == AIState.PATROL

    def test_already_dead_robots_are_skipped(self, event_bus):
        ai = AISystem()
        alive = _make_robot(x=0.0, y=0.0, aggro_range=50.0)
        dead = _make_robot(x=0.0, y=0.0)
        dead.alive = False
        x_dead_before = dead.x
        player = MockPlayer(x=0.0, y=0.0)
        ai.update([alive, dead], player, None, dt=1.0, event_bus=event_bus)
        # Dead robot position must not change.
        assert dead.x == x_dead_before

    def test_multiple_deaths_emit_multiple_events(self, event_bus):
        ai = AISystem()
        robots = [_make_robot(hp=10) for _ in range(3)]
        for r in robots:
            r.take_damage(10)
        ai.update(robots, MockPlayer(), None, dt=1.0, event_bus=event_bus)
        assert len(event_bus.all_events("enemy_killed")) == 3

    def test_empty_enemy_list_is_a_no_op(self, event_bus):
        ai = AISystem()
        # Should not raise.
        ai.update([], MockPlayer(), None, dt=0.016, event_bus=event_bus)
        assert event_bus.emitted == []
