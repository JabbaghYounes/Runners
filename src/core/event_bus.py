"""Lightweight synchronous pub/sub event bus."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Callable


class EventBus:
    """Thread-unsafe synchronous event bus.

    Usage::

        bus = EventBus()
        bus.subscribe("enemy_killed", on_enemy_killed)
        bus.emit("enemy_killed", enemy=robot, killer=player)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callable[..., None]) -> None:
        """Register *callback* to be called when *event* is emitted."""
        if callback not in self._handlers[event]:
            self._handlers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., None]) -> None:
        """Remove a previously registered *callback* for *event* (no-op if absent)."""
        try:
            self._handlers[event].remove(callback)
        except ValueError:
            pass

    def emit(self, event: str, **payload: Any) -> None:
        """Fire *event*, calling every registered callback with *payload* as kwargs."""
        for callback in list(self._handlers[event]):
            callback(**payload)

    def clear(self) -> None:
        """Remove all subscriptions (useful for teardown in tests)."""
        self._handlers.clear()


# Module-level singleton used by modules that import it directly
event_bus = EventBus()
