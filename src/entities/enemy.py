"""PvE humanoid-robot enemy with finite-state-machine AI.

States cycle through ``IDLE → PATROL → DETECT → ATTACK → DEAD``.
Stats are data-driven via :class:`EnemyTierConfig`.
"""

from __future__ import annotations

from enum import Enum, auto

import pygame

from src.entities.base import Entity, resolve_tilemap_collision
from src.entities.enemy_config import EnemyTierConfig
from src.entities.projectile import Projectile
from src.events import EventBus


class EnemyState(Enum):
    IDLE = auto()
    PATROL = auto()
    DETECT = auto()
    ATTACK = auto()
    DEAD = auto()


# How far beyond detection_range the player must move before the enemy
# disengages.  Prevents rapid state flickering at the boundary.
_DISENGAGE_MULTIPLIER: float = 1.5

# Distance (pixels) from a patrol waypoint at which the enemy considers
# itself "arrived" and moves to the next one.
_WAYPOINT_THRESHOLD: float = 8.0


class Enemy(Entity):
    """A PvE humanoid-robot enemy.

    Parameters:
        x, y: Initial world-pixel position.
        tier_config: Stat block loaded from ``data/enemies.json``.
        patrol_path: List of ``(x, y)`` world-pixel waypoints.
        event_bus: For publishing ``enemy_killed`` / ``entity_hit`` events.
        projectile_group: Shared sprite group for enemy-fired projectiles.
    """

    def __init__(
        self,
        x: float,
        y: float,
        tier_config: EnemyTierConfig,
        patrol_path: list[list[float] | tuple[float, float]] | None = None,
        event_bus: EventBus | None = None,
        projectile_group: pygame.sprite.Group | None = None,
    ) -> None:
        super().__init__(x, y, health=tier_config.health, width=32, height=32)

        # Config ----------------------------------------------------------
        self.tier_config = tier_config
        self.speed: float = tier_config.speed
        self.damage: int = tier_config.damage
        self.detection_range: float = tier_config.detection_range
        self.attack_range: float = tier_config.attack_range
        self.fire_rate: float = tier_config.fire_rate
        self.xp_reward: int = tier_config.xp_reward
        self.loot_table_id: str = tier_config.loot_table_id
        self.sprite_key: str = tier_config.sprite_key

        # Services --------------------------------------------------------
        self.event_bus: EventBus | None = event_bus
        self.projectile_group = projectile_group or pygame.sprite.Group()

        # FSM -------------------------------------------------------------
        self.state: EnemyState = EnemyState.IDLE
        self._state_timer: float = 0.0

        # Patrol ----------------------------------------------------------
        self._patrol_path: list[pygame.math.Vector2] = [
            pygame.math.Vector2(p[0], p[1]) for p in (patrol_path or [])
        ]
        self._patrol_index: int = 0

        # Combat ----------------------------------------------------------
        self._fire_timer: float = 0.0
        self._alert_timer: float = 0.0

        # Visual feedback -------------------------------------------------
        self._hit_flash_timer: float = 0.0

        # Track the last known killer for death event
        self._last_damage_source: Entity | None = None

    # ==================================================================
    # Main update — dispatches to current state handler
    # ==================================================================

    def update(self, dt: float, tilemap=None, player=None, **kwargs) -> None:  # noqa: D401
        if not self.alive:
            return

        self._hit_flash_timer = max(0.0, self._hit_flash_timer - dt)

        dispatch = {
            EnemyState.IDLE: self._update_idle,
            EnemyState.PATROL: self._update_patrol,
            EnemyState.DETECT: self._update_detect,
            EnemyState.ATTACK: self._update_attack,
            EnemyState.DEAD: self._update_dead,
        }
        handler = dispatch.get(self.state)
        if handler:
            handler(dt, tilemap=tilemap, player=player)

    # ==================================================================
    # State handlers
    # ==================================================================

    def _update_idle(self, dt: float, **kwargs) -> None:
        """Stand guard.  Transition to PATROL after ``idle_duration``."""
        self._state_timer += dt
        if self._state_timer >= self.tier_config.idle_duration:
            self._change_state(EnemyState.PATROL)

        # Even while idle, check for player detection
        player = kwargs.get("player")
        tilemap = kwargs.get("tilemap")
        if player is not None and tilemap is not None:
            if self._can_see_player(player, tilemap):
                self._change_state(EnemyState.DETECT)

    def _update_patrol(self, dt: float, **kwargs) -> None:
        """Move along waypoints.  Detect player if in range + LOS."""
        tilemap = kwargs.get("tilemap")
        player = kwargs.get("player")

        # Check detection first
        if player is not None and tilemap is not None:
            if self._can_see_player(player, tilemap):
                self._change_state(EnemyState.DETECT)
                return

        # Follow patrol path
        if self._patrol_path:
            self._move_along_patrol(dt, tilemap)
        else:
            # No patrol path — stay idle-like
            self._state_timer += dt
            if self._state_timer >= self.tier_config.idle_duration:
                self._change_state(EnemyState.IDLE)

    def _update_detect(self, dt: float, **kwargs) -> None:
        """Alert delay.  Turn toward player, then transition to ATTACK."""
        player = kwargs.get("player")
        tilemap = kwargs.get("tilemap")

        self._alert_timer += dt

        # Face the player
        if player is not None:
            to_player = player.pos - self.pos
            if to_player.length() > 0:
                self.facing_direction = to_player.normalize()

        # If the player has left the extended range, go back to patrol
        if player is not None and tilemap is not None:
            if not self._in_extended_range(player):
                self._change_state(EnemyState.PATROL)
                return

        if self._alert_timer >= self.tier_config.alert_delay:
            self._change_state(EnemyState.ATTACK)

    def _update_attack(self, dt: float, **kwargs) -> None:
        """Chase player and fire projectiles."""
        tilemap = kwargs.get("tilemap")
        player = kwargs.get("player")

        if player is None:
            self._change_state(EnemyState.PATROL)
            return

        # Disengage if player has left the extended range
        if not self._in_extended_range(player):
            self._change_state(EnemyState.PATROL)
            return

        # Face the player
        to_player = player.pos - self.pos
        dist = to_player.length()
        if dist > 0:
            self.facing_direction = to_player.normalize()

        # Move toward player if outside attack_range
        if dist > self.attack_range:
            self._move_toward(player.pos, dt, tilemap)

        # Fire projectiles
        self._fire_timer += dt
        fire_interval = 1.0 / self.fire_rate if self.fire_rate > 0 else float("inf")
        if self._fire_timer >= fire_interval and dist <= self.attack_range:
            self._fire_projectile(player.pos)
            self._fire_timer = 0.0

    def _update_dead(self, dt: float, **kwargs) -> None:
        """Post-death.  Entity should already be removed by ``die()``."""

    # ==================================================================
    # Detection helpers
    # ==================================================================

    def _can_see_player(self, player: Entity, tilemap) -> bool:
        """Return ``True`` if *player* is within ``detection_range`` and
        there is a clear line of sight through the tilemap."""
        if not player.alive:
            return False
        dist = self._distance_to(player)
        if dist > self.detection_range:
            return False
        # Bresenham LOS check through tilemap collision grid
        return not tilemap.raycast_solid(
            (self.pos.x, self.pos.y),
            (player.pos.x, player.pos.y),
        )

    def _in_extended_range(self, player: Entity) -> bool:
        """Return ``True`` if *player* is within the disengage range."""
        return self._distance_to(player) <= self.detection_range * _DISENGAGE_MULTIPLIER

    def _distance_to(self, other: Entity) -> float:
        return self.pos.distance_to(other.pos)

    # ==================================================================
    # Movement
    # ==================================================================

    def _move_toward(self, target: pygame.math.Vector2, dt: float, tilemap=None) -> None:
        """Move toward *target* at ``self.speed``, respecting tilemap collision."""
        direction = target - self.pos
        dist = direction.length()
        if dist < 1.0:
            return
        direction = direction.normalize()
        self.facing_direction = direction

        dx = direction.x * self.speed * dt
        dy = direction.y * self.speed * dt

        if tilemap is not None:
            resolve_tilemap_collision(self, tilemap, dx, dy)
        else:
            self.pos.x += dx
            self.pos.y += dy
            self._sync_rect()

    def _move_along_patrol(self, dt: float, tilemap=None) -> None:
        """Follow the patrol path waypoints, wrapping at the end."""
        if not self._patrol_path:
            return
        target = self._patrol_path[self._patrol_index]
        dist = self.pos.distance_to(target)

        if dist <= _WAYPOINT_THRESHOLD:
            self._patrol_index = (self._patrol_index + 1) % len(self._patrol_path)
            target = self._patrol_path[self._patrol_index]

        self._move_toward(target, dt, tilemap)

    # ==================================================================
    # Combat
    # ==================================================================

    def _fire_projectile(self, target_pos: pygame.math.Vector2) -> Projectile:
        """Create and return a projectile aimed at *target_pos*."""
        direction = target_pos - self.pos
        if direction.length() == 0:
            direction = pygame.math.Vector2(1, 0)
        else:
            direction = direction.normalize()

        proj = Projectile(
            x=self.pos.x,
            y=self.pos.y,
            direction=direction,
            speed=400.0,
            damage=self.damage,
            owner=self,
            max_range=self.attack_range * 1.5,
        )
        self.projectile_group.add(proj)

        if self.event_bus is not None:
            self.event_bus.publish("shot_fired", source=self)

        return proj

    def take_damage(self, amount: int, source: Entity | None = None) -> int:
        """Take damage, trigger hit flash, and transition to DEAD if health reaches 0."""
        if not self.alive:
            return 0

        actual = super().take_damage(amount, source)
        self._hit_flash_timer = 0.15  # flash duration in seconds
        self._last_damage_source = source

        if self.event_bus is not None:
            self.event_bus.publish(
                "entity_hit",
                target=self,
                damage=actual,
                source=source,
            )

        if not self.alive:
            self.die()

        return actual

    def die(self) -> None:
        """Handle death: publish event, transition to DEAD, remove from group."""
        if self.state == EnemyState.DEAD:
            return

        self.state = EnemyState.DEAD
        self.alive = False

        if self.event_bus is not None:
            self.event_bus.publish(
                "enemy_killed",
                enemy=self,
                killer=self._last_damage_source,
                xp_reward=self.xp_reward,
                loot_table_id=self.loot_table_id,
            )

        self.kill()  # remove from all sprite groups

    # ==================================================================
    # Drawing
    # ==================================================================

    def draw(self, surface: pygame.Surface, camera) -> None:
        """Render the enemy sprite and an overhead health bar."""
        if self.state == EnemyState.DEAD:
            return

        screen_pos = camera.world_to_screen(self.pos)
        sx, sy = int(screen_pos.x), int(screen_pos.y)

        # Body (placeholder rectangle)
        body_color = (255, 80, 80) if self._hit_flash_timer > 0 else (200, 60, 60)
        body_rect = pygame.Rect(sx - self.width // 2, sy - self.height // 2, self.width, self.height)
        pygame.draw.rect(surface, body_color, body_rect)

        # Health bar above
        bar_w, bar_h = 32, 4
        bar_x = sx - bar_w // 2
        bar_y = sy - self.height // 2 - 8
        # Background
        pygame.draw.rect(surface, (60, 60, 60), (bar_x, bar_y, bar_w, bar_h))
        # Foreground (health fraction)
        frac = self.health / self.max_health if self.max_health > 0 else 0
        pygame.draw.rect(surface, (200, 40, 40), (bar_x, bar_y, int(bar_w * frac), bar_h))

    # ==================================================================
    # Internal
    # ==================================================================

    def _change_state(self, new_state: EnemyState) -> None:
        """Transition to *new_state*, resetting relevant timers."""
        self.state = new_state
        self._state_timer = 0.0
        if new_state == EnemyState.DETECT:
            self._alert_timer = 0.0
        elif new_state == EnemyState.ATTACK:
            self._fire_timer = 0.0
