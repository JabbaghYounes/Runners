"""Lightweight synchronous pub/sub event bus.

No external dependencies. A module-level singleton ``event_bus`` is the
default channel used by all game systems.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


class EventBus:
    """Synchronous publish-subscribe event bus.

    Systems call ``subscribe(event, callback)`` during initialisation and
    ``emit(event, payload)`` to dispatch.  All registered callbacks are
    invoked immediately (same call stack) in the order they subscribed.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], None]]] = (
            defaultdict(list)
        )

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Register *callback* to be called whenever *event* is emitted."""
        self._subscribers[event].append(callback)

    def unsubscribe(
        self,
        event: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Remove *callback* from *event*. Silently ignores missing entries."""
        try:
            self._subscribers[event].remove(callback)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def emit(
        self,
        event: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Call every callback registered for *event* with *payload*.

        A copy of the subscriber list is iterated so that callbacks may
        safely unsubscribe themselves during handling.
        """
        if payload is None:
            payload = {}
        for callback in list(self._subscribers[event]):
            callback(payload)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all subscriptions (useful between tests)."""
        self._subscribers.clear()


# Module-level singleton used throughout the game.
event_bus = EventBus()
