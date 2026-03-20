"""Unit tests for :class:`~src.systems.round_timer.RoundTimer`.

Coverage matrix
---------------
Countdown behaviour
  - seconds_remaining initialised to duration
  - update() is a no-op before start() is called
  - seconds_remaining decrements by dt each call
  - fractional dt is accumulated correctly
  - multiple sequential updates accumulate
  - seconds_remaining is clamped to 0.0 (never goes negative)
  - update() is a no-op after the timer has expired

timer_tick events
  - no tick fires for a sub-second update
  - exactly one tick fires per elapsed whole second
  - tick payload carries floor(seconds_remaining) after decrement
  - two sequential one-second updates each fire one tick
  - one large dt that spans N whole seconds fires N ticks in order
  - no duplicate ticks when dt lands exactly on a second boundary

round_end event
  - round_end fires once when the timer expires
  - round_end fires on a large dt that overshoots zero
  - round_end fires exactly once (no re-fire on continued updates)
  - round_end does not fire before expiry
  - round_end does not fire if start() was never called

is_expired property
  - False initially
  - False while counting down
  - True after reaching zero
  - True after overshoot
  - False if start() was never called

display_str formatting
  - "15:00" for 900 s (full round)
  - "00:00" for 0 s
  - "00:59" for 59 s
  - "01:00" for 60 s
  - "07:30" for 450 s
  - "01:05" for 65 s (leading zero on minutes)
  - fractional sub-second remainder is truncated, not rounded

reset
  - restores seconds_remaining to full duration
  - halts the timer (update is no-op after reset until start is called again)
  - clears the is_expired flag
  - allows timer to be restarted after reset
  - clears the internal tick tracker so no stale ticks fire after restart
"""
from __future__ import annotations

import pytest

from src.core.constants import ROUND_DURATION_SECS, TIMER_WARN_SECS
from src.core.event_bus import EventBus
from src.systems.round_timer import RoundTimer


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def make_timer(duration: float = ROUND_DURATION_SECS) -> tuple[RoundTimer, EventBus]:
    """Return a fresh *(timer, bus)* pair with the given duration."""
    bus = EventBus()
    return RoundTimer(bus, duration=duration), bus


def collect_ticks(bus: EventBus) -> list[int]:
    """Subscribe a collector to 'timer_tick' and return the list it fills."""
    ticks: list[int] = []
    bus.subscribe("timer_tick", lambda seconds_remaining: ticks.append(seconds_remaining))
    return ticks


def count_round_ends(bus: EventBus) -> list[bool]:
    """Subscribe a counter to 'round_end' and return the list it fills."""
    calls: list[bool] = []
    bus.subscribe("round_end", lambda **kw: calls.append(True))
    return calls


# ===========================================================================
# Countdown behaviour
# ===========================================================================

class TestCountdown:
    def test_seconds_remaining_starts_at_duration(self):
        timer, _ = make_timer(60.0)
        assert timer.seconds_remaining == pytest.approx(60.0)

    def test_update_before_start_is_noop(self):
        """update() must not decrement while the timer has not been started."""
        timer, _ = make_timer(60.0)
        timer.update(5.0)
        assert timer.seconds_remaining == pytest.approx(60.0)

    def test_countdown_decrements_by_dt(self):
        timer, _ = make_timer(60.0)
        timer.start()
        timer.update(1.0)
        assert timer.seconds_remaining == pytest.approx(59.0)

    def test_countdown_decrements_by_fractional_dt(self):
        timer, _ = make_timer(10.0)
        timer.start()
        timer.update(0.5)
        assert timer.seconds_remaining == pytest.approx(9.5)

    def test_countdown_multiple_updates_accumulate(self):
        timer, _ = make_timer(10.0)
        timer.start()
        for _ in range(5):
            timer.update(1.0)
        assert timer.seconds_remaining == pytest.approx(5.0)

    def test_seconds_remaining_clamped_to_zero(self):
        """A single overshooting dt must not push seconds_remaining below 0."""
        timer, _ = make_timer(1.0)
        timer.start()
        timer.update(100.0)
        assert timer.seconds_remaining == pytest.approx(0.0)

    def test_update_after_expiry_is_noop(self):
        """Further calls to update() after expiry must not change state."""
        timer, _ = make_timer(1.0)
        timer.start()
        timer.update(1.0)
        timer.update(99.0)
        assert timer.seconds_remaining == pytest.approx(0.0)


