"""Session-wide pytest configuration and shared fixtures.

Why this file exists
--------------------
GameApp._shutdown() calls pygame.quit() to clean up SDL resources.  Any test
that exercises _shutdown() or run() (which calls _shutdown() internally) leaves
pygame de-initialised.  Tests in later modules -- particularly test_main_menu.py
which needs pygame.font -- then fail with "font not initialized".

The ``reinitialize_pygame_if_needed`` fixture is applied automatically after
every test.  When a test has caused pygame to shut down, the fixture restores
the subsystems and creates a minimal dummy display so the next test starts from
a clean, fully-initialised state.
"""

from __future__ import annotations

import json
import os
from typing import Any

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
        # 1x1 is sufficient for headless test environments.
        pygame.display.set_mode((1, 1))


@pytest.fixture
def pygame_init():
    """Initialise Pygame with a headless 1x1 display for tests that need it."""
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
    yield
    # Don't call pygame.quit() here — reinitialize_pygame_if_needed handles it.


@pytest.fixture
def tmp_map_json(tmp_path):
    """Write a minimal 10x8 tile map JSON to a temp file and return its path."""
    tiles = []
    for row in range(8):
        if row == 0 or row >= 6:
            tiles.append([1] * 10)
        else:
            row_data = [1] + [0] * 8 + [1]
            tiles.append(row_data)
    # Place an extraction tile
    tiles[1][4] = 2

    data = {
        "tile_size": 32,
        "width": 10,
        "height": 8,
        "tiles": tiles,
        "player_spawn": [64, 128],
        "extraction_rect": [96, 32, 64, 32],
        "loot_spawns": [[64, 96]],
        "zones": [
            {
                "name": "ZONE_A",
                "rect": [0, 0, 160, 256],
                "spawn_points": [[64, 128]],
                "enemy_spawns": [{"type": "grunt", "pos": [96, 160]}],
                "music_track": None,
            },
            {
                "name": "ZONE_B",
                "rect": [160, 0, 160, 256],
                "spawn_points": [[224, 128]],
                "enemy_spawns": [],
                "music_track": None,
            },
            {
                "name": "ZONE_C",
                "rect": [0, 0, 320, 256],
                "spawn_points": [],
                "enemy_spawns": [],
                "music_track": None,
            },
        ],
    }
    map_path = tmp_path / "test_map.json"
    map_path.write_text(json.dumps(data))
    return str(map_path)


# ---------------------------------------------------------------------------
# Shared fixtures used by multiple test modules
# ---------------------------------------------------------------------------


class _TrackingEventBus:
    """A lightweight event bus that records all emitted events for assertions.

    Provides the standard emit()/subscribe()/unsubscribe()/clear() API plus:
    - ``emitted``:           list of ``(event_name, payload_dict)`` tuples
    - ``all_events(name)``:  list of payload dicts for the given event name
    - ``first_event(name)``: the first payload dict for the given event name
    """

    def __init__(self) -> None:
        from collections import defaultdict
        self._handlers: dict[str, list] = defaultdict(list)
        self.emitted: list[tuple[str, dict]] = []

    def subscribe(self, event: str, callback) -> None:
        if callback not in self._handlers[event]:
            self._handlers[event].append(callback)

    def unsubscribe(self, event: str, callback) -> None:
        try:
            self._handlers[event].remove(callback)
        except ValueError:
            pass

    def emit(self, event: str, **kwargs: Any) -> None:
        self.emitted.append((event, kwargs))
        for cb in list(self._handlers[event]):
            cb(**kwargs)

    def publish(self, event: str, **kwargs: Any) -> None:
        self.emit(event, **kwargs)

    def clear(self, event: str | None = None) -> None:
        if event is None:
            self._handlers.clear()
        else:
            self._handlers.pop(event, None)

    def all_events(self, name: str) -> list[dict]:
        return [payload for ename, payload in self.emitted if ename == name]

    def first_event(self, name: str) -> dict:
        for ename, payload in self.emitted:
            if ename == name:
                return payload
        raise KeyError(f"No event named {name!r} was emitted")

    def first(self, name: str) -> dict:
        """Alias for first_event."""
        return self.first_event(name)

    @property
    def _listeners(self):
        """Compatibility alias so tests can inspect handler dict."""
        return self._handlers

    def listener_count(self, event: str) -> int:
        return len(self._handlers.get(event, []))


@pytest.fixture
def event_bus():
    """A tracking event bus that records all emitted events."""
    return _TrackingEventBus()


@pytest.fixture
def settings():
    """Default Settings object for testing."""
    from src.core.settings import Settings
    return Settings(
        resolution=[1280, 720],
        fullscreen=False,
        master_volume=0.8,
        music_volume=0.7,
        sfx_volume=1.0,
    )


@pytest.fixture
def assets():
    """An AssetManager instance (uses pygame's built-in fonts)."""
    from src.core.asset_manager import AssetManager
    return AssetManager()


@pytest.fixture
def screen():
    """A 1280x720 surface matching the game resolution."""
    return pygame.Surface((1280, 720))
