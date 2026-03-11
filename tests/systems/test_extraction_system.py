"""Unit tests for :class:`~src.systems.extraction_system.ExtractionSystem`.

Coverage matrix
---------------
Initial state
  - state is IDLE
  - channel_progress is 0.0
  - is_done is False
  - is_in_zone is False

IDLE → IN_ZONE  (player enters zone)
  - state becomes IN_ZONE when player rect overlaps zone
  - state stays IDLE when player is outside zone
  - zone_entered event is published with the zone reference
  - zone_entered fires only once on entry, not every frame while inside
  - zone_entered is NOT published when player is outside

IN_ZONE → IDLE  (player exits zone)
  - state returns to IDLE when player leaves zone
  - state stays IN_ZONE while player remains inside

IN_ZONE → CHANNELING  (F held, player stationary)
  - state becomes CHANNELING when F is held and player is stationary
  - extraction_started event is published
  - state stays IN_ZONE if player is moving (even with F held)
  - state stays IN_ZONE if F is not held (even when stationary)

CHANNELING → IN_ZONE  (cancellation)
  - movement cancels the channel → state returns to IN_ZONE
  - releasing F cancels the channel → state returns to IN_ZONE
  - both movement and F released simultaneously cancel the channel
  - extraction_cancelled event is published on movement cancellation
  - extraction_cancelled event is published on F-release cancellation
  - channel_elapsed is reset to 0.0 after cancellation
  - player can restart the channel after a cancellation

CHANNELING → DONE  (successful extraction)
  - state becomes DONE once channel_elapsed ≥ channel_duration
  - extraction_success event is published
  - extraction_success payload carries a snapshot of player.inventory
  - loot snapshot is a copy (mutations to inventory after extraction don't affect it)
  - extraction_success carries empty loot when inventory is empty
  - is_done becomes True
  - update() is a no-op once DONE
  - extraction_success fires exactly once even if update() keeps being called

channel_progress
  - 0.0 when IDLE
  - 0.0 when IN_ZONE
  - rises proportionally during CHANNELING
  - capped at 1.0 on overshoot
  - 1.0 when DONE

extraction_failed  (round_end while not DONE)
  - emitted when round_end fires while IDLE
  - emitted when round_end fires while IN_ZONE
  - emitted when round_end fires while CHANNELING
  - NOT emitted when round_end fires after DONE
  - extraction_success is not spuriously emitted on round_end

is_in_zone property
  - True while IN_ZONE
  - True while CHANNELING
  - False while IDLE
  - False while DONE
"""
from __future__ import annotations

import pytest
import pygame

from src.core.constants import EXTRACTION_CHANNEL_SECS, KEY_EXTRACT, MOVE_THRESHOLD
from src.core.event_bus import EventBus
from src.entities.player import Player
from src.map.extraction_zone import ExtractionZone
from src.systems.extraction_system import ExtractionState, ExtractionSystem


# ---------------------------------------------------------------------------
# Test geometry
# ---------------------------------------------------------------------------

# A 200×200 zone at (100, 100)–(300, 300)
_ZONE_RECT = pygame.Rect(100, 100, 200, 200)

# A position firmly inside and outside the zone
_INSIDE_XY = (150, 150)
_OUTSIDE_XY = (600, 600)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def make_zone(rect: pygame.Rect | None = None) -> ExtractionZone:
    return ExtractionZone(rect=pygame.Rect(_ZONE_RECT) if rect is None else rect)


def make_system(
    bus: EventBus | None = None,
    zone: ExtractionZone | None = None,
    duration: float = EXTRACTION_CHANNEL_SECS,
) -> tuple[ExtractionSystem, EventBus]:
    """Return a fresh *(system, bus)* pair."""
    if bus is None:
        bus = EventBus()
    if zone is None:
        zone = make_zone()
    system = ExtractionSystem(bus, zone, channel_duration=duration)
    return system, bus


def player_in_zone() -> Player:
    """Player positioned squarely inside the default zone."""
    return Player(x=_INSIDE_XY[0], y=_INSIDE_XY[1], width=32, height=32)


def player_outside_zone() -> Player:
    """Player positioned well outside the default zone."""
    return Player(x=_OUTSIDE_XY[0], y=_OUTSIDE_XY[1], width=32, height=32)


def keys_f_held() -> list[bool]:
    """Simulated pressed_keys sequence with F held down."""
    keys: list[bool] = [False] * 512
    keys[KEY_EXTRACT] = True
    return keys


