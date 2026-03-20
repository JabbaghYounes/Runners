"""Tests for HUD render-layer constant, teardown/unsubscribe, and input passthrough.

Covers:
  - LAYER_HUD constant equals 5 per the spec
  - LAYER_HUD is the topmost layer (above tiles, enemies, player, projectiles)
  - teardown() unsubscribes all event handlers; subsequent events have no effect
  - HUD has no handle_events() method — it does not consume game input
  - Full composite draw cycle (all seven HUD regions) does not crash

# Run: pytest tests/test_hud_layer_and_teardown.py
"""
from __future__ import annotations

import pytest
import pygame

from src.core.event_bus import EventBus
from src.ui.hud import HUD
from src.ui.hud_state import HUDState, BuffEntry, WeaponInfo, ConsumableSlot, ChallengeInfo
from src.constants import (
    LAYER_HUD, LAYER_TILES, LAYER_LOOT, LAYER_ENEMIES,
    LAYER_PLAYER, LAYER_PROJECTILES,
)


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

def _full_state() -> HUDState:
    """Return a HUDState with every field populated for a comprehensive draw test."""
    return HUDState(
        hp=75, max_hp=100,
        armor=40, max_armor=100,
        level=5, xp=1200.0, xp_to_next=800.0,
        seconds_remaining=270.0,
        active_buffs=[
            BuffEntry(label="speed", seconds_left=8.0),
            BuffEntry(label="damage", seconds_left=1.5),
        ],
        player_world_pos=(640.0, 480.0),
        map_world_rect=pygame.Rect(0, 0, 3200, 2400),
        extraction_pos=(2400.0, 800.0),
        equipped_weapon=WeaponInfo(name="Assault Rifle", ammo_current=24, ammo_reserve=90),
        consumable_slots=[
            ConsumableSlot(label="Medkit", count=2),
            ConsumableSlot(label="Grenade", count=1),
            ConsumableSlot(label="", count=0),
            ConsumableSlot(label="", count=0),
        ],
        active_challenges=[
            ChallengeInfo(name="Kill 5 robots", progress=3, target=5),
            ChallengeInfo(name="Loot 2 items", progress=2, target=2, completed=True),
        ],
        active_quick_slot=1,
        in_extraction_zone=False,
        extraction_progress=0.0,
    )


# ---------------------------------------------------------------------------
# Unit: render-layer constant
# ---------------------------------------------------------------------------

class TestLayerHUDConstant:
    def test_layer_hud_equals_5(self):
        assert LAYER_HUD == 5

    def test_layer_hud_is_above_tiles(self):
        assert LAYER_TILES < LAYER_HUD

    def test_layer_hud_is_above_loot(self):
        assert LAYER_LOOT < LAYER_HUD

    def test_layer_hud_is_above_enemies(self):
        assert LAYER_ENEMIES < LAYER_HUD

    def test_layer_hud_is_above_player(self):
        assert LAYER_PLAYER < LAYER_HUD

    def test_layer_hud_is_above_projectiles(self):
        assert LAYER_PROJECTILES < LAYER_HUD

    def test_layer_ordering_is_strictly_monotone(self):
        layers = [LAYER_TILES, LAYER_LOOT, LAYER_ENEMIES,
                  LAYER_PLAYER, LAYER_PROJECTILES, LAYER_HUD]
        for a, b in zip(layers, layers[1:]):
            assert a < b, f"Expected {a} < {b}"


# ---------------------------------------------------------------------------
# Unit: HUD does not intercept game input
# ---------------------------------------------------------------------------

class TestHUDInputPassthrough:
    def test_hud_has_no_handle_events_method(self, hud):
        """HUD must not consume game events; it renders only."""
        assert not hasattr(hud, 'handle_events'), (
            "HUD should not implement handle_events() as it must not "
            "block input from reaching game systems."
        )

    def test_hud_has_no_process_events_method(self, hud):
        assert not hasattr(hud, 'process_events')

    def test_hud_update_accepts_state_and_dt_only(self, hud):
        """update() signature is (state, dt) — no event list parameter."""
        import inspect
        sig = inspect.signature(hud.update)
        params = list(sig.parameters.keys())
        assert 'state' in params
        assert 'dt' in params
        assert 'events' not in params


