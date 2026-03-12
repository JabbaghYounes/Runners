"""ShootingSystem -- mouse aim tracking, crosshair rendering, fire/reload dispatch.

Orchestrates input (mouse position, LMB, R key) and delegates to
:class:`WeaponSystem` for cooldown/ammo logic and projectile creation.

Usage from GameScene::

    self._shooting = ShootingSystem(self._event_bus)
    # in handle_events:
    self._shooting.handle_events(events)
    # in update:
    new_projs = self._shooting.update(player, dt)
    self.projectiles.extend(new_projs)
    # in render:
    self._shooting.render_crosshair(screen, camera_offset)
"""
from __future__ import annotations

import math
from typing import Any, List

import pygame

from src.constants import (
    CROSSHAIR_COLOR,
    CROSSHAIR_GAP,
    CROSSHAIR_SIZE,
    KEY_BINDINGS,
)
from src.systems.weapon_system import WeaponState, WeaponSystem


class ShootingSystem:
    """Handles mouse aim tracking, crosshair rendering, and fire/reload dispatch."""

    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus
        self._weapon_system = WeaponSystem(event_bus=event_bus)
        self._weapon_state = WeaponState()

        # Mouse state
        self._mouse_screen_x: float = 0.0
        self._mouse_screen_y: float = 0.0
        self._mouse_world_x: float = 0.0
        self._mouse_world_y: float = 0.0
        self._fire_held: bool = False
        self._reload_pressed: bool = False

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def weapon_state(self) -> WeaponState:
        return self._weapon_state

    @property
    def aim_world_pos(self) -> tuple[float, float]:
        """Current crosshair position in world coordinates."""
        return (self._mouse_world_x, self._mouse_world_y)

    @property
    def aim_screen_pos(self) -> tuple[float, float]:
        """Current crosshair position in screen coordinates."""
        return (self._mouse_screen_x, self._mouse_screen_y)

    # ------------------------------------------------------------------
    # Weapon equip
    # ------------------------------------------------------------------

    def equip_weapon(self, weapon: Any) -> None:
        """Load stats from an inventory Weapon item into the weapon state."""
        if weapon is not None:
            self._weapon_state.load_from_weapon(weapon)
        else:
            self._weapon_state = WeaponState()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        """Process input events for shooting (mouse button, R key)."""
        reload_key = KEY_BINDINGS.get("reload", pygame.K_r)

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._fire_held = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self._fire_held = False
            elif event.type == pygame.KEYDOWN and event.key == reload_key:
                self._reload_pressed = True
            elif event.type == pygame.MOUSEMOTION:
                self._mouse_screen_x = float(event.pos[0])
                self._mouse_screen_y = float(event.pos[1])

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(
        self,
        player: Any,
        dt: float,
        camera_offset: tuple[float, float] = (0.0, 0.0),
    ) -> List[Any]:
        """Advance weapon timers and fire if LMB is held.

        Args:
            player: The player entity (must have ``.center`` property).
            dt: Frame delta time in seconds.
            camera_offset: ``(ox, oy)`` world-to-screen offset.

        Returns:
            List of newly created Projectile entities (may be empty).
        """
        # Convert screen mouse position to world coordinates
        ox, oy = camera_offset
        self._mouse_world_x = self._mouse_screen_x + ox
        self._mouse_world_y = self._mouse_screen_y + oy

        # Sync weapon stats from equipped weapon (if player inventory changed)
        self._sync_weapon_from_player(player)

        # Tick weapon cooldowns / reload
        self._weapon_system.update(self._weapon_state, dt)

        new_projectiles: list = []

        # Reload request
        if self._reload_pressed:
            self._weapon_system.start_reload(self._weapon_state)
            self._reload_pressed = False

        # Fire request
        if self._fire_held and player.alive:
            proj = self._weapon_system.try_fire(
                self._weapon_state, player,
                self._mouse_world_x, self._mouse_world_y,
            )
            if proj is not None:
                new_projectiles.append(proj)

        return new_projectiles

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_crosshair(self, screen: pygame.Surface,
                         camera_offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw a crosshair at the current mouse position."""
        sx = int(self._mouse_screen_x)
        sy = int(self._mouse_screen_y)
        gap = CROSSHAIR_GAP
        size = CROSSHAIR_SIZE
        color = CROSSHAIR_COLOR

        # Horizontal lines
        pygame.draw.line(screen, color, (sx - size, sy), (sx - gap, sy), 2)
        pygame.draw.line(screen, color, (sx + gap, sy), (sx + size, sy), 2)
        # Vertical lines
        pygame.draw.line(screen, color, (sx, sy - size), (sx, sy - gap), 2)
        pygame.draw.line(screen, color, (sx, sy + gap), (sx, sy + size), 2)
        # Centre dot
        pygame.draw.circle(screen, color, (sx, sy), 2)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _sync_weapon_from_player(self, player: Any) -> None:
        """Keep weapon state in sync with equipped weapon from player inventory.

        Only reloads stats when the equipped weapon reference actually changes.
        """
        if not hasattr(player, "inventory"):
            return
        inv = player.inventory
        weapon = getattr(inv, "equipped_weapon", None)
        if weapon is not None and not hasattr(self, "_last_equipped_weapon"):
            self._weapon_state.load_from_weapon(weapon)
            self._last_equipped_weapon = weapon
        elif weapon is not None and weapon is not getattr(self, "_last_equipped_weapon", None):
            self._weapon_state.load_from_weapon(weapon)
            self._last_equipped_weapon = weapon
