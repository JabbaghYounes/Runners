"""Shared pytest fixtures for the Runners test suite."""

from __future__ import annotations

import os
import sys

import pytest

# Ensure headless rendering for CI and test environments.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src.events import EventBus  # noqa: E402


@pytest.fixture
def mock_event_bus():
    return EventBus()


@pytest.fixture(scope="session")
def headless_pygame():
    """Initialise Pygame once for the entire test session (headless)."""
    import pygame

    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass
    yield pygame
    pygame.quit()
