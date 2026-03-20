# Run: pytest tests/test_extraction_zone.py
"""Unit tests for ExtractionZone — construction and rendering.

Coverage matrix
---------------
Construction
  - rect stored correctly via __init__
  - default name is "Extraction"
  - custom name stored
  - from_topleft() builds correct rect and name
  - from_topleft() default name

render() — no crash
  - default args only
  - channel_progress=0.0
  - channel_progress=1.0
  - camera_offset applied
  - non-zero pulse_time
  - all args together

Border rendering
  - top-left corner pixel is EXTRACTION_ZONE_BORDER_COLOR at zero camera offset
  - camera offset shifts the drawn position correctly
  - bottom-right corner pixel is border color

Fill alpha
  - interior pixel differs from background after render (fill visible)
  - active channel (channel_progress > 0) produces brighter fill than idle
  - different pulse_time values produce different fill brightnesses

Progress bar
  - no bar drawn when channel_progress == 0
  - bar fill colour matches EXTRACTION_CHANNEL_BAR_COLOR when progress > 0
  - bar does not extend past the filled portion of the zone
  - full-width bar appears at 100 % progress
"""
from __future__ import annotations

import math

import pygame
import pytest

from src.constants import (
    EXTRACTION_CHANNEL_BAR_COLOR,
    EXTRACTION_ZONE_ALPHA,
    EXTRACTION_ZONE_BORDER_COLOR,
    EXTRACTION_ZONE_COLOR,
    EXTRACTION_ZONE_PULSE_SPEED,
)
from src.map.extraction_zone import ExtractionZone

# ---------------------------------------------------------------------------
# Test geometry
# ---------------------------------------------------------------------------
_SCREEN_W = 400
_SCREEN_H = 300
_ZONE_X, _ZONE_Y = 50, 40
_ZONE_W, _ZONE_H = 100, 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zone(
    x: int = _ZONE_X,
    y: int = _ZONE_Y,
    w: int = _ZONE_W,
    h: int = _ZONE_H,
    name: str = "Extraction",
) -> ExtractionZone:
    return ExtractionZone(rect=pygame.Rect(x, y, w, h), name=name)


def _blank_screen(color: tuple[int, int, int] = (0, 0, 0)) -> pygame.Surface:
    surf = pygame.Surface((_SCREEN_W, _SCREEN_H))
    surf.fill(color)
    return surf


# ===========================================================================
# Construction
# ===========================================================================

class TestConstruction:
    def test_rect_stored_correctly(self):
        rect = pygame.Rect(10, 20, 80, 40)
        zone = ExtractionZone(rect=rect)
        assert zone.rect == rect

    def test_default_name_is_extraction(self):
        zone = ExtractionZone(rect=pygame.Rect(0, 0, 32, 32))
        assert zone.name == "Extraction"

    def test_custom_name_stored(self):
        zone = ExtractionZone(rect=pygame.Rect(0, 0, 32, 32), name="Alpha Pad")
        assert zone.name == "Alpha Pad"

    def test_from_topleft_builds_correct_rect(self):
        zone = ExtractionZone.from_topleft(10, 20, 80, 40)
        assert zone.rect.x == 10
        assert zone.rect.y == 20
        assert zone.rect.width == 80
        assert zone.rect.height == 40

    def test_from_topleft_stores_custom_name(self):
        zone = ExtractionZone.from_topleft(0, 0, 32, 32, name="Beta")
        assert zone.name == "Beta"

    def test_from_topleft_default_name(self):
        zone = ExtractionZone.from_topleft(0, 0, 32, 32)
        assert zone.name == "Extraction"


# ===========================================================================
# render() — no crash
# ===========================================================================

class TestRenderDoesNotCrash:
    """render() must not raise under any combination of valid inputs."""

    def test_minimal_call(self, pygame_init):
        _make_zone().render(_blank_screen())

    def test_zero_channel_progress(self, pygame_init):
        _make_zone().render(_blank_screen(), channel_progress=0.0)

    def test_full_channel_progress(self, pygame_init):
        _make_zone().render(_blank_screen(), channel_progress=1.0)

    def test_camera_offset(self, pygame_init):
        _make_zone().render(_blank_screen(), camera_offset=(10, 20))

    def test_nonzero_pulse_time(self, pygame_init):
        _make_zone().render(_blank_screen(), pulse_time=3.14)

    def test_all_args_together(self, pygame_init):
        _make_zone().render(
            _blank_screen(),
            camera_offset=(5, 5),
            channel_progress=0.5,
            pulse_time=1.0,
        )

    def test_negative_camera_offset_clips_zone_off_screen(self, pygame_init):
        """Zone scrolled fully off-screen must not crash."""
        zone = _make_zone()
        # Offset so zone.x - ox is well off screen to the left
        zone.render(_blank_screen(), camera_offset=(2000, 0))

    def test_zero_size_zone_does_not_crash(self, pygame_init):
        """A degenerate 0×0 zone must not raise."""
        zone = ExtractionZone(rect=pygame.Rect(0, 0, 0, 0))
        zone.render(_blank_screen(), channel_progress=0.5)


