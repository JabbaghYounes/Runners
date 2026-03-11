"""Abstract base class for all game scenes."""
from __future__ import annotations
from abc import ABC, abstractmethod


class BaseScene(ABC):
    """Abstract interface that every scene must implement.

    Scenes are managed by SceneManager as a stack. The topmost scene
    receives all events, updates, and render calls each frame.
    """

    @abstractmethod
    def handle_events(self, events: list) -> None:
        """Process a list of pygame events."""
        ...

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance scene logic by *dt* seconds."""
        ...

    @abstractmethod
    def render(self, screen) -> None:
        """Draw the scene onto *screen*."""
        ...

    def on_enter(self) -> None:
        """Called once when the scene becomes the active scene."""

    def on_exit(self) -> None:
        """Called once just before the scene is popped or replaced."""
