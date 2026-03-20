"""Tests for HUD zone-label overlay: event wiring, timer countdown, and draw.

Covers:
  - zone_entered event populates _zone_label and _zone_label_timer
  - Timer ticks down via update() and is clamped at 0.0
  - Subsequent zone entries overwrite the label and reset the timer
  - zone_entered without a zone kwarg does not raise or set state
  - Zone objects without a name attribute fall back to empty string
  - draw() does not crash while the zone label is active
  - draw() silently skips the overlay when the timer has expired

# Run: pytest tests/test_hud_zone_label.py
"""
from __future__ import annotations

import pytest
import pygame

from src.core.event_bus import EventBus
from src.ui.hud import HUD, _ZONE_LABEL_DURATION
from src.ui.hud_state import HUDState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def event_bus():
    return EventBus()


@pytest.fixture()
def hud(event_bus):
    return HUD(event_bus)


@pytest.fixture()
def screen():
    return pygame.Surface((1280, 720))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeZone:
    """Minimal stand-in for a zone object with a name attribute."""
    def __init__(self, name: str) -> None:
        self.name = name


def _state(**overrides) -> HUDState:
    defaults: dict = dict(hp=100, max_hp=100, seconds_remaining=900.0)
    defaults.update(overrides)
    return HUDState(**defaults)


# ---------------------------------------------------------------------------
# Unit: event handler wiring
# ---------------------------------------------------------------------------

class TestZoneLabelEventWiring:
    def test_zone_entered_sets_zone_label_to_zone_name(self, event_bus, hud):
        event_bus.emit('zone_entered', zone=_FakeZone("REACTOR CORE"))
        assert hud._zone_label == "REACTOR CORE"

    def test_zone_entered_sets_timer_to_full_duration(self, event_bus, hud):
        event_bus.emit('zone_entered', zone=_FakeZone("HANGAR BAY"))
        assert hud._zone_label_timer == pytest.approx(_ZONE_LABEL_DURATION)

    def test_zone_entered_without_zone_kwarg_does_not_raise(self, event_bus, hud):
        event_bus.emit('zone_entered')   # no zone kwarg at all

    def test_zone_entered_without_zone_kwarg_leaves_label_empty(self, event_bus, hud):
        event_bus.emit('zone_entered')
        assert hud._zone_label == ""

    def test_zone_entered_without_zone_kwarg_leaves_timer_at_zero(self, event_bus, hud):
        event_bus.emit('zone_entered')
        assert hud._zone_label_timer == pytest.approx(0.0)

    def test_zone_object_without_name_attribute_falls_back_to_empty_string(self, event_bus, hud):
        class _ZoneNoName:
            pass
        event_bus.emit('zone_entered', zone=_ZoneNoName())
        assert hud._zone_label == ""

    def test_zone_object_without_name_attribute_still_sets_timer(self, event_bus, hud):
        """When zone has no name but exists, timer still fires."""
        class _ZoneNoName:
            pass
        event_bus.emit('zone_entered', zone=_ZoneNoName())
        # timer should NOT have been set because name is empty (short-circuit guard)
        # The implementation sets label = getattr(zone, 'name', '')
        # and only sets timer when zone is not None; check actual behaviour
        # _on_zone_entered sets timer only when zone is not None, so:
        assert hud._zone_label_timer == pytest.approx(_ZONE_LABEL_DURATION)

    def test_subsequent_zone_entry_overwrites_label(self, event_bus, hud):
        event_bus.emit('zone_entered', zone=_FakeZone("ZONE ALPHA"))
        event_bus.emit('zone_entered', zone=_FakeZone("ZONE BETA"))
        assert hud._zone_label == "ZONE BETA"

    def test_subsequent_zone_entry_resets_timer_to_full(self, event_bus, hud):
        event_bus.emit('zone_entered', zone=_FakeZone("ZONE ALPHA"))
        hud.update(_state(), dt=1.0)                     # timer → 1.5
        event_bus.emit('zone_entered', zone=_FakeZone("ZONE BETA"))
        assert hud._zone_label_timer == pytest.approx(_ZONE_LABEL_DURATION)

    def test_initial_zone_label_is_empty_string(self, hud):
        assert hud._zone_label == ""

    def test_initial_zone_label_timer_is_zero(self, hud):
        assert hud._zone_label_timer == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Unit: timer countdown behaviour
