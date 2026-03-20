# Run: pytest tests/map/test_camera.py
"""Unit tests for Camera: smooth follow, edge clamping, small-map guard,
and world ↔ screen coordinate transforms.

Key coverage added beyond tests/test_camera.py:
- Map narrower/shorter than screen must never produce a negative offset
  (Phase 2 guard: max(0.0, map_w - screen_w) in _clamp())
- Exact-fit map (map == screen size) clamps to offset 0
- All four boundary directions converge to valid clamped values
- world_to_screen / screen_to_world roundtrip with arbitrary offsets
"""
from __future__ import annotations

import pytest
import pygame

from src.map.camera import Camera


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cam():
    """Standard camera: 320×240 screen on a 1 000×800 map."""
    return Camera(screen_w=320, screen_h=240, map_w=1000, map_h=800)


@pytest.fixture
def small_map_cam():
    """Camera whose viewport is LARGER than the map in both dimensions.

    This is the edge-case introduced in Phase 2: the clamp guard must
    produce max_x = max_y = 0.0 so offsets never go negative.
    """
    return Camera(screen_w=800, screen_h=600, map_w=200, map_h=150)


# ---------------------------------------------------------------------------
# TestSmoothFollow — convergence behaviour
# ---------------------------------------------------------------------------


class TestSmoothFollow:
    def test_converges_to_player_center_after_many_updates(self, cam):
        """After 200 updates the offset should be within 2 px of the target."""
        player = pygame.Rect(500, 400, 28, 48)
        for _ in range(200):
            cam.update(player)
        # target_x = centerx − screen_w / 2 = 514 − 160 = 354
        assert abs(cam.offset_x - 354) < 2

    def test_initial_offset_is_zero_before_any_update(self):
        cam = Camera(320, 240, 1000, 800)
        assert cam.offset_x == 0.0
        assert cam.offset_y == 0.0

    def test_each_update_moves_offset_toward_target(self, cam):
        """A single update with a far-right player must increase offset_x."""
        player = pygame.Rect(800, 600, 28, 48)
        before_x = cam.offset_x
        cam.update(player)
        assert cam.offset_x >= before_x

    def test_offset_monotonically_converges_without_overshoot(self, cam):
        """Smooth-follow (coefficient < 1) must not overshoot the target."""
        player = pygame.Rect(600, 500, 28, 48)
        target_x = player.centerx - cam.screen_w // 2  # 614 - 160 = 454
        for _ in range(300):
            cam.update(player)
        # After convergence offset must be at or below max clamp (1000-320=680)
        assert cam.offset_x <= float(cam.map_w - cam.screen_w)
        assert cam.offset_x <= target_x + 1  # never overshot by more than 1 px


# ---------------------------------------------------------------------------
# TestEdgeClamping — all four map boundaries
# ---------------------------------------------------------------------------


class TestEdgeClamping:
    def test_clamps_left_offset_x_never_negative(self, cam):
        """Player at the far left must clamp offset_x to 0, never below."""
        player = pygame.Rect(0, 400, 28, 48)
        for _ in range(300):
            cam.update(player)
        assert cam.offset_x >= 0.0

    def test_clamps_right_offset_x_not_past_map_minus_screen(self, cam):
        """Player beyond map right edge must cap offset_x at map_w − screen_w."""
        player = pygame.Rect(9999, 400, 28, 48)
        for _ in range(300):
            cam.update(player)
        assert cam.offset_x <= float(cam.map_w - cam.screen_w)

    def test_clamps_top_offset_y_never_negative(self, cam):
        player = pygame.Rect(400, 0, 28, 48)
        for _ in range(300):
            cam.update(player)
        assert cam.offset_y >= 0.0

    def test_clamps_bottom_offset_y_not_past_map_minus_screen(self, cam):
        player = pygame.Rect(400, 9999, 28, 48)
        for _ in range(300):
            cam.update(player)
        assert cam.offset_y <= float(cam.map_h - cam.screen_h)

    def test_direct_clamp_at_zero_stays_zero(self, cam):
        """_clamp() on an already-valid zero offset must be a no-op."""
        cam.offset_x = 0.0
        cam.offset_y = 0.0
        cam._clamp()
        assert cam.offset_x == 0.0
        assert cam.offset_y == 0.0

    def test_direct_clamp_at_max_stays_at_max(self, cam):
        """_clamp() at exactly the maximum valid value must be a no-op."""
        max_x = float(cam.map_w - cam.screen_w)  # 680.0
        max_y = float(cam.map_h - cam.screen_h)  # 560.0
        cam.offset_x = max_x
        cam.offset_y = max_y
        cam._clamp()
        assert cam.offset_x == max_x
        assert cam.offset_y == max_y

    def test_direct_clamp_corrects_out_of_range_large_offset(self, cam):
        """Offsets beyond the map boundary must be clamped down."""
        cam.offset_x = 99999.0
        cam.offset_y = 99999.0
        cam._clamp()
        assert cam.offset_x <= float(cam.map_w - cam.screen_w)
        assert cam.offset_y <= float(cam.map_h - cam.screen_h)


