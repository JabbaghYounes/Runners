"""Scene manager — maintains a stack of BaseScene instances.

Only the top-most scene receives per-frame ``handle_events``, ``update``, and
``render`` calls.  Pushing a new scene freezes the one below it (useful for
overlay scenes like the pause menu); popping resumes the scene beneath.

Typical usage::

    sm = SceneManager()
    sm.push(MainMenu(settings, assets, bus))

    # In the main loop:
    sm.handle_events(pygame.event.get())
    sm.update(FIXED_TIMESTEP)
    sm.render(screen)
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

import pygame

from src.scenes.base_scene import BaseScene

# Set RUNNERS_DEBUG=1 in the environment to enable verbose scene-stack logging.
_DEBUG: bool = os.environ.get("RUNNERS_DEBUG", "") == "1"


def _dbg(msg: str) -> None:
    """Print *msg* to stderr when debug mode is active (RUNNERS_DEBUG=1)."""
    if _DEBUG:
        print(f"[Runners] {msg}", file=sys.stderr)


class _CallableBool(int):
    """A bool-like value that can also be called (returns itself).

    This allows ``is_empty`` to work as both a property (``sm.is_empty``)
    and a method-style call (``sm.is_empty()``).
    """
    def __new__(cls, val: bool):
        return super().__new__(cls, val)

    def __call__(self) -> bool:
        return bool(self)

    def __bool__(self) -> bool:
        return int.__bool__(self)


class SceneManager:
    """Push/pop scene stack with per-frame routing to the active scene."""

    def __init__(self) -> None:
        self._stack: List[BaseScene] = []

    # ── Stack mutations ───────────────────────────────────────────────────────

    def push(self, scene: BaseScene) -> None:
        """Push *scene* on top of the stack.

        The previously active scene (if any) receives ``on_pause``.
        The new scene receives ``on_enter``.
        """
        _dbg(f"push → {scene.__class__.__name__}")
        if self._stack:
            self._stack[-1].on_pause()
        self._stack.append(scene)
        scene.on_enter()

    def pop(self) -> Optional[BaseScene]:
        """Remove and return the top scene.

        The removed scene receives ``on_exit``.
        The scene now on top (if any) receives ``on_resume``.
        Returns ``None`` if the stack is already empty.
        """
        if not self._stack:
            return None
        scene = self._stack.pop()
        _dbg(f"pop  ← {scene.__class__.__name__}")
        scene.on_exit()
        if self._stack:
            _dbg(f"resume → {self._stack[-1].__class__.__name__}")
            self._stack[-1].on_resume()
        return scene

    def replace(self, scene: BaseScene) -> None:
        """Replace the top scene with *scene* without resuming the scene below.

        Equivalent to a pop (no ``on_resume`` for the scene below) followed by a
        push.  Use this for non-overlay transitions such as MainMenu → HomeBase.
        """
        if self._stack:
            old = self._stack.pop()
            _dbg(f"replace {old.__class__.__name__} → {scene.__class__.__name__}")
            old.on_exit()
        else:
            _dbg(f"replace (empty) → {scene.__class__.__name__}")
        self._stack.append(scene)
        scene.on_enter()

    def replace_all(self, scene: BaseScene) -> None:
        """Clear the entire stack, then push *scene* as the sole entry.

        Use this for hard navigations that must discard all history — e.g.
        PauseMenu's "Exit to Menu" action.  Every evicted scene receives
        ``on_exit``; the new scene receives ``on_enter``.  The scene beneath
        the previous top does *not* receive ``on_resume`` (intentional).
        """
        _dbg(f"replace_all → {scene.__class__.__name__} (clearing {len(self._stack)} scene(s))")
        while self._stack:
            old = self._stack.pop()
            old.on_exit()
        self._stack.append(scene)
        scene.on_enter()

    def clear(self) -> None:
        """Pop every scene off the stack (each receives ``on_exit``)."""
        while self._stack:
            self.pop()

    # ── Per-frame routing ─────────────────────────────────────────────────────

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        """Forward *events* to the active (top) scene."""
        if self._stack:
            self._stack[-1].handle_events(events)

    def update(self, dt: float) -> None:
        """Advance the active scene by *dt* seconds."""
        if self._stack:
            self._stack[-1].update(dt)

    def render(self, screen: pygame.Surface) -> None:
        """Render all scenes in stack order (bottom to top), so overlay scenes
        such as ``PauseMenu`` are drawn over the scenes beneath them."""
        for scene in self._stack:
            scene.render(screen)

    # ── Queries ───────────────────────────────────────────────────────────────

    @property
    def active(self) -> Optional[BaseScene]:
        """The top-most scene, or ``None`` if the stack is empty."""
        return self._stack[-1] if self._stack else None

    @property
    def is_empty(self) -> _CallableBool:
        """``True`` when no scenes are on the stack.

        Works both as a property (``sm.is_empty``) and as a call
        (``sm.is_empty()``) for backwards compatibility.
        """
        return _CallableBool(not self._stack)

    def depth(self) -> int:
        """Number of scenes currently on the stack."""
        return len(self._stack)
