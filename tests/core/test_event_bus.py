"""Unit tests for EventBus — the pub/sub backbone used by all game systems
and HUD transient effects.

The EventBus is tested in complete isolation: no Pygame, no game state.
"""
from __future__ import annotations

import pytest
from src.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# subscribe
# ---------------------------------------------------------------------------
class TestEventBusSubscribe:
    def test_subscribe_registers_callback_and_emit_calls_it(self):
        bus = EventBus()
        calls: list[dict] = []
        bus.subscribe('evt', lambda **kw: calls.append(kw))
        bus.emit('evt')
        assert len(calls) == 1

    def test_subscribe_same_callback_twice_is_idempotent(self):
        """Registering the same callback object twice must not double-fire."""
        bus = EventBus()
        calls: list[int] = []
        cb = lambda **kw: calls.append(1)
        bus.subscribe('evt', cb)
        bus.subscribe('evt', cb)
        bus.emit('evt')
        assert len(calls) == 1

    def test_subscribe_two_different_callbacks_both_fire(self):
        bus = EventBus()
        a: list[int] = []
        b: list[int] = []
        bus.subscribe('evt', lambda **kw: a.append(1))
        bus.subscribe('evt', lambda **kw: b.append(1))
        bus.emit('evt')
        assert len(a) == 1
        assert len(b) == 1

    def test_subscribe_to_different_events_independently(self):
        bus = EventBus()
        a: list[int] = []
        b: list[int] = []
        bus.subscribe('event_a', lambda **kw: a.append(1))
        bus.subscribe('event_b', lambda **kw: b.append(1))
        bus.emit('event_a')
        assert a == [1]
        assert b == []

    def test_subscribe_on_unknown_event_does_not_raise(self):
        bus = EventBus()
        bus.subscribe('never_emitted', lambda **kw: None)  # must not raise


# ---------------------------------------------------------------------------
# unsubscribe
# ---------------------------------------------------------------------------
class TestEventBusUnsubscribe:
    def test_unsubscribe_removes_registered_callback(self):
        bus = EventBus()
        calls: list[int] = []
        cb = lambda **kw: calls.append(1)
        bus.subscribe('evt', cb)
        bus.unsubscribe('evt', cb)
        bus.emit('evt')
        assert calls == []

    def test_unsubscribe_nonexistent_callback_is_noop(self):
        """Unsubscribing a callback that was never registered must not raise."""
        bus = EventBus()
        cb = lambda **kw: None
        bus.unsubscribe('evt', cb)  # must not raise

    def test_unsubscribe_from_unknown_event_is_noop(self):
        """Unsubscribing from an event with no subscribers must not raise."""
        bus = EventBus()
        cb = lambda **kw: None
        bus.subscribe('evt', cb)
        bus.unsubscribe('other_evt', cb)  # different event — no-op

    def test_unsubscribe_leaves_other_callbacks_intact(self):
        """Removing one callback must leave sibling callbacks registered."""
        bus = EventBus()
        a: list[int] = []
        b: list[int] = []
        cb_a = lambda **kw: a.append(1)
        cb_b = lambda **kw: b.append(1)
        bus.subscribe('evt', cb_a)
        bus.subscribe('evt', cb_b)
        bus.unsubscribe('evt', cb_a)
        bus.emit('evt')
        assert a == []
        assert b == [1]

    def test_unsubscribe_twice_is_idempotent(self):
        """Calling unsubscribe twice for the same callback must not raise."""
        bus = EventBus()
        cb = lambda **kw: None
        bus.subscribe('evt', cb)
        bus.unsubscribe('evt', cb)
        bus.unsubscribe('evt', cb)  # second call must not raise


