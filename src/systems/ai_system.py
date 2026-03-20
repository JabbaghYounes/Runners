"""AI System -- drives the four-state FSM for robot enemies and PvP bots.

State machine: PATROL -> AGGRO -> ATTACK -> DEAD

Exported constants used by tests:
    LOST_PLAYER_TIMEOUT  -- seconds the robot stays in AGGRO after losing sight
    PATH_RECALC_INTERVAL -- seconds between BFS path recalculations
"""
from __future__ import annotations

import math
from typing import List, Any, Optional, TYPE_CHECKING

from src.constants import PVP_LOOT_DETECT_RANGE
from src.entities.robot_enemy import AIState, RobotEnemy
from src.utils.pathfinding import world_to_cell, cell_to_world, bfs

if TYPE_CHECKING:
    from src.entities.player_agent import PlayerAgent
    from src.systems.weapon_system import WeaponSystem as _WeaponSystemType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LOST_PLAYER_TIMEOUT: float = 5.0
PATH_RECALC_INTERVAL: float = 0.5
_ARRIVAL_THRESHOLD: float = 4.0   # px distance to consider "arrived" at waypoint
_DEATH_ANIM_DURATION: float = 0.6  # seconds for death animation before alive=False


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def _centre_of(obj: Any) -> tuple[float, float]:
    """Return world-space centre of an object with x/y/width/height."""
    return obj.x + obj.width / 2.0, obj.y + obj.height / 2.0


