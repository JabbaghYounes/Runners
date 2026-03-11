"""Tests for Camera: update centering, clamping, world↔screen conversions."""
import pytest
import pygame
from src.map.camera import Camera


@pytest.fixture()
def cam():
    return Camera(screen_w=320, screen_h=240, map_w=1000, map_h=800)


class TestCameraUpdate:
    def test_centers_on_player(self, cam):
        player = pygame.Rect(500, 400, 28, 48)
        # Run update many times to let smooth-follow converge
        for _ in range(120):
            cam.update(player)
        # offset should place player center at screen center
        # target_x = 500+14 - 160 = 354, target_y = 400+24 - 120 = 304
        # but map is 1000 wide, screen 320, max offset_x = 680
        assert abs(cam.offset_x - 354) < 5

    def test_clamp_left_edge(self, cam):
        player = pygame.Rect(0, 400, 28, 48)
        for _ in range(200):
            cam.update(player)
        assert cam.offset_x >= 0.0

    def test_clamp_right_edge(self, cam):
        player = pygame.Rect(990, 400, 28, 48)
        for _ in range(200):
            cam.update(player)
        assert cam.offset_x <= float(cam.map_w - cam.screen_w)

    def test_clamp_top_edge(self, cam):
        player = pygame.Rect(400, 0, 28, 48)
        for _ in range(200):
            cam.update(player)
        assert cam.offset_y >= 0.0

    def test_clamp_bottom_edge(self, cam):
        player = pygame.Rect(400, 790, 28, 48)
        for _ in range(200):
            cam.update(player)
        assert cam.offset_y <= float(cam.map_h - cam.screen_h)


class TestWorldToScreen:
    def test_origin_at_zero_offset(self):
        cam = Camera(320, 240, 1000, 800)
        # offset is 0 initially
        sx, sy = cam.world_to_screen(0, 0)
        assert sx == 0
        assert sy == 0

    def test_world_to_screen_with_offset(self, cam):
        cam.offset_x = 50.0
        cam.offset_y = 30.0
        sx, sy = cam.world_to_screen(100, 80)
        assert sx == 50   # 100 - 50
        assert sy == 50   # 80 - 30

    def test_screen_to_world_inverses(self, cam):
        cam.offset_x = 100.0
        cam.offset_y = 50.0
        wx, wy = 350.0, 200.0
        sx, sy = cam.world_to_screen(wx, wy)
        wx2, wy2 = cam.screen_to_world(sx, sy)
        assert abs(wx2 - wx) < 1
        assert abs(wy2 - wy) < 1


class TestCameraOffset:
    def test_offset_property_returns_int_tuple(self, cam):
        cam.offset_x = 12.7
        cam.offset_y = 34.9
        off = cam.offset
        assert isinstance(off, tuple)
        assert off[0] == 12
        assert off[1] == 34

    def test_initial_offset_is_zero(self, cam):
        assert cam.offset == (0, 0)


class TestCameraClampMethod:
    def test_clamp_updates_map_dimensions(self):
        cam = Camera(320, 240, 100, 100)
        cam.offset_x = 200.0  # out of bounds for map 100w
        cam.clamp(1000, 800)
        # after clamp with larger map, offset should be clamped to [0, 680]
        assert cam.offset_x <= float(1000 - 320)
        assert cam.map_w == 1000
