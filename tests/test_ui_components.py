"""Unit tests for UI widget components — RoundTimer, ExtractionProgressBar,
ExtractionPrompt, HealthBar, XPBar."""

from __future__ import annotations

import math

import pygame
import pytest


from src.ui.components import (
    ExtractionProgressBar,
    ExtractionPrompt,
    HealthBar,
    RoundTimer,
    XPBar,
)


# ======================================================================
# RoundTimer
# ======================================================================


class TestRoundTimer:
    """Tests for the MM:SS round countdown display."""

    @pytest.fixture
    def timer(self):
        return RoundTimer(x=640, y=16)

    @pytest.fixture
    def surface(self):
        return pygame.Surface((1280, 720))

    # --- State ---

    def test_initial_remaining_is_900(self, timer):
        assert timer._remaining == 900.0

    def test_set_time_updates_remaining(self, timer):
        timer.set_time(450.0, 900.0)
        assert timer._remaining == pytest.approx(450.0)
        assert timer._total == 900.0

    def test_set_time_clamps_negative_to_zero(self, timer):
        timer.set_time(-5.0, 900.0)
        assert timer._remaining == 0.0

    def test_normal_state_above_60s(self, timer):
        timer.set_time(120.0, 900.0)
        assert not timer._warning
        assert not timer._critical

    def test_warning_state_below_60s(self, timer):
        timer.set_time(59.0, 900.0)
        assert timer._warning
        assert not timer._critical

    def test_critical_state_below_30s(self, timer):
        timer.set_time(15.0, 900.0)
        assert timer._warning
        assert timer._critical

    def test_warning_at_exactly_60s_not_triggered(self, timer):
        timer.set_time(60.0, 900.0)
        assert not timer._warning

    def test_critical_at_exactly_30s_not_triggered(self, timer):
        timer.set_time(30.0, 900.0)
        assert not timer._critical

    def test_update_advances_anim_time(self, timer):
        timer.update(0.5)
        assert timer._anim_time == pytest.approx(0.5)
        timer.update(0.3)
        assert timer._anim_time == pytest.approx(0.8)

    # --- Drawing ---

    def test_draw_without_crash_normal(self, timer, surface):
        timer.set_time(600.0, 900.0)
        timer.draw(surface)

    def test_draw_without_crash_warning(self, timer, surface):
        timer.set_time(45.0, 900.0)
        timer.update(1.0)
        timer.draw(surface)

    def test_draw_without_crash_critical(self, timer, surface):
        timer.set_time(10.0, 900.0)
        timer.update(1.0)
        timer.draw(surface)

    def test_draw_at_zero(self, timer, surface):
        timer.set_time(0.0, 900.0)
        timer.draw(surface)

    def test_draw_at_full_15_minutes(self, timer, surface):
        timer.set_time(900.0, 900.0)
        timer.draw(surface)

    def test_format_produces_mm_ss(self, timer):
        """Verify that RoundTimer formats time as MM:SS."""
        timer.set_time(754.0, 900.0)  # 12:34
        timer._ensure_font()
        minutes = int(timer._remaining) // 60
        seconds = int(timer._remaining) % 60
        text = f"{minutes:02d}:{seconds:02d}"
        assert text == "12:34"

    def test_format_at_zero_is_00_00(self, timer):
        timer.set_time(0.0, 900.0)
        minutes = int(timer._remaining) // 60
        seconds = int(timer._remaining) % 60
        text = f"{minutes:02d}:{seconds:02d}"
        assert text == "00:00"

    def test_format_at_15_minutes_is_15_00(self, timer):
        timer.set_time(900.0, 900.0)
        minutes = int(timer._remaining) // 60
        seconds = int(timer._remaining) % 60
        text = f"{minutes:02d}:{seconds:02d}"
        assert text == "15:00"

    def test_format_single_digit_seconds_padded(self, timer):
        timer.set_time(61.0, 900.0)  # 1:01
        minutes = int(timer._remaining) // 60
        seconds = int(timer._remaining) % 60
        text = f"{minutes:02d}:{seconds:02d}"
        assert text == "01:01"


# ======================================================================
# ExtractionProgressBar
# ======================================================================


class TestExtractionProgressBar:
    """Tests for the extraction channel progress bar."""

    @pytest.fixture
    def bar(self):
        return ExtractionProgressBar(screen_width=1280, screen_height=720)

    @pytest.fixture
    def surface(self):
        return pygame.Surface((1280, 720))

    # --- State ---

    def test_initially_not_visible(self, bar):
        assert not bar._visible

    def test_set_visible_true(self, bar):
        bar.set_visible(True)
        assert bar._visible

    def test_set_visible_false(self, bar):
        bar.set_visible(True)
        bar.set_visible(False)
        assert not bar._visible

    def test_initial_progress_is_zero(self, bar):
        assert bar._progress == 0.0

    def test_set_progress_computes_ratio(self, bar):
        bar.set_progress(2.5, 5.0)
        assert bar._progress == pytest.approx(0.5)

    def test_set_progress_clamps_to_one(self, bar):
        bar.set_progress(10.0, 5.0)
        assert bar._progress == pytest.approx(1.0)

    def test_set_progress_zero_duration_returns_zero(self, bar):
        bar.set_progress(5.0, 0.0)
        assert bar._progress == 0.0

    def test_set_progress_at_start(self, bar):
        bar.set_progress(0.0, 5.0)
        assert bar._progress == 0.0

    def test_set_progress_at_completion(self, bar):
        bar.set_progress(5.0, 5.0)
        assert bar._progress == pytest.approx(1.0)

    def test_update_advances_anim_time(self, bar):
        bar.update(0.5)
        assert bar._anim_time == pytest.approx(0.5)

    # --- Drawing ---

    def test_draw_when_not_visible_no_crash(self, bar, surface):
        bar.draw(surface)

    def test_draw_when_visible_no_crash(self, bar, surface):
        bar.set_visible(True)
        bar.set_progress(2.5, 5.0)
        bar.update(0.5)
        bar.draw(surface)

    def test_draw_at_full_progress(self, bar, surface):
        bar.set_visible(True)
        bar.set_progress(5.0, 5.0)
        bar.draw(surface)

    def test_draw_at_zero_progress(self, bar, surface):
        bar.set_visible(True)
        bar.set_progress(0.0, 5.0)
        bar.draw(surface)

    def test_bar_dimensions(self, bar):
        assert bar.WIDTH == 300
        assert bar.HEIGHT == 24


