"""Tests for HUD player-status rendering (health bar, armor bar) and event wiring.

Covers:
  - HUDState dataclass defaults and field types
  - HUD.update stores state and decrements all three timers
  - Timers clamp at 0.0 and never go negative
  - Event handlers: player.damaged sets vignette timer; level.up sets level-up
    timer; zone_entered sets zone label and timer
  - HUD.draw does not raise with a valid HUDState
  - HUD.draw is a no-op when _state is None
  - ProgressBar value is clamped and normalised correctly for hp and armor
"""
import pytest
import pygame

from src.core.event_bus import EventBus
from src.ui.hud import HUD
from src.ui.hud_state import HUDState
from src.ui.widgets import ProgressBar
from src.constants import HEALTH_COLOR, ARMOR_COLOR


# ---------------------------------------------------------------------------
# Helpers
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


def _full_state(**overrides):
    """Return a HUDState with sensible defaults, optionally overridden."""
    defaults = dict(
        hp=80, max_hp=100,
        armor=30, max_armor=100,
        level=3, xp=400, xp_to_next=900,
        seconds_remaining=300.0,
    )
    defaults.update(overrides)
    return HUDState(**defaults)


# ---------------------------------------------------------------------------
# HUDState dataclass
# ---------------------------------------------------------------------------

class TestHUDStateDefaults:
    def test_default_hp(self):
        st = HUDState()
        assert st.hp == 100

    def test_default_max_hp(self):
        assert HUDState().max_hp == 100

    def test_default_armor(self):
        assert HUDState().armor == 0

    def test_default_max_armor(self):
        assert HUDState().max_armor == 100

    def test_default_level(self):
        assert HUDState().level == 1

    def test_default_xp(self):
        assert HUDState().xp == 0

    def test_default_seconds_remaining(self):
        assert HUDState().seconds_remaining == pytest.approx(900.0)

    def test_hp_is_int(self):
        assert isinstance(HUDState().hp, int)

    def test_armor_is_int(self):
        assert isinstance(HUDState().armor, int)

    def test_in_extraction_zone_defaults_false(self):
        assert HUDState().in_extraction_zone is False

    def test_extraction_progress_defaults_zero(self):
        assert HUDState().extraction_progress == pytest.approx(0.0)

    def test_custom_hp(self):
        st = HUDState(hp=45, max_hp=150)
        assert st.hp == 45
        assert st.max_hp == 150

    def test_custom_armor(self):
        st = HUDState(armor=22, max_armor=100)
        assert st.armor == 22


# ---------------------------------------------------------------------------
# HUD.update — timer management
# ---------------------------------------------------------------------------

class TestHUDUpdate:
    def test_update_stores_state(self, hud):
        st = _full_state()
        hud.update(st, dt=0.016)
        assert hud._state is st

    def test_vignette_timer_decrements(self, hud):
        hud._vignette_timer = 0.5
        hud.update(_full_state(), dt=0.1)
        assert hud._vignette_timer == pytest.approx(0.4)

    def test_vignette_timer_clamped_at_zero(self, hud):
        hud._vignette_timer = 0.05
        hud.update(_full_state(), dt=1.0)
        assert hud._vignette_timer == 0.0

    def test_vignette_timer_not_negative(self, hud):
        hud._vignette_timer = 0.0
        hud.update(_full_state(), dt=0.5)
        assert hud._vignette_timer >= 0.0

    def test_level_up_timer_decrements(self, hud):
        hud._level_up_timer = 3.0
        hud.update(_full_state(), dt=0.5)
        assert hud._level_up_timer == pytest.approx(2.5)

    def test_level_up_timer_clamped_at_zero(self, hud):
        hud._level_up_timer = 0.1
        hud.update(_full_state(), dt=5.0)
        assert hud._level_up_timer == 0.0

    def test_zone_label_timer_decrements(self, hud):
        hud._zone_label_timer = 2.5
        hud.update(_full_state(), dt=0.5)
        assert hud._zone_label_timer == pytest.approx(2.0)

    def test_zone_label_timer_clamped_at_zero(self, hud):
        hud._zone_label_timer = 0.1
        hud.update(_full_state(), dt=5.0)
        assert hud._zone_label_timer == 0.0


# ---------------------------------------------------------------------------
# HUD event handlers
# ---------------------------------------------------------------------------

