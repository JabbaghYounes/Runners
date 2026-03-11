"""Shared pytest fixtures and pygame initialisation for the entire test suite.

The SDL_VIDEODRIVER / SDL_AUDIODRIVER environment variables **must** be set
before pygame is imported anywhere, so they are set at module level here.
`conftest.py` is always collected by pytest before any test module in the
same directory tree, ensuring the variables are present in time.
"""
import os

# Use headless SDL drivers so the test suite can run in CI without a display.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.core.scene_manager import SceneManager


# ---------------------------------------------------------------------------
# Session-scoped pygame lifecycle
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def pygame_session():
    """Initialise pygame once for the entire test session and shut it down
    cleanly after all tests have run."""
    pygame.init()
    pygame.display.set_mode((1280, 720))
    yield
    pygame.quit()


# ---------------------------------------------------------------------------
# Per-test helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def screen():
    """An off-screen 1280×720 surface suitable for rendering tests."""
    return pygame.Surface((1280, 720))


@pytest.fixture
def settings():
    """A fresh default Settings instance."""
    return Settings()


@pytest.fixture
def assets():
    """A fresh AssetManager (empty cache) for each test."""
    return AssetManager()


@pytest.fixture
def scene_manager():
    """A fresh, empty SceneManager for each test."""
    return SceneManager()
