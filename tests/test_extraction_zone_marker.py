"""Tests for ExtractionZoneMarker — visual entity at extraction zones."""

from __future__ import annotations

import pygame
import pytest

from src.entities.extraction_zone import ExtractionZoneMarker
from src.map import Camera, Zone


# ======================================================================
# Helpers
# ======================================================================


def make_zone(
    name: str = "extract_a",
    x: int = 200,
    y: int = 200,
    w: int = 128,
    h: int = 128,
) -> Zone:
    return Zone(name=name, zone_type="extraction", rect=pygame.Rect(x, y, w, h))


def make_camera(sw: int = 1280, sh: int = 720) -> Camera:
    return Camera(sw, sh)


# ======================================================================
# Construction
# ======================================================================


class TestExtractionZoneMarkerInit:
    def test_init_from_zone(self):
        zone = make_zone()
        marker = ExtractionZoneMarker(zone)
        assert marker.zone is zone

    def test_position_at_zone_center(self):
        zone = make_zone(x=200, y=300, w=100, h=80)
        marker = ExtractionZoneMarker(zone)
        assert marker.pos.x == pytest.approx(250.0)  # 200 + 100/2
        assert marker.pos.y == pytest.approx(340.0)  # 300 + 80/2

    def test_dimensions_match_zone(self):
        zone = make_zone(w=256, h=192)
        marker = ExtractionZoneMarker(zone)
        assert marker.width == 256
        assert marker.height == 192

    def test_initial_anim_time_is_zero(self):
        zone = make_zone()
        marker = ExtractionZoneMarker(zone)
        assert marker._anim_time == 0.0

    def test_is_alive(self):
        zone = make_zone()
        marker = ExtractionZoneMarker(zone)
        assert marker.alive

    def test_inherits_from_entity(self):
        from src.entities.base import Entity

        zone = make_zone()
        marker = ExtractionZoneMarker(zone)
        assert isinstance(marker, Entity)


# ======================================================================
# Update
# ======================================================================


class TestExtractionZoneMarkerUpdate:
    def test_update_advances_anim_time(self):
        marker = ExtractionZoneMarker(make_zone())
        marker.update(0.5)
        assert marker._anim_time == pytest.approx(0.5)

    def test_update_accumulates(self):
        marker = ExtractionZoneMarker(make_zone())
        marker.update(0.3)
        marker.update(0.2)
        assert marker._anim_time == pytest.approx(0.5)

    def test_update_with_zero_dt(self):
        marker = ExtractionZoneMarker(make_zone())
        marker.update(0.0)
        assert marker._anim_time == 0.0


# ======================================================================
# Draw
# ======================================================================


class TestExtractionZoneMarkerDraw:
    @pytest.fixture
    def surface(self):
        return pygame.Surface((1280, 720))

    @pytest.fixture
    def camera(self):
        cam = make_camera()
        cam.offset = pygame.math.Vector2(0, 0)
        return cam

    def test_draw_without_crash(self, surface, camera):
        marker = ExtractionZoneMarker(make_zone())
        marker.draw(surface, camera)

    def test_draw_after_animation_advance(self, surface, camera):
        marker = ExtractionZoneMarker(make_zone())
        marker.update(2.0)
        marker.draw(surface, camera)

    def test_draw_with_camera_offset(self, surface):
        camera = make_camera()
        camera.offset = pygame.math.Vector2(100, 100)
        marker = ExtractionZoneMarker(make_zone(x=200, y=200))
        marker.draw(surface, camera)

    def test_draw_zone_partially_offscreen(self, surface, camera):
        """Zone at the edge should render partially."""
        marker = ExtractionZoneMarker(make_zone(x=1200, y=650, w=128, h=128))
        marker.draw(surface, camera)

    def test_draw_zone_fully_offscreen(self, surface):
        """Zone far off-screen should not crash."""
        camera = make_camera()
        camera.offset = pygame.math.Vector2(5000, 5000)
        marker = ExtractionZoneMarker(make_zone(x=200, y=200))
        marker.draw(surface, camera)

    def test_draw_large_zone(self, surface, camera):
        marker = ExtractionZoneMarker(make_zone(x=0, y=0, w=512, h=512))
        marker.draw(surface, camera)

    def test_draw_small_zone(self, surface, camera):
        marker = ExtractionZoneMarker(make_zone(x=100, y=100, w=32, h=32))
        marker.draw(surface, camera)


# ======================================================================
# Off-screen indicator
# ======================================================================


class TestExtractionZoneMarkerIndicator:
    @pytest.fixture
    def surface(self):
        return pygame.Surface((1280, 720))

    def test_indicator_not_drawn_when_onscreen(self, surface):
        camera = make_camera()
        camera.offset = pygame.math.Vector2(0, 0)
        # Zone is well within the viewport
        marker = ExtractionZoneMarker(make_zone(x=400, y=300, w=128, h=128))
        player_pos = pygame.math.Vector2(640, 360)
        # Should not crash; indicator just returns early
        marker.draw_indicator(surface, camera, player_pos)

    def test_indicator_drawn_when_offscreen_right(self, surface):
        camera = make_camera()
        camera.offset = pygame.math.Vector2(0, 0)
        # Zone is off-screen to the right
        marker = ExtractionZoneMarker(make_zone(x=2000, y=360, w=128, h=128))
        player_pos = pygame.math.Vector2(640, 360)
        marker.draw_indicator(surface, camera, player_pos)

    def test_indicator_drawn_when_offscreen_left(self, surface):
        camera = make_camera()
        camera.offset = pygame.math.Vector2(2000, 0)
        marker = ExtractionZoneMarker(make_zone(x=100, y=360, w=128, h=128))
        player_pos = pygame.math.Vector2(640, 360)
        marker.draw_indicator(surface, camera, player_pos)

    def test_indicator_drawn_when_offscreen_above(self, surface):
        camera = make_camera()
        camera.offset = pygame.math.Vector2(0, 2000)
        marker = ExtractionZoneMarker(make_zone(x=640, y=100, w=128, h=128))
        player_pos = pygame.math.Vector2(640, 360)
        marker.draw_indicator(surface, camera, player_pos)

    def test_indicator_drawn_when_offscreen_below(self, surface):
        camera = make_camera()
        camera.offset = pygame.math.Vector2(0, 0)
        marker = ExtractionZoneMarker(make_zone(x=640, y=2000, w=128, h=128))
        player_pos = pygame.math.Vector2(640, 360)
        marker.draw_indicator(surface, camera, player_pos)

    def test_indicator_after_animation_advance(self, surface):
        camera = make_camera()
        camera.offset = pygame.math.Vector2(0, 0)
        marker = ExtractionZoneMarker(make_zone(x=2000, y=360))
        marker.update(3.0)  # advance animation
        player_pos = pygame.math.Vector2(640, 360)
        marker.draw_indicator(surface, camera, player_pos)


# ======================================================================
# Entity exports
# ======================================================================


class TestEntityExport:
    def test_extraction_zone_marker_in_entities_init(self):
        from src.entities import ExtractionZoneMarker as Exported

        assert Exported is ExtractionZoneMarker