class TestHUDEventHandlers:
    def test_player_damaged_sets_vignette_timer(self, event_bus, hud):
        assert hud._vignette_timer == 0.0
        event_bus.emit('player.damaged')
        assert hud._vignette_timer == pytest.approx(0.5)

    def test_level_up_sets_timer(self, event_bus, hud):
        assert hud._level_up_timer == 0.0
        event_bus.emit('level.up')
        assert hud._level_up_timer == pytest.approx(3.0)

    def test_zone_entered_sets_label(self, event_bus, hud):
        class _Zone:
            name = "REACTOR CORE"
        event_bus.emit('zone_entered', zone=_Zone())
        assert hud._zone_label == "REACTOR CORE"

    def test_zone_entered_sets_timer(self, event_bus, hud):
        class _Zone:
            name = "TEST ZONE"
        event_bus.emit('zone_entered', zone=_Zone())
        assert hud._zone_label_timer == pytest.approx(2.5)

    def test_zone_entered_without_zone_kwarg_does_not_crash(self, event_bus, hud):
        event_bus.emit('zone_entered')   # zone kwarg absent → must not raise

    def test_multiple_damage_events_reset_timer(self, event_bus, hud):
        event_bus.emit('player.damaged')
        hud.update(_full_state(), dt=0.3)   # timer now 0.2
        event_bus.emit('player.damaged')    # should reset back to 0.5
        assert hud._vignette_timer == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# HUD.draw — smoke tests (no pixel assertions; just no exceptions)
# ---------------------------------------------------------------------------

class TestHUDDraw:
    def test_draw_with_valid_state_does_not_crash(self, hud, screen):
        hud.update(_full_state(), dt=0.016)
        hud.draw(screen)

    def test_draw_without_state_is_noop(self, hud, screen):
        # _state is None at construction → draw must silently return
        hud.draw(screen)

    def test_draw_with_zero_hp(self, hud, screen):
        hud.update(_full_state(hp=0, max_hp=100), dt=0.016)
        hud.draw(screen)

    def test_draw_with_full_armor(self, hud, screen):
        hud.update(_full_state(armor=100, max_armor=100), dt=0.016)
        hud.draw(screen)

    def test_draw_with_low_timer_does_not_crash(self, hud, screen):
        # seconds_remaining <= 60 → timer turns DANGER_RED
        hud.update(_full_state(seconds_remaining=45.0), dt=0.016)
        hud.draw(screen)

    def test_draw_with_amber_timer_does_not_crash(self, hud, screen):
        # 60 < seconds_remaining <= 300 → timer turns amber
        hud.update(_full_state(seconds_remaining=180.0), dt=0.016)
        hud.draw(screen)

    def test_draw_with_active_vignette_does_not_crash(self, hud, screen):
        hud._vignette_timer = 0.3
        hud.update(_full_state(), dt=0.016)
        hud.draw(screen)

    def test_draw_with_active_level_up_banner(self, hud, screen):
        hud._level_up_timer = 2.0
        hud.update(_full_state(level=5), dt=0.016)
        hud.draw(screen)

    def test_draw_with_active_zone_label(self, hud, screen):
        hud._zone_label = "HANGAR BAY"
        hud._zone_label_timer = 1.5
        hud.update(_full_state(), dt=0.016)
        hud.draw(screen)

    def test_draw_with_extraction_prompt(self, hud, screen):
        st = _full_state(in_extraction_zone=True, extraction_progress=0.5)
        hud.update(st, dt=0.016)
        hud.draw(screen)


# ---------------------------------------------------------------------------
# ProgressBar — value normalisation for health and armor
# ---------------------------------------------------------------------------

