"""Integration tests for HUD — event subscription, state management, rendering."""

from __future__ import annotations

import pygame
import pytest

from src.events import EventBus
from src.ui.hud import HUD


# ======================================================================
# Helpers
# ======================================================================


class EventTracker:
    """Tracks whether specific event handlers are registered on the bus."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def has_subscribers(self, event_type: str) -> bool:
        listeners = self._bus._listeners.get(event_type, [])
        return len(listeners) > 0

    def subscriber_count(self, event_type: str) -> int:
        return len(self._bus._listeners.get(event_type, []))


# ======================================================================
# HUD event handling tests
# ======================================================================


class TestHUDEventSubscription:
    """Verify the HUD subscribes to the correct events on init."""

    @pytest.fixture
    def bus(self):
        return EventBus()

    @pytest.fixture
    def hud(self, bus):
        return HUD(bus, screen_width=1280, screen_height=720)

    def test_subscribes_to_round_tick(self, bus, hud):
        tracker = EventTracker(bus)
        assert tracker.has_subscribers("round_tick")

    def test_subscribes_to_round_started(self, bus, hud):
        tracker = EventTracker(bus)
        assert tracker.has_subscribers("round_started")

    def test_subscribes_to_extraction_started(self, bus, hud):
        tracker = EventTracker(bus)
        assert tracker.has_subscribers("extraction_started")

    def test_subscribes_to_extraction_progress(self, bus, hud):
        tracker = EventTracker(bus)
        assert tracker.has_subscribers("extraction_progress")

    def test_subscribes_to_extraction_cancelled(self, bus, hud):
        tracker = EventTracker(bus)
        assert tracker.has_subscribers("extraction_cancelled")

    def test_subscribes_to_extraction_complete(self, bus, hud):
        tracker = EventTracker(bus)
        assert tracker.has_subscribers("extraction_complete")

    def test_subscribes_to_timer_warning(self, bus, hud):
        tracker = EventTracker(bus)
        assert tracker.has_subscribers("timer_warning")


class TestHUDEventHandling:
    """Verify HUD state changes in response to events."""

    @pytest.fixture
    def bus(self):
        return EventBus()

    @pytest.fixture
    def hud(self, bus):
        return HUD(bus, screen_width=1280, screen_height=720)

    def test_round_started_sets_timer(self, bus, hud):
        bus.publish("round_started", timer=300.0)
        assert hud._timer._remaining == pytest.approx(300.0)
        assert hud._timer._total == 300.0

    def test_round_tick_updates_timer(self, bus, hud):
        bus.publish("round_tick", remaining=450.0, total=900.0)
        assert hud._timer._remaining == pytest.approx(450.0)
        assert hud._timer._total == 900.0

    def test_extraction_started_shows_bar(self, bus, hud):
        bus.publish("extraction_started", zone_name="extract_a", duration=5.0)
        assert hud._extraction_bar._visible
        assert hud._is_extracting

    def test_extraction_started_hides_prompt(self, bus, hud):
        hud.set_near_extraction(True)
        assert hud._extraction_prompt._target_alpha == 1.0

        bus.publish("extraction_started", zone_name="extract_a", duration=5.0)
        assert hud._extraction_prompt._target_alpha == 0.0

    def test_extraction_progress_updates_bar(self, bus, hud):
        bus.publish("extraction_started", zone_name="extract_a", duration=5.0)
        bus.publish("extraction_progress", progress=2.5, duration=5.0)
        assert hud._extraction_bar._progress == pytest.approx(0.5)

    def test_extraction_cancelled_hides_bar(self, bus, hud):
        bus.publish("extraction_started", zone_name="extract_a", duration=5.0)
        assert hud._extraction_bar._visible

        bus.publish("extraction_cancelled", reason="interrupted")
        assert not hud._extraction_bar._visible
        assert not hud._is_extracting

    def test_extraction_cancelled_reshows_prompt_when_near(self, bus, hud):
        hud.set_near_extraction(True)
        bus.publish("extraction_started", zone_name="extract_a", duration=5.0)
        # Prompt hidden during extraction
        assert hud._extraction_prompt._target_alpha == 0.0

        bus.publish("extraction_cancelled", reason="left_zone")
        # Since still near extraction, prompt should reappear
        assert hud._extraction_prompt._target_alpha == 1.0

    def test_extraction_complete_hides_bar(self, bus, hud):
        bus.publish("extraction_started", zone_name="extract_a", duration=5.0)
        bus.publish("extraction_complete", loot_summary={})
        assert not hud._extraction_bar._visible
        assert not hud._is_extracting

    def test_extraction_complete_hides_prompt(self, bus, hud):
        hud.set_near_extraction(True)
        bus.publish("extraction_started", zone_name="extract_a", duration=5.0)
        bus.publish("extraction_complete", loot_summary={})
        assert hud._extraction_prompt._target_alpha == 0.0


class TestHUDPublicAPI:
    """Test the public API methods on HUD."""

    @pytest.fixture
    def bus(self):
        return EventBus()

    @pytest.fixture
    def hud(self, bus):
        return HUD(bus, screen_width=1280, screen_height=720)

    def test_set_player_health(self, hud):
        hud.set_player_health(50, 100)
        assert hud._health_bar._target == pytest.approx(0.5)

    def test_set_near_extraction_true(self, hud):
        hud.set_near_extraction(True)
        assert hud._is_near_extraction
        assert hud._extraction_prompt._target_alpha == 1.0

    def test_set_near_extraction_false(self, hud):
        hud.set_near_extraction(True)
        hud.set_near_extraction(False)
        assert not hud._is_near_extraction
        assert hud._extraction_prompt._target_alpha == 0.0

    def test_set_near_extraction_suppressed_during_extracting(self, bus, hud):
        """Prompt should not show while actively extracting."""
        bus.publish("extraction_started", zone_name="test", duration=5.0)
        hud.set_near_extraction(True)
        # During extraction, prompt should stay hidden
        assert hud._extraction_prompt._target_alpha == 0.0

    def test_set_extraction_zones(self, hud):
        zones = [object(), object()]
        hud.set_extraction_zones(zones)
        assert len(hud._minimap._extraction_zones) == 2

    def test_set_extracting(self, hud):
        hud.set_extracting(True)
        assert hud._minimap._is_extracting

    def test_set_map_size(self, hud):
        hud.set_map_size(5000, 4000)
        assert hud._minimap._map_w == 5000
        assert hud._minimap._map_h == 4000


class TestHUDRendering:
    """Verify HUD renders without errors in different states."""

    @pytest.fixture
    def bus(self):
        return EventBus()

    @pytest.fixture
    def hud(self, bus):
        return HUD(bus, screen_width=1280, screen_height=720)

    @pytest.fixture
    def surface(self):
        return pygame.Surface((1280, 720))

    def test_update_without_crash(self, hud):
        hud.update(0.016)

    def test_draw_without_crash(self, hud, surface):
        hud.update(0.016)
        hud.draw(surface)

    def test_draw_with_extraction_bar_visible(self, bus, hud, surface):
        bus.publish("extraction_started", zone_name="extract_a", duration=5.0)
        bus.publish("extraction_progress", progress=2.5, duration=5.0)
        hud.update(0.5)
        hud.draw(surface)

    def test_draw_with_timer_warning(self, bus, hud, surface):
        bus.publish("round_tick", remaining=45.0, total=900.0)
        hud.update(0.5)
        hud.draw(surface)

    def test_draw_with_timer_critical(self, bus, hud, surface):
        bus.publish("round_tick", remaining=10.0, total=900.0)
        hud.update(0.5)
        hud.draw(surface)

    def test_multiple_frames_no_crash(self, bus, hud, surface):
        bus.publish("round_started", timer=900.0)
        for i in range(60):
            bus.publish("round_tick", remaining=900.0 - i * 0.016, total=900.0)
            hud.update(0.016)
            hud.draw(surface)


class TestHUDCleanup:
    """Verify HUD unsubscribes on cleanup."""

    def test_cleanup_unsubscribes_all_events(self):
        bus = EventBus()
        hud = HUD(bus, screen_width=1280, screen_height=720)
        tracker = EventTracker(bus)

        # Before cleanup, events have subscribers
        assert tracker.has_subscribers("round_tick")

        hud.cleanup()

        # After cleanup, the HUD's handlers should be removed
        # (other subscribers might still exist, so we check count)
        # With only HUD subscribed, counts should be zero
        assert tracker.subscriber_count("round_tick") == 0
        assert tracker.subscriber_count("round_started") == 0
        assert tracker.subscriber_count("extraction_started") == 0
        assert tracker.subscriber_count("extraction_progress") == 0
        assert tracker.subscriber_count("extraction_cancelled") == 0
        assert tracker.subscriber_count("extraction_complete") == 0
        assert tracker.subscriber_count("timer_warning") == 0

    def test_cleanup_safe_to_call_twice(self):
        bus = EventBus()
        hud = HUD(bus, screen_width=1280, screen_height=720)
        hud.cleanup()
        hud.cleanup()  # Should not raise

    def test_events_not_processed_after_cleanup(self):
        bus = EventBus()
        hud = HUD(bus, screen_width=1280, screen_height=720)
        hud.cleanup()

        # Publishing events after cleanup should not affect HUD
        initial_remaining = hud._timer._remaining
        bus.publish("round_tick", remaining=100.0, total=900.0)
        assert hud._timer._remaining == initial_remaining
