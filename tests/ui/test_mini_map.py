"""Tests for MiniMap world-to-minimap coordinate transform."""
from __future__ import annotations

import pytest
import pygame

from src.ui.mini_map import MiniMap
from src.ui.hud_state import HUDState, ZoneInfo


@pytest.fixture(scope='session', autouse=True)
def pygame_headless():
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.quit()


@pytest.fixture
def mini_rect():
    return pygame.Rect(1064, 16, 200, 200)


@pytest.fixture
def map_rect():
    """A 1280×720 world map."""
    return pygame.Rect(0, 0, 1280, 720)


@pytest.fixture
def base_state(map_rect):
    """Minimal HUDState with a 1280×720 map."""
    return HUDState(
        map_world_rect=map_rect,
        player_world_pos=(0.0, 0.0),
    )


class TestWorldToMiniTransform:
    def test_player_at_world_origin_maps_to_minimap_topleft(self, mini_rect, map_rect):
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=map_rect, player_world_pos=(0.0, 0.0))
        mm.update(state)
        px, py = mm._world_to_mini(0.0, 0.0)
        assert px == mini_rect.x
        assert py == mini_rect.y

    def test_player_at_world_max_maps_to_minimap_bottomright(self, mini_rect, map_rect):
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=map_rect, player_world_pos=(1280.0, 720.0))
        mm.update(state)
        px, py = mm._world_to_mini(1280.0, 720.0)
        # Should be clamped to right/bottom edge
        assert px == mini_rect.right - 1
        assert py == mini_rect.bottom - 1

    def test_player_at_center_maps_to_minimap_center(self, mini_rect, map_rect):
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=map_rect, player_world_pos=(640.0, 360.0))
        mm.update(state)
        px, py = mm._world_to_mini(640.0, 360.0)
        expected_x = mini_rect.x + mini_rect.width // 2
        expected_y = mini_rect.y + mini_rect.height // 2
        # Allow ±1 pixel for integer rounding
        assert abs(px - expected_x) <= 1
        assert abs(py - expected_y) <= 1

    def test_negative_world_pos_clamped_to_minimap_left(self, mini_rect, map_rect):
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=map_rect, player_world_pos=(-999.0, 0.0))
        mm.update(state)
        px, py = mm._world_to_mini(-999.0, 0.0)
        assert px >= mini_rect.x

    def test_beyond_max_world_pos_clamped_to_minimap_right(self, mini_rect, map_rect):
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=map_rect, player_world_pos=(9999.0, 0.0))
        mm.update(state)
        px, py = mm._world_to_mini(9999.0, 0.0)
        assert px <= mini_rect.right - 1

    def test_result_stays_within_minimap_rect(self, mini_rect, map_rect):
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=map_rect, player_world_pos=(640.0, 360.0))
        mm.update(state)
        for wx, wy in [(0, 0), (640, 360), (1280, 720), (-100, -100), (9999, 9999)]:
            px, py = mm._world_to_mini(float(wx), float(wy))
            assert mini_rect.x <= px < mini_rect.right, f"x={px} out of {mini_rect}"
            assert mini_rect.y <= py < mini_rect.bottom, f"y={py} out of {mini_rect}"

    def test_extraction_point_placement(self, mini_rect, map_rect):
        """Extraction at world center should map near minimap center."""
        mm = MiniMap(mini_rect)
        state = HUDState(
            map_world_rect=map_rect,
            player_world_pos=(0.0, 0.0),
            extraction_pos=(640.0, 360.0),
        )
        mm.update(state)
        ex, ey = mm._world_to_mini(640.0, 360.0)
        cx = mini_rect.x + mini_rect.width // 2
        cy = mini_rect.y + mini_rect.height // 2
        assert abs(ex - cx) <= 1
        assert abs(ey - cy) <= 1


class TestMiniMapUpdate:
    def test_update_caches_state(self, mini_rect, base_state):
        mm = MiniMap(mini_rect)
        mm.update(base_state)
        assert mm._state is base_state

    def test_update_replaces_previous_state(self, mini_rect, base_state):
        mm = MiniMap(mini_rect)
        mm.update(base_state)
        new_state = HUDState(map_world_rect=pygame.Rect(0, 0, 640, 480))
        mm.update(new_state)
        assert mm._state is new_state


