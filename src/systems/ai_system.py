"""AI System -- drives the four-state FSM for robot enemies and PvP bots.

State machine: PATROL -> AGGRO -> ATTACK -> DEAD

Public API
----------
``AISystem.update()`` now accepts an optional ``combat_system`` argument and
returns ``List[Projectile]`` — the projectiles fired by enemies this frame.
Pass the same ``CombatSystem`` instance used for player shots so robot
projectiles travel through the shared physics/collision pipeline.

When ``combat_system=None`` (default), ``_do_attack()`` falls back to calling
``player.take_damage()`` directly.  This preserves every existing unit-test
contract: tests that do not pass a combat system continue to work unchanged.

Coordinate contract
-------------------
``PhysicsSystem`` resolves gravity/collision by writing ``entity.rect``.
``RobotEnemy.x`` / ``.y`` are properties backed by float fields; after
``PhysicsSystem`` runs, call ``enemy.update(dt)`` (``sync_from_rect``) before
calling ``AISystem.update()`` so the AI reads physics-resolved coordinates.

Exported constants used by tests:
    LOST_PLAYER_TIMEOUT  -- seconds the robot stays in AGGRO after losing sight
    PATH_RECALC_INTERVAL -- seconds between BFS path recalculations
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, List, Optional

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
_ARRIVAL_THRESHOLD: float = 4.0   # px — considered "arrived" at a path cell
_DEATH_ANIM_DURATION: float = 0.6  # seconds for death animation before alive=False


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def _centre_of(obj: Any) -> tuple[float, float]:
    """Return world-space centre of an object with x/y/width/height."""
    return obj.x + obj.width / 2.0, obj.y + obj.height / 2.0


class AISystem:
    """Drives all robot enemies each frame.

    ``update()`` returns the list of ``Projectile`` objects created this frame
    by enemy ATTACK actions (so the caller can add them to the shared projectile
    list and let ``CombatSystem`` resolve collisions on subsequent frames).
    """

    def update_bots(
        self,
        bots: List[Any],
        player: Any,
        loot_items: List[Any],
        tilemap: Any,
        dt: float,
        event_bus: Any,
        combat_system: Any = None,
    ) -> List[Any]:
        """Update all PvP bot agents using a PlayerAgent-aware FSM.

        Uses ``_update_bot_one`` which reads ``health``/``_waypoint_idx``
        (PlayerAgent fields) instead of the RobotEnemy fields expected by
        ``_update_one``.

        Returns projectiles fired by bots this frame.
        """
        result: List[Any] = []
        for bot in bots:
            ai_state = getattr(bot, "ai_state", None)
            # Skip bots that are externally marked dead but not in DEAD state
            if not getattr(bot, "alive", True) and ai_state != AIState.DEAD:
                continue
            # Skip bots whose death animation has already been fully processed
            if not getattr(bot, "alive", True) and getattr(bot, "_death_event_emitted", False):
                continue
            proj = self._update_bot_one(
                bot, player, loot_items, tilemap, dt, event_bus,
                combat_system=combat_system,
            )
            if proj is not None:
                result.append(proj)
        return result

    def _update_bot_one(
        self,
        bot: Any,
        player: Any,
        loot_items: List[Any],
        tilemap: Any,
        dt: float,
        bus: Any,
        combat_system: Any = None,
    ) -> Optional[Any]:
        """Drive one PlayerAgent through its PATROL/AGGRO/ATTACK/DEAD FSM.

        Differences from ``_update_one`` (RobotEnemy-centric):
          - Uses ``health`` instead of ``hp``
          - Uses ``_waypoint_idx`` instead of ``current_waypoint``
          - ATTACK fires via ``weapon_state`` (fire cooldown, reload)
          - DEAD emits ``player_killed`` (not ``enemy_killed``)
        """
        ai_state = bot.ai_state

        # ------------------------------------------------------------------
        # DEAD: run death-animation timer then emit player_killed once
        # ------------------------------------------------------------------
        if ai_state == AIState.DEAD:
            bot._death_timer = getattr(bot, "_death_timer", 0.0) + dt
            if bot._death_timer >= _DEATH_ANIM_DURATION:
                if not getattr(bot, "_death_event_emitted", False):
                    bot._death_event_emitted = True
                    bcx, bcy = _centre_of(bot)
                    bus.emit(
                        "player_killed",
                        victim=bot,
                        killer=getattr(bot, "_killer", None),
                    )
            return None  # no movement in DEAD state

        # ------------------------------------------------------------------
        # HP → DEAD transition (external health zeroing)
        # ------------------------------------------------------------------
        if getattr(bot, "health", 1) <= 0:
            bot.ai_state = AIState.DEAD
            bot._death_timer = 0.0
            return None

        bcx, bcy = _centre_of(bot)
        pcx, pcy = _centre_of(player)
        dist = _dist(bcx, bcy, pcx, pcy)

        # ------------------------------------------------------------------
        # PATROL
        # ------------------------------------------------------------------
        if ai_state == AIState.PATROL:
            # Loot pickup: consume any loot within detect range
            for loot in loot_items:
                if not getattr(loot, "alive", False):
                    continue
                lcx = getattr(getattr(loot, "rect", None), "centerx", loot.x)
                lcy = getattr(getattr(loot, "rect", None), "centery", loot.y)
                if _dist(bcx, bcy, lcx, lcy) <= PVP_LOOT_DETECT_RANGE:
                    loot.alive = False
                    bus.emit(
                        "item_picked_up",
                        bot=bot,
                        item=getattr(loot, "item", None),
                    )
                    break

            # Aggro check: switch to AGGRO when player is nearby
            if dist <= bot.aggro_range:
                bot.ai_state = AIState.AGGRO
                bot.lost_timer = 0.0
                bot.path = []
            else:
                self._do_bot_patrol(bot, dt)
            return None

        # ------------------------------------------------------------------
        # AGGRO
        # ------------------------------------------------------------------
        if ai_state == AIState.AGGRO:
            if dist <= bot.attack_range:
                bot.ai_state = AIState.ATTACK
            elif dist > bot.aggro_range:
                bot.lost_timer = getattr(bot, "lost_timer", 0.0) + dt
                if bot.lost_timer >= LOST_PLAYER_TIMEOUT:
                    bot.ai_state = AIState.PATROL
                    bot.path = []
            else:
                bot.lost_timer = 0.0

            if bot.ai_state == AIState.AGGRO:
                self._do_chase(bot, player, tilemap, dt)
            return None

        # ------------------------------------------------------------------
        # ATTACK
        # ------------------------------------------------------------------
        if ai_state == AIState.ATTACK:
            if dist > bot.attack_range:
                bot.ai_state = AIState.AGGRO
                bot.path = []
                return None
            return self._do_bot_attack(bot, player, dt, bus, combat_system)

        return None

    def _do_bot_patrol(self, bot: Any, dt: float) -> None:
        """Advance the bot along its patrol waypoints using ``_waypoint_idx``."""
        if not bot.patrol_waypoints:
            return
        idx = getattr(bot, "_waypoint_idx", 0)
        wp = bot.patrol_waypoints[idx % len(bot.patrol_waypoints)]
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

    def _do_bot_attack(
        self,
        bot: Any,
        player: Any,
        dt: float,
        bus: Any,
        combat_system: Any = None,
    ) -> Optional[Any]:
        """Fire at *player* using the bot's ``weapon_state``, handling reload."""
        ws = getattr(bot, "weapon_state", None)
        if ws is None:
            return None  # unarmed bot — cannot fire

        # Trigger reload when magazine is empty
        if ws.needs_reload:
            ws.reloading = True
            ws.reload_timer = ws.reload_time
            return None

        # Count down active reload
        if ws.reloading:
            ws.reload_timer = max(0.0, ws.reload_timer - dt)
            if ws.reload_timer <= 0.0:
                ws.reloading = False
                ws.reload_timer = 0.0
                ws.ammo = ws.magazine_size
            return None

        # Decrement fire cooldown
        if ws.fire_cooldown > 0:
            ws.fire_cooldown = max(0.0, ws.fire_cooldown - dt)

        # Fire when weapon is ready
        if ws.can_fire and combat_system is not None:
            pcx, pcy = _centre_of(player)
            try:
                proj = combat_system.fire(bot, pcx, pcy)
                ws.ammo -= 1
                ws.fire_cooldown = ws.fire_interval
                return proj
            except Exception:
                pass

        return None

    def update(
        self,
        enemies: List[RobotEnemy],
        player: Any,
        tilemap: Any,
        dt: float,
        event_bus: Any,
        combat_system: Any = None,
    ) -> List[Any]:
        """Update every living enemy and return enemy-fired projectiles."""
        result: List[Any] = []
        for enemy in enemies:
            if not enemy.alive:
                continue
            proj = self._update_one(
                enemy, player, tilemap, dt, event_bus,
                combat_system=combat_system,
            )
            if proj is not None:
                result.append(proj)
        return result

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
        combat_system: Any = None,
    ) -> Optional[Any]:
        """Update one enemy; return a Projectile if one was fired, else None."""
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
            return None  # Do not move or transition when dead

        # -- HP check: catch external HP zeroing (bypassed take_damage) ------
        if enemy.hp <= 0 and enemy.state != AIState.DEAD:
            enemy.state = AIState.DEAD
            enemy.ai_state = AIState.DEAD
            enemy._death_timer = 0.0
            return None

        # -- PATROL ----------------------------------------------------------
        if enemy.state == AIState.PATROL:
            if dist <= enemy.aggro_range:
                enemy.state = AIState.AGGRO
                enemy.ai_state = AIState.AGGRO
                enemy.lost_timer = 0.0
                enemy.path = []
            else:
                self._do_patrol(enemy, dt)
            return None

        # -- AGGRO -----------------------------------------------------------
        if enemy.state == AIState.AGGRO:
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
            return None

        # -- ATTACK ----------------------------------------------------------
        if enemy.state == AIState.ATTACK:
            if dist > enemy.attack_range:
                enemy.state = AIState.AGGRO
                enemy.ai_state = AIState.AGGRO
                enemy.path = []
                return None
            return self._do_attack(
                enemy, player, dt, bus, combat_system=combat_system,
            )

        return None

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

        # BFS path-following: step toward the centre of the next path cell
        if tilemap is not None and len(enemy.path) >= 2:
            ts = tilemap.tile_size
            target_wx, _target_wy = cell_to_world(enemy.path[1], ts)
            ecx, _ecy = _centre_of(enemy)
            dx = target_wx - ecx
            if abs(dx) <= _ARRIVAL_THRESHOLD:
                # Arrived at this cell — advance path
                try:
                    enemy.path.pop(0)
                except IndexError:
                    pass
            else:
                direction = 1.0 if dx > 0 else -1.0
                enemy.x += direction * enemy.move_speed * dt
        else:
            # Fallback: direct horizontal move toward player
            ecx, _ecy = _centre_of(enemy)
            pcx, _pcy = _centre_of(player)
            dx = pcx - ecx
            if abs(dx) > 1.0:
                direction = 1.0 if dx > 0 else -1.0
                enemy.x += direction * enemy.move_speed * dt

    def _do_attack(
        self,
        enemy: RobotEnemy,
        player: Any,
        dt: float,
        bus: Any,
        combat_system: Any = None,
    ) -> Optional[Any]:
        """Fire at the player when the attack cooldown elapses.

        Returns a ``Projectile`` if one was created (combat_system path),
        otherwise returns ``None``.

        When ``combat_system`` is None the legacy direct-damage path is used
        so all existing tests without a combat system continue to pass.
        """
        enemy.attack_timer += dt
        if enemy.attack_timer < enemy.attack_cooldown:
            return None

        enemy.attack_timer = 0.0

        # Guard: never attack a dead player
        if not getattr(player, "alive", True):
            return None

        if combat_system is not None:
            pcx, pcy = _centre_of(player)
            try:
                return combat_system.fire(
                    enemy, pcx, pcy, damage=enemy.attack_damage,
                )
            except Exception:
                return None
        else:
            # Legacy fallback: direct damage (preserves pre-projectile test contracts)
            if hasattr(player, "take_damage"):
                player.take_damage(enemy.attack_damage)
                bus.emit("player.damaged", amount=enemy.attack_damage)
            return None
