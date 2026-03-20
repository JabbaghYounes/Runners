"""Tests for HUD active-buff display and item-used/heal-flash events.

Covers:
  - _draw_buffs is a no-op when active_buffs is empty
  - Buffs with seconds_left < _BUFF_PULSE_THRESHOLD render as selected (pulsing)
  - Buffs with seconds_left >= _BUFF_PULSE_THRESHOLD render as unselected
  - Up to 6 buffs are rendered; extras are silently truncated
  - item_used event triggers heal-flash timer
  - player_healed event triggers heal-flash timer (alias)
  - Heal-flash timer decrements on update() and clamps at 0
  - draw() does not crash with an active heal flash overlay

# Run: pytest tests/test_hud_buffs.py
"""
from __future__ import annotations

import pytest
import pygame

from src.core.event_bus import EventBus
from src.ui.hud import HUD, _BUFF_PULSE_THRESHOLD, _HEAL_FLASH_DURATION
from src.ui.hud_state import HUDState, BuffEntry


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

def _state(buffs: list | None = None, **overrides) -> HUDState:
    defaults: dict = dict(hp=100, max_hp=100, seconds_remaining=900.0,
                          active_buffs=buffs or [])
    defaults.update(overrides)
    return HUDState(**defaults)


def _buff(label: str, seconds_left: float) -> BuffEntry:
    return BuffEntry(label=label, seconds_left=seconds_left)


# ---------------------------------------------------------------------------
# Unit: BuffEntry dataclass
# ---------------------------------------------------------------------------

class TestBuffEntryDataclass:
    def test_buff_entry_stores_label(self):
        b = _buff("speed", 5.0)
        assert b.label == "speed"

    def test_buff_entry_stores_seconds_left(self):
        b = _buff("damage", 2.5)
        assert b.seconds_left == pytest.approx(2.5)

    def test_buff_entry_default_icon_is_none(self):
        b = _buff("armor", 10.0)
        assert b.icon is None

    def test_buff_entry_with_surface_icon(self):
        icon = pygame.Surface((32, 32))
        b = BuffEntry(label="regen", seconds_left=8.0, icon=icon)
        assert b.icon is icon


# ---------------------------------------------------------------------------
# Unit: buff pulse-threshold selection logic
# ---------------------------------------------------------------------------

class TestBuffPulseThreshold:
    def test_pulse_threshold_constant_is_3_seconds(self):
        assert _BUFF_PULSE_THRESHOLD == pytest.approx(3.0)

    def test_buff_below_threshold_should_be_selected(self):
        b = _buff("speed", seconds_left=2.9)
        assert b.seconds_left < _BUFF_PULSE_THRESHOLD

    def test_buff_at_threshold_should_not_be_selected(self):
        b = _buff("speed", seconds_left=3.0)
        assert not (b.seconds_left < _BUFF_PULSE_THRESHOLD)

    def test_buff_above_threshold_should_not_be_selected(self):
        b = _buff("speed", seconds_left=10.0)
        assert not (b.seconds_left < _BUFF_PULSE_THRESHOLD)

    def test_buff_with_zero_seconds_left_should_be_selected(self):
        b = _buff("damage", seconds_left=0.0)
        assert b.seconds_left < _BUFF_PULSE_THRESHOLD

    def test_buff_with_one_second_left_should_be_selected(self):
        b = _buff("damage", seconds_left=1.0)
        assert b.seconds_left < _BUFF_PULSE_THRESHOLD


# ---------------------------------------------------------------------------
# Draw smoke tests: _draw_buffs via full HUD pipeline
# ---------------------------------------------------------------------------

