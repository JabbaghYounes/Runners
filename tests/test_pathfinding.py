"""
Unit tests for src.utils.pathfinding
=====================================

All tests are pure-Python — no Pygame or display context required.

Coverage:
- ``world_to_cell``  coordinate conversion (pixel → grid cell)
- ``cell_to_world``  coordinate conversion (grid cell → pixel centre)
- ``bfs``            shortest-path search:
    * happy-path traversal on open grids
    * start == goal edge case
    * blocked start / goal / no-path cases
    * empty and malformed grids
    * path correctness (adjacency, start/goal inclusion)
    * obstacle avoidance
"""
from __future__ import annotations

import pytest

from src.utils.pathfinding import bfs, cell_to_world, world_to_cell


# ---------------------------------------------------------------------------
# Grid factory helpers
# ---------------------------------------------------------------------------

def _open(rows: int, cols: int) -> list[list[int]]:
    """Return a fully-walkable (all-zero) grid."""
    return [[0] * cols for _ in range(rows)]


def _blocked(rows: int, cols: int) -> list[list[int]]:
    """Return a fully-blocked (all-one) grid."""
    return [[1] * cols for _ in range(rows)]


# ===========================================================================
# world_to_cell
# ===========================================================================

class TestWorldToCell:
    """``world_to_cell(world_pos, tile_size) → (col, row)``"""

    def test_origin_maps_to_cell_zero(self):
        assert world_to_cell((0.0, 0.0), 32) == (0, 0)

    def test_tile_aligned_position(self):
        # (64, 96) with tile_size=32 → col=2, row=3
        assert world_to_cell((64.0, 96.0), 32) == (2, 3)

    def test_within_first_tile(self):
        # Anywhere in [0, 32) × [0, 32) is still cell (0, 0)
        assert world_to_cell((15.0, 15.0), 32) == (0, 0)

    def test_exact_tile_boundary_starts_next_cell(self):
        assert world_to_cell((32.0, 32.0), 32) == (1, 1)

    def test_just_before_boundary_stays_in_current_cell(self):
        assert world_to_cell((31.9, 31.9), 32) == (0, 0)

    def test_float_sub_tile_positions(self):
        assert world_to_cell((47.9, 63.9), 32) == (1, 1)

    def test_larger_tile_size(self):
        # tile_size=64: (100, 200) → col=1, row=3
        assert world_to_cell((100.0, 200.0), 64) == (1, 3)

    def test_x_and_y_axes_are_independent(self):
        col, row = world_to_cell((96.0, 32.0), 32)
        assert col == 3
        assert row == 1


# ===========================================================================
# cell_to_world
# ===========================================================================

class TestCellToWorld:
    """``cell_to_world(cell, tile_size) → (centre_x, centre_y)``"""

    def test_origin_cell_returns_half_tile_centre(self):
        x, y = cell_to_world((0, 0), 32)
        assert x == 16.0
        assert y == 16.0

    def test_cell_one_one(self):
        x, y = cell_to_world((1, 1), 32)
        assert x == 48.0
        assert y == 48.0

    def test_asymmetric_col_row(self):
        x, y = cell_to_world((3, 2), 32)
        assert x == 3 * 32 + 16.0
        assert y == 2 * 32 + 16.0

    def test_different_tile_size(self):
        x, y = cell_to_world((1, 0), 64)
        assert x == 96.0
        assert y == 32.0

    def test_result_is_always_cell_centre(self):
        tile = 32
        for col in range(5):
            for row in range(5):
                x, y = cell_to_world((col, row), tile)
                assert x == col * tile + tile / 2.0
                assert y == row * tile + tile / 2.0

    def test_round_trip_with_world_to_cell(self):
        """cell → world centre → cell should be identity."""
        tile = 32
        for col in range(6):
            for row in range(6):
                wx, wy = cell_to_world((col, row), tile)
                assert world_to_cell((wx, wy), tile) == (col, row)


# ===========================================================================
# BFS — basic correctness
# ===========================================================================

class TestBFSBasic:
    """Happy-path BFS traversal."""

    def test_start_equals_goal_returns_single_element_list(self):
        grid = _open(5, 5)
        assert bfs(grid, (2, 2), (2, 2)) == [(2, 2)]

    def test_horizontal_straight_path(self):
        grid = _open(3, 5)
        path = bfs(grid, (0, 1), (4, 1))
        assert path[0] == (0, 1)
        assert path[-1] == (4, 1)
        assert len(path) == 5

    def test_vertical_straight_path(self):
        grid = _open(5, 3)
        path = bfs(grid, (1, 0), (1, 4))
        assert path[0] == (1, 0)
        assert path[-1] == (1, 4)
        assert len(path) == 5

    def test_diagonal_shortest_path_length(self):
        # 5×5 open grid, corner to corner.  Manhattan dist = 8, so 9 cells.
        grid = _open(5, 5)
        path = bfs(grid, (0, 0), (4, 4))
        assert len(path) == 9

    def test_path_always_includes_start(self):
        grid = _open(4, 4)
        path = bfs(grid, (0, 0), (3, 3))
        assert path[0] == (0, 0)

    def test_path_always_includes_goal(self):
        grid = _open(4, 4)
        path = bfs(grid, (0, 0), (3, 3))
        assert path[-1] == (3, 3)

    def test_all_steps_are_single_tile_moves(self):
        """Consecutive cells in the path must be 4-directional neighbours."""
        grid = _open(5, 5)
        path = bfs(grid, (0, 0), (4, 4))
        for (c1, r1), (c2, r2) in zip(path, path[1:]):
            assert abs(c1 - c2) + abs(r1 - r2) == 1

    def test_all_cells_in_path_are_walkable(self):
        grid = _open(5, 5)
        path = bfs(grid, (0, 0), (4, 4))
        for col, row in path:
            assert grid[row][col] == 0

    def test_single_cell_grid_start_equals_goal(self):
        grid = [[0]]
        assert bfs(grid, (0, 0), (0, 0)) == [(0, 0)]

    def test_path_not_duplicated_in_reverse(self):
        grid = _open(3, 3)
        path_ab = bfs(grid, (0, 0), (2, 2))
        # Both directions should yield the same length.
        path_ba = bfs(grid, (2, 2), (0, 0))
        assert len(path_ab) == len(path_ba)