# ---------------------------------------------------------------------------
# emit
# ---------------------------------------------------------------------------
class TestEventBusEmit:
    def test_emit_passes_keyword_args_to_callback(self):
        bus = EventBus()
        received: dict = {}

        def cb(**kw: object) -> None:
            received.update(kw)

        bus.subscribe('evt', cb)
        bus.emit('evt', player=42, amount=10)
        assert received == {'player': 42, 'amount': 10}

    def test_emit_with_no_subscribers_does_not_raise(self):
        bus = EventBus()
        bus.emit('no_subscribers_event')  # must not raise

    def test_emit_with_no_kwargs_fires_callback_with_empty_payload(self):
        bus = EventBus()
        payloads: list[dict] = []
        bus.subscribe('evt', lambda **kw: payloads.append(kw))
        bus.emit('evt')
        assert payloads == [{}]

    def test_emit_only_fires_matching_event_subscribers(self):
        bus = EventBus()
        a: list[int] = []
        b: list[int] = []
        bus.subscribe('player.damaged', lambda **kw: a.append(1))
        bus.subscribe('level.up',       lambda **kw: b.append(1))
        bus.emit('player.damaged')
        assert a == [1]
        assert b == []

    def test_emit_fires_all_subscribers_in_registration_order(self):
        bus = EventBus()
        order: list[int] = []
        bus.subscribe('evt', lambda **kw: order.append(1))
        bus.subscribe('evt', lambda **kw: order.append(2))
        bus.subscribe('evt', lambda **kw: order.append(3))
        bus.emit('evt')
        assert order == [1, 2, 3]

    def test_emit_multiple_times_accumulates_calls(self):
        bus = EventBus()
        calls: list[int] = []
        bus.subscribe('evt', lambda **kw: calls.append(1))
        bus.emit('evt')
        bus.emit('evt')
        bus.emit('evt')
        assert len(calls) == 3

    def test_emit_dotted_event_name_works(self):
        """Event names containing dots are treated as opaque strings."""
        bus = EventBus()
        calls: list[int] = []
        bus.subscribe('player.damaged', lambda **kw: calls.append(1))
        bus.emit('player.damaged', amount=5)
        assert calls == [1]


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------
class TestEventBusClear:
    def test_clear_removes_all_subscriptions(self):
        bus = EventBus()
        calls: list[str] = []
        bus.subscribe('evt_a', lambda **kw: calls.append('a'))
        bus.subscribe('evt_b', lambda **kw: calls.append('b'))
        bus.clear()
        bus.emit('evt_a')
        bus.emit('evt_b')
        assert calls == []

    def test_emit_after_clear_does_not_raise(self):
        bus = EventBus()
        bus.subscribe('evt', lambda **kw: None)
        bus.clear()
        bus.emit('evt')  # must not raise

    def test_subscribe_after_clear_works_normally(self):
        bus = EventBus()
        bus.subscribe('evt', lambda **kw: None)
        bus.clear()
        calls: list[int] = []
        bus.subscribe('evt', lambda **kw: calls.append(1))
        bus.emit('evt')
        assert calls == [1]


# ---------------------------------------------------------------------------
# HUD-specific event names (used by HUD for transient effects)
# ---------------------------------------------------------------------------
class TestEventBusHUDEvents:
    def test_player_damaged_event_fires_subscriber(self):
        bus = EventBus()
        received: list[dict] = []
        bus.subscribe('player_damaged', lambda **kw: received.append(kw))
        bus.emit('player_damaged', player=None, amount=25)
        assert len(received) == 1
        assert received[0]['amount'] == 25

    def test_player_dot_damaged_event_fires_subscriber(self):
        """The HUD subscribes to both 'player.damaged' and 'player_damaged'."""
        bus = EventBus()
        received: list[int] = []
        bus.subscribe('player.damaged', lambda **kw: received.append(1))
        bus.emit('player.damaged', amount=10)
        assert received == [1]

    def test_level_up_event_fires_subscriber(self):
        bus = EventBus()
        received: list[dict] = []
        bus.subscribe('level_up', lambda **kw: received.append(kw))
        bus.emit('level_up', player=None, new_level=3)
        assert received[0]['new_level'] == 3

    def test_zone_entered_event_fires_subscriber(self):
        bus = EventBus()
        zones_seen: list[object] = []
        sentinel = object()
        bus.subscribe('zone_entered', lambda **kw: zones_seen.append(kw.get('zone')))
        bus.emit('zone_entered', zone=sentinel)
        assert zones_seen == [sentinel]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
class TestEventBusModuleSingleton:
    def test_module_level_event_bus_is_event_bus_instance(self):
        from src.core.event_bus import event_bus
        assert isinstance(event_bus, EventBus)

    def test_singleton_subscribe_and_emit_work(self):
        from src.core.event_bus import event_bus
        calls: list[int] = []
        cb = lambda **kw: calls.append(1)
        event_bus.subscribe('_test_singleton_evt', cb)
        event_bus.emit('_test_singleton_evt')
        event_bus.unsubscribe('_test_singleton_evt', cb)  # cleanup
        assert calls == [1]
