"""Synchronous publish/subscribe event bus."""
from __future__ import annotations

from typing import Callable, Dict, List


class EventBus:
    """Lightweight in-process pub/sub bus.

    Usage::

        bus = EventBus()
        bus.subscribe("player_died", lambda **kw: print(kw))
        bus.emit("player_died", cause="fall_damage", damage=50)
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable) -> None:
        """Register *callback* to be called when *event_name* is emitted."""
        self._subscribers.setdefault(event_name, []).append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """Remove a previously registered *callback* for *event_name*."""
        listeners = self._subscribers.get(event_name)
        if listeners and callback in listeners:
            listeners.remove(callback)

    def emit(self, event_name: str, **data) -> None:
        """Call all callbacks registered for *event_name* with **data** kwargs."""
        for callback in list(self._subscribers.get(event_name, [])):
            callback(**data)
