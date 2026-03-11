"""Unit tests for src/core/scene_manager.py.

Uses a lightweight stub scene — no Pygame display required.
"""

import os
import sys
from pathlib import Path
from typing import List

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()

from src.core.scene_manager import SceneManager
from src.scenes.base_scene import BaseScene


# ── Stub scene ────────────────────────────────────────────────────────────────

class StubScene(BaseScene):
    """Records every lifecycle call so tests can assert call order."""

    def __init__(self, name: str = "stub", log: list | None = None):
        self.name  = name
        self._log  = log if log is not None else []
        self._dt_received: list[float] = []

    def handle_events(self, events):
        self._log.append(f"{self.name}.handle_events")

    def update(self, dt: float):
        self._dt_received.append(dt)
        self._log.append(f"{self.name}.update")

    def render(self, screen):
        self._log.append(f"{self.name}.render")

    def on_enter(self):
        self._log.append(f"{self.name}.on_enter")

    def on_exit(self):
        self._log.append(f"{self.name}.on_exit")

    def on_pause(self):
        self._log.append(f"{self.name}.on_pause")

    def on_resume(self):
        self._log.append(f"{self.name}.on_resume")


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSceneManagerStack:
    def setup_method(self):
        self.sm  = SceneManager()
        self.log: List[str] = []

    def _scene(self, name: str) -> StubScene:
        return StubScene(name, self.log)

    def test_push_calls_on_enter(self):
        a = self._scene("a")
        self.sm.push(a)
        assert "a.on_enter" in self.log

    def test_push_pauses_previous_scene(self):
        a, b = self._scene("a"), self._scene("b")
        self.sm.push(a)
        self.sm.push(b)
        assert "a.on_pause" in self.log
        assert "b.on_enter" in self.log

    def test_pop_exits_top_and_resumes_below(self):
        a, b = self._scene("a"), self._scene("b")
        self.sm.push(a)
        self.sm.push(b)
        self.log.clear()
        self.sm.pop()
        assert "b.on_exit"   in self.log
        assert "a.on_resume" in self.log

    def test_pop_empty_stack_returns_none(self):
        assert self.sm.pop() is None

    def test_active_returns_top_scene(self):
        a, b = self._scene("a"), self._scene("b")
        self.sm.push(a)
        assert self.sm.active is a
        self.sm.push(b)
        assert self.sm.active is b

    def test_active_none_when_empty(self):
        assert self.sm.active is None

    def test_is_empty(self):
        assert self.sm.is_empty()
        self.sm.push(self._scene("x"))
        assert not self.sm.is_empty()

    def test_depth(self):
        assert self.sm.depth() == 0
        self.sm.push(self._scene("a"))
        assert self.sm.depth() == 1
        self.sm.push(self._scene("b"))
        assert self.sm.depth() == 2

    def test_replace_exits_old_enters_new(self):
        a, b = self._scene("a"), self._scene("b")
        self.sm.push(a)
        self.log.clear()
        self.sm.replace(b)
        assert "a.on_exit"  in self.log
        assert "b.on_enter" in self.log
        assert self.sm.active is b

    def test_clear_exits_all_scenes(self):
        a, b = self._scene("a"), self._scene("b")
        self.sm.push(a)
        self.sm.push(b)
        self.log.clear()
        self.sm.clear()
        assert self.sm.is_empty()
        assert "b.on_exit" in self.log
        assert "a.on_exit" in self.log


class TestSceneManagerRouting:
    def setup_method(self):
        self.sm  = SceneManager()
        self.log: List[str] = []

    def _scene(self, name: str) -> StubScene:
        return StubScene(name, self.log)

    def test_update_routed_to_active_scene(self):
        a = self._scene("a")
        self.sm.push(a)
        self.sm.update(0.016)
        assert a._dt_received == [0.016]

    def test_render_routed_to_active_scene(self):
        a = self._scene("a")
        self.sm.push(a)
        surf = pygame.Surface((1, 1))
        self.sm.render(surf)
        assert "a.render" in self.log

    def test_handle_events_routed_to_active_scene(self):
        a = self._scene("a")
        self.sm.push(a)
        self.sm.handle_events([])
        assert "a.handle_events" in self.log

    def test_only_top_scene_receives_update(self):
        a, b = self._scene("a"), self._scene("b")
        self.sm.push(a)
        self.sm.push(b)
        self.sm.update(0.016)
        # a is paused — it must NOT receive updates
        assert a._dt_received == []
        assert b._dt_received == [0.016]
