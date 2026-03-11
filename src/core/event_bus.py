"""Lightweight synchronous pub/sub event bus."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Callable


class EventBus:
    """Subscribe callbacks to named events and emit those events.

    Design notes:
    - Synchronous: emit() calls all callbacks immediately in subscription order.
    - No thread safety — single-threaded Pygame use only.
    - Callbacks receive a single ``payload`` dict argument.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callable) -> None:
        """Register *callback* to be called when *event* is emitted."""
        if callback not in self._listeners[event]:
            self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable) -> None:
        """Remove *callback* from *event* listeners (no-op if not registered)."""
        try:
            self._listeners[event].remove(callback)
        except ValueError:
            pass

    def emit(self, event: str, payload: dict[str, Any] | None = None) -> None:
        """Call all listeners registered for *event* with *payload*."""
        if payload is None:
            payload = {}
        for callback in list(self._listeners[event]):
            callback(payload)

    def clear(self) -> None:
        """Remove all subscriptions (useful between rounds)."""
        self._listeners.clear()


# Module-level singleton used by systems that import directly.
event_bus = EventBus()