# ---------------------------------------------------------------------------
# TestSmallMapNoNegativeOffset — Phase 2 guard
# ---------------------------------------------------------------------------


class TestSmallMapNoNegativeOffset:
    """When map < screen the max offset is 0; offset must never go negative."""

    def test_offset_x_stays_zero_after_update_with_small_map(self, small_map_cam):
        """Map width (200) < screen width (800): offset_x must stay at 0."""
        player = pygame.Rect(100, 75, 28, 48)
        for _ in range(200):
            small_map_cam.update(player)
        assert small_map_cam.offset_x == 0.0

    def test_offset_y_stays_zero_after_update_with_small_map(self, small_map_cam):
        """Map height (150) < screen height (600): offset_y must stay at 0."""
        player = pygame.Rect(100, 75, 28, 48)
        for _ in range(200):
            small_map_cam.update(player)
        assert small_map_cam.offset_y == 0.0

    def test_forced_large_offset_x_clamped_to_zero_small_map(self, small_map_cam):
        """Force offset_x = 9999 then clamp — must return to 0, not negative."""
        small_map_cam.offset_x = 9999.0
        small_map_cam._clamp()
        assert small_map_cam.offset_x == 0.0

    def test_forced_large_offset_y_clamped_to_zero_small_map(self, small_map_cam):
        small_map_cam.offset_y = 9999.0
        small_map_cam._clamp()
        assert small_map_cam.offset_y == 0.0

    def test_forced_negative_offset_x_clamped_to_zero_small_map(self, small_map_cam):
        """Negative offsets must also be corrected to 0."""
        small_map_cam.offset_x = -500.0
        small_map_cam._clamp()
        assert small_map_cam.offset_x == 0.0

    def test_exact_fit_map_offset_clamped_to_zero(self):
        """Map exactly matches screen (max offset = 0): any offset → 0."""
        cam = Camera(screen_w=320, screen_h=240, map_w=320, map_h=240)
        cam.offset_x = 50.0
        cam.offset_y = 30.0
        cam._clamp()
        assert cam.offset_x == 0.0
        assert cam.offset_y == 0.0

    def test_offset_never_negative_across_multiple_player_positions(
        self, small_map_cam
    ):
        """Fuzz player positions: offset must stay ≥ 0 in a small-map camera."""
        for px in [0, 50, 100, 150, 200, 500, 9999]:
            player = pygame.Rect(px, 75, 28, 48)
            small_map_cam.update(player)
            assert small_map_cam.offset_x >= 0.0, (
                f"offset_x={small_map_cam.offset_x} < 0 for player_x={px}"
            )
            assert small_map_cam.offset_y >= 0.0, (
                f"offset_y={small_map_cam.offset_y} < 0 for player_x={px}"
            )

    def test_map_one_pixel_wider_than_screen_allows_tiny_scroll(self):
        """If map is just 1 px wider, max offset_x = 1 — must stay in [0, 1]."""
        cam = Camera(screen_w=320, screen_h=240, map_w=321, map_h=240)
        cam.offset_x = 9999.0
        cam._clamp()
        assert 0.0 <= cam.offset_x <= 1.0


# ---------------------------------------------------------------------------
# TestWorldScreenTransform — coordinate conversions
# ---------------------------------------------------------------------------


