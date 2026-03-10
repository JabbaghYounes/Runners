"""Unit tests for the EventBus pub/sub system."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from src.events import EventBus


# =====================================================================
# Subscribe / Publish
# =====================================================================

class TestSubscribePublish:

    def test_subscriber_receives_event(self):
        bus = EventBus()
        received = []
        bus.subscribe("test", lambda **kw: received.append(kw))
        bus.publish("test", value=42)
        assert len(received) == 1
        assert received[0]["value"] == 42

    def test_multiple_subscribers(self):
        bus = EventBus()
        a, b = [], []
        bus.subscribe("test", lambda **kw: a.append(kw))
        bus.subscribe("test", lambda **kw: b.append(kw))
        bus.publish("test", x=1)
        assert len(a) == 1
        assert len(b) == 1

    def test_different_event_types_isolated(self):
        bus = EventBus()
        a_events, b_events = [], []
        bus.subscribe("event_a", lambda **kw: a_events.append(kw))
        bus.subscribe("event_b", lambda **kw: b_events.append(kw))
        bus.publish("event_a", data="a")
        assert len(a_events) == 1
        assert len(b_events) == 0

    def test_publish_with_no_subscribers(self):
        """Publishing an event with no subscribers should not raise."""
        bus = EventBus()
        bus.publish("nobody_listens", value=123)  # should not raise

    def test_publish_no_kwargs(self):
        bus = EventBus()
        received = []
        bus.subscribe("ping", lambda **kw: received.append(kw))
        bus.publish("ping")
        assert len(received) == 1
        assert received[0] == {}

    def test_publish_multiple_kwargs(self):
        bus = EventBus()
        received = []
        bus.subscribe("multi", lambda **kw: received.append(kw))
        bus.publish("multi", a=1, b="hello", c=[1, 2, 3])
        assert received[0] == {"a": 1, "b": "hello", "c": [1, 2, 3]}

    def test_subscriber_called_in_order(self):
        bus = EventBus()
        order = []
        bus.subscribe("test", lambda **kw: order.append("first"))
        bus.subscribe("test", lambda **kw: order.append("second"))
        bus.publish("test")
        assert order == ["first", "second"]


# =====================================================================
# Unsubscribe
# =====================================================================

class TestUnsubscribe:

    def test_unsubscribed_callback_not_called(self):
        bus = EventBus()
        received = []
        callback = lambda **kw: received.append(kw)
        bus.subscribe("test", callback)
        bus.unsubscribe("test", callback)
        bus.publish("test", value=1)
        assert len(received) == 0

    def test_unsubscribe_nonexistent_callback(self):
        """Unsubscribing a callback that was never subscribed should not raise."""
        bus = EventBus()
        bus.unsubscribe("test", lambda **kw: None)  # should not raise

    def test_unsubscribe_nonexistent_event(self):
        """Unsubscribing from a never-used event type should not raise."""
        bus = EventBus()
        bus.unsubscribe("nonexistent", lambda **kw: None)

    def test_unsubscribe_one_leaves_others(self):
        bus = EventBus()
        a, b = [], []
        cb_a = lambda **kw: a.append(kw)
        cb_b = lambda **kw: b.append(kw)
        bus.subscribe("test", cb_a)
        bus.subscribe("test", cb_b)
        bus.unsubscribe("test", cb_a)
        bus.publish("test", value=1)
        assert len(a) == 0
        assert len(b) == 1


# =====================================================================
# Internal state
# =====================================================================

class TestEventBusInternals:

    def test_listeners_dict_initialized_empty(self):
        bus = EventBus()
        assert bus._listeners == {}

    def test_subscribe_creates_listener_list(self):
        bus = EventBus()
        bus.subscribe("event", lambda **kw: None)
        assert "event" in bus._listeners
        assert len(bus._listeners["event"]) == 1

    def test_multiple_events_tracked(self):
        bus = EventBus()
        bus.subscribe("a", lambda **kw: None)
        bus.subscribe("b", lambda **kw: None)
        assert "a" in bus._listeners
        assert "b" in bus._listeners


# =====================================================================
# Game-specific event contracts
# =====================================================================

class TestGameEventContracts:
    """Verify the event contracts used by the PvE enemy system."""

    def test_enemy_killed_event_shape(self):
        bus = EventBus()
        received = []
        bus.subscribe("enemy_killed", lambda **kw: received.append(kw))
        bus.publish(
            "enemy_killed",
            enemy="enemy_obj",
            killer="player_obj",
            xp_reward=25,
            loot_table_id="enemy_scout",
        )
        ev = received[0]
        assert ev["enemy"] == "enemy_obj"
        assert ev["killer"] == "player_obj"
        assert ev["xp_reward"] == 25
        assert ev["loot_table_id"] == "enemy_scout"

    def test_entity_hit_event_shape(self):
        bus = EventBus()
        received = []
        bus.subscribe("entity_hit", lambda **kw: received.append(kw))
        bus.publish("entity_hit", target="enemy", damage=20, source="player")
        ev = received[0]
        assert ev["target"] == "enemy"
        assert ev["damage"] == 20
        assert ev["source"] == "player"

    def test_shot_fired_event_shape(self):
        bus = EventBus()
        received = []
        bus.subscribe("shot_fired", lambda **kw: received.append(kw))
        bus.publish("shot_fired", source="enemy_obj")
        assert received[0]["source"] == "enemy_obj"