class AISystem:
    """Drives all robot enemies each frame."""

    def update(
        self,
        enemies: List[RobotEnemy],
        player: Any,
        tilemap: Any,
        dt: float,
        event_bus: Any,
    ) -> None:
        for enemy in enemies:
            if not enemy.alive:
                continue
            self._update_one(enemy, player, tilemap, dt, event_bus)

    # ------------------------------------------------------------------
    # Per-enemy update
    # ------------------------------------------------------------------

    def _update_one(
        self,
        enemy: RobotEnemy,
        player: Any,
        tilemap: Any,
        dt: float,
        bus: Any,
    ) -> None:
        ecx, ecy = _centre_of(enemy)
        pcx, pcy = _centre_of(player)
        dist = _dist(ecx, ecy, pcx, pcy)

        # -- DEAD state: run death animation then mark alive=False -----------
        if enemy.state == AIState.DEAD:
            enemy._death_timer += dt
            if enemy._death_timer >= _DEATH_ANIM_DURATION:
                if not enemy._death_event_emitted:
                    enemy.alive = False
                    enemy._death_event_emitted = True
                    bus.emit(
                        "enemy_killed",
                        enemy=enemy,
                        x=ecx,
                        y=ecy,
                        loot_table=enemy.loot_table,
                        xp_reward=enemy.xp_reward,
                    )
            return  # Do not move or transition when dead

        # -- HP check: catch external HP zeroing (bypassed take_damage) ------
        if enemy.hp <= 0 and enemy.state != AIState.DEAD:
            enemy.state = AIState.DEAD
            enemy.ai_state = AIState.DEAD
            enemy._death_timer = 0.0
            return

        # -- PATROL ----------------------------------------------------------
        if enemy.state == AIState.PATROL:
            if dist <= enemy.aggro_range:
                enemy.state = AIState.AGGRO
                enemy.ai_state = AIState.AGGRO
                enemy.lost_timer = 0.0
                enemy.path = []
            else:
                self._do_patrol(enemy, dt)

        # -- AGGRO -----------------------------------------------------------
        elif enemy.state == AIState.AGGRO:
            if dist <= enemy.attack_range:
                enemy.state = AIState.ATTACK
                enemy.ai_state = AIState.ATTACK
                enemy.attack_timer = 0.0
            elif dist > enemy.aggro_range:
                # Player left aggro range -- start lost timer
                enemy.lost_timer += dt
                if enemy.lost_timer >= LOST_PLAYER_TIMEOUT:
                    enemy.state = AIState.PATROL
                    enemy.ai_state = AIState.PATROL
                    enemy.path = []
            else:
                # Player still within aggro range -- reset lost timer
                enemy.lost_timer = 0.0

            if enemy.state == AIState.AGGRO:
                self._do_chase(enemy, player, tilemap, dt)

        # -- ATTACK ----------------------------------------------------------
        elif enemy.state == AIState.ATTACK:
            if dist > enemy.attack_range:
                enemy.state = AIState.AGGRO
                enemy.ai_state = AIState.AGGRO
                enemy.path = []
            else:
                self._do_attack(enemy, player, dt, bus)

    # ------------------------------------------------------------------
    # State execution
    # ------------------------------------------------------------------

    def _do_patrol(self, enemy: RobotEnemy, dt: float) -> None:
        if not enemy.patrol_waypoints:
            return
        wp = enemy.patrol_waypoints[enemy.current_waypoint % len(enemy.patrol_waypoints)]
        ecx, ecy = _centre_of(enemy)
        dx = wp[0] - ecx
        dy = wp[1] - ecy
        dist_to_wp = math.hypot(dx, dy)

        if dist_to_wp < _ARRIVAL_THRESHOLD:
            enemy.current_waypoint = (enemy.current_waypoint + 1) % len(enemy.patrol_waypoints)
            enemy._wp_index = enemy.current_waypoint
        else:
            direction = 1.0 if dx > 0 else -1.0
            enemy.x += direction * enemy.patrol_speed * dt

    def _do_chase(
        self,
        enemy: RobotEnemy,
        player: Any,
        tilemap: Any,
        dt: float,
    ) -> None:
        # Path recalculation timer
        enemy.path_timer += dt

        if tilemap is not None and enemy.path_timer >= PATH_RECALC_INTERVAL:
            enemy.path_timer = 0.0
            try:
                ts = tilemap.tile_size
                start = world_to_cell(enemy.x, enemy.y, ts)
                goal = world_to_cell(player.x, player.y, ts)
                path = bfs(tilemap.walkability_grid, start, goal)
                enemy.path = path if path else []
            except Exception:
                enemy.path = []

        # Move toward player (direct approach if no tilemap or empty path)
        ecx, ecy = _centre_of(enemy)
        pcx, pcy = _centre_of(player)
        dx = pcx - ecx
        dist_h = abs(dx)
        if dist_h > 1.0:
            direction = 1.0 if dx > 0 else -1.0
            enemy.x += direction * enemy.move_speed * dt

    def _do_attack(
        self,
        enemy: RobotEnemy,
        player: Any,
        dt: float,
        bus: Any,
    ) -> None:
        enemy.attack_timer += dt
        if enemy.attack_timer >= enemy.attack_cooldown:
            enemy.attack_timer = 0.0
            if getattr(player, "alive", True) and hasattr(player, "take_damage"):
                player.take_damage(enemy.attack_damage)
                bus.emit("player.damaged", amount=enemy.attack_damage)

    # ==================================================================
    # PvP bot FSM  (PlayerAgent entities)
    # ==================================================================

    def update_bots(
        self,
        bots: "List[Any]",
        player: Any,
        loot_drops: list,
        tilemap: Any,
        dt: float,
        event_bus: Any,
        combat_system: Any,
    ) -> None:
        """Drive the PvP bot FSM for all PlayerAgent instances."""
        for bot in bots:
            # Skip bots that are fully dead and already processed
            if not bot.alive and bot.ai_state != AIState.DEAD:
                continue
            self._update_one_bot(bot, player, loot_drops, tilemap, dt, event_bus, combat_system)

    # ------------------------------------------------------------------
    # Per-bot update
    # ------------------------------------------------------------------

    def _update_one_bot(
        self,
        bot: Any,
        player: Any,
        loot_drops: list,
        tilemap: Any,
        dt: float,
        bus: Any,
        combat: Any,
    ) -> None:
        bcx, bcy = _centre_of(bot)
        pcx, pcy = _centre_of(player)
        dist = _dist(bcx, bcy, pcx, pcy)

        # -- DEAD: run animation, then emit player_killed once -----------
        if bot.ai_state == AIState.DEAD:
            bot._death_timer += dt
            if bot._death_timer >= _DEATH_ANIM_DURATION and not bot._death_event_emitted:
                bot._death_event_emitted = True
                bot.alive = False
                bus.emit(
                    "player_killed",
                    victim=bot,
                    killer=getattr(bot, "_killer", None),
                    x=bcx,
                    y=bcy,
                )
            return

        # -- HP check ----------------------------------------------------
        if bot.health <= 0:
            bot.ai_state = AIState.DEAD
            bot._death_timer = 0.0
            return

        # -- PATROL ------------------------------------------------------
        if bot.ai_state == AIState.PATROL:
            # Loot pickup
            for loot in loot_drops:
                if not getattr(loot, "alive", False):
                    continue
                lx = getattr(loot.rect, "centerx", loot.x)
                ly = getattr(loot.rect, "centery", loot.y)
                if _dist(bcx, bcy, lx, ly) <= PVP_LOOT_DETECT_RANGE:
                    loot.alive = False
                    bus.emit("item_picked_up", bot=bot, item=loot.item)

            if dist <= bot.aggro_range:
                bot.ai_state = AIState.AGGRO
                bot.lost_timer = 0.0
                bot.path = []
            else:
                self._do_bot_patrol(bot, dt)

        # -- AGGRO -------------------------------------------------------
        elif bot.ai_state == AIState.AGGRO:
            if dist <= bot.attack_range:
                bot.ai_state = AIState.ATTACK
            elif dist > bot.aggro_range:
                bot.lost_timer += dt
                if bot.lost_timer >= LOST_PLAYER_TIMEOUT:
                    bot.ai_state = AIState.PATROL
                    bot.path = []
            else:
                bot.lost_timer = 0.0

            if bot.ai_state == AIState.AGGRO:
                self._do_chase(bot, player, tilemap, dt)

        # -- ATTACK ------------------------------------------------------
        elif bot.ai_state == AIState.ATTACK:
            if dist > bot.attack_range:
                bot.ai_state = AIState.AGGRO
                bot.path = []
            else:
                self._tick_weapon_state(bot, dt)
                self._bot_fire(bot, player, combat)

    # ------------------------------------------------------------------
    # Bot-specific state helpers
    # ------------------------------------------------------------------

    def _do_bot_patrol(self, bot: Any, dt: float) -> None:
        """Move bot toward its current patrol waypoint; advance index on arrival."""
        if not bot.patrol_waypoints:
            return
        idx = bot._waypoint_idx % len(bot.patrol_waypoints)
        wp = bot.patrol_waypoints[idx]
        bcx, bcy = _centre_of(bot)
        dx = wp[0] - bcx
        dy = wp[1] - bcy
        dist_to_wp = math.hypot(dx, dy)
        if dist_to_wp < _ARRIVAL_THRESHOLD:
            bot._waypoint_idx = (idx + 1) % len(bot.patrol_waypoints)
        else:
            direction = 1.0 if dx > 0 else -1.0
            bot.target_vx = direction * bot.patrol_speed
            bot.x += direction * bot.patrol_speed * dt

    def _tick_weapon_state(self, bot: Any, dt: float) -> None:
        """Advance fire-cooldown and reload timers on the bot's weapon state."""
        ws = bot.weapon_state
        if ws is None:
            return
        if ws.fire_cooldown > 0:
            ws.fire_cooldown = max(0.0, ws.fire_cooldown - dt)
        if ws.reloading:
            ws.reload_timer -= dt
            if ws.reload_timer <= 0:
                ws.reloading = False
                ws.reload_timer = 0.0
                ws.ammo = ws.magazine_size
                ws.fire_cooldown = ws.fire_interval

    def _bot_fire(self, bot: Any, player: Any, combat: Any) -> None:
        """Attempt to fire at the player; start reload if magazine is empty."""
        ws = bot.weapon_state
        if ws is None:
            return
        if ws.needs_reload:
            ws.reloading = True
            ws.reload_timer = ws.reload_time
            return
        if not ws.can_fire:
            return
        pcx, pcy = _centre_of(player)
        combat.fire(bot, pcx, pcy)
        ws.ammo -= 1
        ws.fire_cooldown = ws.fire_interval
        if ws.ammo <= 0 and not ws.reloading:
            ws.reloading = True
            ws.reload_timer = ws.reload_time
