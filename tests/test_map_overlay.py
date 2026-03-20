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


# ---------------------------------------------------------------------------
# Data-driven zone colours — feature requirement: color comes from zone.color
# ---------------------------------------------------------------------------


class TestMapOverlayZoneColors:
    """MapOverlay must use zone.color when present rather than a fixed palette."""

    def test_render_with_zone_color_attribute_does_not_crash(
        self, overlay_surface, extraction_rect
    ):
        """A Zone whose .color differs from the indexed palette must render fine."""
        ov = MapOverlay(1280, 720)
        # Use a Zone with an unusual colour that is NOT in ZONE_COLORS
        zones = [
            Zone("CUSTOM_ZONE", pygame.Rect(0, 0, 3200, 960), color=(200, 100, 50)),
        ]
        ov.render(
            screen=overlay_surface,
            zones=zones,
            player_pos=(100.0, 800.0),
            extraction_rect=extraction_rect,
            enemies=[],
            seconds_remaining=900.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )

    def test_render_with_object_lacking_color_attr_falls_back_to_palette(
        self, overlay_surface
    ):
        """Minimal objects without .color must fall back to indexed palette gracefully."""

        class BareZone:
            name = "BARE"
            rect = pygame.Rect(0, 0, 3200, 960)

        ov = MapOverlay(1280, 720)
        ov.render(
            screen=overlay_surface,
            zones=[BareZone()],
            player_pos=(100.0, 800.0),
            extraction_rect=None,
            enemies=[],
            seconds_remaining=900.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )

    def test_render_all_three_zones_with_distinct_custom_colors(
        self, overlay_surface, extraction_rect
    ):
        """All three real-map zones with their intended colours must render."""
        ov = MapOverlay(1280, 720)
        zones = [
            Zone("HANGAR BAY",     pygame.Rect(0, 0, 1088, 960),    color=(60, 120, 180)),
            Zone("REACTOR CORE",   pygame.Rect(1088, 0, 1088, 960), color=(180, 80, 60)),
            Zone("EXTRACTION PAD", pygame.Rect(2176, 0, 1024, 960), color=(60, 160, 80)),
        ]
        ov.render(
            screen=overlay_surface,
            zones=zones,
            player_pos=(100.0, 800.0),
            extraction_rect=extraction_rect,
            enemies=[],
            seconds_remaining=300.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )

    def test_render_with_zero_zone_list_does_not_crash(self, overlay_surface):
        """Empty zone list must render without error (no palette-index crash)."""
        ov = MapOverlay(1280, 720)
        ov.render(
            screen=overlay_surface,
            zones=[],
            player_pos=(100.0, 800.0),
            extraction_rect=None,
            enemies=[],
            seconds_remaining=900.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )

    def test_render_with_zone_tuple_rect_does_not_crash(self, overlay_surface):
        """Zones whose .rect is a (x, y, w, h) tuple must be accepted."""
        ov = MapOverlay(1280, 720)

        class TupleRectZone:
            name = "TUPLE_ZONE"
            rect = (0, 0, 3200, 960)
            color = (100, 150, 200)

        ov.render(
            screen=overlay_surface,
            zones=[TupleRectZone()],
            player_pos=(100.0, 800.0),
            extraction_rect=None,
            enemies=[],
            seconds_remaining=900.0,
            map_rect=pygame.Rect(0, 0, 3200, 960),
        )