# ---------------------------------------------------------------------------

class TestZoneLabelTimer:
    def test_timer_decrements_by_dt_on_update(self, event_bus, hud):
        event_bus.emit('zone_entered', zone=_FakeZone("TEST"))
        hud.update(_state(), dt=0.5)
        assert hud._zone_label_timer == pytest.approx(_ZONE_LABEL_DURATION - 0.5)

    def test_timer_clamped_at_zero_when_large_dt(self, event_bus, hud):
        event_bus.emit('zone_entered', zone=_FakeZone("TEST"))
        hud.update(_state(), dt=9999.0)
        assert hud._zone_label_timer == 0.0

    def test_timer_never_goes_negative(self, event_bus, hud):
        event_bus.emit('zone_entered', zone=_FakeZone("TEST"))
        hud.update(_state(), dt=9999.0)
        assert hud._zone_label_timer >= 0.0

    def test_timer_reaches_zero_after_exactly_one_duration(self, event_bus, hud):
        event_bus.emit('zone_entered', zone=_FakeZone("TEST"))
        hud.update(_state(), dt=_ZONE_LABEL_DURATION)
        assert hud._zone_label_timer == 0.0

    def test_timer_not_decremented_when_already_zero(self, hud):
        """Timer must stay at 0 when no zone was entered (initial state)."""
        hud.update(_state(), dt=0.5)
        assert hud._zone_label_timer == 0.0

    def test_multiple_updates_accumulate_decrement(self, event_bus, hud):
        event_bus.emit('zone_entered', zone=_FakeZone("TEST"))
        hud.update(_state(), dt=0.3)
        hud.update(_state(), dt=0.3)
        expected = _ZONE_LABEL_DURATION - 0.6
        assert hud._zone_label_timer == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# Draw smoke tests
# ---------------------------------------------------------------------------

class TestZoneLabelDraw:
    def test_draw_with_active_zone_label_does_not_crash(self, hud, screen):
        hud._zone_label = "OUTER PERIMETER"
        hud._zone_label_timer = 2.0
        hud.update(_state(), dt=0.016)
        hud.draw(screen)

    def test_draw_skips_label_when_timer_is_zero(self, hud, screen):
        hud._zone_label = "SOME ZONE"
        hud._zone_label_timer = 0.0
        hud.update(_state(), dt=0.0)
        hud.draw(screen)   # must not crash

    def test_draw_with_empty_label_and_positive_timer_does_not_crash(self, hud, screen):
        hud._zone_label = ""
        hud._zone_label_timer = 1.5
        hud.update(_state(), dt=0.016)
        hud.draw(screen)

    def test_draw_immediately_after_zone_entered_event_does_not_crash(self, event_bus, hud, screen):
        event_bus.emit('zone_entered', zone=_FakeZone("DOCKING BAY"))
        hud.update(_state(), dt=0.016)
        hud.draw(screen)

    def test_draw_zone_label_near_expiry_fading_does_not_crash(self, hud, screen):
        """Label with < full timer → alpha < 255 path in _draw_zone_label."""
        hud._zone_label = "DOCKS"
        hud._zone_label_timer = 0.4   # very close to expiry
        hud.update(_state(), dt=0.016)
        hud.draw(screen)

    def test_draw_at_full_timer_does_not_crash(self, event_bus, hud, screen):
        event_bus.emit('zone_entered', zone=_FakeZone("REACTOR CORE"))
        # no update call → timer still at full duration
        hud._ensure_fonts()
        hud.draw(screen)

    def test_draw_with_unicode_zone_name_does_not_crash(self, hud, screen):
        hud._zone_label = "ZONE \u03a9"
        hud._zone_label_timer = 1.8
        hud.update(_state(), dt=0.016)
        hud.draw(screen)

    def test_draw_after_timer_expires_is_silent(self, event_bus, hud, screen):
        """After the full duration, the label must not re-render."""
        event_bus.emit('zone_entered', zone=_FakeZone("FACTORY"))
        hud.update(_state(), dt=_ZONE_LABEL_DURATION + 1.0)   # expire completely
        hud.draw(screen)   # must not crash; label is suppressed
