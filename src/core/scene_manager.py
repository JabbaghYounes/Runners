"""Stack-based scene manager: push / pop / replace / replace_all."""
from __future__ import annotations

from typing import List, TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from src.scenes.base_scene import BaseScene


class SceneManager:
    """Manages a stack of :class:`~src.scenes.base_scene.BaseScene` objects.

    Event routing and updates go to the **top** scene only.
    Rendering traverses the stack **bottom-to-top**, so scenes below the top
    (e.g. a frozen :class:`GameScene` under :class:`PauseMenu`) are still
    visible without any extra work.
    """

    def __init__(self) -> None:
        self._stack: List["BaseScene"] = []

    # ------------------------------------------------------------------
    # Stack operations
    # ------------------------------------------------------------------

    def push(self, scene: "BaseScene") -> None:
        """Push *scene* on top of the stack and call its ``on_enter`` hook."""
        scene.on_enter()
        self._stack.append(scene)

    def pop(self) -> None:
        """Remove the top scene (calls ``on_exit``) and resume the one below
        (calls ``on_enter`` on the newly-revealed top).

        Does nothing when the stack is empty.
        """
        if not self._stack:
            return
        self._stack[-1].on_exit()
        self._stack.pop()
        if self._stack:
            self._stack[-1].on_enter()

    def replace(self, scene: "BaseScene") -> None:
        """Replace the top scene with *scene*.

        The current top's ``on_exit`` is called; the scene that would be
        revealed is *not* given an ``on_enter`` call because *scene* is
        pushed immediately afterward.
        """
        if self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
        scene.on_enter()
        self._stack.append(scene)

    def replace_all(self, scene: "BaseScene") -> None:
        """Clear the entire stack and push *scene* as the sole entry.

        ``on_exit`` is called on every evicted scene in top-to-bottom order.
        """
        while self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
        scene.on_enter()
        self._stack.append(scene)

    # ------------------------------------------------------------------
    # Per-frame dispatch
    # ------------------------------------------------------------------

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        """Forward *events* to the top scene only."""
        if self._stack:
            self._stack[-1].handle_events(events)

    def update(self, dt: float) -> None:
        """Advance the top scene by *dt* seconds."""
        if self._stack:
            self._stack[-1].update(dt)

    def render(self, screen: pygame.Surface) -> None:
        """Render all scenes bottom-to-top so overlays appear in front."""
        for scene in self._stack:
            scene.render(screen)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        """``True`` when no scenes are on the stack."""
        return len(self._stack) == 0
