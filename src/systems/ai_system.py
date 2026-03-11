"""AISystem — per-frame FSM driver for all robot enemies.

State transitions
-----------------
PATROL  ──(dist < aggro_range)────────► AGGRO
AGGRO   ──(dist ≤ attack_range)───────► ATTACK
AGGRO   ──(dist > aggro_range ≥ 3 s)──► PATROL
ATTACK  ──(dist > attack_range)───────► AGGRO
any     ──(hp ≤ 0, handled by take_damage)► DEAD
DEAD    ──(animation done)────────────► alive = False; emit enemy_killed

Pathfinding
-----------
While in AGGRO state a BFS path is recomputed every
``PATH_RECALC_INTERVAL`` seconds (or immediately when the path becomes
empty).  Between recalculations the robot advances one tile toward the
goal each frame.  When no tile-map is available the robot moves in a
straight line toward the player.

EventBus payload for ``enemy_killed``
--------------------------------------
::

    {
        "enemy":      RobotEnemy,     # the dead robot instance
        "x":          float,          # world-space centre X
        "y":          float,          # world-space centre Y
        "loot_table": list[dict],     # [{item_id, weight}, …] — for LootSystem
        "xp_reward":  int,            # — for XPSystem
    }
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, List, Optional

from src.entities.robot_enemy import AIState
from src.utils.pathfinding import bfs, cell_to_world, world_to_cell

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.entities.robot_enemy import RobotEnemy

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

#: Seconds the robot waits before returning to PATROL after losing sight.
LOST_PLAYER_TIMEOUT: float = 3.0

#: Minimum seconds between BFS path recalculations.
PATH_RECALC_INTERVAL: float = 0.5

#: Pixel radius within which a robot considers itself "at" a waypoint / cell.
_ARRIVAL_THRESHOLD: float = 4.0

#: Default tile size used when the tile-map is unavailable.
_DEFAULT_TILE_SIZE: int = 32


class AISystem:
    """Drives all :class:`~src.entities.robot_enemy.RobotEnemy` FSMs each frame.

    This class is stateless beyond what is stored on each robot; a single
    instance can therefore be shared across re-used ``GameScene`` instances.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        enemies: List["RobotEnemy"],
        player: object,
        tilemap: object,
        dt: float,
        event_bus: "EventBus",
    ) -> None:
        """Update every robot in *enemies* for one frame.

        Parameters
        ----------
        enemies:
            List managed by ``GameScene``.  Robots are mutated in-place;
            dead robots have ``alive`` set to ``False`` here, ready for
            the purge step that follows in ``GameScene.update``.
        player:
            The active player entity.  Must expose either ``.rect.centerx /
            .rect.centery`` or ``.x / .y / .width / .height``.
        tilemap:
            Current tile-map.  Must expose ``.tile_size: int`` and
            ``.walkability_grid: list[list[int]]``.  May be *None* (direct
            movement is used as a fallback).
        dt:
            Frame delta-time in seconds.
        event_bus:
            Shared :class:`~src.core.event_bus.EventBus` instance.
        """
        px, py = self._player_centre(player)

        for robot in enemies:
            if not robot.alive:
                continue

            # Ensure DEAD state is set if HP was reduced externally.
            if robot.hp <= 0 and robot.state != AIState.DEAD:
                robot.state = AIState.DEAD
                robot._death_timer = 0.0

            ex = robot.x + robot.width / 2.0
            ey = robot.y + robot.height / 2.0
            dist = math.hypot(px - ex, py - ey)

            if robot.state == AIState.PATROL:
                self._update_patrol(robot, dist, dt)

            elif robot.state == AIState.AGGRO:
                self._update_aggro(robot, px, py, dist, tilemap, dt)

            elif robot.state == AIState.ATTACK:
                self._update_attack(robot, player, dist, dt)

            elif robot.state == AIState.DEAD:
                done = robot.advance_animation(dt)
                if done:
                    robot.alive = False
                    event_bus.emit("enemy_killed", {
                        "enemy":      robot,
                        "x":          robot.x + robot.width / 2.0,
                        "y":          robot.y + robot.height / 2.0,
                        "loot_table": robot.loot_table,
                        "xp_reward":  robot.xp_reward,
                    })

    # ------------------------------------------------------------------
    # FSM state handlers (private)
    # ------------------------------------------------------------------

    def _update_patrol(
        self,
        robot: "RobotEnemy",
        dist: float,
        dt: float,
    ) -> None:
        """Walk between patrol waypoints; switch to AGGRO when player is near."""
        if dist < robot.aggro_range:
            robot.state = AIState.AGGRO
            robot.lost_timer = 0.0
            robot.path = []
            robot.path_timer = 0.0
            return

        waypoints = robot.patrol_waypoints
        if not waypoints:
            return

        tx, ty = waypoints[robot.current_waypoint]
        ex = robot.x + robot.width / 2.0
        ey = robot.y + robot.height / 2.0
        to_target = math.hypot(tx - ex, ty - ey)

        if to_target < _ARRIVAL_THRESHOLD:
            robot.current_waypoint = (robot.current_waypoint + 1) % len(waypoints)
        else:
            step = robot.patrol_speed * dt
            ratio = min(step / to_target, 1.0)
            robot.x += (tx - ex) * ratio
            robot.y += (ty - ey) * ratio

    def _update_aggro(
        self,
        robot: "RobotEnemy",
        px: float,
        py: float,
        dist: float,
        tilemap: object,
        dt: float,
    ) -> None:
        """Chase the player using BFS; transition to ATTACK or back to PATROL."""
        if dist <= robot.attack_range:
            robot.state = AIState.ATTACK
            robot.attack_timer = 0.0
            return

        # Track how long we have been unable to see the player.
        if dist > robot.aggro_range:
            robot.lost_timer += dt
            if robot.lost_timer >= LOST_PLAYER_TIMEOUT:
                robot.state = AIState.PATROL
                robot.path = []
                robot.path_timer = 0.0
                return
        else:
            robot.lost_timer = 0.0

        # Periodically (or when the path runs out) recompute the BFS path.
        robot.path_timer += dt
        if robot.path_timer >= PATH_RECALC_INTERVAL or not robot.path:
            robot.path_timer = 0.0
            robot.path = self._compute_path(robot, px, py, tilemap)

        # Move one step along the path (or directly if no path available).
        ex = robot.x + robot.width / 2.0
        ey = robot.y + robot.height / 2.0

        if len(robot.path) > 1:
            tile_size = self._tile_size(tilemap)
            next_cell = robot.path[1]
            nx, ny = cell_to_world(next_cell, tile_size)
            to_next = math.hypot(nx - ex, ny - ey)
            if to_next < _ARRIVAL_THRESHOLD:
                robot.path.pop(0)
            else:
                step = robot.move_speed * dt
                ratio = min(step / to_next, 1.0)
                robot.x += (nx - ex) * ratio
                robot.y += (ny - ey) * ratio
        else:
            # No path or only the starting cell — move directly toward player.
            to_player = math.hypot(px - ex, py - ey)
            if to_player > 1.0:
                step = robot.move_speed * dt
                ratio = min(step / to_player, 1.0)
                robot.x += (px - ex) * ratio
                robot.y += (py - ey) * ratio

    def _update_attack(
        self,
        robot: "RobotEnemy",
        player: object,
        dist: float,
        dt: float,
    ) -> None:
        """Deal damage when cooldown elapsed; revert to AGGRO if player escapes."""
        if dist > robot.attack_range:
            robot.state = AIState.AGGRO
            robot.path = []
            robot.path_timer = 0.0
            return

        robot.attack_timer += dt
        if robot.attack_timer >= robot.attack_cooldown:
            robot.attack_timer = 0.0
            if getattr(player, "alive", True) and hasattr(player, "take_damage"):
                player.take_damage(robot.attack_damage)

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _player_centre(player: object) -> tuple[float, float]:
        """Extract ``(x, y)`` world-space centre from *player*."""
        rect = getattr(player, "rect", None)
        if rect is not None:
            return float(getattr(rect, "centerx", 0)), float(getattr(rect, "centery", 0))
        # Fallback for entities that expose raw x/y/width/height.
        x = float(getattr(player, "x", 0))
        y = float(getattr(player, "y", 0))
        w = float(getattr(player, "width", 0))
        h = float(getattr(player, "height", 0))
        return x + w / 2.0, y + h / 2.0

    @staticmethod
    def _tile_size(tilemap: object) -> int:
        if tilemap is None:
            return _DEFAULT_TILE_SIZE
        return int(getattr(tilemap, "tile_size", _DEFAULT_TILE_SIZE))

    @staticmethod
    def _walkability_grid(tilemap: object) -> list:
        if tilemap is None:
            return []
        return getattr(tilemap, "walkability_grid", [])

    def _compute_path(
        self,
        robot: "RobotEnemy",
        px: float,
        py: float,
        tilemap: object,
    ) -> list:
        tile_size = self._tile_size(tilemap)
        grid = self._walkability_grid(tilemap)
        if not grid:
            return []
        start = world_to_cell(
            (robot.x + robot.width / 2.0, robot.y + robot.height / 2.0),
            tile_size,
        )
        goal = world_to_cell((px, py), tile_size)
        return bfs(grid, start, goal)
