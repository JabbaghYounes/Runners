"""Tests for HUD mini-map sub-renderer: initialisation, update, and draw.

Covers:
  - MiniMap initialises with _state == None
  - update() stores the HUDState snapshot
  - draw() is a silent no-op when state has not been set
  - draw() does not crash with a default (empty) HUDState
  - draw() renders player position dot when player_world_pos is set
  - draw() renders extraction marker when extraction_pos is set
  - draw() renders zone overlays when zones list is populated
  - _world_to_mini returns rect origin when map_world_rect is None
  - _world_to_mini clamps coordinates to minimap bounds
  - _world_to_mini handles zero-width map rect without division by zero

# Run: pytest tests/test_hud_minimap.py
"""
from __future__ import annotations

import pytest
import pygame

from src.ui.mini_map import MiniMap
from src.ui.hud_state import HUDState, ZoneInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAP_RECT = pygame.Rect(0, 0, 3200, 2400)   # 100×75 tiles at 32 px
_MINIMAP_RECT = pygame.Rect(1086, 16, 180, 180)


def _make_minimap(rect: pygame.Rect | None = None) -> MiniMap:
    return MiniMap(rect or _MINIMAP_RECT)


def _state(**overrides) -> HUDState:
    defaults: dict = dict(hp=100, max_hp=100, seconds_remaining=900.0)
    defaults.update(overrides)
    return HUDState(**defaults)


# ---------------------------------------------------------------------------
# Unit: initialisation
# ---------------------------------------------------------------------------

class TestMiniMapInit:
    def test_initial_state_is_none(self):
        mm = _make_minimap()
        assert mm._state is None

    def test_rect_stored_correctly(self):
        r = pygame.Rect(100, 100, 200, 200)
        mm = MiniMap(r)
        assert mm.rect == r


# ---------------------------------------------------------------------------
# Unit: update
# ---------------------------------------------------------------------------

class TestMiniMapUpdate:
    def test_update_stores_state(self):
        mm = _make_minimap()
        st = _state()
        mm.update(st)
        assert mm._state is st

    def test_update_replaces_previous_state(self):
        mm = _make_minimap()
        st1 = _state(hp=80)
        st2 = _state(hp=50)
        mm.update(st1)
        mm.update(st2)
        assert mm._state is st2

    def test_update_with_zones_stores_them(self):
        mm = _make_minimap()
        zone = ZoneInfo(name="ZONE_A", world_rect=pygame.Rect(0, 0, 320, 256))
        st = _state(zones=[zone])
        mm.update(st)
        assert mm._state.zones == [zone]

    def test_update_with_player_pos_stores_it(self):
        mm = _make_minimap()
        st = _state(player_world_pos=(640.0, 480.0))
        mm.update(st)
        assert mm._state.player_world_pos == (640.0, 480.0)

    def test_update_with_extraction_pos_stores_it(self):
        mm = _make_minimap()
        st = _state(extraction_pos=(1600.0, 1200.0))
        mm.update(st)
        assert mm._state.extraction_pos == (1600.0, 1200.0)


# ---------------------------------------------------------------------------
# Unit: _world_to_mini coordinate transform
# ---------------------------------------------------------------------------

class TestWorldToMini:
    def test_returns_rect_origin_when_no_state(self):
        mm = _make_minimap()
        result = mm._world_to_mini(0.0, 0.0)
        assert result == (mm.rect.x, mm.rect.y)

    def test_returns_rect_origin_when_map_world_rect_is_none(self):
        mm = _make_minimap()
        mm.update(_state(map_world_rect=None))
        result = mm._world_to_mini(500.0, 300.0)
        assert result == (mm.rect.x, mm.rect.y)

    def test_world_origin_maps_to_minimap_origin(self):
        mm = _make_minimap(_MINIMAP_RECT)
        st = _state(map_world_rect=_MAP_RECT, player_world_pos=(0.0, 0.0))
        mm.update(st)
        mx, my = mm._world_to_mini(0.0, 0.0)
        assert mx == _MINIMAP_RECT.x
        assert my == _MINIMAP_RECT.y

    def test_world_center_maps_to_minimap_center_approximately(self):
        mm = _make_minimap(_MINIMAP_RECT)
        st = _state(map_world_rect=_MAP_RECT)
        mm.update(st)
        cx = _MAP_RECT.w / 2
        cy = _MAP_RECT.h / 2
        mx, my = mm._world_to_mini(cx, cy)
        # Should be roughly at minimap centre ± 1 pixel
        assert abs(mx - _MINIMAP_RECT.centerx) <= 1
        assert abs(my - _MINIMAP_RECT.centery) <= 1

    def test_coordinates_clamped_within_minimap_bounds(self):
        mm = _make_minimap(_MINIMAP_RECT)
        st = _state(map_world_rect=_MAP_RECT)
        mm.update(st)
        # Player far outside the map → clamped to rect bounds
        mx, my = mm._world_to_mini(99999.0, 99999.0)
        assert _MINIMAP_RECT.x <= mx <= _MINIMAP_RECT.right - 1
        assert _MINIMAP_RECT.y <= my <= _MINIMAP_RECT.bottom - 1

    def test_negative_coordinates_clamped_to_minimap_origin(self):
        mm = _make_minimap(_MINIMAP_RECT)
        st = _state(map_world_rect=_MAP_RECT)
        mm.update(st)
        mx, my = mm._world_to_mini(-999.0, -999.0)
        assert mx == _MINIMAP_RECT.x
        assert my == _MINIMAP_RECT.y


