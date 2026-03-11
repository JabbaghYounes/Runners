import pygame
from typing import List, Optional
from src.scenes.base_scene import BaseScene

class SceneManager:
    def __init__(self):
        self._stack: List[BaseScene] = []

    @property
    def is_empty(self) -> bool:
        return len(self._stack) == 0

    def push(self, scene: BaseScene) -> None:
        scene.on_enter()
        self._stack.append(scene)

    def pop(self) -> Optional[BaseScene]:
        if self._stack:
            scene = self._stack.pop()
            scene.on_exit()
            if self._stack:
                self._stack[-1].on_enter()
            return scene
        return None

    def replace(self, scene: BaseScene) -> None:
        if self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
        scene.on_enter()
        self._stack.append(scene)

    def replace_all(self, scene: BaseScene) -> None:
        while self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
        scene.on_enter()
        self._stack.append(scene)

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        if self._stack:
            self._stack[-1].handle_events(events)

    def update(self, dt: float) -> None:
        if self._stack:
            self._stack[-1].update(dt)

    def render(self, screen: pygame.Surface) -> None:
        if self._stack:
            self._stack[-1].render(screen)