# ---------------------------------------------------------------------------
# Unit: teardown — unsubscribe logic
# ---------------------------------------------------------------------------

class TestHUDTeardown:
    def test_teardown_does_not_raise(self, hud, event_bus):
        hud.teardown()

    def test_teardown_removes_player_damaged_handler(self, hud, event_bus):
        hud.teardown()
        # After teardown, emitting should not update vignette timer
        event_bus.emit('player.damaged')
        assert hud._vignette_timer == pytest.approx(0.0)

    def test_teardown_removes_player_damaged_alias_handler(self, hud, event_bus):
        hud.teardown()
        event_bus.emit('player_damaged')
        assert hud._vignette_timer == pytest.approx(0.0)

    def test_teardown_removes_level_up_handler(self, hud, event_bus):
        hud.teardown()
        event_bus.emit('level.up')
        assert hud._level_up_timer == pytest.approx(0.0)

    def test_teardown_removes_level_up_alias_handler(self, hud, event_bus):
        hud.teardown()
        event_bus.emit('level_up')
        assert hud._level_up_timer == pytest.approx(0.0)

    def test_teardown_removes_zone_entered_handler(self, hud, event_bus):
        class _FakeZone:
            name = "ZONE X"
        hud.teardown()
        event_bus.emit('zone_entered', zone=_FakeZone())
        assert hud._zone_label == ""
        assert hud._zone_label_timer == pytest.approx(0.0)

    def test_teardown_removes_item_used_handler(self, hud, event_bus):
        hud.teardown()
        event_bus.emit('item_used')
        assert hud._heal_flash_timer == pytest.approx(0.0)

    def test_teardown_removes_player_healed_handler(self, hud, event_bus):
        hud.teardown()
        event_bus.emit('player_healed')
        assert hud._heal_flash_timer == pytest.approx(0.0)

    def test_teardown_is_idempotent(self, hud, event_bus):
        """Calling teardown() twice must not raise."""
        hud.teardown()
        hud.teardown()

    def test_handlers_active_before_teardown(self, event_bus, hud):
        """Confirm handlers are wired before teardown is called."""
        event_bus.emit('player.damaged')
        assert hud._vignette_timer > 0.0


# ---------------------------------------------------------------------------
# Integration: full composite HUD draw cycle
# ---------------------------------------------------------------------------

class TestFullHUDDrawCycle:
    def test_full_draw_with_all_fields_does_not_crash(self, hud, screen):
        st = _full_state()
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_full_draw_with_extraction_in_progress_does_not_crash(self, hud, screen):
        st = _full_state()
        st.in_extraction_zone = True
        st.extraction_progress = 0.65
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_full_draw_with_all_transient_effects_active(self, event_bus, hud, screen):
        event_bus.emit('player.damaged')
        event_bus.emit('level.up')
        event_bus.emit('item_used')

        class _Zone:
            name = "REACTOR"
        event_bus.emit('zone_entered', zone=_Zone())

        st = _full_state()
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_full_draw_after_vignette_expires_does_not_crash(self, event_bus, hud, screen):
        event_bus.emit('player.damaged')
        hud.update(_full_state(), dt=1.0)   # expire vignette
        hud.draw(screen)

    def test_full_draw_with_no_weapon_does_not_crash(self, hud, screen):
        st = _full_state()
        st.equipped_weapon = None
        hud.update(st, dt=0.016)
        hud.draw(screen)

    def test_full_draw_multiple_frames_does_not_crash(self, hud, screen):
        st = _full_state()
        for _ in range(10):
            hud.update(st, dt=1 / 60)
            hud.draw(screen)
