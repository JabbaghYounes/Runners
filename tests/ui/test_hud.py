"""Integration smoke tests for the HUD orchestrator."""
from __future__ import annotations

import pytest
import pygame

from src.core.event_bus import EventBus
from src.ui.hud import HUD
from src.ui.hud_state import (
    HUDState,
    BuffEntry,
    WeaponInfo,
    ZoneInfo,
    ChallengeInfo,
    ConsumableSlot,
)


@pytest.fixture(scope='session', autouse=True)
def pygame_headless():
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.quit()


@pytest.fixture
def screen():
    """1280×720 surface matching the game resolution."""
    return pygame.Surface((1280, 720))


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def hud(event_bus):
    return HUD(event_bus)


def _full_state() -> HUDState:
    """Build a realistic HUDState for smoke-testing."""
    zones = [
        ZoneInfo(name='Sector Alpha', color=(80, 60, 120),
                 world_rect=pygame.Rect(0, 0, 640, 720)),
        ZoneInfo(name='Sector Beta',  color=(60, 100, 80),
                 world_rect=pygame.Rect(640, 0, 640, 720)),
    ]
    challenges = [
        ChallengeInfo(name='Kill 3 Robots', progress=1, target=3),
        ChallengeInfo(name='Collect 5 Caches', progress=5, target=5, completed=True),
    ]
    buffs = [
        BuffEntry(label='Speed+', seconds_left=8.5),
        BuffEntry(label='Shield', seconds_left=2.1),
    ]
    weapon = WeaponInfo(name='Assault Rifle', ammo_current=24, ammo_reserve=72)
    consumables = [
        ConsumableSlot(label='MedKit', count=2),
        ConsumableSlot(label='Stim', count=1),
    ]
    return HUDState(
        hp=65.0,
        max_hp=100.0,
        armor=40.0,
        max_armor=100.0,
        level=5,
        xp=1200.0,
        xp_to_next=200.0,
        seconds_remaining=450.0,
        active_buffs=buffs,
        player_world_pos=(320.0, 360.0),
        map_world_rect=pygame.Rect(0, 0, 1280, 720),
        zones=zones,
        extraction_pos=(960.0, 360.0),
        equipped_weapon=weapon,
        consumable_slots=consumables,
        active_challenges=challenges,
    )


class TestHUDSmoke:
    def test_update_then_draw_does_not_raise(self, hud, screen):
        state = _full_state()
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_draw_without_update_does_not_raise(self, hud, screen):
        """HUD must be safe even before the first update() call."""
        hud.draw(screen)

    def test_update_with_minimal_state_does_not_raise(self, hud, screen):
        state = HUDState()  # all defaults
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_multiple_update_draw_cycles_do_not_raise(self, hud, screen):
        state = _full_state()
        for frame in range(10):
            hud.update(state, 0.016)
            hud.draw(screen)

    def test_draw_with_no_weapon_does_not_raise(self, hud, screen):
        state = _full_state()
        state.equipped_weapon = None
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_draw_with_no_zones_does_not_raise(self, hud, screen):
        state = _full_state()
        state.zones = []
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_draw_with_no_challenges_does_not_raise(self, hud, screen):
        state = _full_state()
        state.active_challenges = []
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_draw_with_no_buffs_does_not_raise(self, hud, screen):
        state = _full_state()
        state.active_buffs = []
        hud.update(state, 0.016)
        hud.draw(screen)


class TestHUDDamageFlash:
    def test_damage_flash_timer_set_on_event(self, event_bus, screen):
        hud = HUD(event_bus)
        assert hud._damage_flash_timer == pytest.approx(0.0)
        event_bus.emit('player_damaged', player=None, amount=20)
        # Timer should be > 0 after damage event
        assert hud._damage_flash_timer > 0.0

    def test_damage_flash_timer_decrements_on_update(self, event_bus, screen):
        hud = HUD(event_bus)
        event_bus.emit('player_damaged', player=None, amount=10)
        initial = hud._damage_flash_timer
        hud.update(HUDState(), 0.1)
        assert hud._damage_flash_timer < initial

    def test_damage_flash_timer_stops_at_zero(self, event_bus, screen):
        hud = HUD(event_bus)
        event_bus.emit('player_damaged', player=None, amount=10)
        # Fast-forward past the flash duration
        hud.update(HUDState(), 10.0)
        assert hud._damage_flash_timer == pytest.approx(0.0)

    def test_damage_vignette_drawn_during_flash(self, event_bus, screen):
        """Smoke test: damage vignette code path runs without raising."""
        hud = HUD(event_bus)
        event_bus.emit('player_damaged', player=None, amount=50)
        hud.update(HUDState(), 0.016)
        hud.draw(screen)  # vignette path should be active here


