"""Abstract base class that every game scene must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import pygame


class BaseScene(ABC):
    """Contract that all scenes must satisfy.

    ``SceneManager`` calls these methods every frame:
    - ``handle_events`` — process Pygame events (top of stack only)
    - ``update``        — advance scene logic by *dt* seconds (top only)
    - ``render``        — draw to *screen* (all scenes, bottom → top)

    Lifecycle hooks ``on_enter`` / ``on_exit`` have empty default bodies and
    are called by ``SceneManager`` during push / pop / replace operations.
    """

    @abstractmethod
    def handle_events(self, events: List[pygame.event.Event]) -> None:
        """Process a batch of Pygame events for this frame."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance scene state by *dt* seconds."""

    @abstractmethod
    def render(self, screen: pygame.Surface) -> None:
        """Draw the scene onto *screen*."""

    # ------------------------------------------------------------------
    # Lifecycle hooks (optional overrides)
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        """Called when this scene becomes active (pushed or revealed by pop)."""

    def on_exit(self) -> None:
        """Called just before this scene is removed from the stack."""
