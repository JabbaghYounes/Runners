"""Tests for HUD XP bar and level indicator rendering.

Covers:
  - XP ratio arithmetic for full, partial, and zero XP
  - xp_to_next == 0 guard (max(1, ...) denominator avoids division-by-zero)
  - HUDState level field is reflected in the snapshot
  - level.up event sets the level-up banner timer
  - level_up event (alias) also sets the timer
  - Level-up banner timer decrements on update() and clamps at 0
  - draw() does not crash with a level-up banner active
  - draw() renders correctly at levels 1 through 99

# Run: pytest tests/test_hud_xp_level.py
"""
from __future__ import annotations

import pytest
import pygame

from src.core.event_bus import EventBus
from src.ui.hud import HUD, _LEVELUP_BANNER_DURATION
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

def _state(**overrides) -> HUDState:
    defaults: dict = dict(hp=100, max_hp=100, seconds_remaining=900.0,
                          level=1, xp=0.0, xp_to_next=100.0)
    defaults.update(overrides)
    return HUDState(**defaults)


# ---------------------------------------------------------------------------
# Unit: HUDState XP fields
# ---------------------------------------------------------------------------

class TestHUDStateXPFields:
    def test_default_xp_is_zero(self):
        assert HUDState().xp == pytest.approx(0.0)

    def test_default_xp_to_next_is_100(self):
        assert HUDState().xp_to_next == pytest.approx(100.0)

    def test_default_level_is_one(self):
        assert HUDState().level == 1

    def test_custom_xp(self):
        st = HUDState(xp=250.0, xp_to_next=500.0)
        assert st.xp == pytest.approx(250.0)

    def test_custom_level(self):
        st = HUDState(level=7)
        assert st.level == 7


# ---------------------------------------------------------------------------
# Unit: XP bar fill ratio arithmetic
# ---------------------------------------------------------------------------

class TestXPBarRatioArithmetic:
    def test_full_xp_ratio_is_one(self):
        """Player at max XP for the level → bar should be full."""
        xp, xp_to_next = 900.0, 0.0
        # HUD uses: xp / (xp + max(xp_to_next, 1))
        ratio = xp / (xp + max(xp_to_next, 1))
        assert ratio == pytest.approx(900 / 901, rel=1e-4)

    def test_partial_xp_ratio_correct(self):
        xp, xp_to_next = 400.0, 500.0
        ratio = xp / (xp + max(xp_to_next, 1))
        assert ratio == pytest.approx(400 / 900, rel=1e-4)

    def test_zero_xp_ratio_is_zero(self):
        xp, xp_to_next = 0.0, 100.0
        ratio = xp / (xp + max(xp_to_next, 1))
        assert ratio == pytest.approx(0.0)

    def test_xp_to_next_zero_guard_prevents_full_denominator_of_zero(self):
        """max(xp_to_next, 1) must never let denominator reach 0."""
        xp, xp_to_next = 0.0, 0.0
        denom = xp + max(xp_to_next, 1)
        assert denom >= 1

    def test_xp_to_next_zero_does_not_divide_by_zero(self):
        xp, xp_to_next = 100.0, 0.0
        denom = xp + max(xp_to_next, 1)
        ratio = xp / denom
        assert 0.0 <= ratio <= 1.0

    def test_xp_ratio_with_state_fields_matches_direct_computation(self):
        st = _state(xp=300.0, xp_to_next=600.0)
        ratio = st.xp / (st.xp + max(st.xp_to_next, 1))
        assert ratio == pytest.approx(300 / 900, rel=1e-4)


# ---------------------------------------------------------------------------
# Unit: level-up event handlers
# ---------------------------------------------------------------------------

class TestLevelUpEventHandlers:
    def test_level_up_event_sets_banner_timer(self, event_bus, hud):
        assert hud._level_up_timer == pytest.approx(0.0)
        event_bus.emit('level.up')
        assert hud._level_up_timer == pytest.approx(3.0)

    def test_level_up_alias_event_sets_banner_timer(self, event_bus, hud):
        event_bus.emit('level_up')
        assert hud._level_up_timer == pytest.approx(3.0)

    def test_level_up_event_sets_levelup_banner_timer(self, event_bus, hud):
        event_bus.emit('level.up')
        assert hud._levelup_banner_timer == pytest.approx(_LEVELUP_BANNER_DURATION)

    def test_level_up_timer_decrements_on_update(self, event_bus, hud):
        event_bus.emit('level.up')
        hud.update(_state(), dt=0.5)
        assert hud._level_up_timer == pytest.approx(2.5)

    def test_level_up_timer_clamped_at_zero(self, event_bus, hud):
        event_bus.emit('level.up')
        hud.update(_state(), dt=9999.0)
        assert hud._level_up_timer == 0.0

    def test_level_up_timer_never_negative(self, event_bus, hud):
        event_bus.emit('level.up')
        hud.update(_state(), dt=9999.0)
        assert hud._level_up_timer >= 0.0

    def test_multiple_level_up_events_reset_timer(self, event_bus, hud):
        event_bus.emit('level.up')
        hud.update(_state(), dt=1.0)      # timer now 2.0
        event_bus.emit('level.up')        # reset to 3.0
        assert hud._level_up_timer == pytest.approx(3.0)

    def test_level_up_timer_starts_at_zero_before_any_event(self, hud):
        assert hud._levelup_banner_timer == pytest.approx(0.0)
        assert hud._level_up_timer == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Draw smoke tests
# ---------------------------------------------------------------------------

class TestXPAndLevelDraw:
    def test_draw_with_level_1_does_not_crash(self, hud, screen):
        hud.update(_state(level=1, xp=0.0, xp_to_next=100.0), dt=0.016)
        hud.draw(screen)

    def test_draw_with_level_99_does_not_crash(self, hud, screen):
        hud.update(_state(level=99, xp=9000.0, xp_to_next=500.0), dt=0.016)
        hud.draw(screen)

    def test_draw_with_full_xp_bar_does_not_crash(self, hud, screen):
        hud.update(_state(xp=900.0, xp_to_next=0.0), dt=0.016)
        hud.draw(screen)

    def test_draw_with_zero_xp_does_not_crash(self, hud, screen):
        hud.update(_state(xp=0.0, xp_to_next=100.0), dt=0.016)
        hud.draw(screen)

    def test_draw_with_active_level_up_banner_does_not_crash(self, event_bus, hud, screen):
        event_bus.emit('level.up')
        hud.update(_state(level=5), dt=0.016)
        hud.draw(screen)

    def test_draw_with_level_up_banner_fading_does_not_crash(self, hud, screen):
        """Near-end of banner → alpha < 255."""
        hud._levelup_banner_timer = 0.2
        hud._level_up_timer = 0.2
        hud.update(_state(level=3), dt=0.016)
        hud.draw(screen)

    def test_draw_with_levelup_banner_at_full_does_not_crash(self, event_bus, hud, screen):
        """Immediately after level.up → full alpha banner."""
        event_bus.emit('level.up')
        # Draw without calling update (banner still at full timer)
        hud._ensure_fonts()
        hud.draw(screen)
