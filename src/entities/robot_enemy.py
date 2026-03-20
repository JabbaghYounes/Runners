"""Robot enemy entity with FSM state and configurable stats."""
from __future__ import annotations

import pygame
from enum import Enum, auto
from typing import Tuple, List, Dict, Any, Optional
from src.entities.entity import Entity


class AIState(Enum):
    PATROL = auto()
    AGGRO = auto()
    ATTACK = auto()
    DEAD = auto()


# Map FSM state → animation key used by AnimationController
_STATE_ANIM_KEY: dict[AIState, str] = {
    AIState.PATROL: "patrol",
    AIState.AGGRO:  "aggro",
    AIState.ATTACK: "attack",
    AIState.DEAD:   "dead",
}


class RobotEnemy(Entity):
    """Humanoid robot enemy driven by the AISystem.

    Accepts keyword-only configuration so that each enemy type (grunt, elite,
    heavy, etc.) can be spawned with different stats from the enemy database.

    Coordinate contract
    -------------------
    ``x`` / ``y`` are properties backed by ``_float_x`` / ``_float_y``.
    Every write also updates ``rect.x`` / ``rect.y`` (int).  After
    ``PhysicsSystem`` resolves gravity and tile collisions (which moves
    ``rect`` directly), call ``sync_from_rect()`` to pull the corrected
    integer position back into the float backing fields.

    Ordering per frame::

        PhysicsSystem.update(...)     # writes rect
        enemy.update(dt)              # sync_from_rect → advance animation
        AISystem.update(...)          # reads/writes enemy.x via property
    """

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        type_id: str = "grunt",
        hp: int = 60,
        patrol_speed: float = 40.0,
        move_speed: float = 80.0,
        aggro_range: float = 200.0,
        attack_range: float = 60.0,
        attack_damage: int = 10,
        attack_cooldown: float = 1.5,
        xp_reward: int = 50,
        loot_table: List[Dict[str, Any]] | None = None,
        patrol_waypoints: List[Tuple[float, float]] | None = None,
        width: int = 32,
        height: int = 48,
        **kwargs: Any,
    ) -> None:
        # Initialise float backing fields BEFORE super().__init__ so the
        # x/y property setters work even if super() were to call them.
        self._float_x: float = float(x)
        self._float_y: float = float(y)

        super().__init__(x, y, width, height)  # sets self.rect

        self.type_id: str = type_id
        self.hp: int = hp
        self.max_hp: int = hp
        self.patrol_speed: float = patrol_speed
        self.move_speed: float = move_speed
        self.speed: float = move_speed  # alias for legacy code
        self.aggro_range: float = aggro_range
        self.attack_range: float = attack_range
        self.attack_damage: int = attack_damage
        self.attack_cooldown: float = attack_cooldown
        self.xp_reward: int = xp_reward
        self.loot_table: List[Dict[str, Any]] = loot_table or []
        self.patrol_waypoints: List[Tuple[float, float]] = (
            patrol_waypoints if patrol_waypoints is not None
            else [(float(x), float(y))]
        )

        # FSM state
        self.state: AIState = AIState.PATROL
        # Legacy alias
        self.ai_state: AIState = self.state

        # Navigation
        self.current_waypoint: int = 0
        self._wp_index: int = 0  # legacy alias
        self.path: List[Tuple[int, int]] = []
        self.path_timer: float = 0.0

        # Combat
        self.attack_timer: float = 0.0
        self._attack_timer: float = 0.0  # legacy alias

        # Loss-of-sight timer
        self.lost_timer: float = 0.0

        # Death animation
        self._death_timer: float = 0.0
        self._death_anim_duration: float = 0.6
        self._death_event_emitted: bool = False

        # Physics state (PhysicsSystem reads target_vx and writes vx/vy/on_ground)
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.on_ground: bool = False
        self.target_vx: float = 0.0   # intent velocity read by PhysicsSystem
        self._anim_timer: float = 0.0

        # Explicit width/height for callers that access them as attributes
        self.width: int = width
        self.height: int = height

    # ------------------------------------------------------------------
    # x / y properties — delegate to rect with float accumulation
    # ------------------------------------------------------------------

    @property
    def x(self) -> float:
        return self._float_x

    @x.setter
    def x(self, v: float) -> None:
        self._float_x = float(v)
        self.rect.x = int(v)

    @property
    def y(self) -> float:
        return self._float_y

    @y.setter
    def y(self, v: float) -> None:
        self._float_y = float(v)
        self.rect.y = int(v)

    # ------------------------------------------------------------------
    # Physics sync
    # ------------------------------------------------------------------

    def sync_from_rect(self) -> None:
        """Pull rect.x / rect.y (set by PhysicsSystem) into the float fields.

        Call once per frame, immediately after PhysicsSystem.update() and
        before AISystem.update(), so the AI always reads physics-resolved
        coordinates.
        """
        self._float_x = float(self.rect.x)
        self._float_y = float(self.rect.y)

    # ------------------------------------------------------------------
    # Update — sync + advance animation
    # ------------------------------------------------------------------

    def update(self, dt: float, tile_map: Optional[object] = None) -> None:
        """Sync physics position and advance the animation controller.

        Must be called after PhysicsSystem and before AISystem each frame.
        """
        self.sync_from_rect()

        if self.animation_controller is not None:
            key = _STATE_ANIM_KEY.get(self.state, "patrol")
            facing_right = self.vx >= 0
            self.animation_controller.set_state(key, facing_right=facing_right)
            self.animation_controller.update(dt)

    # ------------------------------------------------------------------
    # Combat
    # ------------------------------------------------------------------

    def take_damage(self, amount: int) -> int:
        """Apply damage. Transitions to DEAD state when HP reaches 0.
        Returns remaining HP."""
        if self.hp <= 0:
            return 0
        self.hp = max(0, self.hp - amount)
        if self.hp <= 0:
            self.state = AIState.DEAD
            self.ai_state = AIState.DEAD
            self._death_timer = 0.0
        return self.hp

    def is_dead(self) -> bool:
        return self.hp <= 0

    def advance_animation(self, dt: float = 0.016) -> bool:
        """Advance the death animation by *dt* seconds.
        Returns True when the animation is complete."""
        self._death_timer += dt
        return self._death_timer >= self._death_anim_duration

    # ------------------------------------------------------------------
    # Render — animated sprite or coloured-rect fallback + HP bar
    # ------------------------------------------------------------------

    def render(self, screen: pygame.Surface, camera_offset: Tuple[int, int]) -> None:
        if not self.alive:
            return
        ox, oy = camera_offset
        draw_x = self.rect.x - ox
        draw_y = self.rect.y - oy

        if self.animation_controller is not None:
            # Entity.render() blits the current animation frame
            super().render(screen, camera_offset)
        else:
            # Coloured-rect fallback (no sprite sheet loaded)
            color = (220, 80, 80) if self.type_id == "elite" else (180, 60, 60)
            pygame.draw.rect(
                screen, color,
                pygame.Rect(draw_x, draw_y, self.rect.w, self.rect.h),
            )

        # HP bar (always drawn when alive)
        bar_w = self.rect.w
        hp_pct = self.hp / max(1, self.max_hp)
        pygame.draw.rect(screen, (60, 20, 20), (draw_x, draw_y - 6, bar_w, 4))
        pygame.draw.rect(
            screen,
            (220, 60, 60),
            (draw_x, draw_y - 6, int(bar_w * hp_pct), 4),
        )
