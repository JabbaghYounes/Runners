"""AI-controlled player-agent entity (PvP bot).

``PlayerAgent`` is driven by ``AISystem.update_bots()``.  It shares the
``AIState`` FSM with ``RobotEnemy`` but is tagged ``Faction.PLAYER`` so
projectile routing through ``CombatSystem`` works identically to the human
player.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple, TYPE_CHECKING

import pygame

from src.entities.entity import Entity
from src.entities.robot_enemy import AIState
from src.constants import (
    Faction,
    PVP_AGENT_AGGRO_RANGE,
    PVP_AGENT_SHOOT_RANGE,
    PVP_AGENT_PATROL_SPEED,
    PVP_AGENT_MOVE_SPEED,
)

if TYPE_CHECKING:
    from src.inventory.item import Item
    from src.systems.weapon_system import WeaponState

_BOT_WIDTH: int = 28
_BOT_HEIGHT: int = 48
_BOT_MAX_HEALTH: int = 100

# Colours
_FILL_COLOR: Tuple[int, int, int] = (255, 140, 0)    # orange
_DEAD_COLOR: Tuple[int, int, int] = (100, 70, 20)    # dark brown corpse
_BORDER_COLOR: Tuple[int, int, int] = (255, 255, 255)
_HP_BG_COLOR: Tuple[int, int, int] = (60, 20, 20)
_HP_FG_COLOR: Tuple[int, int, int] = (255, 140, 0)
_LABEL_COLOR: Tuple[int, int, int] = (255, 255, 255)


class PlayerAgent(Entity):
    """Bot-controlled agent in PvP.  ``is_player_controlled`` is always False."""

    is_player_controlled: bool = False

    # Class-level dimension constants (used by _centre_of() in AISystem)
    width: int = _BOT_WIDTH
    height: int = _BOT_HEIGHT

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        patrol_waypoints: Optional[List[Tuple[float, float]]] = None,
        loadout: Optional[dict] = None,
        driver: Any = None,
        difficulty: str = "medium",
    ) -> None:
        super().__init__(x=x, y=y, w=_BOT_WIDTH, h=_BOT_HEIGHT)

        # Faction / control flags
        self.faction: Faction = Faction.PLAYER
        self.is_player_controlled: bool = False

        # Health
        self.max_health: int = _BOT_MAX_HEALTH
        self.health: int = _BOT_MAX_HEALTH

        # Physics state (read/written by PhysicsSystem)
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.on_ground: bool = False
        self.slide_timer: float = 0.0  # PhysicsSystem compatibility

        # Intent flags (written by AISystem, read by PhysicsSystem)
        self.target_vx: float = 0.0
        self.jump_intent: bool = False

        # AI state machine
        self.ai_state: AIState = AIState.PATROL

        # Navigation
        self.patrol_waypoints: List[Tuple[float, float]] = (
            list(patrol_waypoints) if patrol_waypoints else [(x, y)]
        )
        self._waypoint_idx: int = 0
        self.patrol_speed: float = PVP_AGENT_PATROL_SPEED
        self.move_speed: float = PVP_AGENT_MOVE_SPEED

        # Combat ranges
        self.aggro_range: float = PVP_AGENT_AGGRO_RANGE
        self.attack_range: float = PVP_AGENT_SHOOT_RANGE

        # BFS path state (mirrors RobotEnemy fields for AI reuse)
        self.path: List[Tuple[int, int]] = []
        self.path_timer: float = 0.0
        self.lost_timer: float = 0.0

        # Death animation
        self._death_timer: float = 0.0
        self._death_event_emitted: bool = False
        self._killer: Any = None

        # Weapon state (populated by _apply_loadout)
        self.weapon_state: Optional[WeaponState] = None

        # Real inventory
        from src.inventory.inventory import Inventory
        self.inventory = Inventory()

        # Misc
        self.difficulty: str = difficulty
        self._label_surface: Optional[pygame.Surface] = None

        # Apply loadout
        self._apply_loadout(loadout or {})

    # ------------------------------------------------------------------
    # x / y properties — keep in sync with rect so _centre_of() works
    # ------------------------------------------------------------------

    @property  # type: ignore[override]
    def x(self) -> float:
        return float(self.rect.x)

    @x.setter
    def x(self, val: float) -> None:
        self.rect.x = int(val)

    @property  # type: ignore[override]
    def y(self) -> float:
        return float(self.rect.y)

    @y.setter
    def y(self, val: float) -> None:
        self.rect.y = int(val)

    # ------------------------------------------------------------------
    # Loadout
    # ------------------------------------------------------------------

    def _apply_loadout(self, loadout: dict) -> None:
        """Equip weapon and armor from a loadout dict."""
        from src.systems.weapon_system import WeaponState as _WS

        weapon_item = loadout.get("weapon")
        armor_item = loadout.get("armor")

        if weapon_item is not None:
            self.inventory.equipped_weapon = weapon_item
            ws = _WS()
            ws.load_from_weapon(weapon_item)
            self.weapon_state = ws
        else:
            # No weapon — bot can still chase but cannot shoot
            self.weapon_state = None

        if armor_item is not None:
            self.inventory.equipped_armor = armor_item

    # ------------------------------------------------------------------
    # Armor helpers (used by CombatSystem)
    # ------------------------------------------------------------------

    @property
    def armor(self) -> int:
        """Armor value from the equipped armor item (0 if none)."""
        armor_item = self.inventory.equipped_armor
        if armor_item is None:
            return 0
        return int(
            getattr(armor_item, "armor", None)
            or getattr(armor_item, "armor_value", 0)
        )

    def get_effective_armor(self) -> int:
        """Called by CombatSystem for armor-aware damage reduction."""
        return self.armor

    # ------------------------------------------------------------------
    # Damage / death
    # ------------------------------------------------------------------

        # Physics state — required by PhysicsSystem._step()
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.on_ground: bool = False
        self.target_vx: float = 0.0
        self.slide_timer: float = 0.0

    def take_damage(self, amount: int) -> None:
        """Reduce health.  Sets ``alive = False`` on lethal damage so that
        ``CombatSystem`` emits the ``player_killed`` event immediately."""
        if self.ai_state == AIState.DEAD:
            return
        self.health = max(0, self.health - amount)
        if self.health <= 0:
            self.alive = False
            self.ai_state = AIState.DEAD
            self._death_timer = 0.0

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(
        self, screen: pygame.Surface, camera_offset: Tuple[int, int]
    ) -> None:
        """Draw bot as orange rect with white border, HP bar, and BOT label."""
        ox, oy = camera_offset
        draw_rect = pygame.Rect(
            self.rect.x - ox,
            self.rect.y - oy,
            self.rect.w,
            self.rect.h,
        )

        if self.ai_state == AIState.DEAD:
            pygame.draw.rect(screen, _DEAD_COLOR, draw_rect)
            return

        # Body
        pygame.draw.rect(screen, _FILL_COLOR, draw_rect)
        pygame.draw.rect(screen, _BORDER_COLOR, draw_rect, 1)

        # HP bar (8 px above top of rect)
        bar_y = draw_rect.y - 8
        bar_w = draw_rect.w
        hp_pct = max(0.0, self.health / max(1, self.max_health))
        pygame.draw.rect(screen, _HP_BG_COLOR, (draw_rect.x, bar_y, bar_w, 4))
        pygame.draw.rect(
            screen, _HP_FG_COLOR,
            (draw_rect.x, bar_y, int(bar_w * hp_pct), 4),
        )

        # "BOT" label (cached surface)
        if self._label_surface is None:
            try:
                font = pygame.font.SysFont(None, 16)
                self._label_surface = font.render("BOT", True, _LABEL_COLOR)
            except Exception:
                self._label_surface = None
        if self._label_surface is not None:
            lw = self._label_surface.get_width()
            screen.blit(
                self._label_surface,
                (draw_rect.centerx - lw // 2, bar_y - 12),
            )