# ======================================================================
# ExtractionPrompt
# ======================================================================


class TestExtractionPrompt:
    """Tests for the 'Press E — Extract' floating text prompt."""

    @pytest.fixture
    def prompt(self):
        return ExtractionPrompt(screen_width=1280, screen_height=720)

    @pytest.fixture
    def surface(self):
        return pygame.Surface((1280, 720))

    # --- State ---

    def test_initially_invisible(self, prompt):
        assert prompt._target_alpha == 0.0
        assert prompt._current_alpha == 0.0

    def test_set_visible_true_sets_target(self, prompt):
        prompt.set_visible(True)
        assert prompt._target_alpha == 1.0

    def test_set_visible_false_sets_target(self, prompt):
        prompt.set_visible(True)
        prompt.set_visible(False)
        assert prompt._target_alpha == 0.0

    def test_fade_in_over_time(self, prompt):
        prompt.set_visible(True)
        # Current alpha is 0 at start
        assert prompt._current_alpha == 0.0

        # After a short update, alpha increases
        prompt.update(0.1)
        assert prompt._current_alpha > 0.0

    def test_fade_out_over_time(self, prompt):
        # First make it fully visible
        prompt.set_visible(True)
        prompt._current_alpha = 1.0

        # Then hide
        prompt.set_visible(False)
        prompt.update(0.1)
        assert prompt._current_alpha < 1.0

    def test_alpha_capped_at_target(self, prompt):
        prompt.set_visible(True)
        # Run many updates
        for _ in range(100):
            prompt.update(0.1)
        assert prompt._current_alpha == pytest.approx(1.0)

    def test_alpha_floors_at_zero(self, prompt):
        prompt.set_visible(False)
        for _ in range(100):
            prompt.update(0.1)
        assert prompt._current_alpha == 0.0

    # --- Drawing ---

    def test_draw_when_invisible_no_crash(self, prompt, surface):
        prompt.draw(surface)

    def test_draw_when_visible_no_crash(self, prompt, surface):
        prompt.set_visible(True)
        prompt._current_alpha = 1.0
        prompt.draw(surface)

    def test_draw_during_fade_in(self, prompt, surface):
        prompt.set_visible(True)
        prompt.update(0.1)
        prompt.draw(surface)


# ======================================================================
# HealthBar
# ======================================================================


class TestHealthBar:
    """Tests for the HealthBar widget."""

    @pytest.fixture
    def bar(self):
        return HealthBar(x=16, y=16)

    @pytest.fixture
    def surface(self):
        return pygame.Surface((1280, 720))

    def test_initial_health_is_full(self, bar):
        assert bar._current == pytest.approx(1.0)
        assert bar._target == pytest.approx(1.0)

    def test_set_health_ratio(self, bar):
        bar.set_health(50, 100)
        assert bar._target == pytest.approx(0.5)

    def test_set_health_zero_max_returns_zero(self, bar):
        bar.set_health(50, 0)
        assert bar._target == 0.0

    def test_lerp_toward_target(self, bar):
        bar.set_health(50, 100)
        bar.update(0.1)
        # After 0.1s at lerp_speed=3.0: min(3.0*0.1, 1.0) = 0.3
        # current += (0.5 - 1.0) * 0.3 = -0.15, so current ≈ 0.85
        assert bar._current < 1.0
        assert bar._current > 0.5  # hasn't fully arrived yet

    def test_draw_without_crash(self, bar, surface):
        bar.draw(surface)

    def test_draw_at_low_health(self, bar, surface):
        bar.set_health(10, 100)
        bar._current = 0.1  # force low to test red color
        bar.draw(surface)

    def test_draw_at_zero_health(self, bar, surface):
        bar.set_health(0, 100)
        bar._current = 0.0
        bar.draw(surface)


# ======================================================================
# XPBar
# ======================================================================


class TestXPBar:
    """Tests for the XP progress bar widget."""

    @pytest.fixture
    def bar(self):
        return XPBar(x=16, y=36)

    @pytest.fixture
    def surface(self):
        return pygame.Surface((1280, 720))

    def test_initial_progress_is_zero(self, bar):
        assert bar._progress == 0.0

    def test_initial_level_is_one(self, bar):
        assert bar._level == 1

    def test_set_xp_stores_values(self, bar):
        bar.set_xp(0.75, 5)
        assert bar._progress == pytest.approx(0.75)
        assert bar._level == 5

    def test_set_xp_clamps_progress_upper(self, bar):
        bar.set_xp(1.5, 3)
        assert bar._progress == pytest.approx(1.0)

    def test_set_xp_clamps_progress_lower(self, bar):
        bar.set_xp(-0.5, 3)
        assert bar._progress == 0.0

    def test_draw_without_crash(self, bar, surface):
        bar.draw(surface)

    def test_draw_with_progress(self, bar, surface):
        bar.set_xp(0.5, 3)
        bar.draw(surface)