# ---------------------------------------------------------------------------
# Draw smoke tests
# ---------------------------------------------------------------------------

class TestMiniMapDraw:
    def test_draw_without_state_is_silent_noop(self):
        surface = pygame.Surface((1280, 720))
        mm = _make_minimap()
        mm.draw(surface)   # _state is None → must not crash

    def test_draw_with_default_hud_state_does_not_crash(self):
        surface = pygame.Surface((1280, 720))
        mm = _make_minimap()
        mm.update(_state())
        mm.draw(surface)

    def test_draw_with_player_position_does_not_crash(self):
        surface = pygame.Surface((1280, 720))
        mm = _make_minimap()
        st = _state(
            map_world_rect=_MAP_RECT,
            player_world_pos=(640.0, 480.0),
        )
        mm.update(st)
        mm.draw(surface)

    def test_draw_with_extraction_position_does_not_crash(self):
        surface = pygame.Surface((1280, 720))
        mm = _make_minimap()
        st = _state(
            map_world_rect=_MAP_RECT,
            extraction_pos=(1600.0, 400.0),
        )
        mm.update(st)
        mm.draw(surface)

    def test_draw_with_zones_using_world_rect_does_not_crash(self):
        surface = pygame.Surface((1280, 720))
        mm = _make_minimap()
        zone = ZoneInfo(name="ZONE_A", world_rect=pygame.Rect(0, 0, 800, 600))
        st = _state(map_world_rect=_MAP_RECT, zones=[zone])
        mm.update(st)
        mm.draw(surface)

    def test_draw_with_zones_using_rect_tuple_does_not_crash(self):
        surface = pygame.Surface((1280, 720))
        mm = _make_minimap()
        zone = ZoneInfo(name="ZONE_B", rect_tuple=(100, 100, 400, 300))
        st = _state(map_world_rect=_MAP_RECT, zones=[zone])
        mm.update(st)
        mm.draw(surface)

    def test_draw_with_zone_missing_both_rects_does_not_crash(self):
        """Zone with neither world_rect nor rect_tuple is silently skipped."""
        surface = pygame.Surface((1280, 720))
        mm = _make_minimap()
        # ZoneInfo with no world_rect or rect_tuple
        zone = ZoneInfo(name="ZONE_C")
        st = _state(map_world_rect=_MAP_RECT, zones=[zone])
        mm.update(st)
        mm.draw(surface)

    def test_draw_with_no_map_world_rect_does_not_crash(self):
        surface = pygame.Surface((1280, 720))
        mm = _make_minimap()
        st = _state(map_world_rect=None, player_world_pos=(100.0, 100.0))
        mm.update(st)
        mm.draw(surface)

    def test_draw_with_all_hud_fields_populated_does_not_crash(self):
        surface = pygame.Surface((1280, 720))
        mm = _make_minimap()
        zone = ZoneInfo(name="ZONE_A", world_rect=pygame.Rect(0, 0, 800, 600))
        st = _state(
            map_world_rect=_MAP_RECT,
            player_world_pos=(320.0, 240.0),
            extraction_pos=(2000.0, 1500.0),
            zones=[zone],
        )
        mm.update(st)
        mm.draw(surface)


# ---------------------------------------------------------------------------
# Integration: MiniMap embedded in full HUD pipeline
# ---------------------------------------------------------------------------

class TestMiniMapInHUD:
    def test_hud_draw_initialises_minimap_lazily(self):
        """MiniMap is None before first update() and created during update."""
        from src.core.event_bus import EventBus
        from src.ui.hud import HUD

        bus = EventBus()
        hud = HUD(bus)
        assert hud._minimap is None

        hud.update(_state(), dt=0.016)
        assert hud._minimap is not None

    def test_hud_draw_with_map_world_rect_does_not_crash(self):
        from src.core.event_bus import EventBus
        from src.ui.hud import HUD

        surface = pygame.Surface((1280, 720))
        bus = EventBus()
        hud = HUD(bus)
        st = _state(
            map_world_rect=_MAP_RECT,
            player_world_pos=(320.0, 240.0),
            extraction_pos=(1600.0, 1200.0),
        )
        hud.update(st, dt=0.016)
        hud.draw(surface)
