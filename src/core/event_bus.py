"""Lightweight synchronous publish-subscribe event bus.

Systems never import each other directly; they communicate exclusively through
the EventBus so every subsystem stays independently testable.

Usage::

    bus = EventBus()

    def on_kill(*, killer, enemy):
        print(f"{killer} eliminated {enemy}")

    bus.subscribe("enemy_killed", on_kill)
    bus.emit("enemy_killed", killer=player, enemy=robot)
    bus.unsubscribe("enemy_killed", on_kill)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List


class EventBus:
    """Synchronous publish-subscribe broker.

    All listener invocations happen on the calling thread before ``emit``
    returns, so there is no deferred or async dispatch complexity.
    """

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable[..., None]]] = defaultdict(list)

    # ── Subscription ──────────────────────────────────────────────────────────

    def subscribe(self, event: str, callback: Callable[..., None]) -> None:
        """Register *callback* to be invoked whenever *event* is emitted."""
        if callback not in self._listeners[event]:
            self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., None]) -> None:
        """Remove *callback* from *event*'s listener list (no-op if absent)."""
        try:
            self._listeners[event].remove(callback)
        except ValueError:
            pass

    # ── Emission ──────────────────────────────────────────────────────────────

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Invoke every listener registered for *event* with **kwargs.

        Also accepts a single positional dict arg for backwards compatibility:
        ``emit("event", {"key": "val"})`` is equivalent to
        ``emit("event", key="val")``.
        """
        if args and isinstance(args[0], dict) and not kwargs:
            kwargs = args[0]
        for callback in list(self._listeners[event]):
            try:
                callback(**kwargs)
            except TypeError:
                # Fallback: pass kwargs dict as a single positional arg
                try:
                    callback(kwargs)
                except TypeError:
                    pass

    # publish is an alias for emit (used by some subsystems)
    def publish(self, event: str, **kwargs: Any) -> None:
        """Alias for :meth:`emit`."""
        self.emit(event, **kwargs)

    # ── Utility ───────────────────────────────────────────────────────────────

    def clear(self, event: str | None = None) -> None:
        """Remove listeners.

        Args:
            event: If given, clear only that event's listeners.
                   If ``None``, clear all listeners on the bus.
        """
        if event is None:
            self._listeners.clear()
        else:
            self._listeners.pop(event, None)

    def listener_count(self, event: str) -> int:
        """Return the number of listeners currently subscribed to *event*."""
        return len(self._listeners[event])


# Module-level singleton used by modules that import it directly.
event_bus = EventBus()
