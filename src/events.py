"""Lightweight publish/subscribe event bus for decoupled system communication."""

from __future__ import annotations

from typing import Callable


class EventBus:
    """Simple pub/sub event system.

    Systems subscribe callbacks to named event types. When an event is
    published, all registered callbacks for that type are invoked with
    the provided keyword arguments.

    Example::

        bus = EventBus()
        bus.subscribe("enemy_killed", lambda **d: print(d))
        bus.publish("enemy_killed", xp=50, pos=(100, 200))
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[..., None]) -> None:
        """Register *callback* to be called when *event_type* is published."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        if callback not in self._listeners[event_type]:
            self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[..., None]) -> None:
        """Remove *callback* from *event_type* listeners.

        Silently does nothing if *callback* was not subscribed.
        """
        listeners = self._listeners.get(event_type)
        if listeners is not None:
            try:
                listeners.remove(callback)
            except ValueError:
                pass

    def publish(self, event_type: str, **data) -> None:
        """Invoke all callbacks registered for *event_type*.

        Each callback receives **data as keyword arguments.
        """
        for callback in self._listeners.get(event_type, []):
            callback(**data)