def keys_f_released() -> list[bool]:
    """Simulated pressed_keys sequence with F not held."""
    return [False] * 512


def set_moving(player: Player, speed: float = MOVE_THRESHOLD + 1.0) -> None:
    """Give the player a velocity that exceeds MOVE_THRESHOLD."""
    player.velocity = pygame.Vector2(speed, 0.0)


def set_stationary(player: Player) -> None:
    """Set player velocity to zero."""
    player.velocity = pygame.Vector2(0.0, 0.0)


# Tiny dt for "advance one frame" calls that shouldn't complete a channel
_FRAME = 0.016


# ---------------------------------------------------------------------------
# Helper that drives a player to CHANNELING state from scratch
# ---------------------------------------------------------------------------

def _advance_to_channeling(
    system: ExtractionSystem,
    player: Player,
) -> None:
    """Drive *system* from IDLE to CHANNELING using *player* (must be in zone)."""
    set_stationary(player)
    system.update(_FRAME, player, keys_f_released())   # IDLE → IN_ZONE
    system.update(_FRAME, player, keys_f_held())       # IN_ZONE → CHANNELING


def _advance_to_done(
    system: ExtractionSystem,
    player: Player,
    duration: float,
) -> None:
    """Drive *system* from IDLE all the way to DONE."""
    _advance_to_channeling(system, player)
    system.update(duration, player, keys_f_held())     # CHANNELING → DONE


# ===========================================================================
# Initial state
# ===========================================================================

class TestInitialState:
    def test_state_is_idle(self):
        system, _ = make_system()
        assert system.state is ExtractionState.IDLE

    def test_channel_progress_is_zero(self):
        system, _ = make_system()
        assert system.channel_progress == pytest.approx(0.0)

    def test_is_done_false(self):
        system, _ = make_system()
        assert not system.is_done

    def test_is_in_zone_false(self):
        system, _ = make_system()
        assert not system.is_in_zone


# ===========================================================================
# IDLE → IN_ZONE
# ===========================================================================

class TestIdleToInZone:
    def test_transitions_to_in_zone_on_overlap(self):
        system, _ = make_system()
        system.update(_FRAME, player_in_zone(), keys_f_released())
        assert system.state is ExtractionState.IN_ZONE

    def test_stays_idle_when_player_outside(self):
        system, _ = make_system()
        system.update(_FRAME, player_outside_zone(), keys_f_released())
        assert system.state is ExtractionState.IDLE

    def test_zone_entered_event_published(self):
        system, bus = make_system()
        entered: list = []
        bus.subscribe("zone_entered", lambda zone: entered.append(zone))
        system.update(_FRAME, player_in_zone(), keys_f_released())
        assert len(entered) == 1

    def test_zone_entered_carries_zone_reference(self):
        zone = make_zone()
        system, bus = make_system(zone=zone)
        entered: list = []
        bus.subscribe("zone_entered", lambda zone: entered.append(zone))
        system.update(_FRAME, player_in_zone(), keys_f_released())
        assert entered[0] is zone

    def test_zone_entered_not_published_when_outside(self):
        system, bus = make_system()
        entered: list = []
        bus.subscribe("zone_entered", lambda zone: entered.append(zone))
        system.update(_FRAME, player_outside_zone(), keys_f_released())
        assert entered == []

    def test_zone_entered_fires_only_once_on_entry(self):
        """zone_entered must not re-fire on consecutive frames while inside."""
        system, bus = make_system()
        entered: list = []
        bus.subscribe("zone_entered", lambda zone: entered.append(zone))
        player = player_in_zone()
        system.update(_FRAME, player, keys_f_released())
        system.update(_FRAME, player, keys_f_released())
        system.update(_FRAME, player, keys_f_released())
        assert len(entered) == 1


# ===========================================================================
# IN_ZONE → IDLE  (player exits zone)
# ===========================================================================

class TestInZoneToIdle:
    def test_returns_to_idle_when_player_leaves(self):
        system, _ = make_system()
        system.update(_FRAME, player_in_zone(), keys_f_released())
        assert system.state is ExtractionState.IN_ZONE
        system.update(_FRAME, player_outside_zone(), keys_f_released())
        assert system.state is ExtractionState.IDLE

    def test_stays_in_zone_while_player_remains_inside(self):
        system, _ = make_system()
        player = player_in_zone()
        system.update(_FRAME, player, keys_f_released())
        system.update(_FRAME, player, keys_f_released())
        assert system.state is ExtractionState.IN_ZONE