# ===========================================================================
# BFS — blocked / no-path cases
# ===========================================================================

class TestBFSBlocked:

    def test_blocked_start_returns_empty(self):
        grid = _open(5, 5)
        grid[0][0] = 1  # block start cell (col=0, row=0)
        assert bfs(grid, (0, 0), (4, 4)) == []

    def test_blocked_goal_returns_empty(self):
        grid = _open(5, 5)
        grid[4][4] = 1  # block goal cell (col=4, row=4)
        assert bfs(grid, (0, 0), (4, 4)) == []

    def test_vertical_wall_cuts_off_goal(self):
        # Block entire column 2 → no path from left to right.
        grid = _open(5, 5)
        for row in range(5):
            grid[row][2] = 1
        assert bfs(grid, (0, 2), (4, 2)) == []

    def test_horizontal_wall_cuts_off_goal(self):
        # Block entire row 2 → no path from top to bottom.
        grid = _open(5, 5)
        for col in range(5):
            grid[2][col] = 1
        assert bfs(grid, (2, 0), (2, 4)) == []

    def test_fully_blocked_grid_returns_empty(self):
        assert bfs(_blocked(4, 4), (0, 0), (3, 3)) == []

    def test_empty_grid_returns_empty(self):
        assert bfs([], (0, 0), (1, 1)) == []

    def test_grid_with_empty_rows_returns_empty(self):
        assert bfs([[]], (0, 0), (1, 0)) == []

    def test_out_of_bounds_start_returns_empty(self):
        grid = _open(3, 3)
        assert bfs(grid, (10, 10), (0, 0)) == []

    def test_out_of_bounds_goal_returns_empty(self):
        grid = _open(3, 3)
        assert bfs(grid, (0, 0), (10, 10)) == []

    def test_negative_start_col_returns_empty(self):
        grid = _open(3, 3)
        assert bfs(grid, (-1, 0), (2, 2)) == []

    def test_negative_start_row_returns_empty(self):
        grid = _open(3, 3)
        assert bfs(grid, (0, -1), (2, 2)) == []

    def test_isolated_start_cell_returns_empty(self):
        # Start cell is walkable but entirely surrounded by blocked cells.
        grid = _open(3, 3)
        grid[0][1] = 1  # above
        grid[1][0] = 1  # left
        grid[1][2] = 1  # right
        grid[2][1] = 1  # below
        # Start=(1,1) is open, goal=(0,0) is reachable only via blocked cells.
        assert bfs(grid, (1, 1), (0, 0)) == []


# ===========================================================================
# BFS — obstacle avoidance
# ===========================================================================

class TestBFSObstacleAvoidance:

    def test_path_goes_around_single_blocked_cell(self):
        # 2-row corridor; block (col=2, row=0) — path must dip to row 1.
        #   . . X . .
        #   . . . . .
        grid = _open(2, 5)
        grid[0][2] = 1
        path = bfs(grid, (0, 0), (4, 0))
        assert path is not None and len(path) > 0
        assert path[0] == (0, 0)
        assert path[-1] == (4, 0)
        for col, row in path:
            assert grid[row][col] == 0

    def test_path_avoids_l_shaped_obstacle(self):
        grid = _open(5, 5)
        # L-shaped wall
        for col in (1, 2, 3):
            grid[2][col] = 1
        grid[3][1] = 1
        path = bfs(grid, (0, 0), (4, 4))
        assert path[-1] == (4, 4)
        for col, row in path:
            assert grid[row][col] == 0

    def test_single_gap_in_wall_is_used(self):
        # Full vertical wall except for one gap in the middle row.
        grid = _open(5, 5)
        for row in range(5):
            grid[row][2] = 1
        grid[2][2] = 0  # open the gap at row 2
        path = bfs(grid, (0, 2), (4, 2))
        assert path[-1] == (4, 2)
        for col, row in path:
            assert grid[row][col] == 0

    def test_path_through_maze_is_valid(self):
        # Manually constructed 5×5 maze with one valid route.
        # 0 = walkable, 1 = wall
        grid = [
            [0, 1, 0, 0, 0],
            [0, 1, 0, 1, 0],
            [0, 0, 0, 1, 0],
            [1, 1, 0, 0, 0],
            [0, 0, 0, 1, 0],
        ]
        path = bfs(grid, (0, 0), (4, 4))
        assert len(path) > 0
        assert path[0] == (0, 0)
        assert path[-1] == (4, 4)
        for col, row in path:
            assert grid[row][col] == 0

    def test_dead_end_maze_returns_empty(self):
        # Goal cell (3, 3) is walkable but all four of its neighbours are
        # blocked, so no path can reach it from the open left section.
        grid = [
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 1, 1, 1],
            [0, 0, 1, 0, 1],
            [0, 0, 1, 1, 1],
        ]
        assert bfs(grid, (0, 0), (3, 3)) == []