# ===========================================================================
# Border rendering
# ===========================================================================

class TestBorderRendering:
    """The 2-px border must be drawn in EXTRACTION_ZONE_BORDER_COLOR."""

    def test_top_left_corner_pixel_is_border_color(self, pygame_init):
        """(zone_x, zone_y) must be the border colour at zero camera offset."""
        zone = _make_zone()
        screen = _blank_screen()
        zone.render(screen, camera_offset=(0, 0))
        pixel = screen.get_at((_ZONE_X, _ZONE_Y))[:3]
        assert pixel == EXTRACTION_ZONE_BORDER_COLOR

    def test_border_shifts_with_camera_offset(self, pygame_init):
        """With camera_offset=(ox, oy) the border moves to (zone_x-ox, zone_y-oy)."""
        zone = _make_zone()
        ox, oy = 10, 15
        expected_x = _ZONE_X - ox
        expected_y = _ZONE_Y - oy
        screen = _blank_screen()
        zone.render(screen, camera_offset=(ox, oy))
        pixel = screen.get_at((expected_x, expected_y))[:3]
        assert pixel == EXTRACTION_ZONE_BORDER_COLOR

    def test_bottom_right_corner_pixel_is_border_color(self, pygame_init):
        """Bottom-right corner of the zone rect must carry the border colour."""
        zone = _make_zone()
        screen = _blank_screen()
        zone.render(screen, camera_offset=(0, 0))
        br_x = _ZONE_X + _ZONE_W - 1
        br_y = _ZONE_Y + _ZONE_H - 1
        pixel = screen.get_at((br_x, br_y))[:3]
        assert pixel == EXTRACTION_ZONE_BORDER_COLOR

    def test_interior_pixel_is_not_border_color(self, pygame_init):
        """A pixel well inside the zone must NOT be the border colour (it is fill)."""
        zone = _make_zone()
        screen = _blank_screen()
        zone.render(screen, camera_offset=(0, 0))
        # True interior: centre of zone
        cx = _ZONE_X + _ZONE_W // 2
        cy = _ZONE_Y + _ZONE_H // 2
        pixel = screen.get_at((cx, cy))[:3]
        assert pixel != EXTRACTION_ZONE_BORDER_COLOR


# ===========================================================================
# Fill alpha
# ===========================================================================

class TestFillAlpha:
    """The semi-transparent fill must blend visibly with the background."""

    def _interior_pixel(self, screen: pygame.Surface) -> tuple:
        """Centre pixel of the zone — inside the 2-px border, outside the bar."""
        cx = _ZONE_X + _ZONE_W // 2
        cy = _ZONE_Y + _ZONE_H // 2
        return screen.get_at((cx, cy))[:3]

    def test_fill_changes_interior_pixel_from_background(self, pygame_init):
        """Blitting the tinted fill must make interior pixels differ from black."""
        zone = _make_zone()
        screen = _blank_screen()   # pure black
        zone.render(screen, channel_progress=0.0, pulse_time=0.0)
        pixel = self._interior_pixel(screen)
        assert pixel != (0, 0, 0), (
            "Interior pixel should be alpha-blended with the zone fill, not black"
        )

    def test_active_channel_brightens_fill(self, pygame_init):
        """channel_progress > 0 uses alpha=200 vs idle alpha≈60; must be brighter."""
        zone = _make_zone()

        screen_idle = _blank_screen()
        zone.render(screen_idle, channel_progress=0.0, pulse_time=0.0)
        idle_lum = sum(self._interior_pixel(screen_idle))

        screen_active = _blank_screen()
        zone.render(screen_active, channel_progress=0.5, pulse_time=0.0)
        active_lum = sum(self._interior_pixel(screen_active))

        assert active_lum > idle_lum, (
            "Active-channel fill (alpha=200) must be brighter than idle fill (alpha≈60)"
        )

    def test_pulse_time_changes_fill_brightness(self, pygame_init):
        """Different pulse_time values must yield different fill alphas.

        pulse_time = 0     → sin(0) = 0   → alpha = EXTRACTION_ZONE_ALPHA
        pulse_time = T_max → sin(π/2) = 1 → alpha = EXTRACTION_ZONE_ALPHA + 30
        """
        zone = _make_zone()
        # pulse_time where sin reaches its maximum (= 1.0)
        t_max = 1.0 / (4.0 * EXTRACTION_ZONE_PULSE_SPEED)

        screen_zero = _blank_screen()
        zone.render(screen_zero, channel_progress=0.0, pulse_time=0.0)
        p_zero = self._interior_pixel(screen_zero)

        screen_max = _blank_screen()
        zone.render(screen_max, channel_progress=0.0, pulse_time=t_max)
        p_max = self._interior_pixel(screen_max)

        assert p_zero != p_max, (
            f"pulse_time=0 {p_zero} and pulse_time={t_max} {p_max} "
            "should produce different fill alphas"
        )