# ===========================================================================
# IN_ZONE → CHANNELING
# ===========================================================================

class TestInZoneToChanneling:
    def test_starts_channeling_when_f_held_and_stationary(self):
        system, _ = make_system()
        player = player_in_zone()
        set_stationary(player)
        system.update(_FRAME, player, keys_f_released())  # enter zone
        system.update(_FRAME, player, keys_f_held())      # start channel
        assert system.state is ExtractionState.CHANNELING

    def test_extraction_started_event_published(self):
        system, bus = make_system()
        started: list = []
        bus.subscribe("extraction_started", lambda **kw: started.append(True))
        player = player_in_zone()
        set_stationary(player)
        system.update(_FRAME, player, keys_f_released())
        system.update(_FRAME, player, keys_f_held())
        assert len(started) == 1

    def test_does_not_channel_when_moving_with_f_held(self):
        """Moving while holding F must NOT start the channel."""
        system, _ = make_system()
        player = player_in_zone()
        set_moving(player)
        system.update(_FRAME, player, keys_f_released())  # enter zone
        system.update(_FRAME, player, keys_f_held())      # F held but moving
        assert system.state is ExtractionState.IN_ZONE

    def test_does_not_channel_when_stationary_without_f(self):
        """Stationary in zone without holding F must stay IN_ZONE."""
        system, _ = make_system()
        player = player_in_zone()
        set_stationary(player)
        system.update(_FRAME, player, keys_f_released())
        system.update(_FRAME, player, keys_f_released())
        assert system.state is ExtractionState.IN_ZONE

    def test_extraction_started_fires_only_once_per_channel_attempt(self):
        """extraction_started must fire once on transition, not every frame."""
        system, bus = make_system(duration=10.0)
        started: list = []
        bus.subscribe("extraction_started", lambda **kw: started.append(True))
        player = player_in_zone()
        set_stationary(player)
        system.update(_FRAME, player, keys_f_released())  # enter zone
        system.update(_FRAME, player, keys_f_held())      # CHANNELING — fires once
        system.update(_FRAME, player, keys_f_held())      # stays CHANNELING
        system.update(_FRAME, player, keys_f_held())      # stays CHANNELING
        assert len(started) == 1


# ===========================================================================
# CHANNELING → IN_ZONE  (cancellation)
# ===========================================================================

class TestChannelingCancellation:
    def test_movement_cancels_channel(self):
        system, _ = make_system()
        player = player_in_zone()
        _advance_to_channeling(system, player)
        set_moving(player)
        system.update(_FRAME, player, keys_f_held())
        assert system.state is ExtractionState.IN_ZONE

    def test_f_release_cancels_channel(self):
        system, _ = make_system()
        player = player_in_zone()
        _advance_to_channeling(system, player)
        system.update(_FRAME, player, keys_f_released())
        assert system.state is ExtractionState.IN_ZONE

    def test_movement_and_f_release_simultaneously_cancels(self):
        """Both cancellation conditions active at once still cancels."""
        system, _ = make_system()
        player = player_in_zone()
        _advance_to_channeling(system, player)
        set_moving(player)
        system.update(_FRAME, player, keys_f_released())
        assert system.state is ExtractionState.IN_ZONE

    def test_extraction_cancelled_published_on_movement(self):
        system, bus = make_system()
        cancelled: list = []
        bus.subscribe("extraction_cancelled", lambda **kw: cancelled.append(True))
        player = player_in_zone()
        _advance_to_channeling(system, player)
        set_moving(player)
        system.update(_FRAME, player, keys_f_held())
        assert len(cancelled) == 1

    def test_extraction_cancelled_published_on_f_release(self):
        system, bus = make_system()
        cancelled: list = []
        bus.subscribe("extraction_cancelled", lambda **kw: cancelled.append(True))
        player = player_in_zone()
        _advance_to_channeling(system, player)
        system.update(_FRAME, player, keys_f_released())
        assert len(cancelled) == 1

    def test_channel_progress_resets_to_zero_after_cancellation(self):
        system, _ = make_system(duration=5.0)
        player = player_in_zone()
        _advance_to_channeling(system, player)
        system.update(2.0, player, keys_f_held())   # accumulate 2 s
        set_moving(player)
        system.update(_FRAME, player, keys_f_held())  # cancel
        assert system.channel_progress == pytest.approx(0.0)

    def test_can_restart_channel_after_cancellation(self):
        """Player may attempt extraction again after a cancellation."""
        system, _ = make_system()
        player = player_in_zone()
        _advance_to_channeling(system, player)
        system.update(_FRAME, player, keys_f_released())  # cancel
        assert system.state is ExtractionState.IN_ZONE
        set_stationary(player)
        system.update(_FRAME, player, keys_f_held())  # restart
        assert system.state is ExtractionState.CHANNELING

    def test_cancellation_fires_exactly_once_per_interrupt(self):
        system, bus = make_system(duration=10.0)
        cancelled: list = []
        bus.subscribe("extraction_cancelled", lambda **kw: cancelled.append(True))
        player = player_in_zone()
        _advance_to_channeling(system, player)
        # Cancel once by releasing F
        system.update(_FRAME, player, keys_f_released())
        # Now IN_ZONE — subsequent updates with F released should NOT fire again
        system.update(_FRAME, player, keys_f_released())
        assert len(cancelled) == 1