class TestMiniMapDraw:
    def test_draw_does_not_raise_with_no_state(self, mini_rect):
        surface = pygame.Surface((1280, 720))
        mm = MiniMap(mini_rect)
        mm.draw(surface)  # should not raise even with no state

    def test_draw_does_not_raise_with_full_state(self, mini_rect, map_rect):
        surface = pygame.Surface((1280, 720))
        mm = MiniMap(mini_rect)
        zones = [
            ZoneInfo(
                name='Alpha',
                color=(80, 60, 120),
                world_rect=pygame.Rect(0, 0, 640, 720),
            ),
        ]
        state = HUDState(
            map_world_rect=map_rect,
            player_world_pos=(320.0, 360.0),
            zones=zones,
            extraction_pos=(960.0, 360.0),
        )
        mm.update(state)
        mm.draw(surface)

    def test_draw_with_no_map_rect_does_not_raise(self, mini_rect):
        surface = pygame.Surface((1280, 720))
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=None, player_world_pos=(100.0, 100.0))
        mm.update(state)
        mm.draw(surface)

    def test_draw_without_extraction_pos_does_not_raise(self, mini_rect, map_rect):
        surface = pygame.Surface((1280, 720))
        mm = MiniMap(mini_rect)
        state = HUDState(
            map_world_rect=map_rect,
            player_world_pos=(100.0, 100.0),
            extraction_pos=None,
        )
        mm.update(state)
        mm.draw(surface)

    def test_draw_with_multiple_zones_does_not_raise(self, mini_rect, map_rect):
        surface = pygame.Surface((1280, 720))
        mm = MiniMap(mini_rect)
        zones = [
            ZoneInfo(name='Alpha', color=(80, 60, 120),
                     world_rect=pygame.Rect(0, 0, 427, 720)),
            ZoneInfo(name='Beta',  color=(60, 100, 80),
                     world_rect=pygame.Rect(427, 0, 426, 720)),
            ZoneInfo(name='Gamma', color=(110, 80, 60),
                     world_rect=pygame.Rect(853, 0, 427, 720)),
        ]
        state = HUDState(
            map_world_rect=map_rect,
            player_world_pos=(640.0, 360.0),
            zones=zones,
            extraction_pos=(900.0, 200.0),
        )
        mm.update(state)
        mm.draw(surface)

    def test_draw_with_zone_outside_map_rect_does_not_raise(self, mini_rect, map_rect):
        """A zone rect that extends beyond the map rect must be clipped, not crash."""
        surface = pygame.Surface((1280, 720))
        mm = MiniMap(mini_rect)
        oversized_zone = ZoneInfo(
            name='Oversized',
            color=(200, 50, 50),
            world_rect=pygame.Rect(-500, -500, 5000, 5000),
        )
        state = HUDState(
            map_world_rect=map_rect,
            player_world_pos=(320.0, 180.0),
            zones=[oversized_zone],
        )
        mm.update(state)
        mm.draw(surface)


# ---------------------------------------------------------------------------
# _world_to_mini with no state (initial/None state)
# ---------------------------------------------------------------------------
class TestWorldToMiniNoState:
    def test_world_to_mini_before_update_returns_minimap_origin(self, mini_rect):
        """Before update() is called, _world_to_mini should return the
        minimap's top-left corner (a safe default)."""
        mm = MiniMap(mini_rect)
        # State is None at construction
        px, py = mm._world_to_mini(640.0, 360.0)
        assert px == mini_rect.x
        assert py == mini_rect.y

    def test_world_to_mini_with_none_map_rect_returns_minimap_origin(
        self, mini_rect
    ):
        """State present but map_world_rect=None: fall back to minimap origin."""
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=None, player_world_pos=(0.0, 0.0))
        mm.update(state)
        px, py = mm._world_to_mini(640.0, 360.0)
        assert px == mini_rect.x
        assert py == mini_rect.y


# ---------------------------------------------------------------------------
# Transform accuracy at fractional positions
# ---------------------------------------------------------------------------
class TestWorldToMiniAccuracy:
    def test_quarter_x_maps_to_quarter_minimap_width(self, mini_rect, map_rect):
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=map_rect, player_world_pos=(0.0, 0.0))
        mm.update(state)
        # world x=320 is 1/4 of 1280 → should be at mini_rect.x + mini_rect.w//4
        px, _ = mm._world_to_mini(320.0, 0.0)
        expected = mini_rect.x + mini_rect.width // 4
        assert abs(px - expected) <= 1

    def test_three_quarter_y_maps_to_three_quarter_minimap_height(
        self, mini_rect, map_rect
    ):
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=map_rect, player_world_pos=(0.0, 0.0))
        mm.update(state)
        # world y=540 is 3/4 of 720 → should be at mini_rect.y + 3*mini_rect.h//4
        _, py = mm._world_to_mini(0.0, 540.0)
        expected = mini_rect.y + 3 * mini_rect.height // 4
        assert abs(py - expected) <= 1

    def test_output_always_within_minimap_for_arbitrary_inputs(
        self, mini_rect, map_rect
    ):
        """Fuzz a range of world coords; all must stay within minimap bounds."""
        mm = MiniMap(mini_rect)
        state = HUDState(map_world_rect=map_rect, player_world_pos=(0.0, 0.0))
        mm.update(state)
        test_coords = [
            (-10000.0, -10000.0),
            (0.0, 0.0),
            (320.0, 180.0),
            (640.0, 360.0),
            (960.0, 540.0),
            (1280.0, 720.0),
            (10000.0, 10000.0),
        ]
        for wx, wy in test_coords:
            px, py = mm._world_to_mini(wx, wy)
            assert mini_rect.x <= px < mini_rect.right, \
                f"x={px} out of [{mini_rect.x}, {mini_rect.right}) for world ({wx},{wy})"
            assert mini_rect.y <= py < mini_rect.bottom, \
                f"y={py} out of [{mini_rect.y}, {mini_rect.bottom}) for world ({wx},{wy})"
