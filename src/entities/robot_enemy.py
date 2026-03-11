"""RobotEnemy — humanoid robot entity with a four-state FSM.

State machine
-------------
PATROL  ──(player in aggro_range)──► AGGRO
AGGRO   ──(player in attack_range)─► ATTACK
AGGRO   ──(player lost ≥ 3 s)──────► PATROL
ATTACK  ──(player leaves range)────► AGGRO
any     ──(hp ≤ 0)─────────────────► DEAD
DEAD    ──(animation complete)─────► alive = False  (purged by GameScene)
"""
from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, List, Optional, Tuple

from src.entities.entity import Entity

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# FSM state enum
# ---------------------------------------------------------------------------

class AIState(Enum):
    PATROL = auto()
    AGGRO  = auto()
    ATTACK = auto()
    DEAD   = auto()


# ---------------------------------------------------------------------------
# Robot entity
# ---------------------------------------------------------------------------

# Seconds for a single death-animation frame (4 frames ≈ 0.6 s total).
_FRAME_DURATION: float = 0.15


class RobotEnemy(Entity):
    """A humanoid robot enemy driven by :class:`~src.systems.ai_system.AISystem`.

    Parameters
    ----------
    x, y:
        Initial world-space top-left position.
    width, height:
        Sprite/collision dimensions in pixels.
    hp:
        Starting (and maximum) hit-points.
    patrol_speed:
        Movement speed (px/s) while patrolling waypoints.
    move_speed:
        Movement speed (px/s) while chasing the player.
    aggro_range:
        Distance in pixels at which the robot detects the player.
    attack_range:
        Distance in pixels at which the robot begins attacking.
    attack_damage:
        Hit-points subtracted from the player per successful hit.
    attack_cooldown:
        Minimum seconds between consecutive attacks.
    xp_reward:
        XP granted to the player on kill (forwarded via ``enemy_killed``).
    loot_table:
        List of ``{"item_id": str, "weight": int}`` dicts; used by LootSystem.
    type_id:
        Config key used to look up this robot (e.g. ``"grunt"``).
    patrol_waypoints:
        Ordered list of ``(x, y)`` world positions to walk between.
    """

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        width: int = 32,
        height: int = 48,
        *,
        hp: int = 50,
        patrol_speed: float = 40.0,
        move_speed: float = 80.0,
        aggro_range: float = 200.0,
        attack_range: float = 40.0,
        attack_damage: int = 10,
        attack_cooldown: float = 1.2,
        xp_reward: int = 25,
        loot_table: Optional[List[dict]] = None,
        type_id: str = "grunt",
        patrol_waypoints: Optional[List[Tuple[float, float]]] = None,
    ) -> None:
        super().__init__(x, y, width=width, height=height)

        # --- Stats ---
        self.max_hp: int = hp
        self.hp: int = hp
        self.patrol_speed: float = patrol_speed
        self.move_speed: float = move_speed
        self.aggro_range: float = aggro_range
        self.attack_range: float = attack_range
        self.attack_damage: int = attack_damage
        self.attack_cooldown: float = attack_cooldown
        self.xp_reward: int = xp_reward
        self.loot_table: List[dict] = loot_table if loot_table is not None else []
        self.type_id: str = type_id

        # --- Patrol ---
        self.patrol_waypoints: List[Tuple[float, float]] = (
            list(patrol_waypoints) if patrol_waypoints else [(x, y)]
        )
        self.current_waypoint: int = 0

        # --- FSM ---
        self.state: AIState = AIState.PATROL
        self.lost_timer: float = 0.0   # seconds since player left aggro range

        # --- Path (AGGRO movement) ---
        self.path: list = []
        self.path_timer: float = 0.0   # seconds since last BFS recalc

        # --- Attack ---
        self.attack_timer: float = 0.0  # counts up; fires when ≥ attack_cooldown

        # --- Death animation ---
        self._death_timer: float = 0.0
        self._death_duration: float = _FRAME_DURATION * 4  # 4 death frames

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def rect(self) -> object:
        """Return a ``pygame.Rect`` (or a lightweight stub in non-Pygame envs)."""
        try:
            import pygame
            return pygame.Rect(int(self.x), int(self.y), self.width, self.height)
        except Exception:
            return _SimpleRect(int(self.x), int(self.y), self.width, self.height)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def take_damage(self, amount: int) -> int:
        """Reduce HP by *amount* (clamped to 0).

        If HP reaches 0 and the robot is not already dead, the FSM
        transitions to :attr:`AIState.DEAD` and the death-animation timer
        resets.

        Returns
        -------
        int
            Remaining HP after the hit.
        """
        if self.state == AIState.DEAD:
            return self.hp

        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.state = AIState.DEAD
            self._death_timer = 0.0

        return self.hp

    def is_dead(self) -> bool:
        """Return True when HP has reached zero."""
        return self.hp <= 0

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def advance_animation(self, dt: float) -> bool:
        """Tick the death animation by *dt* seconds.

        Returns
        -------
        bool
            True once the full death animation has played; False otherwise.
            The caller (AISystem) is responsible for setting ``alive = False``
            and emitting ``enemy_killed`` exactly once when True is returned.
        """
        self._death_timer += dt
        return self._death_timer >= self._death_duration


# ---------------------------------------------------------------------------
# Fallback rect (used when pygame is unavailable, e.g. in unit tests)
# ---------------------------------------------------------------------------

class _SimpleRect:
    """Minimal pygame.Rect substitute for non-display environments."""

    __slots__ = ("x", "y", "width", "height")

    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    @property
    def centerx(self) -> int:
        return self.x + self.width // 2

    @property
    def centery(self) -> int:
        return self.y + self.height // 2

    @property
    def center(self) -> Tuple[int, int]:
        return (self.centerx, self.centery)

    @property
    def bottom(self) -> int:
        return self.y + self.height