# ===========================================================================
# CHANNELING → DONE  (successful extraction)
# ===========================================================================

class TestSuccessfulExtraction:
    def test_state_becomes_done_after_full_channel(self):
        system, _ = make_system(duration=3.0)
        player = player_in_zone()
        _advance_to_done(system, player, 3.0)
        assert system.state is ExtractionState.DONE

    def test_extraction_success_event_published(self):
        system, bus = make_system(duration=3.0)
        successes: list = []
        bus.subscribe("extraction_success", lambda **kw: successes.append(kw))
        player = player_in_zone()
        _advance_to_done(system, player, 3.0)
        assert len(successes) == 1

    def test_extraction_success_carries_loot_snapshot(self):
        system, bus = make_system(duration=3.0)
        successes: list = []
        bus.subscribe("extraction_success", lambda **kw: successes.append(kw))
        player = player_in_zone()
        item = {"id": "medkit", "qty": 1}
        player.inventory.append(item)
        _advance_to_done(system, player, 3.0)
        assert successes[0]["loot"] == [item]

    def test_extraction_success_loot_is_a_copy(self):
        """Mutating inventory after extraction must not affect the payload copy."""
        system, bus = make_system(duration=3.0)
        successes: list = []
        bus.subscribe("extraction_success", lambda **kw: successes.append(kw))
        player = player_in_zone()
        player.inventory.append({"id": "rifle"})
        _advance_to_done(system, player, 3.0)
        player.inventory.clear()           # mutate the live inventory
        assert len(successes[0]["loot"]) == 1

    def test_extraction_success_with_empty_inventory(self):
        system, bus = make_system(duration=3.0)
        successes: list = []
        bus.subscribe("extraction_success", lambda **kw: successes.append(kw))
        player = player_in_zone()
        _advance_to_done(system, player, 3.0)
        assert successes[0]["loot"] == []

    def test_is_done_true_after_success(self):
        system, _ = make_system(duration=3.0)
        player = player_in_zone()
        _advance_to_done(system, player, 3.0)
        assert system.is_done

    def test_update_after_done_is_noop(self):
        """Once DONE, calling update() must not change state."""
        system, _ = make_system(duration=3.0)
        player = player_in_zone()
        _advance_to_done(system, player, 3.0)
        system.update(10.0, player, keys_f_released())
        assert system.state is ExtractionState.DONE

    def test_extraction_success_fires_exactly_once(self):
        """extraction_success must not re-fire on continued updates."""
        system, bus = make_system(duration=3.0)
        successes: list = []
        bus.subscribe("extraction_success", lambda **kw: successes.append(kw))
        player = player_in_zone()
        _advance_to_done(system, player, 3.0)
        system.update(10.0, player, keys_f_held())  # further update after DONE
        assert len(successes) == 1

    def test_state_not_done_before_channel_complete(self):
        """Partial channel progress must not advance to DONE."""
        system, _ = make_system(duration=4.0)
        player = player_in_zone()
        _advance_to_channeling(system, player)
        system.update(3.9, player, keys_f_held())   # just short of 4.0 s
        assert system.state is ExtractionState.CHANNELING


# ===========================================================================
# channel_progress property
# ===========================================================================

