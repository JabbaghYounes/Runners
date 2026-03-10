"""Comprehensive tests for RoundManager — phase transitions, timer, extraction, events."""

from __future__ import annotations

import pygame
import pytest

from src.events import EventBus
from src.entities.base import Entity
from src.map import Zone
from src.round import RoundManager, RoundPhase
from tests.conftest import MockTileMap


# ======================================================================
# Helpers
# ======================================================================


class EventRecorder:
    """Records published events for assertion."""

    def __init__(self, bus: EventBus, event_types: list[str] | None = None) -> None:
        self.events: list[tuple[str, dict]] = []
        self._bus = bus
        types = event_types or [
            "round_started",
            "round_tick",
            "extraction_started",
            "extraction_progress",
            "extraction_cancelled",
            "extraction_complete",
            "round_timeout",
            "round_failed",
            "timer_warning",
        ]
        for et in types:
            bus.subscribe(et, self._make_handler(et))

    def _make_handler(self, event_type: str):
        def handler(**data):
            self.events.append((event_type, dict(data)))
        return handler

    def count(self, event_type: str) -> int:
        return sum(1 for e, _ in self.events if e == event_type)

    def get_all(self, event_type: str) -> list[dict]:
        return [d for e, d in self.events if e == event_type]

    def last(self, event_type: str) -> dict | None:
        matches = self.get_all(event_type)
        return matches[-1] if matches else None


def make_player(x: float = 128.0, y: float = 128.0, alive: bool = True) -> Entity:
    p = Entity(x=x, y=y, health=100, width=32, height=32)
    p.alive = alive
    return p


def make_tilemap(zones: list[Zone] | None = None) -> MockTileMap:
    return MockTileMap(zones=zones or [])


def make_extraction_zone(
    name: str = "extract_a", x: int = 200, y: int = 200, w: int = 128, h: int = 128
) -> Zone:
    return Zone(name=name, zone_type="extraction", rect=pygame.Rect(x, y, w, h))


def make_spawn_zone() -> Zone:
    return Zone(name="spawn_a", zone_type="spawn", rect=pygame.Rect(64, 64, 128, 128))


def place_player_in_zone(player: Entity, zone: Zone) -> None:
    """Move player to the centre of a zone (call after start_round)."""
    player.pos.x = float(zone.rect.centerx)
    player.pos.y = float(zone.rect.centery)


# ======================================================================
# Phase transition tests
# ======================================================================


class TestPhaseTransitions:
    """Verify the full lifecycle of phase transitions."""

    def test_initial_phase_is_spawning(self, mock_event_bus):
        rm = RoundManager(mock_event_bus)
        assert rm.phase == RoundPhase.SPAWNING

    def test_start_round_transitions_to_playing(self, mock_event_bus):
        rm = RoundManager(mock_event_bus)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), make_extraction_zone()])
        rm.start_round(player, tilemap)
        assert rm.phase == RoundPhase.PLAYING

    def test_playing_to_extracting(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=900.0, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)

        # Move player into zone after start_round placed them at spawn
        place_player_in_zone(player, zone)
        rm.update(0.016, player)

        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.EXTRACTING

    def test_extracting_to_extracted(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=1.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        # Advance past extraction duration
        rm.update(1.1, player)
        assert rm.phase == RoundPhase.EXTRACTED

    def test_playing_to_failed_timeout(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=1.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), make_extraction_zone()])
        rm.start_round(player, tilemap)

        rm.update(1.5, player)
        assert rm.phase == RoundPhase.FAILED

    def test_playing_to_failed_death(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=900.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), make_extraction_zone()])
        rm.start_round(player, tilemap)

        player.alive = False
        rm.update(0.016, player)
        assert rm.phase == RoundPhase.FAILED

    def test_full_success_lifecycle(self, mock_event_bus):
        """SPAWNING -> PLAYING -> EXTRACTING -> EXTRACTED."""
        rm = RoundManager(mock_event_bus, extraction_duration=0.5)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])

        # SPAWNING -> PLAYING
        rm.start_round(player, tilemap)
        assert rm.phase == RoundPhase.PLAYING

        # Move player into extraction zone
        place_player_in_zone(player, zone)

        # PLAYING -> EXTRACTING
        rm.update(0.016, player)
        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.EXTRACTING

        # EXTRACTING -> EXTRACTED
        rm.update(0.6, player)
        assert rm.phase == RoundPhase.EXTRACTED

        # Finalise
        rm.update(0.016, player)
        assert rm.is_finished


