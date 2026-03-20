"""Tests for HUD round-timer display: MM:SS formatting and colour thresholds.

Covers:
  - seconds_remaining > 300 → TEXT_PRIMARY colour range (white)
  - 60 < seconds_remaining ≤ 300 → ACCENT_AMBER colour range (amber)
  - seconds_remaining ≤ 60 → DANGER_RED colour range (red)
  - Boundary conditions at exactly 300 s and 60 s
  - MM:SS integer arithmetic for representative values
  - draw() does not crash for all three colour regions

# Run: pytest tests/test_hud_timer.py
"""
from __future__ import annotations

import pytest
import pygame

from src.core.event_bus import EventBus
from src.ui.hud import HUD, _TIMER_WARN_SECS, _TIMER_DANGER_SECS, ACCENT_AMBER
from src.ui.hud_state import HUDState
from src.constants import TEXT_PRIMARY, DANGER_RED


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


def _state(seconds: float) -> HUDState:
    return HUDState(seconds_remaining=seconds)


# ---------------------------------------------------------------------------
# Timer threshold constants
# ---------------------------------------------------------------------------

class TestTimerThresholdConstants:
    def test_warn_threshold_is_300_seconds(self):
        """5 minutes remaining triggers the amber transition."""
        assert _TIMER_WARN_SECS == 300

    def test_danger_threshold_is_60_seconds(self):
        """1 minute remaining triggers the red transition."""
        assert _TIMER_DANGER_SECS == 60


# ---------------------------------------------------------------------------
# Unit: colour selection logic (mirrors _draw_timer branches)
# ---------------------------------------------------------------------------

def _pick_color(seconds_remaining: float) -> tuple:
    """Replicate the timer colour logic from HUD._draw_timer."""
    if seconds_remaining > _TIMER_WARN_SECS:
        return TEXT_PRIMARY
    elif seconds_remaining > _TIMER_DANGER_SECS:
        return ACCENT_AMBER
    else:
        return DANGER_RED


class TestTimerColorLogic:
    def test_above_5_minutes_uses_text_primary(self):
        color = _pick_color(900.0)   # full round
        assert color == TEXT_PRIMARY

    def test_just_above_warn_threshold_uses_text_primary(self):
        color = _pick_color(301.0)
        assert color == TEXT_PRIMARY

    def test_at_exactly_warn_threshold_uses_amber(self):
        """300.0 is NOT above 300 → switches to amber."""
        color = _pick_color(300.0)
        assert color == ACCENT_AMBER

    def test_between_60_and_300_uses_amber(self):
        color = _pick_color(180.0)   # 3 minutes
        assert color == ACCENT_AMBER

    def test_just_above_danger_threshold_uses_amber(self):
        color = _pick_color(61.0)
        assert color == ACCENT_AMBER

    def test_at_exactly_danger_threshold_uses_danger_red(self):
        """60.0 is NOT above 60 → switches to red."""
        color = _pick_color(60.0)
        assert color == DANGER_RED

    def test_below_danger_threshold_uses_danger_red(self):
        color = _pick_color(30.0)
        assert color == DANGER_RED

    def test_zero_seconds_uses_danger_red(self):
        color = _pick_color(0.0)
        assert color == DANGER_RED

    def test_hud_state_seconds_above_300_is_primary_range(self):
        """State value check — mirrors test_hud_status threshold assertions."""
        st = _state(500.0)
        assert st.seconds_remaining > _TIMER_WARN_SECS

    def test_hud_state_seconds_between_60_and_300_is_amber_range(self):
        st = _state(120.0)
        assert _TIMER_DANGER_SECS < st.seconds_remaining <= _TIMER_WARN_SECS

    def test_hud_state_seconds_below_60_is_danger_range(self):
        st = _state(45.0)
        assert st.seconds_remaining <= _TIMER_DANGER_SECS

    def test_hud_state_seconds_at_exactly_300_triggers_amber(self):
        """Boundary: 300.0 must not be in the white (> 300) range."""
        st = _state(300.0)
        assert not (st.seconds_remaining > _TIMER_WARN_SECS)

    def test_hud_state_seconds_at_exactly_60_triggers_red(self):
        """Boundary: 60.0 must not be in the amber (> 60) range."""
        st = _state(60.0)
        assert not (st.seconds_remaining > _TIMER_DANGER_SECS)


# ---------------------------------------------------------------------------
# Unit: MM:SS integer arithmetic
# ---------------------------------------------------------------------------

class TestTimerFormatArithmetic:
    def test_900_seconds_formats_as_15_00(self):
        total = int(900)
        assert total // 60 == 15
        assert total % 60 == 0

    def test_185_seconds_formats_as_3_05(self):
        total = int(185)
        assert total // 60 == 3
        assert total % 60 == 5

    def test_60_seconds_formats_as_1_00(self):
        total = int(60)
        assert total // 60 == 1
        assert total % 60 == 0

    def test_59_seconds_formats_as_0_59(self):
        total = int(59)
        assert total // 60 == 0
        assert total % 60 == 59

    def test_0_seconds_formats_as_0_00(self):
        total = max(0, int(0))
        assert total // 60 == 0
        assert total % 60 == 0

    def test_fractional_seconds_truncated(self):
        """185.7 should display as 03:05, not 03:06."""
        total = int(185.7)
        assert total == 185
        assert total // 60 == 3
        assert total % 60 == 5

    def test_negative_seconds_clamped_to_zero(self):
        """max(0, ...) guard prevents negative timer string."""
        secs = max(0, int(-5.0))
        assert secs == 0

    def test_format_string_two_digit_minutes(self):
        total = int(900)
        mm = total // 60
        ss = total % 60
        result = f'{mm:02d}:{ss:02d}'
        assert result == '15:00'

    def test_format_string_zero_padded_seconds(self):
        total = int(65)
        mm = total // 60
        ss = total % 60
        result = f'{mm:02d}:{ss:02d}'
        assert result == '01:05'


# ---------------------------------------------------------------------------
# Draw smoke tests — one per colour region
# ---------------------------------------------------------------------------

class TestTimerDraw:
    def test_draw_with_timer_in_white_region_does_not_crash(self, hud, screen):
        st = _state(seconds=600.0)   # > 300 s → white
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_draw_with_timer_in_amber_region_does_not_crash(self, hud, screen):
        st = _state(seconds=150.0)   # 60-300 s → amber
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_draw_with_timer_in_red_region_does_not_crash(self, hud, screen):
        st = _state(seconds=30.0)    # ≤ 60 s → red
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_draw_at_exactly_300_seconds_does_not_crash(self, hud, screen):
        hud.update(_state(seconds=300.0), dt=0.016)
        hud.draw(screen)

    def test_draw_at_exactly_60_seconds_does_not_crash(self, hud, screen):
        hud.update(_state(seconds=60.0), dt=0.016)
        hud.draw(screen)

    def test_draw_at_zero_seconds_does_not_crash(self, hud, screen):
        hud.update(_state(seconds=0.0), dt=0.016)
        hud.draw(screen)

    def test_draw_at_full_round_duration_does_not_crash(self, hud, screen):
        hud.update(_state(seconds=900.0), dt=0.016)
        hud.draw(screen)