class TestWorldScreenTransform:
    def test_world_to_screen_at_zero_offset_is_identity(self):
        cam = Camera(320, 240, 1000, 800)
        sx, sy = cam.world_to_screen(100.0, 200.0)
        assert sx == 100
        assert sy == 200

    def test_world_to_screen_subtracts_camera_offset(self, cam):
        cam.offset_x = 50.0
        cam.offset_y = 20.0
        sx, sy = cam.world_to_screen(150.0, 120.0)
        assert sx == 100   # 150 − 50
        assert sy == 100   # 120 − 20

    def test_screen_to_world_adds_camera_offset(self, cam):
        cam.offset_x = 50.0
        cam.offset_y = 20.0
        wx, wy = cam.screen_to_world(100.0, 100.0)
        assert wx == pytest.approx(150.0)
        assert wy == pytest.approx(120.0)

    def test_roundtrip_world_to_screen_to_world(self, cam):
        """screen_to_world(world_to_screen(p)) must recover p within 1 px."""
        cam.offset_x = 123.0
        cam.offset_y = 87.0
        wx_in, wy_in = 400.0, 250.0
        sx, sy = cam.world_to_screen(wx_in, wy_in)
        wx_out, wy_out = cam.screen_to_world(float(sx), float(sy))
        assert abs(wx_out - wx_in) <= 1.0  # allow 1 px integer truncation
        assert abs(wy_out - wy_in) <= 1.0

    def test_roundtrip_at_map_origin(self, cam):
        sx, sy = cam.world_to_screen(0.0, 0.0)
        wx, wy = cam.screen_to_world(float(sx), float(sy))
        assert wx == pytest.approx(0.0)
        assert wy == pytest.approx(0.0)

    def test_roundtrip_for_various_world_positions(self, cam):
        """Multiple world positions must survive the roundtrip."""
        cam.offset_x = 200.0
        cam.offset_y = 150.0
        for wx_in, wy_in in [(0.0, 0.0), (320.0, 240.0), (999.0, 799.0)]:
            sx, sy = cam.world_to_screen(wx_in, wy_in)
            wx_out, wy_out = cam.screen_to_world(float(sx), float(sy))
            assert abs(wx_out - wx_in) <= 1.0
            assert abs(wy_out - wy_in) <= 1.0


# ---------------------------------------------------------------------------
# TestOffsetProperty — integer truncation
# ---------------------------------------------------------------------------


class TestOffsetProperty:
    def test_offset_truncates_float_to_int(self, cam):
        cam.offset_x = 12.9
        cam.offset_y = 34.7
        ox, oy = cam.offset
        assert ox == 12
        assert oy == 34

    def test_offset_returns_tuple_of_ints(self, cam):
        off = cam.offset
        assert isinstance(off, tuple)
        assert isinstance(off[0], int)
        assert isinstance(off[1], int)

    def test_initial_offset_property_is_zero_zero(self, cam):
        assert cam.offset == (0, 0)


# ---------------------------------------------------------------------------
# TestClampPublicMethod — public clamp() API
# ---------------------------------------------------------------------------


class TestClampPublicMethod:
    def test_clamp_updates_map_w(self):
        cam = Camera(320, 240, 100, 100)
        cam.clamp(1000, 800)
        assert cam.map_w == 1000

    def test_clamp_updates_map_h(self):
        cam = Camera(320, 240, 100, 100)
        cam.clamp(1000, 800)
        assert cam.map_h == 800

    def test_clamp_corrects_out_of_bounds_offset_after_map_resize(self):
        cam = Camera(320, 240, 2000, 2000)
        cam.offset_x = 1500.0
        cam.clamp(400, 400)
        assert cam.offset_x <= float(400 - 320)

    def test_clamp_to_smaller_map_than_screen_resets_offset_to_zero(self):
        """After resizing the map to be smaller than the screen, offset → 0."""
        cam = Camera(320, 240, 2000, 2000)
        cam.offset_x = 500.0
        cam.offset_y = 300.0
        cam.clamp(100, 100)  # now 100 < 320 → max_x = max_y = 0
        assert cam.offset_x == 0.0
        assert cam.offset_y == 0.0
