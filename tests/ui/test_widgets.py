"""Tests for widget primitives — src/ui/widgets.py

Focused on StatCounter, the animated count-up widget introduced for the
PostRound feature (Task 2 / Task 7 in the feature plan).
"""
import pygame
import pytest

from src.ui.widgets import StatCounter


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def counter(pygame_init):
    return StatCounter(
        label="XP Earned",
        target_value=1000,
        prefix="+",
        color=(57, 255, 20),   # ACCENT_GREEN
        duration=1.0,
        delay=0.0,
    )


# ── Initial state (before start()) ────────────────────────────────────────────

class TestStatCounterInitialState:

    def test_current_value_is_zero(self, counter):
        assert counter.current_value == 0

    def test_is_done_is_false(self, counter):
        assert counter.is_done is False

    def test_update_before_start_has_no_effect_on_value(self, counter):
        counter.update(5.0)
        assert counter.current_value == 0

    def test_update_before_start_does_not_set_done(self, counter):
        counter.update(5.0)
        assert counter.is_done is False


# ── Animation progression ──────────────────────────────────────────────────────

class TestStatCounterAnimation:

    def test_reaches_target_after_exact_duration(self, counter):
        counter.start()
        counter.update(1.0)   # == duration
        assert counter.current_value == 1000

    def test_is_done_true_after_full_duration(self, counter):
        counter.start()
        counter.update(1.0)
        assert counter.is_done is True

    def test_overshoot_clamps_to_target(self, counter):
        counter.start()
        counter.update(100.0)
        assert counter.current_value == 1000

    def test_is_done_false_partway_through(self, counter):
        counter.start()
        counter.update(0.5)
        assert counter.is_done is False

    def test_value_positive_partway_through(self, counter):
        counter.start()
        counter.update(0.5)
        assert counter.current_value > 0

    def test_value_never_negative(self, counter):
        counter.start()
        counter.update(0.001)
        assert counter.current_value >= 0


# ── Ease-out curve: 1 − (1 − t)² ─────────────────────────────────────────────

class TestEaseOutCurve:

    def test_midpoint_t05_gives_approx_75_percent(self, counter):
        """ease_out(0.5) = 1 − 0.5² = 0.75  →  value ≈ 750."""
        counter.start()
        counter.update(0.5)
        assert abs(counter.current_value - 750) <= 1

    def test_quarter_point_t025_gives_approx_4375_percent(self, counter):
        """ease_out(0.25) = 1 − 0.75² = 0.4375  →  value ≈ 437."""
        counter.start()
        counter.update(0.25)
        assert abs(counter.current_value - 437) <= 1

    def test_three_quarter_point_t075_gives_approx_9375_percent(self, counter):
        """ease_out(0.75) = 1 − 0.25² = 0.9375  →  value ≈ 937."""
        counter.start()
        counter.update(0.75)
        assert abs(counter.current_value - 937) <= 1

    def test_value_grows_faster_early_than_late(self, counter):
        """Ease-out means the first half of time covers more than 50% of value."""
        counter.start()
        counter.update(0.5)
        halfway_value = counter.current_value
        assert halfway_value > 500   # more than linear midpoint


# ── Delay ──────────────────────────────────────────────────────────────────────

class TestStatCounterDelay:

    @pytest.fixture
    def delayed(self, pygame_init):
        return StatCounter(
            label="Money Earned",
            target_value=500,
            prefix="$",
            color=(255, 184, 0),   # ACCENT_AMBER
            duration=1.0,
            delay=0.5,
        )

    def test_value_zero_during_delay_period(self, delayed):
        delayed.start()
        delayed.update(0.49)
        assert delayed.current_value == 0

    def test_is_done_false_during_delay_period(self, delayed):
        delayed.start()
        delayed.update(0.49)
        assert delayed.is_done is False

    def test_value_positive_just_after_delay(self, delayed):
        delayed.start()
        delayed.update(0.6)   # 0.1 s into the animation after 0.5 s delay
        assert delayed.current_value > 0

    def test_reaches_target_after_delay_plus_duration(self, delayed):
        delayed.start()
        delayed.update(1.5)   # 0.5 delay + 1.0 duration
        assert delayed.current_value == 500
        assert delayed.is_done is True

    def test_exact_delay_boundary_value_still_zero(self, delayed):
        delayed.start()
        delayed.update(0.5)   # exactly at delay boundary, t=0
        assert delayed.current_value == 0


# ── Zero target ────────────────────────────────────────────────────────────────

class TestStatCounterZeroTarget:

    def test_zero_target_value_is_zero_after_duration(self, pygame_init):
        c = StatCounter("Kills", 0, "", (255, 255, 255), duration=1.0, delay=0.0)
        c.start()
        c.update(1.0)
        assert c.current_value == 0

    def test_zero_target_is_done_after_duration(self, pygame_init):
        c = StatCounter("Kills", 0, "", (255, 255, 255), duration=1.0, delay=0.0)
        c.start()
        c.update(1.0)
        assert c.is_done is True


# ── Restart / idempotency ──────────────────────────────────────────────────────

class TestStatCounterRestart:

    def test_start_resets_value_to_zero(self, counter):
        counter.start()
        counter.update(0.5)
        assert counter.current_value > 0
        counter.start()
        assert counter.current_value == 0

    def test_start_resets_is_done_to_false(self, counter):
        counter.start()
        counter.update(2.0)
        assert counter.is_done is True
        counter.start()
        assert counter.is_done is False

    def test_restarted_counter_reaches_target_again(self, counter):
        counter.start()
        counter.update(1.0)
        counter.start()
        counter.update(1.0)
        assert counter.current_value == 1000
        assert counter.is_done is True


# ── Incremental updates ────────────────────────────────────────────────────────

class TestStatCounterIncrementalUpdates:

    def test_many_small_updates_equal_one_large_update(self, pygame_init):
        """60 × 1/60 s ticks should reach the same result as update(1.0)."""
        c1 = StatCounter("A", 1000, "", (255, 255, 255), duration=1.0, delay=0.0)
        c2 = StatCounter("B", 1000, "", (255, 255, 255), duration=1.0, delay=0.0)
        c1.start()
        c2.start()
        for _ in range(60):
            c1.update(1 / 60)
        c2.update(1.0)
        assert c1.current_value == c2.current_value
        assert c1.is_done == c2.is_done


# ── Render (smoke) ─────────────────────────────────────────────────────────────

class TestStatCounterRender:

    def test_render_before_start_does_not_raise(self, counter, screen):
        counter.render(screen)

    def test_render_mid_animation_does_not_raise(self, counter, screen):
        counter.start()
        counter.update(0.5)
        counter.render(screen)

    def test_render_after_completion_does_not_raise(self, counter, screen):
        counter.start()
        counter.update(2.0)
        counter.render(screen)

    def test_render_returns_none_or_rect(self, counter, screen):
        result = counter.render(screen)
        assert result is None or isinstance(result, pygame.Rect)
