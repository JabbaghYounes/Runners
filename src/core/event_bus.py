"""Synchronous publish/subscribe event bus."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable


class EventBus:
    """Lightweight synchronous pub/sub message bus.

    Subscribers are called in registration order.  Emitting an event with no
    subscribers is a silent no-op — callers never need to guard the call.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., None]]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def subscribe(self, event_name: str, callback: Callable[..., None]) -> None:
        """Register *callback* to be called whenever *event_name* is emitted."""
        if callback not in self._listeners[event_name]:
            self._listeners[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable[..., None]) -> None:
        """Remove *callback* from *event_name*.  No-op if not registered."""
        try:
            self._listeners[event_name].remove(callback)
        except ValueError:
            pass

    def emit(self, event_name: str, **kwargs: object) -> None:
        """Call every subscriber of *event_name* with **kwargs**.

        Iterates over a snapshot so subscribers may safely unsubscribe
        themselves during handling.
        """
        for cb in list(self._listeners[event_name]):
            cb(**kwargs)
