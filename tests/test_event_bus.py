"""Unit tests for EventBus (src/core/event_bus.py).

Verifies:
- subscribe / emit roundtrip
- emit with no payload delivers an empty dict
- emit to an event with no subscribers is a safe no-op
- multiple subscribers per event, called in order
- unsubscribe prevents future delivery (silently handles missing callbacks)
- a handler may unsubscribe itself during dispatch without crashing
- clear() wipes all subscriptions
- the module-level ``event_bus`` singleton is an EventBus instance
"""

from __future__ import annotations

import pytest

from src.core.event_bus import EventBus, event_bus


# ---------------------------------------------------------------------------
# Autouse fixture: isolate each test from the module singleton's state
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Wipe the module-level singleton's subscriptions around every test."""
    event_bus.clear()
    yield
    event_bus.clear()


# ---------------------------------------------------------------------------
# Core subscribe / emit
# ---------------------------------------------------------------------------


class TestEventBusSubscribeAndEmit:
    def test_subscribe_then_emit_delivers_payload(self) -> None:
        received: list[dict] = []
        event_bus.subscribe("ev", received.append)
        event_bus.emit("ev", {"x": 42})
        assert received == [{"x": 42}]

    def test_emit_with_no_payload_delivers_empty_dict(self) -> None:
        received: list[dict] = []
        event_bus.subscribe("ev", received.append)
        event_bus.emit("ev")
        assert received == [{}]

    def test_emit_with_none_payload_delivers_empty_dict(self) -> None:
        received: list[dict] = []
        event_bus.subscribe("ev", received.append)
        event_bus.emit("ev", None)
        assert received == [{}]

    def test_emit_to_event_with_no_subscribers_is_noop(self) -> None:
        # Must not raise
        event_bus.emit("completely_unknown_event", {"data": 1})

    def test_multiple_subscribers_all_receive_payload(self) -> None:
        received_a: list[dict] = []
        received_b: list[dict] = []
        event_bus.subscribe("multi", received_a.append)
        event_bus.subscribe("multi", received_b.append)
        event_bus.emit("multi", {"val": 7})
        assert received_a == [{"val": 7}]
        assert received_b == [{"val": 7}]

    def test_subscribers_called_in_subscription_order(self) -> None:
        call_order: list[str] = []
        event_bus.subscribe("ordered", lambda _: call_order.append("first"))
        event_bus.subscribe("ordered", lambda _: call_order.append("second"))
        event_bus.emit("ordered", {})
        assert call_order == ["first", "second"]

    def test_different_events_do_not_cross_deliver(self) -> None:
        received_a: list[dict] = []
        received_b: list[dict] = []
        event_bus.subscribe("event_a", received_a.append)
        event_bus.subscribe("event_b", received_b.append)
        event_bus.emit("event_a", {})
        assert len(received_a) == 1
        assert received_b == []

    def test_callback_receives_exact_payload_reference(self) -> None:
        """The payload dict handed to the callback is the same object emitted."""
        received: list[dict] = []
        event_bus.subscribe("ref_test", received.append)
        payload = {"key": "value"}
        event_bus.emit("ref_test", payload)
        assert received[0] is payload

    def test_same_callback_can_subscribe_multiple_events(self) -> None:
        received: list[dict] = []
        event_bus.subscribe("alpha", received.append)
        event_bus.subscribe("beta", received.append)
        event_bus.emit("alpha", {"from": "alpha"})
        event_bus.emit("beta", {"from": "beta"})
        assert len(received) == 2


# ---------------------------------------------------------------------------
# Unsubscribe
# ---------------------------------------------------------------------------


class TestEventBusUnsubscribe:
    def test_unsubscribe_prevents_future_delivery(self) -> None:
        received: list[dict] = []
        cb = received.append
        event_bus.subscribe("unsub", cb)
        event_bus.unsubscribe("unsub", cb)
        event_bus.emit("unsub", {})
        assert received == []

    def test_unsubscribe_silently_ignores_callback_not_registered(self) -> None:
        # Should not raise
        event_bus.unsubscribe("no_such_event", lambda _: None)

    def test_unsubscribe_twice_is_silent(self) -> None:
        cb = lambda _: None  # noqa: E731
        event_bus.subscribe("ev", cb)
        event_bus.unsubscribe("ev", cb)
        event_bus.unsubscribe("ev", cb)  # Second call: silently ignored

    def test_unsubscribe_only_removes_specified_callback(self) -> None:
        received_a: list[dict] = []
        received_b: list[dict] = []
        event_bus.subscribe("multi_unsub", received_a.append)
        event_bus.subscribe("multi_unsub", received_b.append)
        event_bus.unsubscribe("multi_unsub", received_a.append)
        event_bus.emit("multi_unsub", {})
        # received_a was unsubscribed; received_b should still receive
        assert received_a == []
        assert len(received_b) == 1

    def test_subscriber_can_unsubscribe_itself_during_emit(self) -> None:
        """Iterating a copy of the subscriber list must allow self-removal."""
        received: list[dict] = []

        def self_removing(payload: dict) -> None:
            received.append(payload)
            event_bus.unsubscribe("self_unsub", self_removing)

        event_bus.subscribe("self_unsub", self_removing)
        event_bus.emit("self_unsub", {"n": 1})
        event_bus.emit("self_unsub", {"n": 2})  # Handler is already gone

        assert len(received) == 1
        assert received[0]["n"] == 1


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------


class TestEventBusClear:
    def test_clear_removes_all_subscriptions(self) -> None:
        received: list[dict] = []
        event_bus.subscribe("ev", received.append)
        event_bus.clear()
        event_bus.emit("ev", {})
        assert received == []

    def test_clear_affects_all_events(self) -> None:
        received: list[dict] = []
        event_bus.subscribe("ev1", received.append)
        event_bus.subscribe("ev2", received.append)
        event_bus.clear()
        event_bus.emit("ev1", {})
        event_bus.emit("ev2", {})
        assert received == []

    def test_new_subscriptions_work_after_clear(self) -> None:
        received: list[dict] = []
        event_bus.subscribe("ev", received.append)
        event_bus.clear()
        event_bus.subscribe("ev", received.append)
        event_bus.emit("ev", {"ok": True})
        assert received == [{"ok": True}]


# ---------------------------------------------------------------------------
# Fresh EventBus instance (not the singleton)
# ---------------------------------------------------------------------------


class TestEventBusInstance:
    def test_new_instance_is_independent_of_singleton(self) -> None:
        bus = EventBus()
        received: list[dict] = []
        bus.subscribe("local", received.append)
        # Emitting on the singleton must NOT reach the fresh instance
        event_bus.emit("local", {"from": "singleton"})
        assert received == []

    def test_new_instance_subscribe_emit_works(self) -> None:
        bus = EventBus()
        received: list[dict] = []
        bus.subscribe("ev", received.append)
        bus.emit("ev", {"hello": "world"})
        assert received == [{"hello": "world"}]

    def test_module_level_event_bus_is_eventbus_instance(self) -> None:
        assert isinstance(event_bus, EventBus)
