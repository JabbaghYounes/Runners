"""
Shared pytest fixtures for the Runners test suite.

Provides:
  - ``SpyEventBus``    — records every emission for assertion without pulling
                         in the full EventBus implementation.
  - ``event_bus``      — pytest fixture that yields a fresh SpyEventBus.
  - ``reinitialize_pygame_if_needed`` — autouse fixture that restores pygame
                         subsystems after any test that calls pygame.quit().
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# sys.path guard (also set by root conftest, but guard here for safety)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# SDL dummy driver — must be set before pygame is first imported
# ---------------------------------------------------------------------------
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


# ---------------------------------------------------------------------------
# Stub: src.entities.entity
#   Several entity modules inherit from Entity; the real file may not yet
#   exist on this branch.  Inject a minimal stand-in so test imports work.
# ---------------------------------------------------------------------------

def _ensure_entity_stub() -> None:
    if "src.entities.entity" not in sys.modules:
        class _Entity:
            """Minimal Entity base for headless unit tests."""

            def __init__(
                self,
                x: float = 0.0,
                y: float = 0.0,
                width: int = 28,
                height: int = 48,
            ) -> None:
                import types as _t

                self.x = float(x)
                self.y = float(y)
                self.width = int(width)
                self.height = int(height)
                self.alive: bool = True

                # Minimal rect-like object so systems can call .rect.center etc.
                rect = _t.SimpleNamespace(
                    x=self.x, y=self.y, w=self.width, h=self.height,
                    centerx=self.x + self.width / 2,
                    centery=self.y + self.height / 2,
                    center=(self.x + self.width / 2, self.y + self.height / 2),
                )

                def _colliderect(other):
                    return (
                        rect.x < other.x + other.w
                        and rect.x + rect.w > other.x
                        and rect.y < other.y + other.h
                        and rect.y + rect.h > other.y
                    )

                rect.colliderect = _colliderect
                self.rect = rect

        _mod = types.ModuleType("src.entities.entity")
        _mod.Entity = _Entity  # type: ignore[attr-defined]
        sys.modules.setdefault("src.entities.entity", _mod)

        # Also ensure src.entities package is present
        if "src.entities" not in sys.modules:
            _pkg = types.ModuleType("src.entities")
            # Set __path__ so Python can find real submodules on disk
            _pkg.__path__ = [str(ROOT / "src" / "entities")]
            _pkg.__package__ = "src.entities"
            sys.modules.setdefault("src.entities", _pkg)


_ensure_entity_stub()


# ---------------------------------------------------------------------------
# SpyEventBus — lightweight recorder used across PvP tests
# ---------------------------------------------------------------------------

class SpyEventBus:
    """Records every emission so tests can assert on event payloads.

    Fully compatible with ``src.core.event_bus.EventBus`` subscribe / emit /
    unsubscribe API so it can be dropped in wherever the real bus is expected.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list] = {}
        self.emitted: list[tuple[str, dict]] = []

    # ── Subscription ──────────────────────────────────────────────────────

    def subscribe(self, event: str, callback) -> None:
        self._listeners.setdefault(event, []).append(callback)

    def unsubscribe(self, event: str, callback) -> None:
        try:
            self._listeners[event].remove(callback)
        except (KeyError, ValueError):
            pass

    # ── Emission ──────────────────────────────────────────────────────────

    def emit(self, event: str, **kwargs: Any) -> None:
        self.emitted.append((event, dict(kwargs)))
        for cb in list(self._listeners.get(event, [])):
            cb(**kwargs)

    # ── Helpers ───────────────────────────────────────────────────────────

    def all_events(self, name: str) -> list[dict]:
        """Return payloads for every emission matching *name*."""
        return [kw for ev, kw in self.emitted if ev == name]

    def first(self, name: str) -> dict:
        """Return payload of the first matching emission; raises if absent."""
        matches = self.all_events(name)
        if not matches:
            raise AssertionError(f"No '{name}' event was emitted. Got: {self.emitted!r}")
        return matches[0]

    def clear(self) -> None:
        self.emitted.clear()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_bus() -> SpyEventBus:
    """Return a fresh SpyEventBus for each test."""
    return SpyEventBus()


@pytest.fixture(autouse=True)
def reinitialize_pygame_if_needed():
    """Restore pygame subsystems after any test that calls pygame.quit()."""
    yield
    try:
        import pygame
        if not pygame.get_init():
            pygame.init()
            pygame.display.set_mode((1, 1))
    except Exception:
        pass  # pygame not installed or not needed for this test
