from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event: str, callback: Callable) -> None:
        if event not in self._listeners:
            self._listeners[event] = []
        if callback not in self._listeners[event]:
            self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable) -> None:
        if event in self._listeners:
            try:
                self._listeners[event].remove(callback)
            except ValueError:
                pass

    def emit(self, event: str, **kwargs: Any) -> None:
        for cb in list(self._listeners.get(event, [])):
            try:
                cb(**kwargs)
            except Exception as e:
                print(f"[EventBus] Error in handler for '{event}': {e}")

    def clear(self) -> None:
        self._listeners.clear()
