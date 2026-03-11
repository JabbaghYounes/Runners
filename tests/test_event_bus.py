"""Tests for EventBus."""
import pytest
from src.core.event_bus import EventBus


def test_subscribe_and_emit_calls_callback():
    bus = EventBus()
    received = []
    bus.subscribe("test_event", lambda **kw: received.append(kw))
    bus.emit("test_event", value=42)
    assert received == [{"value": 42}]


def test_multiple_subscribers_all_called():
    bus = EventBus()
    log: list[int] = []
    bus.subscribe("ping", lambda **_: log.append(1))
    bus.subscribe("ping", lambda **_: log.append(2))
    bus.emit("ping")
    assert log == [1, 2]


def test_emit_unknown_event_is_noop():
    bus = EventBus()
    # Must not raise
    bus.emit("no_such_event", data="x")


def test_unsubscribe_stops_callback():
    bus = EventBus()
    log: list[int] = []
    cb = lambda **_: log.append(1)  # noqa: E731
    bus.subscribe("evt", cb)
    bus.emit("evt")
    assert log == [1]
    bus.unsubscribe("evt", cb)
    bus.emit("evt")
    assert log == [1]  # not called again


def test_unsubscribe_nonexistent_is_noop():
    bus = EventBus()
    cb = lambda **_: None  # noqa: E731
    # Should not raise even if callback was never registered
    bus.unsubscribe("evt", cb)


def test_subscribe_same_callback_twice_not_duplicated():
    bus = EventBus()
    log: list[int] = []
    cb = lambda **_: log.append(1)  # noqa: E731
    bus.subscribe("evt", cb)
    bus.subscribe("evt", cb)
    bus.emit("evt")
    assert log == [1]


def test_kwargs_forwarded_correctly():
    bus = EventBus()
    received = {}
    bus.subscribe("data", lambda zone, extra=None, **_: received.update(zone=zone, extra=extra))
    bus.subscribe("data", lambda zone, extra=None, **_: None)  # second subscriber

    class FakeZone:
        name = "alpha"

    bus.emit("data", zone=FakeZone(), extra="hello")
    assert received["extra"] == "hello"
    assert received["zone"].name == "alpha"


def test_emit_calls_snapshot_so_unsubscribe_during_emit_is_safe():
    """Unsubscribing inside a callback must not cause iteration errors."""
    bus = EventBus()
    log: list[int] = []

    def self_removing(**_):
        bus.unsubscribe("evt", self_removing)
        log.append(1)

    bus.subscribe("evt", self_removing)
    bus.emit("evt")
    bus.emit("evt")   # second emit must not call the removed callback
    assert log == [1]
