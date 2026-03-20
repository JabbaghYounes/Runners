"""Round countdown timer system.

Counts down from ``ROUND_DURATION_SECS`` (900 s / 15 min) to zero.
Each elapsed whole-second tick publishes ``timer_tick(seconds_remaining=N)``
via the ``EventBus``.  When the counter crosses zero it publishes
``round_end()`` exactly once and stops updating.

The timer is *inactive* until :py:meth:`start` is called so that
``GameScene`` can construct the object during ``__init__`` and start it
in ``on_enter``, matching the scene lifecycle pattern.
"""

from __future__ import annotations

import math

from src.core.constants import ROUND_DURATION_SECS, TIMER_WARN_SECS
from src.core.event_bus import EventBus


class RoundTimer:
    """Countdown timer that drives the 15-minute round clock.

    Args:
        event_bus: Shared :class:`~src.core.event_bus.EventBus` instance.
        duration:  Total round duration in seconds (defaults to
                   :data:`~src.core.constants.ROUND_DURATION_SECS`).
    """

    def __init__(
        self,
        event_bus: EventBus,
        duration: float = ROUND_DURATION_SECS,
    ) -> None:
        self._bus = event_bus
        self._duration = duration

        self.seconds_remaining: float = duration
        self._last_published: int = math.ceil(duration)  # whole-second tracker
        self._running: bool = False
        self._expired: bool = False
        self._warning_fired: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin the countdown.  Idempotent — safe to call more than once."""
        self._running = True

    def reset(self) -> None:
        """Restore timer to full duration and halt it."""
        self.seconds_remaining = self._duration
        self._last_published = math.ceil(self._duration)
        self._running = False
        self._expired = False
        self._warning_fired = False

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the timer by *dt* seconds and publish events as needed.

        Calling this when the timer is not running or already expired is a
        no-op so callers do not need to guard against it.
        """
        if not self._running or self._expired:
            return

        self.seconds_remaining -= dt
        if self.seconds_remaining < 0.0:
            self.seconds_remaining = 0.0

        # Publish timer_tick once per elapsed whole second.
        current_whole = math.floor(self.seconds_remaining)
        if current_whole < self._last_published:
            for tick in range(self._last_published - 1, current_whole - 1, -1):
                self._bus.publish("timer_tick", seconds_remaining=tick)
            self._last_published = current_whole

        # Publish round_warning exactly once when the timer drops to or below
        # the warning threshold (default 5 minutes / 300 s).
        if not self._warning_fired and self.seconds_remaining <= TIMER_WARN_SECS:
            self._warning_fired = True
            self._bus.publish("round_warning", seconds_remaining=int(self.seconds_remaining))

        # Publish round_end exactly once when the timer reaches zero.
        if self.seconds_remaining == 0.0 and not self._expired:
            self._expired = True
            self._running = False
            self._bus.publish("round_end")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_expired(self) -> bool:
        """``True`` once the timer has reached zero and ``round_end`` fired."""
        return self._expired

    @property
    def display_str(self) -> str:
        """Return remaining time formatted as ``"MM:SS"``."""
        total_secs = max(0, int(self.seconds_remaining))
        minutes, seconds = divmod(total_secs, 60)
        return f"{minutes:02d}:{seconds:02d}"