class TestChannelProgress:
    def test_progress_zero_in_idle(self):
        system, _ = make_system()
        assert system.channel_progress == pytest.approx(0.0)

    def test_progress_zero_in_in_zone(self):
        system, _ = make_system()
        player = player_in_zone()
        system.update(_FRAME, player, keys_f_released())  # enter zone
        assert system.channel_progress == pytest.approx(0.0)

    def test_progress_rises_proportionally_during_channeling(self):
        system, _ = make_system(duration=4.0)
        player = player_in_zone()
        _advance_to_channeling(system, player)
        system.update(2.0, player, keys_f_held())   # 2 / 4 = 0.5
        assert system.channel_progress == pytest.approx(0.5)

    def test_progress_increases_each_frame(self):
        system, _ = make_system(duration=10.0)
        player = player_in_zone()
        _advance_to_channeling(system, player)
        system.update(1.0, player, keys_f_held())
        p1 = system.channel_progress
        system.update(1.0, player, keys_f_held())
        p2 = system.channel_progress
        assert p2 > p1

    def test_progress_capped_at_one_on_overshoot(self):
        system, _ = make_system(duration=3.0)
        player = player_in_zone()
        _advance_to_channeling(system, player)
        system.update(100.0, player, keys_f_held())   # huge overshoot
        assert system.channel_progress == pytest.approx(1.0)

    def test_progress_one_when_done(self):
        system, _ = make_system(duration=3.0)
        player = player_in_zone()
        _advance_to_done(system, player, 3.0)
        assert system.channel_progress == pytest.approx(1.0)

    def test_progress_zero_after_cancellation(self):
        system, _ = make_system(duration=5.0)
        player = player_in_zone()
        _advance_to_channeling(system, player)
        system.update(2.5, player, keys_f_held())       # half-way
        system.update(_FRAME, player, keys_f_released())  # cancel
        assert system.channel_progress == pytest.approx(0.0)


# ===========================================================================
# extraction_failed  (round_end while not DONE)
# ===========================================================================

class TestExtractionFailed:
    def _collect_failed(self, bus: EventBus) -> list[bool]:
        events: list[bool] = []
        bus.subscribe("extraction_failed", lambda **kw: events.append(True))
        return events

    def test_failed_emitted_when_round_ends_in_idle(self):
        system, bus = make_system()
        failed = self._collect_failed(bus)
        bus.publish("round_end")
        assert len(failed) == 1

    def test_failed_emitted_when_round_ends_in_in_zone(self):
        system, bus = make_system()
        player = player_in_zone()
        system.update(_FRAME, player, keys_f_released())  # enter zone
        failed = self._collect_failed(bus)
        bus.publish("round_end")
        assert len(failed) == 1

    def test_failed_emitted_when_round_ends_during_channeling(self):
        system, bus = make_system(duration=10.0)
        player = player_in_zone()
        _advance_to_channeling(system, player)
        failed = self._collect_failed(bus)
        bus.publish("round_end")
        assert len(failed) == 1

    def test_failed_not_emitted_when_extraction_succeeded(self):
        """A completed extraction must not emit extraction_failed on round_end."""
        system, bus = make_system(duration=3.0)
        player = player_in_zone()
        _advance_to_done(system, player, 3.0)
        failed = self._collect_failed(bus)
        bus.publish("round_end")
        assert failed == []

    def test_success_not_fired_by_round_end(self):
        """round_end must never spuriously emit extraction_success."""
        system, bus = make_system()
        successes: list = []
        bus.subscribe("extraction_success", lambda **kw: successes.append(kw))
        bus.publish("round_end")
        assert successes == []

    def test_failed_fires_exactly_once_per_round_end(self):
        """extraction_failed must not be emitted more than once per round_end."""
        system, bus = make_system()
        failed = self._collect_failed(bus)
        bus.publish("round_end")
        assert len(failed) == 1


# ===========================================================================
# is_in_zone property
# ===========================================================================

class TestIsInZone:
    def test_false_while_idle(self):
        system, _ = make_system()
        assert not system.is_in_zone

    def test_true_while_in_zone_state(self):
        system, _ = make_system()
        player = player_in_zone()
        system.update(_FRAME, player, keys_f_released())
        assert system.is_in_zone

    def test_true_while_channeling(self):
        system, _ = make_system(duration=10.0)
        player = player_in_zone()
        _advance_to_channeling(system, player)
        assert system.is_in_zone

    def test_false_while_done(self):
        system, _ = make_system(duration=3.0)
        player = player_in_zone()
        _advance_to_done(system, player, 3.0)
        assert not system.is_in_zone
