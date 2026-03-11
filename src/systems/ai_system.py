import pygame
from typing import List, Any
from src.entities.robot_enemy import AIState, RobotEnemy
from src.utils.pathfinding import world_to_cell, cell_to_world, bfs

class AISystem:
    def update(self, enemies: List[RobotEnemy], player: Any,
               tilemap: Any, dt: float, event_bus: Any) -> None:
        for enemy in enemies:
            if not enemy.alive or enemy.ai_state == AIState.DEAD:
                continue
            self._update_enemy(enemy, player, tilemap, dt, event_bus)

    def _dist(self, a: Any, b: Any) -> float:
        import math
        ax, ay = a.center
        bx, by = b.center
        return math.hypot(ax - bx, ay - by)

    def _update_enemy(self, enemy: RobotEnemy, player: Any,
                      tilemap: Any, dt: float, event_bus: Any) -> None:
        dist = self._dist(enemy, player)

        # State transitions
        if enemy.ai_state == AIState.PATROL:
            if dist <= enemy.aggro_range:
                enemy.ai_state = AIState.AGGRO
        elif enemy.ai_state == AIState.AGGRO:
            if dist <= enemy.attack_range:
                enemy.ai_state = AIState.ATTACK
            elif dist > enemy.aggro_range * 1.5:
                enemy.ai_state = AIState.PATROL
        elif enemy.ai_state == AIState.ATTACK:
            if dist > enemy.attack_range * 1.2:
                enemy.ai_state = AIState.AGGRO

        # Execute state
        if enemy.ai_state == AIState.PATROL:
            self._do_patrol(enemy, tilemap, dt)
        elif enemy.ai_state == AIState.AGGRO:
            self._do_chase(enemy, player, tilemap, dt)
        elif enemy.ai_state == AIState.ATTACK:
            self._do_attack(enemy, player, dt, event_bus)

        # Apply gravity (basic)
        enemy.vy += 800 * dt
        enemy.rect.y += int(enemy.vy * dt)
        # Simple ground check
        if tilemap.is_solid(enemy.rect.centerx // tilemap.tile_size,
                            enemy.rect.bottom // tilemap.tile_size):
            while tilemap.is_solid(enemy.rect.centerx // tilemap.tile_size,
                                   enemy.rect.bottom // tilemap.tile_size):
                enemy.rect.y -= 1
            enemy.vy = 0
            enemy.on_ground = True

        enemy.advance_animation()

        # Death check
        if enemy.is_dead():
            enemy.ai_state = AIState.DEAD
            enemy.alive = False
            event_bus.emit('enemy_killed',
                           enemy=enemy,
                           x=float(enemy.rect.centerx),
                           y=float(enemy.rect.centery),
                           loot_table=enemy.loot_table,
                           xp_reward=enemy.xp_reward)

    def _do_patrol(self, enemy: RobotEnemy, tilemap: Any, dt: float) -> None:
        if not enemy.patrol_waypoints:
            return
        wp = enemy.patrol_waypoints[enemy._wp_index % len(enemy.patrol_waypoints)]
        tx, ty = wp
        dx = tx - enemy.rect.centerx
        if abs(dx) < 8:
            enemy._wp_index = (enemy._wp_index + 1) % len(enemy.patrol_waypoints)
            enemy.vx = 0
        else:
            direction = 1 if dx > 0 else -1
            enemy.vx = direction * enemy.speed * 0.5
        enemy.rect.x += int(enemy.vx * dt)

    def _do_chase(self, enemy: RobotEnemy, player: Any, tilemap: Any, dt: float) -> None:
        dx = player.rect.centerx - enemy.rect.centerx
        direction = 1 if dx > 0 else -1
        enemy.vx = direction * enemy.speed
        enemy.rect.x += int(enemy.vx * dt)

    def _do_attack(self, enemy: RobotEnemy, player: Any, dt: float, event_bus: Any) -> None:
        enemy._attack_timer -= dt
        if enemy._attack_timer <= 0:
            enemy._attack_timer = enemy.attack_cooldown
            if hasattr(player, 'take_damage'):
                player.take_damage(enemy.attack_damage)
            event_bus.emit('player.damaged', amount=enemy.attack_damage)