class TestBuffDraw:
    def test_draw_with_no_buffs_does_not_crash(self, hud, screen):
        st = _state(buffs=[])
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_draw_with_one_buff_does_not_crash(self, hud, screen):
        st = _state(buffs=[_buff("speed", 5.0)])
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_draw_with_six_buffs_does_not_crash(self, hud, screen):
        buffs = [_buff(f"stat_{i}", float(i + 1)) for i in range(6)]
        st = _state(buffs=buffs)
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_draw_with_more_than_six_buffs_does_not_crash(self, hud, screen):
        """Extra buffs beyond 6 are silently truncated."""
        buffs = [_buff(f"stat_{i}", float(i + 1)) for i in range(10)]
        st = _state(buffs=buffs)
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_draw_with_near_expiry_buff_does_not_crash(self, hud, screen):
        """seconds_left < 3.0 → selected=True (pulsing border)."""
        st = _state(buffs=[_buff("regen", seconds_left=0.5)])
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_draw_with_fresh_buff_does_not_crash(self, hud, screen):
        """seconds_left >= 3.0 → selected=False."""
        st = _state(buffs=[_buff("damage", seconds_left=30.0)])
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_draw_with_buff_icon_surface_does_not_crash(self, hud, screen):
        icon = pygame.Surface((32, 32))
        icon.fill((200, 100, 50))
        b = BuffEntry(label="armor", seconds_left=8.0, icon=icon)
        st = _state(buffs=[b])
        hud.update(st, dt=0.016)
        hud.draw(screen)


# ---------------------------------------------------------------------------
# Unit: item_used and player_healed event handlers
# ---------------------------------------------------------------------------

class TestHealFlashEventHandlers:
    def test_item_used_event_sets_heal_flash_timer(self, event_bus, hud):
        assert hud._heal_flash_timer == pytest.approx(0.0)
        event_bus.emit('item_used')
        assert hud._heal_flash_timer == pytest.approx(_HEAL_FLASH_DURATION)

    def test_player_healed_event_sets_heal_flash_timer(self, event_bus, hud):
        event_bus.emit('player_healed')
        assert hud._heal_flash_timer == pytest.approx(_HEAL_FLASH_DURATION)

    def test_item_used_and_player_healed_both_trigger_heal_flash(self, event_bus, hud):
        """Both event aliases must wire to the same handler."""
        event_bus.emit('item_used')
        t1 = hud._heal_flash_timer
        event_bus.emit('player_healed')
        # Timer is reset to full duration, not doubled
        assert hud._heal_flash_timer == pytest.approx(_HEAL_FLASH_DURATION)

    def test_heal_flash_timer_not_zero_immediately_after_item_used(self, event_bus, hud):
        event_bus.emit('item_used')
        assert hud._heal_flash_timer > 0.0

    def test_heal_flash_timer_decrements_on_update(self, event_bus, hud):
        event_bus.emit('item_used')
        hud.update(_state(), dt=0.1)
        assert hud._heal_flash_timer == pytest.approx(_HEAL_FLASH_DURATION - 0.1)

    def test_heal_flash_timer_clamped_at_zero(self, event_bus, hud):
        event_bus.emit('item_used')
        hud.update(_state(), dt=9999.0)
        assert hud._heal_flash_timer == 0.0

    def test_heal_flash_timer_never_goes_negative(self, event_bus, hud):
        event_bus.emit('item_used')
        hud.update(_state(), dt=9999.0)
        assert hud._heal_flash_timer >= 0.0

    def test_multiple_item_used_events_reset_timer_to_full(self, event_bus, hud):
        event_bus.emit('item_used')
        hud.update(_state(), dt=0.2)       # timer now 0.2
        event_bus.emit('item_used')        # should reset back to full
        assert hud._heal_flash_timer == pytest.approx(_HEAL_FLASH_DURATION)


# ---------------------------------------------------------------------------
# Draw smoke tests: heal-flash vignette
# ---------------------------------------------------------------------------

class TestHealFlashDraw:
    def test_draw_with_active_heal_flash_does_not_crash(self, event_bus, hud, screen):
        event_bus.emit('item_used')
        hud.update(_state(), dt=0.016)
        hud.draw(screen)

    def test_draw_with_partially_expired_heal_flash_does_not_crash(self, event_bus, hud, screen):
        event_bus.emit('item_used')
        hud.update(_state(), dt=_HEAL_FLASH_DURATION * 0.5)
        hud.draw(screen)

    def test_draw_with_zero_heal_flash_does_not_crash(self, hud, screen):
        hud._heal_flash_timer = 0.0
        hud.update(_state(), dt=0.016)
        hud.draw(screen)
