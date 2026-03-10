"""Shared pytest fixtures for the Runners test suite."""

from __future__ import annotations

import os
import sys

import pytest

# Ensure headless Pygame/SDL before any pygame import.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src.events import EventBus  # noqa: E402
from src.settings import Settings  # noqa: E402


@pytest.fixture()
def mock_settings() -> Settings:
    """Settings instance with default values."""
    return Settings()


@pytest.fixture()
def mock_event_bus() -> EventBus:
    """Fresh EventBus instance."""
    return EventBus()


@pytest.fixture(scope="session", autouse=True)
def headless_pygame():
    """Initialise Pygame and the mixer in headless mode once per session."""
    import pygame

    pygame.init()
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
    except Exception:
        pass  # Some CI environments have no audio device at all
    yield
    pygame.quit()


@pytest.fixture()
def audio_manager(mock_settings: Settings, mock_event_bus: EventBus):
    """AudioManager wired to mock settings and event bus."""
    from src.audio import AudioManager

    return AudioManager(mock_settings, mock_event_bus)