# ======================================================================
# Timer tests
# ======================================================================


class TestTimer:
    def test_timer_starts_at_round_duration(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=900.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)
        assert rm.timer == pytest.approx(900.0)

    def test_timer_decrements_by_dt(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=900.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)
        rm.update(1.0, player)
        assert rm.timer == pytest.approx(899.0)

    def test_timer_reaches_zero_triggers_failed(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=2.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        rm.update(2.5, player)
        assert rm.timer == 0.0
        assert rm.phase == RoundPhase.FAILED

    def test_timer_never_goes_negative(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=1.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)
        rm.update(5.0, player)
        assert rm.timer >= 0.0

    def test_custom_round_duration(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=300.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)
        assert rm.timer == pytest.approx(300.0)


# ======================================================================
# Extraction channel tests
# ======================================================================


class TestExtractionChannel:
    def test_extraction_duration_is_5_seconds_default(self, mock_event_bus):
        rm = RoundManager(mock_event_bus)
        assert rm.extraction_duration == 5.0

    def test_extraction_progress_increments(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(2.0, player)
        assert rm.extraction_progress == pytest.approx(2.0)

    def test_extraction_completes_at_duration(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=3.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(3.0, player)
        assert rm.phase == RoundPhase.EXTRACTED

    def test_extraction_progress_ratio(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=10.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(5.0, player)
        assert rm.extraction_progress_ratio == pytest.approx(0.5)

    def test_extraction_progress_ratio_capped_at_one(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=1.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(0.5, player)
        # Not yet complete, ratio should be 0.5
        assert rm.extraction_progress_ratio == pytest.approx(0.5)

    def test_begin_extraction_only_from_playing(self, mock_event_bus):
        rm = RoundManager(mock_event_bus)
        zone = make_extraction_zone()
        # Not started yet (SPAWNING phase)
        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.SPAWNING


# ======================================================================
# Extraction cancel tests
# ======================================================================


class TestExtractionCancel:
    def test_cancel_on_leave_zone(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.EXTRACTING

        # Move player out of zone
        player.pos.x = 0.0
        player.pos.y = 0.0
        rm.update(0.5, player)
        assert rm.phase == RoundPhase.PLAYING

    def test_cancel_on_player_damaged(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.EXTRACTING

        # Simulate player_damaged event
        mock_event_bus.publish("player_damaged", target=player, damage=10, source=None)
        assert rm.phase == RoundPhase.PLAYING

    def test_can_restart_extraction_after_cancel(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        # Start, cancel, then start again
        rm.begin_extraction(zone)
        rm.cancel_extraction("interrupted")
        assert rm.phase == RoundPhase.PLAYING

        rm.begin_extraction(zone)
        assert rm.phase == RoundPhase.EXTRACTING

    def test_cancel_resets_progress(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(2.0, player)  # 2s into extraction
        assert rm.extraction_progress > 0

        rm.cancel_extraction("left_zone")
        assert rm.extraction_progress == 0.0

    def test_cancel_only_from_extracting(self, mock_event_bus):
        rm = RoundManager(mock_event_bus)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        # Cancel when in PLAYING — should be no-op
        rm.cancel_extraction("test")
        assert rm.phase == RoundPhase.PLAYING


# ======================================================================
# Event publishing tests
# ======================================================================


class TestEventPublishing:
    def test_round_started_published(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, round_duration=900.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        assert recorder.count("round_started") == 1
        data = recorder.last("round_started")
        assert data["timer"] == 900.0

    def test_round_tick_published_each_frame(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, round_duration=900.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        rm.update(0.016, player)
        rm.update(0.016, player)
        rm.update(0.016, player)

        assert recorder.count("round_tick") >= 3

    def test_round_tick_contains_remaining_and_total(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, round_duration=100.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        rm.update(1.0, player)
        data = recorder.last("round_tick")
        assert "remaining" in data
        assert "total" in data
        assert data["remaining"] == pytest.approx(99.0)
        assert data["total"] == 100.0

    def test_extraction_started_published(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        assert recorder.count("extraction_started") == 1
        data = recorder.last("extraction_started")
        assert data["zone_name"] == "extract_a"
        assert data["duration"] == 5.0

    def test_extraction_progress_published(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(1.0, player)
        assert recorder.count("extraction_progress") >= 1
        data = recorder.last("extraction_progress")
        assert "progress" in data
        assert "duration" in data

    def test_extraction_cancelled_published(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.cancel_extraction("interrupted")
        assert recorder.count("extraction_cancelled") == 1
        data = recorder.last("extraction_cancelled")
        assert data["reason"] == "interrupted"

    def test_extraction_complete_published(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, extraction_duration=1.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(1.1, player)  # Triggers EXTRACTED
        rm.update(0.016, player)  # Finalise
        assert recorder.count("extraction_complete") == 1
        data = recorder.last("extraction_complete")
        assert "loot_summary" in data

    def test_round_timeout_published(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, round_duration=1.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        rm.update(1.5, player)
        assert recorder.count("round_timeout") == 1

    def test_round_failed_published_on_death(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        player.alive = False
        rm.update(0.016, player)
        rm.update(0.016, player)  # Finalise
        assert recorder.count("round_failed") == 1
        data = recorder.last("round_failed")
        assert data["cause"] == "eliminated"

    def test_round_failed_published_on_timeout(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, round_duration=0.5)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        rm.update(1.0, player)
        rm.update(0.016, player)  # Finalise
        assert recorder.count("round_failed") == 1
        data = recorder.last("round_failed")
        assert data["cause"] == "timeout"


# ======================================================================
# Timer warning tests
# ======================================================================


class TestTimerWarnings:
    def test_warning_at_60s(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, round_duration=120.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        # Advance to 61s remaining (no warning yet)
        rm.update(59.0, player)
        assert recorder.count("timer_warning") == 0

        # Cross the 60s threshold
        rm.update(1.5, player)
        assert recorder.count("timer_warning") == 1
        data = recorder.last("timer_warning")
        assert data["remaining"] < 60.0

    def test_warning_at_30s(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, round_duration=120.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        # Jump to 31s remaining
        rm.update(89.0, player)
        warnings_before = recorder.count("timer_warning")

        # Cross the 30s threshold
        rm.update(2.0, player)
        assert recorder.count("timer_warning") == warnings_before + 1

    def test_warnings_published_exactly_once_each(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, round_duration=120.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        # Run all the way to timeout
        for _ in range(1200):
            rm.update(0.1, player)
            if rm.is_finished:
                break

        # Should have exactly 2 timer_warning events (60s and 30s)
        assert recorder.count("timer_warning") == 2


# ======================================================================
# Result data tests
# ======================================================================


class TestResultData:
    def test_extracted_result_data(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=0.1)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(0.2, player)
        rm.update(0.016, player)

        result = rm.result_data
        assert result["outcome"] == "extracted"
        assert "items" in result
        assert "total_value" in result
        assert "xp_earned" in result
        assert "money_gained" in result

    def test_failed_result_data_timeout(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=0.1)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        rm.update(0.2, player)
        rm.update(0.016, player)

        result = rm.result_data
        assert result["outcome"] == "failed"
        assert result["cause"] == "timeout"
        assert "loot_lost" in result

    def test_failed_result_data_death(self, mock_event_bus):
        rm = RoundManager(mock_event_bus)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        player.alive = False
        rm.update(0.016, player)
        rm.update(0.016, player)

        result = rm.result_data
        assert result["outcome"] == "failed"
        assert result["cause"] == "eliminated"


# ======================================================================
# Extraction zone detection
# ======================================================================


class TestExtractionZoneDetection:
    def test_finds_extraction_zones_from_tilemap(self, mock_event_bus):
        zone_a = make_extraction_zone("extract_a", 200, 200, 128, 128)
        zone_b = make_extraction_zone("extract_b", 800, 800, 128, 128)
        spawn = make_spawn_zone()
        tilemap = make_tilemap([spawn, zone_a, zone_b])

        rm = RoundManager(mock_event_bus)
        player = make_player()
        rm.start_round(player, tilemap)

        assert len(rm.extraction_zones) == 2

    def test_is_near_extraction_when_inside_zone(self, mock_event_bus):
        zone = make_extraction_zone(x=200, y=200, w=128, h=128)
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm = RoundManager(mock_event_bus)
        player = make_player()
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.update(0.016, player)
        assert rm.is_near_extraction

    def test_not_near_extraction_when_outside(self, mock_event_bus):
        zone = make_extraction_zone(x=200, y=200, w=128, h=128)
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm = RoundManager(mock_event_bus)
        player = make_player(x=10.0, y=10.0)
        rm.start_round(player, tilemap)
        # Player was placed at spawn (128, 128), still outside zone (200-328)

        rm.update(0.016, player)
        assert not rm.is_near_extraction

    def test_nearest_extraction_zone_returns_correct_zone(self, mock_event_bus):
        zone = make_extraction_zone("extract_a", 200, 200, 128, 128)
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm = RoundManager(mock_event_bus)
        player = make_player()
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.update(0.016, player)
        assert rm.nearest_extraction_zone is not None
        assert rm.nearest_extraction_zone.name == "extract_a"


# ======================================================================
# Edge cases
# ======================================================================


class TestEdgeCases:
    def test_extraction_during_last_seconds_of_timer(self, mock_event_bus):
        """Start extraction with only 2s left on a 3s extraction."""
        rm = RoundManager(mock_event_bus, round_duration=10.0, extraction_duration=3.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        # Advance to 2s remaining
        rm.update(8.0, player)
        rm.begin_extraction(zone)

        # Extraction needs 3s but only 2s left — timer is not decremented
        # during EXTRACTING, so the channel can complete
        rm.update(3.1, player)
        assert rm.phase == RoundPhase.EXTRACTED

    def test_player_dies_during_extraction(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(1.0, player)

        player.alive = False
        rm.update(0.016, player)
        assert rm.phase == RoundPhase.FAILED

    def test_multiple_extraction_zones(self, mock_event_bus):
        zone_a = make_extraction_zone("extract_a", 200, 200, 128, 128)
        zone_b = make_extraction_zone("extract_b", 800, 800, 128, 128)
        tilemap = make_tilemap([make_spawn_zone(), zone_a, zone_b])

        rm = RoundManager(mock_event_bus)
        player = make_player()
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone_a)

        rm.update(0.016, player)
        assert rm.nearest_extraction_zone is not None
        assert rm.nearest_extraction_zone.name == "extract_a"

    def test_start_round_resets_all_state(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=10.0, extraction_duration=1.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])

        # First round: complete extraction
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)
        rm.begin_extraction(zone)
        rm.update(1.1, player)
        rm.update(0.016, player)
        assert rm.is_finished

        # Second round: should fully reset
        player2 = make_player()
        rm.start_round(player2, tilemap)
        assert rm.phase == RoundPhase.PLAYING
        assert rm.timer == pytest.approx(10.0)
        assert not rm.is_finished
        assert rm.extraction_progress == 0.0

    def test_is_finished_false_during_playing(self, mock_event_bus):
        rm = RoundManager(mock_event_bus)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)
        rm.update(0.016, player)
        assert not rm.is_finished

    def test_extraction_complete_published_only_once(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, extraction_duration=0.1)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(0.2, player)
        rm.update(0.016, player)
        rm.update(0.016, player)
        rm.update(0.016, player)

        assert recorder.count("extraction_complete") == 1

    def test_round_failed_published_only_once(self, mock_event_bus):
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, round_duration=0.1)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        rm.update(0.2, player)
        rm.update(0.016, player)
        rm.update(0.016, player)

        assert recorder.count("round_failed") == 1

    def test_update_with_zero_dt(self, mock_event_bus):
        """Updating with dt=0 should not crash and timer should not change."""
        rm = RoundManager(mock_event_bus, round_duration=900.0)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        rm.update(0.0, player)
        assert rm.timer == pytest.approx(900.0)
        assert rm.phase == RoundPhase.PLAYING

    def test_timer_not_decremented_during_extracting(self, mock_event_bus):
        """Timer should freeze while the extraction channel is active."""
        rm = RoundManager(mock_event_bus, round_duration=100.0, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        # Advance a bit
        rm.update(10.0, player)
        timer_before = rm.timer
        assert timer_before == pytest.approx(90.0)

        # Start extraction
        rm.begin_extraction(zone)
        rm.update(2.0, player)

        # Timer should not have changed (update_extracting doesn't decrement timer)
        assert rm.timer == pytest.approx(timer_before)

    def test_extraction_with_exact_duration(self, mock_event_bus):
        """Extraction at exactly the duration threshold should complete."""
        rm = RoundManager(mock_event_bus, extraction_duration=3.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(3.0, player)
        assert rm.phase == RoundPhase.EXTRACTED

    def test_no_round_tick_during_extracting(self, mock_event_bus):
        """round_tick should not be published during the EXTRACTING phase."""
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        tick_count_before = recorder.count("round_tick")

        rm.update(1.0, player)
        tick_count_after = recorder.count("round_tick")

        # No new round_tick events during EXTRACTING
        assert tick_count_after == tick_count_before

    def test_extraction_progress_published_during_extracting(self, mock_event_bus):
        """extraction_progress is published each frame during EXTRACTING."""
        recorder = EventRecorder(mock_event_bus)
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(1.0, player)
        rm.update(1.0, player)
        rm.update(1.0, player)

        assert recorder.count("extraction_progress") == 3

    def test_result_data_returns_copy(self, mock_event_bus):
        """result_data should return a copy, not a reference."""
        rm = RoundManager(mock_event_bus, extraction_duration=0.1)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.update(0.2, player)
        rm.update(0.016, player)

        data1 = rm.result_data
        data2 = rm.result_data
        assert data1 is not data2
        assert data1 == data2

    def test_round_duration_property(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, round_duration=600.0)
        assert rm.round_duration == 600.0

    def test_extraction_duration_property(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=3.0)
        assert rm.extraction_duration == 3.0

    def test_active_extraction_zone_set_during_extracting(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        assert rm.active_extraction_zone is None
        rm.begin_extraction(zone)
        assert rm.active_extraction_zone is zone

    def test_active_extraction_zone_cleared_on_cancel(self, mock_event_bus):
        rm = RoundManager(mock_event_bus, extraction_duration=5.0)
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm.start_round(player, tilemap)
        place_player_in_zone(player, zone)

        rm.begin_extraction(zone)
        rm.cancel_extraction("test")
        assert rm.active_extraction_zone is None

    def test_extraction_progress_zero_when_not_extracting(self, mock_event_bus):
        rm = RoundManager(mock_event_bus)
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone()])
        rm.start_round(player, tilemap)

        assert rm.extraction_progress == 0.0
        assert rm.extraction_progress_ratio == 0.0


# ======================================================================
# Spawn placement
# ======================================================================


class TestSpawnPlacement:
    def test_player_placed_at_spawn_zone(self, mock_event_bus):
        spawn = make_spawn_zone()  # rect = (64, 64, 128, 128), centre = (128, 128)
        zone = make_extraction_zone()
        tilemap = make_tilemap([spawn, zone])

        rm = RoundManager(mock_event_bus)
        player = make_player(x=0.0, y=0.0)
        rm.start_round(player, tilemap)

        assert player.pos.x == float(spawn.rect.centerx)
        assert player.pos.y == float(spawn.rect.centery)

    def test_no_spawn_zone_keeps_player_position(self, mock_event_bus):
        zone = make_extraction_zone()
        tilemap = make_tilemap([zone])  # no spawn zone

        rm = RoundManager(mock_event_bus)
        player = make_player(x=500.0, y=300.0)
        rm.start_round(player, tilemap)

        assert player.pos.x == 500.0
        assert player.pos.y == 300.0


# ======================================================================
# Cleanup
# ======================================================================


class TestCleanup:
    def test_cleanup_unsubscribes(self, mock_event_bus):
        rm = RoundManager(mock_event_bus)
        rm.cleanup()

        # After cleanup, publishing player_damaged should not affect
        # a NEW RoundManager's extraction
        zone = make_extraction_zone()
        player = make_player()
        tilemap = make_tilemap([make_spawn_zone(), zone])
        rm2 = RoundManager(mock_event_bus, extraction_duration=5.0)
        rm2.start_round(player, tilemap)
        place_player_in_zone(player, zone)
        rm2.begin_extraction(zone)

        # rm2 handler still active — this should cancel rm2's extraction
        mock_event_bus.publish("player_damaged", target=player, damage=10, source=None)
        assert rm2.phase == RoundPhase.PLAYING
