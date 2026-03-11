"""Shared pytest fixtures for the Runners test suite."""
import pytest
import pygame


@pytest.fixture(scope="session")
def pygame_init():
    """Initialise Pygame with a headless 1×1 display for all tests."""
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
    yield
    pygame.quit()


@pytest.fixture
def screen(pygame_init):
    """Return a small test surface."""
    return pygame.Surface((1280, 720))