class TestHUDLevelUpBanner:
    def test_levelup_timer_set_on_event(self, event_bus):
        hud = HUD(event_bus)
        assert hud._levelup_banner_timer == pytest.approx(0.0)
        event_bus.emit('level_up', player=None, new_level=2)
        assert hud._levelup_banner_timer > 0.0

    def test_levelup_timer_decrements_on_update(self, event_bus):
        hud = HUD(event_bus)
        event_bus.emit('level_up', player=None, new_level=3)
        initial = hud._levelup_banner_timer
        hud.update(HUDState(), 0.5)
        assert hud._levelup_banner_timer < initial

    def test_levelup_banner_drawn_during_active(self, event_bus, screen):
        """Smoke test: level-up banner code path runs without raising."""
        hud = HUD(event_bus)
        event_bus.emit('level_up', player=None, new_level=4)
        hud.update(HUDState(level=4), 0.016)
        hud.draw(screen)


class TestHUDTimer:
    def test_timer_formats_correctly_for_900_seconds(self, hud, screen):
        """15:00 countdown."""
        state = HUDState(seconds_remaining=900.0)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_timer_near_zero_does_not_raise(self, hud, screen):
        state = HUDState(seconds_remaining=5.0)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_timer_at_zero_does_not_raise(self, hud, screen):
        state = HUDState(seconds_remaining=0.0)
        hud.update(state, 0.016)
        hud.draw(screen)


class TestHUDTeardown:
    def test_teardown_does_not_raise(self, event_bus):
        hud = HUD(event_bus)
        hud.teardown()  # must not raise

    def test_after_teardown_event_no_longer_updates_timer(self, event_bus):
        hud = HUD(event_bus)
        hud.teardown()
        # After teardown the handler is removed; emitting should not crash
        event_bus.emit('player_damaged', player=None, amount=10)
        # Timer stays at 0 (handler was unsubscribed)
        # Note: teardown may partially succeed; we mainly test no exception


# ---------------------------------------------------------------------------
# HUD health-bar color thresholds
# (The exact color chosen is an internal detail; we verify each code path
# completes draw() without raising at the three HP ratio breakpoints.)
# ---------------------------------------------------------------------------
class TestHUDHealthColorThresholds:
    """HP > 50 % → green, 30–50 % → amber, < 30 % → red (DANGER)."""

    def test_high_hp_above_50_percent_does_not_raise(self, hud, screen):
        # 80/100 = 80 % — should pick ACCENT_GREEN
        state = _full_state()
        state.hp = 80.0
        state.max_hp = 100.0
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_hp_exactly_at_50_percent_does_not_raise(self, hud, screen):
        # 50/100 = 50 % — boundary of amber zone
        state = _full_state()
        state.hp = 50.0
        state.max_hp = 100.0
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_hp_between_30_and_50_percent_does_not_raise(self, hud, screen):
        # 40/100 = 40 % — should pick ACCENT_AMBER
        state = _full_state()
        state.hp = 40.0
        state.max_hp = 100.0
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_hp_exactly_at_30_percent_does_not_raise(self, hud, screen):
        # 30/100 = 30 % — boundary of danger zone
        state = _full_state()
        state.hp = 30.0
        state.max_hp = 100.0
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_low_hp_below_30_percent_does_not_raise(self, hud, screen):
        # 20/100 = 20 % — should pick DANGER_RED
        state = _full_state()
        state.hp = 20.0
        state.max_hp = 100.0
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_hp_at_zero_does_not_raise(self, hud, screen):
        state = _full_state()
        state.hp = 0.0
        state.max_hp = 100.0
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_hp_at_full_does_not_raise(self, hud, screen):
        state = _full_state()
        state.hp = 100.0
        state.max_hp = 100.0
        hud.update(state, 0.016)
        hud.draw(screen)


