"""
Input driver hierarchy for controlling player/agent entities.

Classes
-------
AgentActions      — dataclass carrying a single frame's input snapshot.
InputDriver       — abstract base class; subclasses implement get_actions().
LocalAIDriver     — FSM-based AI with WANDER / AGGRO / ATTACK / DEAD states.
KeyboardDriver    — reads pygame keyboard + mouse state.
NetworkDriver     — stub for remote/network-driven input.
"""
from __future__ import annotations

import enum
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# AgentActions dataclass
# ---------------------------------------------------------------------------

@dataclass
class AgentActions:
    """Immutable snapshot of one frame's desired input for an entity."""

    move_dir: tuple = (0.0, 0.0)
    aim_pos: tuple = (0.0, 0.0)
    fire: bool = False
    reload: bool = False
    use_consumable: Optional[int] = None


# ---------------------------------------------------------------------------
# InputDriver ABC
# ---------------------------------------------------------------------------

class InputDriver(ABC):
    """Abstract base class for all input sources."""

    @abstractmethod
    def get_actions(self, game_state: Any) -> AgentActions:
        """Return an AgentActions snapshot for this frame."""


# ---------------------------------------------------------------------------
# LocalAIDriver FSM
# ---------------------------------------------------------------------------

class _AIState(enum.Enum):
    WANDER = 0
    AGGRO = 1
    ATTACK = 2
    DEAD = 3


_NOOP = AgentActions(
    move_dir=(0.0, 0.0),
    aim_pos=(0.0, 0.0),
    fire=False,
    reload=False,
    use_consumable=None,
)


class LocalAIDriver(InputDriver):
    """Finite-state-machine AI driver.

    States
    ------
    WANDER  — no threat detected; patrol or idle.
    AGGRO   — threat detected within aggro range; close in.
    ATTACK  — threat within shoot range; fire every frame.
    DEAD    — entity is dead; produce no-op actions only.
    """

    _state_enum = _AIState

    def __init__(self, config: dict | None = None) -> None:
        self._config: dict = config or {}
        self.state: _AIState = _AIState.WANDER

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _nearest_hostile_dist(self, game_state: Any) -> float | None:
        """Return distance to the nearest entity in game_state.entities."""
        ax, ay = game_state.agent_pos
        min_dist: float | None = None
        for entity in game_state.entities:
            dist = math.hypot(entity.x - ax, entity.y - ay)
            if min_dist is None or dist < min_dist:
                min_dist = dist
        return min_dist

    # ------------------------------------------------------------------
    # FSM
    # ------------------------------------------------------------------

    def get_actions(self, game_state: Any) -> AgentActions:
        from src.constants import PVP_AGENT_AGGRO_RANGE, PVP_AGENT_SHOOT_RANGE

        if self.state is _AIState.DEAD:
            return AgentActions(
                move_dir=(0.0, 0.0),
                aim_pos=(0.0, 0.0),
                fire=False,
                reload=False,
                use_consumable=None,
            )

        dist = self._nearest_hostile_dist(game_state)

        if self.state is _AIState.WANDER:
            if dist is not None and dist <= PVP_AGENT_AGGRO_RANGE:
                self.state = _AIState.AGGRO
            return AgentActions(move_dir=(0.0, 0.0), aim_pos=(0.0, 0.0))

        if self.state is _AIState.AGGRO:
            if dist is None or dist > PVP_AGENT_AGGRO_RANGE:
                self.state = _AIState.WANDER
            elif dist <= PVP_AGENT_SHOOT_RANGE:
                self.state = _AIState.ATTACK
            return AgentActions(move_dir=(0.0, 0.0), aim_pos=(0.0, 0.0))

        if self.state is _AIState.ATTACK:
            if dist is None or dist > PVP_AGENT_AGGRO_RANGE:
                self.state = _AIState.WANDER
                return AgentActions(move_dir=(0.0, 0.0), aim_pos=(0.0, 0.0))
            if dist > PVP_AGENT_SHOOT_RANGE:
                self.state = _AIState.AGGRO
                return AgentActions(move_dir=(0.0, 0.0), aim_pos=(0.0, 0.0))
            # Still in shoot range — fire!
            return AgentActions(
                move_dir=(0.0, 0.0),
                aim_pos=(0.0, 0.0),
                fire=True,
            )

        # Fallback (should not be reached)
        return AgentActions(move_dir=(0.0, 0.0), aim_pos=(0.0, 0.0))


# ---------------------------------------------------------------------------
# KeyboardDriver
# ---------------------------------------------------------------------------

class KeyboardDriver(InputDriver):
    """Reads pygame keyboard (IJKL) and mouse state each frame."""

    def get_actions(self, game_state: Any) -> AgentActions:
        import pygame

        keys = pygame.key.get_pressed()
        mx, my = pygame.mouse.get_pos()

        dx = 0.0
        dy = 0.0
        if keys[pygame.K_i]:
            dy -= 1.0
        if keys[pygame.K_k]:
            dy += 1.0
        if keys[pygame.K_j]:
            dx -= 1.0
        if keys[pygame.K_l]:
            dx += 1.0

        fire = bool(keys[pygame.K_SPACE])
        reload_ = bool(keys[pygame.K_r])

        return AgentActions(
            move_dir=(dx, dy),
            aim_pos=(float(mx), float(my)),
            fire=fire,
            reload=reload_,
            use_consumable=None,
        )


# ---------------------------------------------------------------------------
# NetworkDriver (stub)
# ---------------------------------------------------------------------------

class NetworkDriver(InputDriver):
    """Stub for remote input; returns no-op actions until network is live."""

    def __init__(self) -> None:
        self._connected: bool = False

    def connect(self, host: str, port: int) -> None:
        """Connect to a remote input server (stub — does nothing yet)."""
        self._connected = True

    def get_actions(self, game_state: Any) -> AgentActions:
        """Return a safe no-op until real network data arrives."""
        return AgentActions(
            move_dir=(0.0, 0.0),
            aim_pos=(0.0, 0.0),
            fire=False,
            reload=False,
            use_consumable=None,
        )