# ===========================================================================
# timer_tick events
# ===========================================================================

class TestTimerTick:
    def test_no_additional_tick_within_same_second(self):
        """Within a single whole-second interval, no new tick fires after the first.

        The first update from a fresh 10 s timer fires tick(9) immediately
        (floor(9.x) == 9 < ceil(10) == 10).  A second sub-second update that
        stays within the same whole-second window must not fire again.
        """
        timer, bus = make_timer(10.0)
        ticks = collect_ticks(bus)
        timer.start()
        timer.update(0.5)       # remaining=9.5 → tick(9) fires (first tick)
        assert len(ticks) == 1  # exactly one tick so far
        timer.update(0.4)       # remaining=9.1 → floor still 9, no new tick
        assert len(ticks) == 1  # still only tick(9)

    def test_one_tick_per_elapsed_whole_second(self):
        timer, bus = make_timer(10.0)
        ticks = collect_ticks(bus)
        timer.start()
        timer.update(1.0)
        assert len(ticks) == 1

    def test_tick_carries_floor_of_remaining(self):
        """timer_tick payload must equal floor(seconds_remaining) after decrement."""
        timer, bus = make_timer(10.0)
        ticks = collect_ticks(bus)
        timer.start()
        timer.update(1.0)   # 9.0 s remaining → tick(9)
        assert ticks == [9]

    def test_two_sequential_updates_each_fire_one_tick(self):
        timer, bus = make_timer(10.0)
        ticks = collect_ticks(bus)
        timer.start()
        timer.update(1.0)   # tick(9)
        timer.update(1.0)   # tick(8)
        assert ticks == [9, 8]

    def test_large_dt_fires_one_tick_per_skipped_second(self):
        """A single dt spanning N whole seconds must emit N ticks."""
        timer, bus = make_timer(10.0)
        ticks = collect_ticks(bus)
        timer.start()
        timer.update(3.0)   # crosses 9, 8, 7 → three ticks
        assert len(ticks) == 3
        assert sorted(ticks, reverse=True) == [9, 8, 7]

    def test_no_duplicate_ticks_on_exact_second_boundary(self):
        """dt=1.0 each frame for N frames must produce exactly N ticks."""
        timer, bus = make_timer(5.0)
        ticks = collect_ticks(bus)
        timer.start()
        for _ in range(5):
            timer.update(1.0)
        # Expected: tick(4), tick(3), tick(2), tick(1), tick(0)
        assert ticks == [4, 3, 2, 1, 0]

    def test_fractional_updates_accumulate_to_cross_second_boundaries(self):
        """Three partial updates that together span a second boundary fire the right ticks.

        0.4 s → remaining=9.6 → tick(9) fires (first tick from 10 s timer).
        0.4 s → remaining=9.2 → floor still 9, no new tick.
        0.3 s → remaining=8.9 → floor drops to 8 → tick(8) fires.
        """
        timer, bus = make_timer(10.0)
        ticks = collect_ticks(bus)
        timer.start()
        timer.update(0.4)   # tick(9) fires immediately
        timer.update(0.4)   # floor(9.2)=9, still within same second — no new tick
        assert len(ticks) == 1
        timer.update(0.3)   # remaining=8.9 → floor drops to 8 → tick(8)
        assert ticks == [9, 8]


# ===========================================================================
# round_end event
# ===========================================================================