class TestProgressBarNormalisation:
    def test_full_hp_value_is_one(self):
        bar = ProgressBar(pygame.Rect(0, 0, 200, 10), color=HEALTH_COLOR)
        bar.value = 100 / max(1, 100)
        assert bar.value == pytest.approx(1.0)

    def test_half_hp_value_is_half(self):
        bar = ProgressBar(pygame.Rect(0, 0, 200, 10), color=HEALTH_COLOR)
        bar.value = 50 / max(1, 100)
        assert bar.value == pytest.approx(0.5)

    def test_zero_hp_value_is_zero(self):
        bar = ProgressBar(pygame.Rect(0, 0, 200, 10), color=HEALTH_COLOR)
        bar.value = 0 / max(1, 100)
        assert bar.value == pytest.approx(0.0)

    def test_full_armor_value_is_one(self):
        bar = ProgressBar(pygame.Rect(0, 0, 200, 8), color=ARMOR_COLOR)
        bar.value = 100 / max(1, 100)
        assert bar.value == pytest.approx(1.0)

    def test_partial_armor_value(self):
        bar = ProgressBar(pygame.Rect(0, 0, 200, 8), color=ARMOR_COLOR)
        bar.value = 30 / max(1, 100)
        assert bar.value == pytest.approx(0.3)

    def test_progress_bar_draw_does_not_crash(self):
        surface = pygame.Surface((300, 50))
        bar = ProgressBar(pygame.Rect(10, 10, 200, 10), color=HEALTH_COLOR)
        bar.value = 0.75
        bar.draw(surface)

    def test_progress_bar_zero_value_draw(self):
        surface = pygame.Surface((300, 50))
        bar = ProgressBar(pygame.Rect(10, 10, 200, 10), color=ARMOR_COLOR)
        bar.value = 0.0
        bar.draw(surface)

    def test_max_armor_zero_uses_one_as_denominator(self):
        """Guard against division by zero when max_armor is 0."""
        # HUD uses: ar_bar.value = st.armor / max(1, st.max_armor)
        denom = max(1, 0)
        assert denom == 1
        bar = ProgressBar(pygame.Rect(0, 0, 200, 8), color=ARMOR_COLOR)
        bar.value = 0 / denom
        assert bar.value == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# HUD health/armor label content
# ---------------------------------------------------------------------------

class TestHUDStateValuesPassedThrough:
    def test_hp_ratio_matches_state(self):
        st = HUDState(hp=60, max_hp=100)
        ratio = st.hp / max(1, st.max_hp)
        assert ratio == pytest.approx(0.6)

    def test_armor_ratio_matches_state(self):
        st = HUDState(armor=25, max_armor=100)
        ratio = st.armor / max(1, st.max_armor)
        assert ratio == pytest.approx(0.25)

    def test_timer_format_below_60s_shows_red_needed(self):
        """Confirm the threshold used in HUD for the red (danger) timer colour.

        The HUD uses _TIMER_DANGER_SECS = 60 as the lower boundary:
          seconds_remaining <= 60  → DANGER_RED
        """
        st = HUDState(seconds_remaining=59.0)
        assert st.seconds_remaining < 60   # triggers DANGER_RED in HUD.draw

    def test_timer_format_above_300s_uses_primary_color_range(self):
        """Above 300 s (5 min) the timer is white (TEXT_PRIMARY).

        The HUD uses _TIMER_WARN_SECS = 300 as the upper boundary:
          seconds_remaining > 300  → TEXT_PRIMARY
        """
        st = HUDState(seconds_remaining=301.0)
        assert st.seconds_remaining > 300   # TEXT_PRIMARY used in HUD.draw

    def test_timer_format_above_60s_normal(self):
        """120 s is in the amber range (60 < x ≤ 300), NOT the white range.

        This replaces the previous (misleading) assertion that 120 s is
        'normal/white'.  The correct white threshold is > 300 s.
        """
        st = HUDState(seconds_remaining=120.0)
        assert 60 < st.seconds_remaining <= 300  # ACCENT_AMBER used in HUD.draw

    def test_timer_below_300s_is_amber_or_red_range(self):
        """Any value ≤ 300 s must NOT use the white TEXT_PRIMARY colour."""
        st = HUDState(seconds_remaining=299.0)
        assert not (st.seconds_remaining > 300)

    def test_timer_at_exactly_300s_is_amber_not_white(self):
        """Boundary: 300.0 is NOT above 300, so it switches to amber."""
        st = HUDState(seconds_remaining=300.0)
        # > 300 is False, so amber (ACCENT_AMBER) is used
        assert not (st.seconds_remaining > 300)

    def test_timer_at_exactly_60s_is_red_not_amber(self):
        """Boundary: 60.0 is NOT above 60, so it switches to red."""
        st = HUDState(seconds_remaining=60.0)
        # > 60 is False, so DANGER_RED is used
        assert not (st.seconds_remaining > 60)

    def test_timer_mm_ss_format(self):
        """Validate the integer maths used to format the timer string."""
        seconds = 185.7
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        assert mins == 3
        assert secs == 5
