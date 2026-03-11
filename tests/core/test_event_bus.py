"""Unit tests for src/core/event_bus.py.

These tests run without a Pygame display or audio device.
"""

import pytest
from src.core.event_bus import EventBus


class TestEventBus:
    def setup_method(self):
        self.bus = EventBus()

    # ── subscribe / emit ──────────────────────────────────────────────────────

    def test_emit_calls_subscriber(self):
        calls = []
        self.bus.subscribe("test_event", lambda **kw: calls.append(kw))
        self.bus.emit("test_event", value=42)
        assert calls == [{"value": 42}]

    def test_emit_calls_multiple_subscribers(self):
        results = []
        self.bus.subscribe("ev", lambda **kw: results.append(("a", kw)))
        self.bus.subscribe("ev", lambda **kw: results.append(("b", kw)))
        self.bus.emit("ev", x=1)
        assert len(results) == 2

    def test_emit_unknown_event_is_noop(self):
        # Should not raise
        self.bus.emit("never_subscribed")

    def test_emit_no_kwargs(self):
        called = []
        self.bus.subscribe("ping", lambda **kw: called.append(kw))
        self.bus.emit("ping")
        assert called == [{}]

    # ── unsubscribe ───────────────────────────────────────────────────────────

    def test_unsubscribe_stops_delivery(self):
        calls = []
        cb = lambda **kw: calls.append(1)
        self.bus.subscribe("ev", cb)
        self.bus.emit("ev")
        self.bus.unsubscribe("ev", cb)
        self.bus.emit("ev")
        assert len(calls) == 1

    def test_unsubscribe_missing_callback_is_noop(self):
        # Should not raise
        self.bus.unsubscribe("ev", lambda: None)

    def test_unsubscribe_during_emit_is_safe(self):
        """A listener may unsubscribe itself during emit without skipping others."""
        log = []

        def cb_a(**kw):
            log.append("a")
            self.bus.unsubscribe("ev", cb_a)

        def cb_b(**kw):
            log.append("b")

        self.bus.subscribe("ev", cb_a)
        self.bus.subscribe("ev", cb_b)
        self.bus.emit("ev")
        assert "a" in log and "b" in log

    # ── clear ─────────────────────────────────────────────────────────────────

    def test_clear_specific_event(self):
        calls = []
        self.bus.subscribe("ev", lambda **kw: calls.append(1))
        self.bus.clear("ev")
        self.bus.emit("ev")
        assert calls == []

    def test_clear_all(self):
        calls = []
        self.bus.subscribe("a", lambda **kw: calls.append("a"))
        self.bus.subscribe("b", lambda **kw: calls.append("b"))
        self.bus.clear()
        self.bus.emit("a")
        self.bus.emit("b")
        assert calls == []

    # ── listener_count ────────────────────────────────────────────────────────

    def test_listener_count(self):
        assert self.bus.listener_count("ev") == 0
        cb = lambda **kw: None
        self.bus.subscribe("ev", cb)
        assert self.bus.listener_count("ev") == 1
        self.bus.unsubscribe("ev", cb)
        assert self.bus.listener_count("ev") == 0