# ===========================================================================
# Progress bar
# ===========================================================================

class TestProgressBar:
    """When channel_progress > 0 the bar must be painted at the zone's bottom edge."""

    # Bar occupies the last `bar_h=6` rows of the zone rect.
    _BAR_H = 6

    def _bar_row(self) -> int:
        """Y-coordinate in the middle of the 6-px bar at zero camera offset."""
        return _ZONE_Y + _ZONE_H - self._BAR_H // 2

    def test_no_bar_drawn_at_zero_progress(self, pygame_init):
        """With channel_progress=0 the bar area must not carry the bar fill colour."""
        zone = _make_zone()
        screen = _blank_screen()
        zone.render(screen, channel_progress=0.0, pulse_time=0.0)
        # Sample a pixel in the bar row inside the zone
        bar_pixel = screen.get_at((_ZONE_X + 5, self._bar_row()))[:3]
        assert bar_pixel != EXTRACTION_CHANNEL_BAR_COLOR

    def test_bar_fill_color_at_half_progress(self, pygame_init):
        """At 50 % progress the filled half of the bar must be the bar colour."""
        zone = _make_zone()
        screen = _blank_screen()
        zone.render(screen, channel_progress=0.5, pulse_time=0.0)
        # 50 % of 100 px → bar covers cols ZONE_X to ZONE_X+49
        # Sample at ZONE_X + 5: firmly in the filled region
        bar_pixel = screen.get_at((_ZONE_X + 5, self._bar_row()))[:3]
        assert bar_pixel == EXTRACTION_CHANNEL_BAR_COLOR

    def test_bar_does_not_extend_past_progress_boundary(self, pygame_init):
        """At 30 % progress, pixels beyond 30 % of zone width must not show bar colour."""
        zone = _make_zone()
        screen = _blank_screen()
        zone.render(screen, channel_progress=0.3, pulse_time=0.0)
        # 80 % along the zone width is outside the 30 % bar
        outside_x = _ZONE_X + int(_ZONE_W * 0.8)
        outside_pixel = screen.get_at((outside_x, self._bar_row()))[:3]
        assert outside_pixel != EXTRACTION_CHANNEL_BAR_COLOR

    def test_full_progress_bar_spans_entire_zone_width(self, pygame_init):
        """At 100 % progress, a pixel near the right edge must carry the bar colour."""
        zone = _make_zone()
        screen = _blank_screen()
        zone.render(screen, channel_progress=1.0, pulse_time=0.0)
        # Near right edge — 5 px inside so we avoid the right-border pixel
        right_x = _ZONE_X + _ZONE_W - 5
        right_pixel = screen.get_at((right_x, self._bar_row()))[:3]
        assert right_pixel == EXTRACTION_CHANNEL_BAR_COLOR

    def test_bar_appears_with_small_nonzero_progress(self, pygame_init):
        """At 10 % progress (10 px wide bar) the interior of the bar must carry the bar colour.

        The very first column of the bar is overwritten by the 1-px bar-track
        outline border, so we sample at the 5th column (well inside the fill).
        """
        zone = _make_zone()
        screen = _blank_screen()
        zone.render(screen, channel_progress=0.10, pulse_time=0.0)
        # 10 % of 100 px → bar covers cols ZONE_X … ZONE_X+9.
        # Sample at ZONE_X + 4 (5th pixel, clear of the left track-outline).
        interior_x = _ZONE_X + 4
        pixel = screen.get_at((interior_x, self._bar_row()))[:3]
        assert pixel == EXTRACTION_CHANNEL_BAR_COLOR
