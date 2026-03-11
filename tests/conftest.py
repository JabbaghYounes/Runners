"""Session-wide pytest configuration and shared fixtures.

Why this file exists
--------------------
GameApp._shutdown() calls pygame.quit() to clean up SDL resources.  Any test
that exercises _shutdown() or run() (which calls _shutdown() internally) leaves
pygame de-initialised.  Tests in later modules — particularly test_main_menu.py
which needs pygame.font — then fail with "font not initialized".

The ``reinitialize_pygame_if_needed`` fixture is applied automatically after
every test.  When a test has caused pygame to shut down, the fixture restores
the subsystems and creates a minimal dummy display so the next test starts from
a clean, fully-initialised state.
"""

from __future__ import annotations

import os

import pygame
import pytest

# Ensure SDL does not try to open a real video/audio device for any test.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


@pytest.fixture(autouse=True)
def reinitialize_pygame_if_needed():
    """Yield to the test; if pygame was shut down, reinitialise it afterwards."""
    yield
    # pygame.get_init() returns the count of initialised subsystems (0 == False
    # when none are running, e.g. after pygame.quit()).
    if not pygame.get_init():
        pygame.init()
        # A display surface is required for Surface.convert() / convert_alpha();
        # 1×1 is sufficient for headless test environments.
        pygame.display.set_mode((1, 1))
