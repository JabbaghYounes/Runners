"""Scene stack manager — push/pop/replace; routes events/update/render."""
from __future__ import annotations
from typing import List, Optional
from src.scenes.base_scene import BaseScene


class SceneManager:
    """Manages a stack of BaseScene instances.

    Only the topmost scene receives handle_events / update / render calls.
    push() calls on_enter() on the new scene.
    pop() calls on_exit() on the removed scene then on_enter() on the
    scene below it (if any).
    replace() calls on_exit() on the current scene, pushes the new one,
    and calls on_enter() on it.
    """

    def __init__(self) -> None:
        self._stack: List[BaseScene] = []

    @property
    def active(self) -> Optional[BaseScene]:
        return self._stack[-1] if self._stack else None

    def push(self, scene: BaseScene) -> None:
        scene.on_enter()
        self._stack.append(scene)

    def pop(self) -> Optional[BaseScene]:
        if not self._stack:
            return None
        scene = self._stack.pop()
        scene.on_exit()
        if self._stack:
            self._stack[-1].on_enter()
        return scene

    def replace(self, scene: BaseScene) -> None:
        if self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
        scene.on_enter()
        self._stack.append(scene)

    def handle_events(self, events: list) -> None:
        if self.active:
            self.active.handle_events(events)

    def update(self, dt: float) -> None:
        if self.active:
            self.active.update(dt)

    def render(self, screen) -> None:
        if self.active:
            self.active.render(screen)
