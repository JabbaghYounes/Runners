"""Unit tests for src/scenes/base_scene.py.

Verifies that:
  1. BaseScene is an abstract class — direct instantiation is forbidden.
  2. A concrete subclass that omits any of the three required methods
     (handle_events / update / render) cannot be instantiated.
  3. A fully-implemented subclass instantiates cleanly and is recognised as a
     BaseScene.
  4. The four optional lifecycle hooks (on_enter / on_exit / on_pause /
     on_resume) have no-op default implementations that return None.
  5. Optional hooks can be overridden; overrides are called correctly.

No Pygame display or audio device is required for these tests.
"""

from __future__ import annotations

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
import pytest

pygame.init()

from src.scenes.base_scene import BaseScene  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_complete_scene_class() -> type[BaseScene]:
    """Return a fully-implemented concrete BaseScene subclass."""

    class ConcreteScene(BaseScene):
        def handle_events(self, events: List[pygame.event.Event]) -> None:
            pass

        def update(self, dt: float) -> None:
            pass

        def render(self, screen: pygame.Surface) -> None:
            pass

    return ConcreteScene


# ── Abstract enforcement ───────────────────────────────────────────────────────

class TestBaseSceneIsAbstract:
    def test_direct_instantiation_raises_type_error(self):
        with pytest.raises(TypeError):
            BaseScene()  # type: ignore[abstract]

    def test_missing_handle_events_raises_type_error(self):
        class Incomplete(BaseScene):
            def update(self, dt: float) -> None:
                pass

            def render(self, screen: pygame.Surface) -> None:
                pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_missing_update_raises_type_error(self):
        class Incomplete(BaseScene):
            def handle_events(self, events) -> None:
                pass

            def render(self, screen: pygame.Surface) -> None:
                pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_missing_render_raises_type_error(self):
        class Incomplete(BaseScene):
            def handle_events(self, events) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_all_three_methods_missing_raises_type_error(self):
        class Empty(BaseScene):
            pass

        with pytest.raises(TypeError):
            Empty()

    def test_only_one_method_implemented_raises_type_error(self):
        class OneMethod(BaseScene):
            def handle_events(self, events) -> None:
                pass

        with pytest.raises(TypeError):
            OneMethod()


# ── Concrete subclass ──────────────────────────────────────────────────────────

class TestConcreteScene:
    def test_complete_subclass_can_be_instantiated(self):
        SceneClass = _make_complete_scene_class()
        scene = SceneClass()
        assert scene is not None

    def test_concrete_scene_is_instance_of_base_scene(self):
        scene = _make_complete_scene_class()()
        assert isinstance(scene, BaseScene)

    def test_required_methods_are_callable(self):
        scene = _make_complete_scene_class()()
        surf  = pygame.Surface((1, 1))
        # None of these should raise
        scene.handle_events([])
        scene.update(1 / 60)
        scene.render(surf)


# ── Optional lifecycle hooks — default no-ops ─────────────────────────────────

class TestOptionalHookDefaults:
    def setup_method(self):
        self.scene = _make_complete_scene_class()()

    def test_on_enter_does_not_raise(self):
        self.scene.on_enter()

    def test_on_exit_does_not_raise(self):
        self.scene.on_exit()

    def test_on_pause_does_not_raise(self):
        self.scene.on_pause()

    def test_on_resume_does_not_raise(self):
        self.scene.on_resume()

    def test_on_enter_returns_none(self):
        assert self.scene.on_enter() is None

    def test_on_exit_returns_none(self):
        assert self.scene.on_exit() is None

    def test_on_pause_returns_none(self):
        assert self.scene.on_pause() is None

    def test_on_resume_returns_none(self):
        assert self.scene.on_resume() is None

    def test_hooks_can_be_called_multiple_times_without_error(self):
        for _ in range(3):
            self.scene.on_enter()
            self.scene.on_pause()
            self.scene.on_resume()
            self.scene.on_exit()


# ── Optional hooks can be overridden ──────────────────────────────────────────

class TestOptionalHookOverrides:
    def test_overridden_hooks_are_invoked(self):
        log: list[str] = []

        class TrackedScene(BaseScene):
            def handle_events(self, events) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self, screen: pygame.Surface) -> None:
                pass

            def on_enter(self) -> None:
                log.append("enter")

            def on_exit(self) -> None:
                log.append("exit")

            def on_pause(self) -> None:
                log.append("pause")

            def on_resume(self) -> None:
                log.append("resume")

        scene = TrackedScene()
        scene.on_enter()
        scene.on_pause()
        scene.on_resume()
        scene.on_exit()

        assert log == ["enter", "pause", "resume", "exit"]

    def test_partial_hook_override_leaves_others_as_noop(self):
        """Overriding only on_enter must not break the remaining no-ops."""
        log: list[str] = []

        class PartialScene(BaseScene):
            def handle_events(self, events) -> None:
                pass

            def update(self, dt: float) -> None:
                pass

            def render(self, screen: pygame.Surface) -> None:
                pass

            def on_enter(self) -> None:
                log.append("enter")

        scene = PartialScene()
        scene.on_enter()   # overridden
        scene.on_pause()   # inherited no-op
        scene.on_resume()  # inherited no-op
        scene.on_exit()    # inherited no-op

        assert log == ["enter"]
