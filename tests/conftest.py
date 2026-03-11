"""
Shared test infrastructure for the enemy-ai-pve test suite.

Stubs for missing infrastructure modules (Entity base class, EventBus) are
injected into ``sys.modules`` at import time — before any project module is
loaded — so that every test file can import the real implementations without
requiring a Pygame display context or missing sibling features.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so that ``import src.*`` works.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Stub: src.entities.entity
#   RobotEnemy inherits from Entity; the real file does not yet exist.
# ---------------------------------------------------------------------------

class _Entity:
    """Minimal stand-in for the real Entity base class."""

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        *,
        width: int = 32,
        height: int = 48,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.width = int(width)
        self.height = int(height)
        self.alive: bool = True


_entity_mod = types.ModuleType("src.entities.entity")
_entity_mod.Entity = _Entity  # type: ignore[attr-defined]
sys.modules["src.entities.entity"] = _entity_mod


# ---------------------------------------------------------------------------
# Shared pytest fixtures
# ---------------------------------------------------------------------------

import pytest  # noqa: E402  — must come after sys.modules manipulation


class SpyEventBus:
    """Lightweight EventBus that records every emission for test assertions."""

    def __init__(self) -> None:
        self.emitted: list[tuple[str, dict]] = []

    def emit(self, event_name: str, payload: dict | None = None) -> None:
        self.emitted.append((event_name, payload if payload is not None else {}))

    def subscribe(self, event_name: str, callback) -> None:  # noqa: ANN001
        pass  # not exercised by these tests

    def clear(self) -> None:
        self.emitted.clear()

    # Convenience helpers used in assertions.
    def all_events(self, name: str) -> list[dict]:
        return [p for n, p in self.emitted if n == name]

    def first_event(self, name: str) -> dict:
        return self.all_events(name)[0]


@pytest.fixture
def event_bus() -> SpyEventBus:
    """Return a fresh SpyEventBus for each test."""
    return SpyEventBus()


@pytest.fixture
def grunt_robot():
    """Default grunt-style RobotEnemy with two patrol waypoints."""
    from src.entities.robot_enemy import RobotEnemy

    return RobotEnemy(
        x=100.0,
        y=100.0,
        hp=50,
        patrol_speed=40.0,
        move_speed=80.0,
        aggro_range=200.0,
        attack_range=40.0,
        attack_damage=10,
        attack_cooldown=1.2,
        xp_reward=25,
        loot_table=[{"item_id": "ammo_pistol", "weight": 60}],
        type_id="grunt",
        patrol_waypoints=[(100.0, 100.0), (300.0, 100.0)],
    )
