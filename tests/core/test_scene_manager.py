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

    def test_handle_events_empty_stack_does_not_raise(self):
        """Calling handle_events when no scene is on the stack must be safe."""
        self.sm.handle_events([])  # no active scene; must not raise

    def test_update_empty_stack_does_not_raise(self):
        """Calling update when no scene is on the stack must be safe."""
        self.sm.update(0.016)

    def test_render_empty_stack_does_not_raise(self):
        """Calling render when no scene is on the stack must be safe."""
        surf = pygame.Surface((1, 1))
        self.sm.render(surf)


# ── replace_all ───────────────────────────────────────────────────────────────


class TestSceneManagerReplaceAll:
    """replace_all() must exit every existing scene and enter only the new one.

    Spec: "exit **all** scenes, enter new one (use for hard navigation:
    'Exit to Menu' from pause)".  No on_resume for any evicted scene.
    """

    def setup_method(self):
        self.sm  = SceneManager()
        self.log: List[str] = []

    def _scene(self, name: str) -> StubScene:
        return StubScene(name, self.log)

    def test_replace_all_calls_on_enter_for_new_scene(self):
        a, b = self._scene("a"), self._scene("b")
        self.sm.push(a)
        self.log.clear()
        self.sm.replace_all(b)
        assert "b.on_enter" in self.log

    def test_replace_all_calls_on_exit_for_every_existing_scene(self):
        a, b, c = self._scene("a"), self._scene("b"), self._scene("c")
        self.sm.push(a)
        self.sm.push(b)
        self.log.clear()
        self.sm.replace_all(c)
        assert "a.on_exit" in self.log
        assert "b.on_exit" in self.log

    def test_replace_all_does_not_call_on_resume_for_any_evicted_scene(self):
        """on_resume must never fire during a replace_all — it is a hard reset."""
        a, b, c = self._scene("a"), self._scene("b"), self._scene("c")
        self.sm.push(a)
        self.sm.push(b)
        self.log.clear()
        self.sm.replace_all(c)
        assert "a.on_resume" not in self.log
        assert "b.on_resume" not in self.log

    def test_replace_all_leaves_only_new_scene_on_stack(self):
        a = self._scene("a")
        b = self._scene("b")
        self.sm.push(a)
        self.sm.replace_all(b)
        assert self.sm.depth() == 1
        assert self.sm.active is b

    def test_replace_all_on_empty_stack_enters_new_scene_without_raising(self):
        b = self._scene("b")
        self.sm.replace_all(b)
        assert self.sm.active is b

    def test_replace_all_clears_deep_stack_to_single_entry(self):
        scenes = [self._scene(str(i)) for i in range(5)]
        for s in scenes:
            self.sm.push(s)
        fresh = self._scene("fresh")
        self.sm.replace_all(fresh)
        assert self.sm.depth() == 1
        assert self.sm.active is fresh


# ── replace / pop edge cases ──────────────────────────────────────────────────


class TestSceneManagerEdgeCases:
    """Edge cases not captured by the happy-path tests above."""

    def setup_method(self):
        self.sm  = SceneManager()
        self.log: List[str] = []

    def _scene(self, name: str) -> StubScene:
        return StubScene(name, self.log)

    def test_replace_on_empty_stack_enters_new_scene(self):
        """replace() on an empty stack must still call on_enter for the new scene."""
        b = self._scene("b")
        self.sm.replace(b)
        assert self.sm.active is b
        assert "b.on_enter" in self.log

    def test_replace_does_not_call_on_resume_for_scene_below(self):
        """replace() is a peer transition — the scene below must NOT get on_resume.

        Spec: 'replace — exit top scene, enter new one, no on_resume for
        scene below (use for peer transitions: MainMenu → HomeBase)'.
        """
        a, b, c = self._scene("a"), self._scene("b"), self._scene("c")
        self.sm.push(a)
        self.sm.push(b)
        self.log.clear()
        self.sm.replace(c)
        # c replaces b; a is the scene below and must NOT receive on_resume
        assert "a.on_resume" not in self.log

    def test_pop_single_scene_does_not_call_on_resume(self):
        """When the last scene is popped, there is nothing below to resume."""
        a = self._scene("a")
        self.sm.push(a)
        self.log.clear()
        self.sm.pop()
        assert all("on_resume" not in entry for entry in self.log)

    def test_is_empty_works_as_a_truthy_property(self):
        """sm.is_empty (without parentheses) must be truthy when the stack is empty."""
        assert self.sm.is_empty

    def test_is_empty_works_as_a_callable(self):
        """sm.is_empty() (called) must return True when the stack is empty."""
        assert self.sm.is_empty()

    def test_is_empty_property_false_after_push(self):
        self.sm.push(self._scene("a"))
        assert not self.sm.is_empty

    def test_is_empty_callable_false_after_push(self):
        self.sm.push(self._scene("a"))
        assert not self.sm.is_empty()
