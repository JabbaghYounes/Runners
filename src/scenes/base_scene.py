"""Abstract base class for all game scenes.

Every concrete scene must implement the three lifecycle methods:

* ``handle_events(events)`` — process raw pygame events for one frame
* ``update(dt)``            — advance scene logic by *dt* seconds (fixed timestep)
* ``render(screen)``        — draw the scene to *screen*

The optional hooks ``on_enter``, ``on_exit``, ``on_pause``, and ``on_resume``
are called by ``SceneManager`` as scenes move on and off the stack.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import pygame


class BaseScene(ABC):
    """Abstract scene.  All concrete scenes must inherit from this class."""

    # ── Required lifecycle methods ────────────────────────────────────────────

    @abstractmethod
    def handle_events(self, events: List[pygame.event.Event]) -> None:
        """Process a batch of pygame events collected for the current frame.

        Args:
            events: List of ``pygame.event.Event`` objects from
                    ``pygame.event.get()``.
        """

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance scene state.

        Args:
            dt: Fixed timestep in seconds (typically ``1/60 ≈ 0.01667``).
        """

    @abstractmethod
    def render(self, screen: pygame.Surface) -> None:
        """Draw the scene to the display surface.

        Args:
            screen: The main ``pygame.Surface`` returned by
                    ``pygame.display.set_mode()``.
        """

    # ── Optional stack hooks ──────────────────────────────────────────────────

    def on_enter(self) -> None:
        """Called once when this scene becomes the active (top) scene.

        Override to run one-time setup that depends on the display being ready
        (e.g. pre-loading assets, starting music, initialising sub-systems).
        """

    def on_exit(self) -> None:
        """Called once just before this scene is popped off the stack.

        Override to release resources, stop music, or persist transient state.
        """

    def on_pause(self) -> None:
        """Called when a new scene is pushed on top of this one.

        The scene remains in the stack but will not receive update/render calls
        until it becomes the top scene again.  Override to pause timers, mute
        music, etc.
        """

    def on_resume(self) -> None:
        """Called when the scene on top of this one is popped.

        This scene is now the active scene again.  Override to resume timers,
        restore music volume, refresh UI state, etc.
        """
