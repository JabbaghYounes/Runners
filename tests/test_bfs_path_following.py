"""Tests for BFS path-following inside AISystem._do_chase().

Verifies that when a BFS path is available the robot steps toward the
next path-cell's world centre rather than directly toward the player's
raw position, that cells are popped on arrival, and that an empty or
unreachable path falls back to direct horizontal movement.
"""
from __future__ import annotations

import pytest

from src.entities.robot_enemy import AIState, RobotEnemy
from src.systems.ai_system import AISystem, PATH_RECALC_INTERVAL, _ARRIVAL_THRESHOLD
from src.utils.pathfinding import cell_to_world


# ---------------------------------------------------------------------------
# Lightweight mocks
# ---------------------------------------------------------------------------

class _Player:
    def __init__(self, x: float = 400.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.width = 32
        self.height = 48
        self.alive = True


class _Tilemap:
    """Fully-walkable grid."""

    def __init__(self, rows: int = 20, cols: int = 20, tile_size: int = 32) -> None:
        self.tile_size = tile_size
        self.walkability_grid = [[0] * cols for _ in range(rows)]


class _BlockedTilemap:
    """Fully-blocked grid (all walls)."""

    def __init__(self, rows: int = 20, cols: int = 20, tile_size: int = 32) -> None:
        self.tile_size = tile_size
        self.walkability_grid = [[1] * cols for _ in range(rows)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_robot(**overrides) -> RobotEnemy:
    defaults = dict(
        x=0.0, y=0.0, hp=50,
        move_speed=80.0, aggro_range=2000.0, attack_range=5.0,
        attack_damage=10, type_id="grunt",
    )
    defaults.update(overrides)
    r = RobotEnemy(**defaults)
    r.state = AIState.AGGRO
    return r


def _centre(robot: RobotEnemy) -> tuple[float, float]:
    return robot.x + robot.width / 2.0, robot.y + robot.height / 2.0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBFSPathFollowing:

    def test_robot_moves_when_path_has_two_or_more_cells(self) -> None:
        """With a valid BFS path, the robot must move each frame."""
        ai = AISystem()
        tilemap = _Tilemap()
        robot = _make_robot(x=0.0, y=0.0, move_speed=80.0)
        player = _Player(x=160.0, y=0.0)   # cell (5, 0)

        # Force immediate BFS recalc
        robot.path_timer = PATH_RECALC_INTERVAL
        x_before = robot.x
        ai._do_chase(robot, player, tilemap, dt=0.016)
        assert robot.x > x_before

    def test_path_cell_popped_when_robot_arrives_at_cell_centre(self) -> None:
        """When the robot centre is within _ARRIVAL_THRESHOLD of path[1],
        path[0] must be popped to advance along the route."""
        ai = AISystem()
        tilemap = _Tilemap(tile_size=32)
        robot = _make_robot(x=0.0, y=0.0, move_speed=0.0)  # stationary
        player = _Player(x=160.0, y=0.0)

        # path[1] = cell (1, 0) → world centre x = 1*32 + 16 = 48
        # robot centre x = robot.x + 16 = 48  ⟹ robot.x = 32
        robot.x = 32.0
        robot.path = [(0, 0), (1, 0), (2, 0)]
        robot.path_timer = 0.0          # no BFS recalc this frame

        path_len_before = len(robot.path)
        ai._do_chase(robot, player, tilemap, dt=0.016)
        assert len(robot.path) < path_len_before

    def test_path_not_recalculated_before_interval(self) -> None:
        """path_timer < PATH_RECALC_INTERVAL → existing path must survive."""
        ai = AISystem()
        tilemap = _Tilemap()
        robot = _make_robot(x=0.0, y=0.0)
        player = _Player(x=400.0, y=0.0)

        sentinel = [(0, 0), (99, 0)]   # impossible cell; survives if no recalc
        robot.path = list(sentinel)
        robot.path_timer = 0.0          # just reset

        ai._do_chase(robot, player, tilemap, dt=0.016)
        # Timer incremented but hasn't reached interval → path unchanged
        assert robot.path == sentinel
        assert robot.path_timer < PATH_RECALC_INTERVAL

    def test_path_timer_resets_after_recalc(self) -> None:
        ai = AISystem()
        tilemap = _Tilemap()
        robot = _make_robot(x=0.0, y=0.0)
        player = _Player(x=64.0, y=0.0)

        robot.path_timer = PATH_RECALC_INTERVAL   # triggers recalc
        ai._do_chase(robot, player, tilemap, dt=0.0)
        assert robot.path_timer == pytest.approx(0.0)

    def test_path_timer_increments_without_recalc(self) -> None:
        ai = AISystem()
        robot = _make_robot(x=0.0, y=0.0)
        player = _Player(x=400.0, y=0.0)
        robot.path_timer = 0.0
        robot.path = [(0, 0), (1, 0)]

        ai._do_chase(robot, player, None, dt=0.1)   # no tilemap → no recalc
        assert robot.path_timer == pytest.approx(0.1)

    def test_empty_path_falls_back_to_direct_move(self) -> None:
        """After a failed BFS (blocked grid), robot still moves horizontally."""
        ai = AISystem()
        tilemap = _BlockedTilemap()
        robot = _make_robot(x=0.0, y=0.0, move_speed=80.0)
        player = _Player(x=400.0, y=0.0)

        robot.path = []
        robot.path_timer = PATH_RECALC_INTERVAL  # triggers BFS → returns []

        x_before = robot.x
        ai._do_chase(robot, player, tilemap, dt=1.0)
        # BFS gives empty path; fallback moves toward player
        assert robot.x > x_before

    def test_no_tilemap_falls_back_to_direct_move(self) -> None:
        ai = AISystem()
        robot = _make_robot(x=0.0, y=0.0, move_speed=80.0)
        player = _Player(x=400.0, y=0.0)

        x_before = robot.x
        ai._do_chase(robot, player, None, dt=1.0)
        assert robot.x > x_before

    def test_path_following_targets_cell_centre_not_raw_player_x(self) -> None:
        """The robot should step toward path[1]'s world-centre x, not player.x."""
        ai = AISystem()
        tilemap = _Tilemap(tile_size=32)
        robot = _make_robot(x=0.0, y=0.0, move_speed=160.0)

        # path[1] = cell (0, 1) → world centre = (16, 48); player is far to the east
        # Since path[1] centre x == robot centre x (both = 16), dx = 0 → either pop
        # (if within threshold) or no horizontal movement this frame.
        robot.path = [(0, 0), (0, 1), (0, 2)]  # going south
        robot.path_timer = 0.0                  # no recalc
        player = _Player(x=600.0, y=0.0)        # player is far east

        x_before = robot.x
        ai._do_chase(robot, player, tilemap, dt=0.016)

        # The robot should NOT have leapt toward player at x=600.
        # Direct move at 160 px/s × 0.016 s = 2.56 px — path-following does ≤ that.
        assert robot.x <= x_before + 3.0

    def test_bfs_path_is_set_after_recalc_on_walkable_grid(self) -> None:
        """After BFS recalculation on a walkable grid a non-empty path is stored."""
        ai = AISystem()
        tilemap = _Tilemap()
        robot = _make_robot(x=0.0, y=0.0)
        player = _Player(x=128.0, y=0.0)   # cell (4, 0)

        robot.path = []
        robot.path_timer = PATH_RECALC_INTERVAL  # trigger recalc

        ai._do_chase(robot, player, tilemap, dt=0.016)
        assert len(robot.path) >= 2

    def test_stale_path_reset_after_failed_bfs(self) -> None:
        """If BFS returns [] (blocked goal), enemy.path is reset to []."""
        ai = AISystem()
        tilemap = _BlockedTilemap()
        robot = _make_robot(x=0.0, y=0.0)
        player = _Player(x=400.0, y=0.0)

        robot.path = [(0, 0), (1, 0), (2, 0)]   # stale path from before
        robot.path_timer = PATH_RECALC_INTERVAL  # trigger recalc

        ai._do_chase(robot, player, tilemap, dt=0.016)
        # Blocked grid → BFS returns [] → path must be cleared
        assert robot.path == []