class TestRoundEnd:
    def test_round_end_fires_when_timer_expires(self):
        timer, bus = make_timer(1.0)
        calls = count_round_ends(bus)
        timer.start()
        timer.update(1.0)
        assert len(calls) == 1

    def test_round_end_fires_on_overshooting_dt(self):
        """round_end must fire even when a single dt jumps past zero."""
        timer, bus = make_timer(1.0)
        calls = count_round_ends(bus)
        timer.start()
        timer.update(100.0)
        assert len(calls) == 1

    def test_round_end_fires_exactly_once(self):
        """Continued updates after expiry must not re-fire round_end."""
        timer, bus = make_timer(1.0)
        calls = count_round_ends(bus)
        timer.start()
        timer.update(1.0)
        timer.update(5.0)   # should be no-op
        timer.update(5.0)   # should be no-op
        assert len(calls) == 1

    def test_round_end_not_fired_before_expiry(self):
        timer, bus = make_timer(10.0)
        calls = count_round_ends(bus)
        timer.start()
        timer.update(5.0)
        assert calls == []

    def test_round_end_not_fired_without_start(self):
        """Updating without calling start() must never fire round_end."""
        timer, bus = make_timer(1.0)
        calls = count_round_ends(bus)
        timer.update(100.0)
        assert calls == []


# ===========================================================================
# is_expired property
# ===========================================================================

class TestIsExpired:
    def test_not_expired_initially(self):
        timer, _ = make_timer()
        assert not timer.is_expired

    def test_not_expired_while_counting_down(self):
        timer, _ = make_timer(10.0)
        timer.start()
        timer.update(5.0)
        assert not timer.is_expired

    def test_expired_after_reaching_zero(self):
        timer, _ = make_timer(1.0)
        timer.start()
        timer.update(1.0)
        assert timer.is_expired

    def test_expired_after_overshoot(self):
        timer, _ = make_timer(1.0)
        timer.start()
        timer.update(999.0)
        assert timer.is_expired

    def test_not_expired_without_start(self):
        timer, _ = make_timer(1.0)
        timer.update(999.0)
        assert not timer.is_expired


# ===========================================================================
# display_str formatting
# ===========================================================================

class TestDisplayStr:
    def test_full_fifteen_minutes(self):
        timer, _ = make_timer(900.0)
        assert timer.display_str == "15:00"

    def test_zero_seconds(self):
        timer, _ = make_timer(1.0)
        timer.start()
        timer.update(2.0)
        assert timer.display_str == "00:00"

    def test_59_seconds(self):
        timer, _ = make_timer(59.0)
        assert timer.display_str == "00:59"

    def test_one_minute_exactly(self):
        timer, _ = make_timer(60.0)
        assert timer.display_str == "01:00"

    def test_7_minutes_30_seconds(self):
        timer, _ = make_timer(450.0)
        assert timer.display_str == "07:30"

    def test_leading_zero_on_minutes_and_seconds(self):
        timer, _ = make_timer(65.0)
        assert timer.display_str == "01:05"

    def test_fractional_remainder_truncated_not_rounded(self):
        """9.9 s remaining should display as '00:09', not '00:10'."""
        timer, _ = make_timer(10.0)
        timer.start()
        timer.update(0.1)   # 9.9 s remaining
        assert timer.display_str == "00:09"


# ===========================================================================
# reset
# ===========================================================================

class TestReset:
    def test_reset_restores_seconds_remaining(self):
        timer, _ = make_timer(60.0)
        timer.start()
        timer.update(30.0)
        timer.reset()
        assert timer.seconds_remaining == pytest.approx(60.0)

    def test_reset_halts_timer(self):
        """After reset(), update() is a no-op until start() is called again."""
        timer, _ = make_timer(60.0)
        timer.start()
        timer.update(10.0)
        timer.reset()
        timer.update(10.0)  # should not decrement
        assert timer.seconds_remaining == pytest.approx(60.0)

    def test_reset_clears_expired_flag(self):
        timer, _ = make_timer(1.0)
        timer.start()
        timer.update(2.0)
        assert timer.is_expired
        timer.reset()
        assert not timer.is_expired

    def test_reset_then_restart_counts_down_from_full(self):
        timer, _ = make_timer(10.0)
        timer.start()
        timer.update(10.0)  # expire
        timer.reset()
        timer.start()
        timer.update(3.0)
        assert timer.seconds_remaining == pytest.approx(7.0)

    def test_reset_clears_tick_tracker_so_ticks_restart_from_full_duration(self):
        """After reset the tick tracker is restored so ticks count down from the
        full duration again, not from wherever the previous run stopped.

        Before reset the timer ran from 5 s down to ~2 s, publishing tick(4)
        and tick(3).  After reset + restart the first tick should be tick(4)
        (i.e. the high-water mark for a 5 s timer), NOT tick(2) or tick(1)
        (which would indicate the tracker was left at the old position).
        """
        timer, bus = make_timer(5.0)
        ticks = collect_ticks(bus)
        timer.start()
        timer.update(3.0)   # fires tick(4), tick(3), tick(2)
        timer.reset()
        ticks.clear()
        timer.start()
        timer.update(0.5)   # remaining=4.5 → tick(4) fires (fresh run)
        assert len(ticks) == 1
        assert ticks[0] == 4   # starts from 4 again, not from stale position

    def test_round_end_can_fire_again_after_reset(self):
        """A timer that has reset and restarted must fire round_end again."""
        timer, bus = make_timer(1.0)
        calls = count_round_ends(bus)
        timer.start()
        timer.update(1.0)   # first expiry
        timer.reset()
        timer.start()
        timer.update(1.0)   # second expiry
        assert len(calls) == 2


