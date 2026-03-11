"""Unit tests for src.core.event_bus.EventBus.

EventBus has no Pygame dependency, so these tests run without pygame init.
"""
import pytest

from src.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Subscribe / emit – happy paths
# ---------------------------------------------------------------------------

def test_subscribe_and_emit_calls_callback():
    bus = EventBus()
    received = []
    bus.subscribe("test_event", lambda **kw: received.append(kw))
    bus.emit("test_event", value=42)
    assert received == [{"value": 42}]


def test_multiple_subscribers_all_called_in_order():
    bus = EventBus()
    calls: list = []
    bus.subscribe("ev", lambda **kw: calls.append("first"))
    bus.subscribe("ev", lambda **kw: calls.append("second"))
    bus.emit("ev")
    assert calls == ["first", "second"]


def test_emit_kwargs_forwarded_to_callback():
    bus = EventBus()
    received: dict = {}

    def capture(**kw):
        received.update(kw)

    bus.subscribe("data", capture)
    bus.emit("data", x=10, y=20, label="hello")
    assert received == {"x": 10, "y": 20, "label": "hello"}


def test_emit_no_kwargs_calls_callback_with_empty_dict():
    bus = EventBus()
    calls: list = []
    bus.subscribe("ping", lambda **kw: calls.append(kw))
    bus.emit("ping")
    assert calls == [{}]


# ---------------------------------------------------------------------------
# Unsubscribe
# ---------------------------------------------------------------------------

def test_unsubscribe_prevents_future_calls():
    bus = EventBus()
    calls: list = []
    cb = lambda **kw: calls.append(1)
    bus.subscribe("ev", cb)
    bus.unsubscribe("ev", cb)
    bus.emit("ev")
    assert calls == []


def test_unsubscribe_only_removes_specified_callback():
    bus = EventBus()
    calls: list = []
    cb_a = lambda **kw: calls.append("a")
    cb_b = lambda **kw: calls.append("b")
    bus.subscribe("ev", cb_a)
    bus.subscribe("ev", cb_b)
    bus.unsubscribe("ev", cb_a)
    bus.emit("ev")
    assert calls == ["b"]


def test_unsubscribe_nonexistent_event_name_is_safe():
    bus = EventBus()
    # Should not raise even though "ghost" was never subscribed to.
    bus.unsubscribe("ghost", lambda **kw: None)


def test_unsubscribe_nonexistent_callback_is_safe():
    bus = EventBus()
    cb = lambda **kw: None
    bus.subscribe("ev", lambda **kw: None)
    # cb was never registered; should not raise.
    bus.unsubscribe("ev", cb)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_emit_unknown_event_does_not_raise():
    bus = EventBus()
    bus.emit("never_registered", x=1)


def test_emit_does_not_cross_contaminate_events():
    bus = EventBus()
    a_calls: list = []
    b_calls: list = []
    bus.subscribe("A", lambda **kw: a_calls.append(1))
    bus.subscribe("B", lambda **kw: b_calls.append(1))
    bus.emit("A")
    assert a_calls == [1]
    assert b_calls == []


def test_subscribing_same_callback_twice_calls_it_twice():
    bus = EventBus()
    calls: list = []
    cb = lambda **kw: calls.append(1)
    bus.subscribe("ev", cb)
    bus.subscribe("ev", cb)
    bus.emit("ev")
    assert calls == [1, 1]


def test_callback_mutation_during_emit_is_safe():
    """Emit iterates over a *copy* of the subscriber list so removing a
    callback inside the callback itself does not raise."""
    bus = EventBus()
    calls: list = []

    def self_removing(**kw):
        calls.append(1)
        bus.unsubscribe("ev", self_removing)

    bus.subscribe("ev", self_removing)
    bus.emit("ev")          # Should not raise
    bus.emit("ev")          # self_removing was removed, calls stays at 1
    assert calls == [1]
