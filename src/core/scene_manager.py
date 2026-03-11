"""Scene stack manager — push/pop/replace; routes events/update/render."""
from __future__ import annotations
from typing import List, Optional
from src.scenes.base_scene import BaseScene


class SceneManager:
    """Manages a stack of BaseScene objects.

    The topmost scene (index -1) is the active scene that receives
    events, updates, and render calls each frame.
    """

    def __init__(self) -> None:
        self._stack: List[BaseScene] = []

    @property
    def active(self) -> Optional[BaseScene]:
        return self._stack[-1] if self._stack else None

    def push(self, scene: BaseScene) -> None:
        """Push *scene* onto the stack and call its on_enter hook."""
        scene.on_enter()
        self._stack.append(scene)

    def pop(self) -> Optional[BaseScene]:
        """Pop the active scene, calling on_exit; resume the scene below."""
        if not self._stack:
            return None
        scene = self._stack.pop()
        scene.on_exit()
        if self._stack:
            self._stack[-1].on_enter()
        return scene

    def replace(self, scene: BaseScene) -> None:
        """Replace the active scene with *scene*."""
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

    def render(self, screen: object) -> None:
        if self.active:
            self.active.render(screen)
