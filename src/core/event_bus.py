"""
Simple synchronous publish-subscribe event bus.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List


class EventBus:
    """Pub/sub event bus.  Listeners are called synchronously on emit."""

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable[..., None]]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(self, event: str, callback: Callable[..., None]) -> None:
        """Register *callback* to be called whenever *event* is emitted."""
        self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., None]) -> None:
        """Remove *callback* from *event* listeners (silently ignores misses)."""
        try:
            self._listeners[event].remove(callback)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    def emit(self, event: str, **kwargs: Any) -> None:
        """Call every listener registered for *event* with *kwargs*."""
        for callback in list(self._listeners[event]):
            callback(**kwargs)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def listener_count(self, event: str) -> int:
        """Return the number of active listeners for *event*."""
        return len(self._listeners[event])

    def clear(self, event: str | None = None) -> None:
        """Remove all listeners; optionally restrict to a single *event*."""
        if event is None:
            self._listeners.clear()
        else:
            self._listeners.pop(event, None)