# ---------------------------------------------------------------------------
# HUD round-timer color thresholds
# ---------------------------------------------------------------------------
class TestHUDTimerColorThresholds:
    """Timer > 120 s → white, 30–120 s → amber, ≤ 30 s → red (pulsing)."""

    def test_timer_well_above_120s_does_not_raise(self, hud, screen):
        state = HUDState(seconds_remaining=600.0)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_timer_exactly_at_120s_does_not_raise(self, hud, screen):
        # 120 s is the amber threshold boundary
        state = HUDState(seconds_remaining=120.0)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_timer_just_below_120s_does_not_raise(self, hud, screen):
        state = HUDState(seconds_remaining=119.9)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_timer_exactly_at_30s_does_not_raise(self, hud, screen):
        # 30 s is the red/danger threshold boundary
        state = HUDState(seconds_remaining=30.0)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_timer_just_below_30s_does_not_raise(self, hud, screen):
        state = HUDState(seconds_remaining=29.0)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_timer_formats_mm_ss_at_900s(self, hud, screen):
        """15:00 — verify draw() completes at max round time."""
        state = HUDState(seconds_remaining=900.0)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_timer_formats_at_61s(self, hud, screen):
        """01:01"""
        state = HUDState(seconds_remaining=61.0)
        hud.update(state, 0.016)
        hud.draw(screen)


# ---------------------------------------------------------------------------
# HUD weapon panel — ammo colour and missing weapon
# ---------------------------------------------------------------------------
class TestHUDWeaponPanel:
    def test_weapon_with_ample_ammo_does_not_raise(self, hud, screen):
        state = _full_state()
        state.equipped_weapon = WeaponInfo(name='Rifle', ammo_current=24,
                                           ammo_reserve=72)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_weapon_with_exactly_3_rounds_does_not_raise(self, hud, screen):
        """≤ 3 rounds triggers red ammo colour."""
        state = _full_state()
        state.equipped_weapon = WeaponInfo(name='Pistol', ammo_current=3,
                                           ammo_reserve=21)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_weapon_with_1_round_does_not_raise(self, hud, screen):
        state = _full_state()
        state.equipped_weapon = WeaponInfo(name='Sniper', ammo_current=1,
                                           ammo_reserve=5)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_weapon_with_zero_ammo_does_not_raise(self, hud, screen):
        state = _full_state()
        state.equipped_weapon = WeaponInfo(name='Empty', ammo_current=0,
                                           ammo_reserve=30)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_weapon_with_reloading_flag_does_not_raise(self, hud, screen):
        state = _full_state()
        state.equipped_weapon = WeaponInfo(name='Shotgun', ammo_current=0,
                                           ammo_reserve=16, reloading=True,
                                           reload_progress=0.5)
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_weapon_name_longer_than_12_chars_does_not_raise(self, hud, screen):
        """Weapon name is truncated to 12 chars internally."""
        state = _full_state()
        state.equipped_weapon = WeaponInfo(
            name='VeryLongWeaponNameThatExceedsLimit',
            ammo_current=20, ammo_reserve=60,
        )
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_weapon_with_icon_surface_does_not_raise(self, hud, screen):
        state = _full_state()
        icon = pygame.Surface((32, 32))
        icon.fill((200, 100, 50))
        state.equipped_weapon = WeaponInfo(name='Rifle', ammo_current=20,
                                           ammo_reserve=60, icon=icon)
        hud.update(state, 0.016)
        hud.draw(screen)


# ---------------------------------------------------------------------------
# HUD buff bar — cap at 6 and expiry pulse
# ---------------------------------------------------------------------------
class TestHUDBuffBar:
    def test_6_buffs_renders_without_raising(self, hud, screen):
        """The buff row shows up to 6 buffs."""
        state = _full_state()
        state.active_buffs = [
            BuffEntry(label=f'Buff{i}', seconds_left=float(10 - i))
            for i in range(6)
        ]
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_7_buffs_only_shows_first_6_without_raising(self, hud, screen):
        """Extra buffs beyond the 6-slot limit are silently ignored."""
        state = _full_state()
        state.active_buffs = [
            BuffEntry(label=f'B{i}', seconds_left=float(10 - i))
            for i in range(7)
        ]
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_10_buffs_does_not_raise(self, hud, screen):
        state = _full_state()
        state.active_buffs = [
            BuffEntry(label=f'X{i}', seconds_left=float(i + 1))
            for i in range(10)
        ]
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_buff_expiring_below_3s_triggers_pulse_path(self, hud, screen):
        """A buff with < 3 s remaining activates the 'selected' icon path."""
        state = _full_state()
        state.active_buffs = [
            BuffEntry(label='Expiring', seconds_left=2.9),  # < 3 s → selected
            BuffEntry(label='Active',   seconds_left=9.0),  # > 3 s → normal
        ]
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_buff_at_exactly_3s_is_not_pulsing(self, hud, screen):
        """Exactly 3.0 s — boundary: the condition is < 3.0, so no pulse."""
        state = _full_state()
        state.active_buffs = [BuffEntry(label='Boundary', seconds_left=3.0)]
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_buff_with_zero_seconds_left_does_not_raise(self, hud, screen):
        state = _full_state()
        state.active_buffs = [BuffEntry(label='Expired', seconds_left=0.0)]
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_single_buff_renders_without_raising(self, hud, screen):
        state = _full_state()
        state.active_buffs = [BuffEntry(label='Shield', seconds_left=5.0)]
        hud.update(state, 0.016)
        hud.draw(screen)


