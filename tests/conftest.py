"""Shared pytest fixtures for the Runners test suite."""

from __future__ import annotations

import os
import sys

import pytest

# Ensure headless rendering for CI and test environments.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from src.events import EventBus  # noqa: E402
from src.map import Zone  # noqa: E402
from src.round import RoundManager, RoundPhase  # noqa: E402
from src.entities.base import Entity  # noqa: E402


# ------------------------------------------------------------------
# Session-wide pygame initialisation
# ------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def headless_pygame():
    """Initialise Pygame once for the entire test session (headless)."""
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass
    yield pygame
    pygame.quit()


# ------------------------------------------------------------------
# Basic fixtures
# ------------------------------------------------------------------

@pytest.fixture
def mock_event_bus():
    """Fresh EventBus instance."""
    return EventBus()


@pytest.fixture
def sample_player():
    """A basic Entity acting as the player for round tests."""
    player = Entity(x=128.0, y=128.0, health=100, width=32, height=32)
    player.alive = True
    return player


@pytest.fixture
def sample_extraction_zone():
    """A single extraction zone at a known position."""
    return Zone(
        name="extract_a",
        zone_type="extraction",
        rect=pygame.Rect(200, 200, 128, 128),
    )


@pytest.fixture
def sample_extraction_zone_b():
    """A second extraction zone at a different position."""
    return Zone(
        name="extract_b",
        zone_type="extraction",
        rect=pygame.Rect(800, 800, 128, 128),
    )


@pytest.fixture
def sample_spawn_zone():
    """A spawn zone that places the player at a known position."""
    return Zone(
        name="spawn_a",
        zone_type="spawn",
        rect=pygame.Rect(64, 64, 128, 128),
    )


class MockTileMap:
    """Lightweight TileMap stand-in for unit tests."""

    def __init__(self, zones: list[Zone] | None = None) -> None:
        self.tile_size = 32
        self.width = 80
        self.height = 60
        self.zones = zones or []

    def is_solid(self, gx: int, gy: int) -> bool:
        return False

    def draw(self, surface, camera) -> None:
        pass


@pytest.fixture
def mock_tilemap(sample_spawn_zone, sample_extraction_zone):
    """TileMap with one spawn zone and one extraction zone."""
    return MockTileMap(zones=[sample_spawn_zone, sample_extraction_zone])


@pytest.fixture
def mock_tilemap_two_extractions(
    sample_spawn_zone, sample_extraction_zone, sample_extraction_zone_b
):
    """TileMap with one spawn zone and two extraction zones."""
    return MockTileMap(
        zones=[sample_spawn_zone, sample_extraction_zone, sample_extraction_zone_b]
    )


@pytest.fixture
def mock_round_manager(mock_event_bus):
    """A RoundManager wired to a fresh EventBus, not yet started."""
    return RoundManager(mock_event_bus, round_duration=900.0, extraction_duration=5.0)


@pytest.fixture
def started_round_manager(mock_event_bus, sample_player, mock_tilemap):
    """A RoundManager that has already called start_round."""
    rm = RoundManager(mock_event_bus, round_duration=900.0, extraction_duration=5.0)
    rm.start_round(sample_player, mock_tilemap)
    return rm


@pytest.fixture
def sample_success_result():
    """Result data dict for a successful extraction."""
    return {
        "outcome": "extracted",
        "items": [
            {"name": "Rifle Mk-II", "rarity": "uncommon", "value": 350},
            {"name": "Med Kit", "rarity": "common", "value": 50},
        ],
        "total_value": 400,
        "xp_earned": {"extraction_bonus": 50, "survival": 25},
        "money_gained": 400,
        "level_before": 3,
        "level_after": 3,
    }


@pytest.fixture
def sample_failure_result():
    """Result data dict for a failed round."""
    return {
        "outcome": "failed",
        "cause": "eliminated",
        "loot_lost": [
            {"name": "Rifle Mk-II", "rarity": "uncommon", "value": 350},
        ],
        "total_lost": 350,
        "xp_retained": 10,
    }
