"""
Shared pytest fixtures for the Runners test suite.
"""
import json
import os
import pytest
import pygame


@pytest.fixture(scope="session", autouse=True)
def pygame_init():
    """Initialise Pygame with a headless 1×1 display for all tests."""
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
    yield
    pygame.quit()


@pytest.fixture()
def tmp_map_json(tmp_path):
    """Write a minimal 10×8 tile map JSON to a temp file and return its path."""
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
