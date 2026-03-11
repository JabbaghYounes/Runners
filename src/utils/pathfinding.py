"""BFS pathfinding over a 2-D tile walkability grid.

Grid convention
---------------
``grid[row][col] == 0``  → walkable tile
``grid[row][col] != 0``  → blocked tile

Cell coordinates are ``(col, row)`` tuples (x, y order) to keep them
consistent with world-space coordinates.
"""
from __future__ import annotations

from collections import deque
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def world_to_cell(world_pos: Tuple[float, float], tile_size: int) -> Tuple[int, int]:
    """Convert a world-space pixel position to a grid ``(col, row)`` cell."""
    x, y = world_pos
    return (int(x // tile_size), int(y // tile_size))


def cell_to_world(cell: Tuple[int, int], tile_size: int) -> Tuple[float, float]:
    """Return the centre of *cell* in world-space pixels."""
    col, row = cell
    half = tile_size / 2.0
    return (col * tile_size + half, row * tile_size + half)


# ---------------------------------------------------------------------------
# Pathfinding
# ---------------------------------------------------------------------------

def bfs(
    grid: List[List[int]],
    start: Tuple[int, int],
    goal: Tuple[int, int],
) -> List[Tuple[int, int]]:
    """Find the shortest path from *start* to *goal* using BFS.

    Parameters
    ----------
    grid:
        2-D list indexed as ``grid[row][col]``.  Zero means walkable.
    start:
        ``(col, row)`` origin cell.
    goal:
        ``(col, row)`` destination cell.

    Returns
    -------
    list[tuple[int, int]]
        Ordered list of cells from *start* to *goal* (both inclusive).
        Returns an empty list when no path exists, when *start* or *goal*
        is blocked, or when the grid is empty.
    """
    if not grid or not grid[0]:
        return []

    rows = len(grid)
    cols = len(grid[0])

    def _walkable(col: int, row: int) -> bool:
        return 0 <= col < cols and 0 <= row < rows and grid[row][col] == 0

    if not _walkable(*start) or not _walkable(*goal):
        return []

    if start == goal:
        return [start]

    visited: set[Tuple[int, int]] = {start}
    parent: dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
    queue: deque[Tuple[int, int]] = deque([start])

    _neighbours = ((0, -1), (0, 1), (-1, 0), (1, 0))

    while queue:
        current = queue.popleft()
        if current == goal:
            # Reconstruct path from goal back to start.
            path: List[Tuple[int, int]] = []
            node: Optional[Tuple[int, int]] = goal
            while node is not None:
                path.append(node)
                node = parent[node]
            path.reverse()
            return path

        col, row = current
        for dc, dr in _neighbours:
            nb = (col + dc, row + dr)
            if nb not in visited and _walkable(*nb):
                visited.add(nb)
                parent[nb] = current
                queue.append(nb)

    return []  # No path found.
