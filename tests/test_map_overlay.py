"""Smoke-tests for MapOverlay.render() — no crash, pixels written."""
import pytest
import pygame
from src.map.map_overlay import MapOverlay
from src.map.zone import Zone


@pytest.fixture()
def overlay_surface():
    return pygame.Surface((1280, 720))


@pytest.fixture()
def three_zones():
    return [
        Zone("HANGAR BAY",     pygame.Rect(0, 0, 1088, 960)),
        Zone("REACTOR CORE",   pygame.Rect(1088, 0, 1088, 960)),
        Zone("EXTRACTION PAD", pygame.Rect(2176, 0, 1024, 960)),
    ]


@pytest.fixture()
def extraction_rect():
    return pygame.Rect(2560, 128, 480, 64)


class TestMapOverlayRender:
    def test_render_does_not_crash(self, overlay_surface, three_zones, extraction_rect):
        ov = MapOverlay(1280, 720)
        ov.render(
            screen=overlay_surface,
            zones=three_zones,
            player_pos=(100.0, 800.0),
            extraction_rect=extraction_rect,
            enemies=[],
            seconds_remaining=540.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )

    def test_render_writes_pixels(self, overlay_surface, three_zones, extraction_rect):
        """Surface should be non-black after rendering (overlay added content)."""
        # Fill with a distinctive background first
        overlay_surface.fill((0, 0, 0))
        ov = MapOverlay(1280, 720)
        ov.render(
            screen=overlay_surface,
            zones=three_zones,
            player_pos=(100.0, 800.0),
            extraction_rect=extraction_rect,
            enemies=[],
            seconds_remaining=540.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )
        # Surface should have at least some non-black pixels
        # (panel background is drawn)
        found_non_black = False
        w, h = overlay_surface.get_size()
        step = 10
        for y in range(0, h, step):
            for x in range(0, w, step):
                if overlay_surface.get_at((x, y))[:3] != (0, 0, 0):
                    found_non_black = True
                    break
            if found_non_black:
                break
        assert found_non_black, "Expected overlay to write non-black pixels"

    def test_render_with_no_extraction_rect(self, overlay_surface, three_zones):
        ov = MapOverlay(1280, 720)
        ov.render(
            screen=overlay_surface,
            zones=three_zones,
            player_pos=(100.0, 800.0),
            extraction_rect=None,
            enemies=[],
            seconds_remaining=0.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )

    def test_render_with_enemies(self, overlay_surface, three_zones, extraction_rect):
        from src.entities.robot_enemy import RobotEnemy
        enemies = [RobotEnemy(500, 800), RobotEnemy(1500, 600)]
        ov = MapOverlay(1280, 720)
        ov.render(
            screen=overlay_surface,
            zones=three_zones,
            player_pos=(200.0, 800.0),
            extraction_rect=extraction_rect,
            enemies=enemies,
            seconds_remaining=300.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )

    def test_timer_low_shows_red_warning(self, overlay_surface, three_zones, extraction_rect):
        """Just verify render completes with low timer (< 60s)."""
        ov = MapOverlay(1280, 720)
        ov.render(
            screen=overlay_surface,
            zones=three_zones,
            player_pos=(100.0, 800.0),
            extraction_rect=extraction_rect,
            enemies=[],
            seconds_remaining=30.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )

    def test_custom_dimensions(self, three_zones, extraction_rect):
        surface = pygame.Surface((800, 600))
        ov = MapOverlay(800, 600)
        ov.render(
            screen=surface,
            zones=three_zones,
            player_pos=(100.0, 800.0),
            extraction_rect=extraction_rect,
            enemies=[],
            seconds_remaining=900.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )
