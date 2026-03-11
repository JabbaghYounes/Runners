"""Lightweight synchronous pub/sub event bus.

Usage::

    bus = EventBus()
    bus.subscribe("timer_tick", lambda seconds_remaining: ...)
    bus.publish("timer_tick", seconds_remaining=59)
    bus.clear()  # removes all subscriptions (useful between rounds / in tests)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable


class EventBus:
    """Synchronous publish/subscribe bus that decouples game systems.

    All callbacks registered for an event name are invoked immediately and
    in registration order when that event is published.  Callbacks receive
    only keyword arguments so callers never depend on positional ordering.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def subscribe(self, event_name: str, callback: Callable) -> None:
        """Register *callback* to be called when *event_name* is published.

        Duplicate registrations of the same callback for the same event are
        silently ignored to prevent double-firing.
        """
        if callback not in self._listeners[event_name]:
            self._listeners[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """Remove a previously registered callback.  No-ops if not found."""
        try:
            self._listeners[event_name].remove(callback)
        except ValueError:
            pass

    def publish(self, event_name: str, **kwargs) -> None:
        """Invoke all callbacks subscribed to *event_name* with *kwargs*.

        Iterates over a snapshot of the listener list so that callbacks may
        safely call subscribe/unsubscribe without corrupting iteration.
        """
        for callback in list(self._listeners[event_name]):
            callback(**kwargs)

    def clear(self, event_name: str | None = None) -> None:
        """Remove subscriptions.

        If *event_name* is given, clears only listeners for that event.
        Otherwise removes **all** listeners (useful for test teardown or
        resetting state between rounds).
        """
        if event_name is not None:
            self._listeners[event_name].clear()
        else:
            self._listeners.clear()
