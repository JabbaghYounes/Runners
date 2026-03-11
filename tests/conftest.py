"""
Shared test infrastructure for the enemy-ai-pve test suite.

Stubs for missing Pygame modules so unit tests run headlessly.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Stub the entity base module so tests that import it in TYPE_CHECKING
# blocks don't need a real pygame install at import time.
# ---------------------------------------------------------------------------
_entity_mod = types.ModuleType('_Entity')


class _Entity:
    def __init__(self, x: float, y: float, width: int = 32, height: int = 32) -> None:
        self.x = float(x)
        self.y = float(y)
        self.width = int(width)
        self.height = int(height)
        self.alive: bool = True


_entity_mod.Entity = _Entity  # type: ignore[attr-defined]
sys.modules['src.entities.entity'] = _entity_mod

import pytest  # noqa: E402  (must come after sys.path manipulation)


# ---------------------------------------------------------------------------
# SpyEventBus — records emitted events; subscribe is a no-op
# ---------------------------------------------------------------------------
class SpyEventBus:
    """EventBus test double that records emitted events.

    Registered callbacks are *not* called — use the real EventBus when you
    need callback delivery.
    """

    def __init__(self) -> None:
        self.emitted: list[tuple[str, dict]] = []

    def emit(self, event_name: str, **payload: object) -> None:  # type: ignore[override]
        self.emitted.append((event_name, payload))

    def subscribe(self, event_name: str, callback: object) -> None:
        pass

    def unsubscribe(self, event_name: str, callback: object) -> None:
        pass

    def clear(self) -> None:
        self.emitted.clear()

    def all_events(self, name: str) -> list[tuple[str, dict]]:
        return [e for e in self.emitted if e[0] == name]

    def first_event(self, name: str) -> tuple[str, dict] | None:
        events = self.all_events(name)
        return events[0] if events else None


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def event_bus() -> SpyEventBus:
    return SpyEventBus()


@pytest.fixture
def grunt_robot() -> object:
    """A minimal stub enemy used by AI system tests."""
    from unittest.mock import MagicMock
    import pygame

    robot = MagicMock()
    robot.rect = pygame.Rect(100, 100, 32, 32)
    robot.alive = True
    robot.health = 50
    robot.max_health = 50
    robot.loot_table = []
    return robot
