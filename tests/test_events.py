"""Unit tests for the EventBus pub/sub system."""

from src.events import EventBus


class TestEventBus:
    """Tests for :class:`EventBus`."""

    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe("test_event", lambda **d: received.append(d))
        bus.publish("test_event", key="value")
        assert len(received) == 1
        assert received[0] == {"key": "value"}

    def test_unsubscribe(self):
        bus = EventBus()
        calls = []
        callback = lambda **d: calls.append(1)  # noqa: E731
        bus.subscribe("evt", callback)
        bus.publish("evt")
        assert len(calls) == 1

        bus.unsubscribe("evt", callback)
        bus.publish("evt")
        assert len(calls) == 1  # no additional call

    def test_unsubscribe_not_subscribed(self):
        """Unsubscribing a callback that was never registered should not raise."""
        bus = EventBus()
        bus.unsubscribe("evt", lambda **d: None)  # should not raise

    def test_multiple_subscribers(self):
        bus = EventBus()
        results: list[str] = []
        bus.subscribe("evt", lambda **d: results.append("a"))
        bus.subscribe("evt", lambda **d: results.append("b"))
        bus.publish("evt")
        assert results == ["a", "b"]

    def test_publish_no_subscribers(self):
        """Publishing an event with no subscribers should not raise."""
        bus = EventBus()
        bus.publish("nobody_listens", foo="bar")  # no error

    def test_publish_with_data(self):
        bus = EventBus()
        received = {}

        def handler(**data):
            received.update(data)

        bus.subscribe("data_event", handler)
        bus.publish("data_event", x=1, y=2, name="test")
        assert received == {"x": 1, "y": 2, "name": "test"}

    def test_duplicate_subscribe_ignored(self):
        """Subscribing the same callback twice should only call it once."""
        bus = EventBus()
        calls = []
        callback = lambda **d: calls.append(1)  # noqa: E731
        bus.subscribe("evt", callback)
        bus.subscribe("evt", callback)
        bus.publish("evt")
        assert len(calls) == 1

    def test_publish_empty_kwargs(self):
        bus = EventBus()
        received = []
        bus.subscribe("evt", lambda **d: received.append(d))
        bus.publish("evt")
        assert received == [{}]

    def test_independent_event_types(self):
        """Subscribers to one event type should not receive another."""
        bus = EventBus()
        a_calls: list[str] = []
        b_calls: list[str] = []
        bus.subscribe("a", lambda **d: a_calls.append("a"))
        bus.subscribe("b", lambda **d: b_calls.append("b"))
        bus.publish("a")
        assert a_calls == ["a"]
        assert b_calls == []

    def test_unsubscribe_nonexistent_event_type(self):
        """Unsubscribing from a never-registered event type should not raise."""
        bus = EventBus()
        bus.unsubscribe("never_registered", lambda **d: None)

    def test_same_callback_on_multiple_events(self):
        """A single callback can be subscribed to different event types."""
        bus = EventBus()
        calls: list[str] = []

        def handler(**data):
            calls.append(data.get("src", ""))

        bus.subscribe("event_a", handler)
        bus.subscribe("event_b", handler)
        bus.publish("event_a", src="a")
        bus.publish("event_b", src="b")
        assert calls == ["a", "b"]

    def test_callback_execution_order(self):
        """Callbacks should fire in subscription order."""
        bus = EventBus()
        order: list[int] = []
        bus.subscribe("evt", lambda **d: order.append(1))
        bus.subscribe("evt", lambda **d: order.append(2))
        bus.subscribe("evt", lambda **d: order.append(3))
        bus.publish("evt")
        assert order == [1, 2, 3]

    def test_publish_multiple_times(self):
        """Publishing the same event multiple times should call handler each time."""
        bus = EventBus()
        count = []
        bus.subscribe("evt", lambda **d: count.append(1))
        bus.publish("evt")
        bus.publish("evt")
        bus.publish("evt")
        assert len(count) == 3

    def test_unsubscribe_one_leaves_others(self):
        """Unsubscribing one callback should not affect other callbacks."""
        bus = EventBus()
        a_calls = []
        b_calls = []
        cb_a = lambda **d: a_calls.append(1)  # noqa: E731
        cb_b = lambda **d: b_calls.append(1)  # noqa: E731
        bus.subscribe("evt", cb_a)
        bus.subscribe("evt", cb_b)
        bus.unsubscribe("evt", cb_a)
        bus.publish("evt")
        assert a_calls == []
        assert b_calls == [1]

    def test_subscribe_after_unsubscribe(self):
        """Re-subscribing after unsubscribing should work."""
        bus = EventBus()
        calls = []
        callback = lambda **d: calls.append(1)  # noqa: E731
        bus.subscribe("evt", callback)
        bus.unsubscribe("evt", callback)
        bus.subscribe("evt", callback)
        bus.publish("evt")
        assert calls == [1]
