"""
Tests for ExtractionSystem:
 - Timer countdown
 - Overlap detection
 - Hold-E progress (2 s → extraction_success)
 - Expired timer → extraction_failed
"""
import pytest
import pygame
from src.systems.extraction import ExtractionSystem
from src.core.event_bus import EventBus


@pytest.fixture()
def event_bus():
    return EventBus()


@pytest.fixture()
def extraction_rect():
    return pygame.Rect(500, 100, 200, 64)


@pytest.fixture()
def player_in_zone(extraction_rect):
    """A mock player whose rect overlaps the extraction zone."""
    class MockPlayer:
        rect = pygame.Rect(550, 120, 28, 48)
        alive = True
    return MockPlayer()


@pytest.fixture()
def player_out_of_zone():
    """A mock player far from the extraction zone."""
    class MockPlayer:
        rect = pygame.Rect(0, 0, 28, 48)
        alive = True
    return MockPlayer()


class TestTimerCountdown:
    def test_timer_decrements(self, event_bus, extraction_rect, player_out_of_zone):
        es = ExtractionSystem(extraction_rect, event_bus, total_time=100.0)
        es.update([player_out_of_zone], dt=1.0, e_held=False)
        assert es.seconds_remaining < 100.0
        assert abs(es.seconds_remaining - 99.0) < 0.01

    def test_timer_stops_at_zero(self, event_bus, extraction_rect, player_out_of_zone):
        es = ExtractionSystem(extraction_rect, event_bus, total_time=2.0)
        es.update([player_out_of_zone], dt=5.0, e_held=False)
        assert es.seconds_remaining == 0.0


class TestExtractionFailed:
    def test_expired_emits_extraction_failed(self, event_bus, extraction_rect, player_out_of_zone):
        failed = []
        event_bus.subscribe('extraction_failed', lambda **kw: failed.append(True))

        es = ExtractionSystem(extraction_rect, event_bus, total_time=1.0)
        es.update([player_out_of_zone], dt=2.0, e_held=False)

        assert len(failed) == 1

    def test_no_double_emission(self, event_bus, extraction_rect, player_out_of_zone):
        failed = []
        event_bus.subscribe('extraction_failed', lambda **kw: failed.append(True))

        es = ExtractionSystem(extraction_rect, event_bus, total_time=1.0)
        # Multiple updates after expiry
        for _ in range(5):
            es.update([player_out_of_zone], dt=1.0, e_held=False)

        assert len(failed) == 1  # only once


class TestOverlapDetection:
    def test_player_in_zone(self, event_bus, extraction_rect, player_in_zone):
        es = ExtractionSystem(extraction_rect, event_bus)
        assert es.is_player_in_zone(player_in_zone)

    def test_player_out_of_zone(self, event_bus, extraction_rect, player_out_of_zone):
        es = ExtractionSystem(extraction_rect, event_bus)
        assert not es.is_player_in_zone(player_out_of_zone)


class TestHoldProgress:
    def test_hold_progress_increases_in_zone(self, event_bus, extraction_rect, player_in_zone):
        es = ExtractionSystem(extraction_rect, event_bus, total_time=900.0)
        es.update([player_in_zone], dt=0.5, e_held=True)
        assert es._hold_progress > 0.0

    def test_hold_progress_resets_when_released(self, event_bus, extraction_rect, player_in_zone):
        es = ExtractionSystem(extraction_rect, event_bus, total_time=900.0)
        es.update([player_in_zone], dt=1.0, e_held=True)
        assert es._hold_progress > 0.0
        # Release E — progress should drop
        es.update([player_in_zone], dt=1.0, e_held=False)
        assert es._hold_progress < 1.0  # decremented or reset

    def test_two_second_hold_emits_success(self, event_bus, extraction_rect, player_in_zone):
        success = []
        event_bus.subscribe('extraction_success', lambda **kw: success.append(kw))

        es = ExtractionSystem(extraction_rect, event_bus, total_time=900.0)
        # Hold for 2 full seconds (HOLD_DURATION=2.0)
        es.update([player_in_zone], dt=2.0, e_held=True)

        assert len(success) == 1
        assert 'player' in success[0]

    def test_extraction_progress_property(self, event_bus, extraction_rect, player_in_zone):
        es = ExtractionSystem(extraction_rect, event_bus, total_time=900.0)
        es._hold_progress = 1.0  # halfway through 2.0 s hold
        assert abs(es.extraction_progress - 0.5) < 0.01

    def test_extraction_progress_clamped_to_one(self, event_bus, extraction_rect, player_in_zone):
        es = ExtractionSystem(extraction_rect, event_bus, total_time=900.0)
        es._hold_progress = 99.0  # beyond hold duration
        assert es.extraction_progress <= 1.0
