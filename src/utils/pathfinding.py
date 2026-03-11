from collections import deque
from typing import List, Tuple, Optional

def world_to_cell(wx_or_pos, wy_or_ts=None, tile_size: int = None) -> Tuple[int, int]:
    """Convert world coordinates to cell. Supports:
    - world_to_cell(wx, wy, tile_size)
    - world_to_cell((wx, wy), tile_size)
    """
    if isinstance(wx_or_pos, (tuple, list)):
        wx, wy = wx_or_pos[0], wx_or_pos[1]
        ts = wy_or_ts if wy_or_ts is not None else tile_size
    else:
        wx = wx_or_pos
        wy = wy_or_ts
        ts = tile_size
    return (int(wx // ts), int(wy // ts))

def cell_to_world(col_or_cell, row_or_ts=None, tile_size: int = None) -> Tuple[float, float]:
    """Convert cell to world center. Supports:
    - cell_to_world(col, row, tile_size)
    - cell_to_world((col, row), tile_size)
    """
    if isinstance(col_or_cell, (tuple, list)):
        col, row = col_or_cell[0], col_or_cell[1]
        ts = row_or_ts if row_or_ts is not None else tile_size
    else:
        col = col_or_cell
        row = row_or_ts
        ts = tile_size
    return (col * ts + ts / 2, row * ts + ts / 2)

def _walkable(grid: List[List[int]], col: int, row: int) -> bool:
    if row < 0 or row >= len(grid):
        return False
    if col < 0 or col >= len(grid[0]):
        return False
    return grid[row][col] == 0

def bfs(grid: List[List[int]], start_cell: Tuple[int, int],
        goal_cell: Tuple[int, int]) -> List[Tuple[int, int]]:
    if not grid or not grid[0]:
        return []
    if not _walkable(grid, start_cell[0], start_cell[1]):
        return []
    if not _walkable(grid, goal_cell[0], goal_cell[1]):
        return []
    if start_cell == goal_cell:
        return [start_cell]
    queue = deque()
    queue.append(start_cell)
    came_from = {start_cell: None}
    DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    while queue:
        current = queue.popleft()
        if current == goal_cell:
            # Reconstruct path
            path = []
            node = goal_cell
            while node is not None:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return path
        col, row = current
        for dc, dr in DIRS:
            nc, nr = col + dc, row + dr
            neighbor = (nc, nr)
            if neighbor not in came_from and _walkable(grid, nc, nr):
                came_from[neighbor] = current
                queue.append(neighbor)
    return []