# ===========================================================================
# round_warning event
# ===========================================================================

def collect_warnings(bus: EventBus) -> list[int]:
    """Subscribe a collector to 'round_warning' and return the list it fills."""
    warnings: list[int] = []
    bus.subscribe("round_warning", lambda seconds_remaining: warnings.append(seconds_remaining))
    return warnings


class TestRoundWarning:
    def test_warning_fires_when_threshold_is_crossed(self):
        """update() that drops seconds_remaining to <= TIMER_WARN_SECS fires exactly
        one 'round_warning' event."""
        # Start slightly above the threshold so the first update crosses it.
        timer, bus = make_timer(float(TIMER_WARN_SECS) + 5.0)
        warnings = collect_warnings(bus)
        timer.start()
        timer.update(10.0)  # crosses TIMER_WARN_SECS
        assert len(warnings) == 1

    def test_warning_not_fired_above_threshold(self):
        """Updates that leave seconds_remaining above TIMER_WARN_SECS produce no
        'round_warning'."""
        timer, bus = make_timer(float(TIMER_WARN_SECS) + 100.0)
        warnings = collect_warnings(bus)
        timer.start()
        timer.update(1.0)   # still well above threshold
        assert warnings == []

    def test_warning_does_not_refire_on_subsequent_updates(self):
        """Further update() calls after the threshold is first crossed must not
        emit additional 'round_warning' events."""
        timer, bus = make_timer(float(TIMER_WARN_SECS) + 5.0)
        warnings = collect_warnings(bus)
        timer.start()
        timer.update(10.0)  # first crossing → one warning
        timer.update(10.0)  # still below threshold
        timer.update(10.0)
        assert len(warnings) == 1

    def test_warning_fires_on_large_dt_that_overshoots_threshold(self):
        """A single dt that jumps from above the threshold all the way to 0 must
        emit exactly one 'round_warning' and one 'round_end'."""
        timer, bus = make_timer(float(TIMER_WARN_SECS) + 10.0)
        warnings = collect_warnings(bus)
        ends = count_round_ends(bus)
        timer.start()
        timer.update(float(TIMER_WARN_SECS) + 100.0)  # overshoots everything
        assert len(warnings) == 1
        assert len(ends) == 1

    def test_warning_fires_again_after_reset(self):
        """After reset() + start() the warning fires a second time when the
        threshold is recrossed."""
        timer, bus = make_timer(float(TIMER_WARN_SECS) + 5.0)
        warnings = collect_warnings(bus)
        timer.start()
        timer.update(10.0)  # first crossing
        timer.reset()
        timer.start()
        timer.update(10.0)  # second crossing
        assert len(warnings) == 2

    def test_warning_not_fired_without_start(self):
        """update() without start() must never emit 'round_warning'."""
        timer, bus = make_timer(float(TIMER_WARN_SECS) + 5.0)
        warnings = collect_warnings(bus)
        timer.update(float(TIMER_WARN_SECS) + 100.0)  # would cross if running
        assert warnings == []
