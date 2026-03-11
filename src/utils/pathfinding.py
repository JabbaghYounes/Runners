from collections import deque
from typing import List, Tuple, Optional

def world_to_cell(wx: float, wy: float, tile_size: int) -> Tuple[int, int]:
    return (int(wx // tile_size), int(wy // tile_size))

def cell_to_world(col: int, row: int, tile_size: int) -> Tuple[float, float]:
    return (col * tile_size + tile_size / 2, row * tile_size + tile_size / 2)

def _walkable(grid: List[List[int]], col: int, row: int) -> bool:
    if row < 0 or row >= len(grid):
        return False
    if col < 0 or col >= len(grid[0]):
        return False
    return grid[row][col] == 1

def bfs(grid: List[List[int]], start_cell: Tuple[int, int],
        goal_cell: Tuple[int, int]) -> List[Tuple[int, int]]:
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