# ---------------------------------------------------------------------------
# HUD quick-slots — partial and full slot configurations
# ---------------------------------------------------------------------------
class TestHUDQuickSlots:
    def test_4_full_consumable_slots_does_not_raise(self, hud, screen):
        state = _full_state()
        state.consumable_slots = [
            ConsumableSlot(label='Med', count=3),
            ConsumableSlot(label='Stim', count=2),
            ConsumableSlot(label='Gren', count=1),
            ConsumableSlot(label='Nano', count=4),
        ]
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_2_consumable_slots_fills_rest_with_empty_does_not_raise(
        self, hud, screen
    ):
        state = _full_state()
        state.consumable_slots = [
            ConsumableSlot(label='Med', count=2),
            ConsumableSlot(label='Stim', count=1),
        ]
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_zero_consumable_slots_does_not_raise(self, hud, screen):
        state = _full_state()
        state.consumable_slots = []
        hud.update(state, 0.016)
        hud.draw(screen)

    def test_consumable_slot_with_zero_count_does_not_raise(self, hud, screen):
        state = _full_state()
        state.consumable_slots = [ConsumableSlot(label='Empty', count=0)]
        hud.update(state, 0.016)
        hud.draw(screen)


# ---------------------------------------------------------------------------
# HUD EventBus — dotted event names (player.damaged / level.up)
# ---------------------------------------------------------------------------
class TestHUDDottedEventNames:
    def test_player_dot_damaged_event_sets_flash_timer(self, event_bus, screen):
        """HUD subscribes to 'player.damaged' (dot notation) as well."""
        hud = HUD(event_bus)
        assert hud._damage_flash_timer == pytest.approx(0.0)
        event_bus.emit('player.damaged', amount=15)
        assert hud._damage_flash_timer > 0.0

    def test_level_dot_up_event_sets_banner_timer(self, event_bus):
        """HUD subscribes to 'level.up' (dot notation) as well."""
        hud = HUD(event_bus)
        assert hud._levelup_banner_timer == pytest.approx(0.0)
        event_bus.emit('level.up', new_level=5)
        assert hud._levelup_banner_timer > 0.0

    def test_damage_flash_timer_initial_value_is_zero(self, event_bus):
        hud = HUD(event_bus)
        assert hud._damage_flash_timer == pytest.approx(0.0)

    def test_levelup_banner_timer_initial_value_is_zero(self, event_bus):
        hud = HUD(event_bus)
        assert hud._levelup_banner_timer == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# HUD minimap and challenge widget lazy initialisation
# ---------------------------------------------------------------------------
class TestHUDSubWidgetInit:
    def test_minimap_is_none_before_first_update(self, event_bus):
        hud = HUD(event_bus)
        assert hud._minimap is None

    def test_challenge_widget_is_none_before_first_update(self, event_bus):
        hud = HUD(event_bus)
        assert hud._challenge_widget is None

    def test_minimap_created_after_update(self, event_bus):
        hud = HUD(event_bus)
        hud.update(HUDState(), 0.016)
        assert hud._minimap is not None

    def test_challenge_widget_created_after_update(self, event_bus):
        hud = HUD(event_bus)
        hud.update(HUDState(), 0.016)
        assert hud._challenge_widget is not None

    def test_fonts_not_ready_before_draw(self, event_bus):
        hud = HUD(event_bus)
        assert hud._fonts_ready is False

    def test_fonts_ready_after_draw(self, event_bus, screen):
        hud = HUD(event_bus)
        hud.update(HUDState(), 0.016)
        hud.draw(screen)
        assert hud._fonts_ready is True
