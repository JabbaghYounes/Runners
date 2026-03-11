"""Unit tests for src/scenes/main_menu.py.

Covers:
  * Initial state (should_quit=False, first item selected)
  * Keyboard navigation — UP / DOWN, wrapping at both ends
  * Activation via Enter and Space keys
  * ESC directly sets should_quit
  * "Quit" item sets should_quit without emitting a bus event
  * "Start Game" emits scene_request(scene="home_base") on the bus
  * "Settings" emits scene_request(scene="settings") on the bus
  * Non-navigation / non-keydown events are silently ignored
  * update() and render() do not raise for any reasonable input

SDL_VIDEODRIVER=dummy + SDL_AUDIODRIVER=dummy keep the suite headless.
A display surface is created so font rendering and blitting work correctly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from src.core.asset_manager import AssetManager  # noqa: E402
from src.core.event_bus import EventBus          # noqa: E402
from src.core.settings import Settings           # noqa: E402
from src.scenes.main_menu import MainMenu        # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _keydown(key: int) -> pygame.event.Event:
    """Build a minimal KEYDOWN event for the given key constant."""
    return pygame.event.Event(
        pygame.KEYDOWN,
        key=key,
        mod=0,
        unicode="",
        scancode=0,
    )


def _make_menu() -> tuple[MainMenu, EventBus]:
    """Return a fresh (MainMenu, EventBus) pair backed by default Settings."""
    settings = Settings()
    assets   = AssetManager()
    bus      = EventBus()
    menu     = MainMenu(settings, assets, bus)
    return menu, bus


_ITEM_COUNT = len(MainMenu._MENU_ITEMS)
_IDX_START  = MainMenu._MENU_ITEMS.index("Start Game")
_IDX_SETTS  = MainMenu._MENU_ITEMS.index("Settings")
_IDX_QUIT   = MainMenu._MENU_ITEMS.index("Quit")


# ── Initial state ─────────────────────────────────────────────────────────────

class TestMainMenuInitialState:
    def test_should_quit_is_false_on_creation(self):
        menu, _ = _make_menu()
        assert menu.should_quit is False

    def test_initial_selection_is_first_item(self):
        menu, _ = _make_menu()
        assert menu._selected == 0

    def test_menu_has_three_items(self):
        assert _ITEM_COUNT == 3

    def test_start_game_is_among_menu_items(self):
        assert "Start Game" in MainMenu._MENU_ITEMS

    def test_settings_is_among_menu_items(self):
        assert "Settings" in MainMenu._MENU_ITEMS

    def test_quit_is_among_menu_items(self):
        assert "Quit" in MainMenu._MENU_ITEMS


# ── Keyboard navigation ───────────────────────────────────────────────────────

class TestMainMenuNavigation:
    def setup_method(self):
        self.menu, _ = _make_menu()

    def test_down_key_advances_selection_by_one(self):
        self.menu._selected = 0
        self.menu.handle_events([_keydown(pygame.K_DOWN)])
        assert self.menu._selected == 1

    def test_up_key_retreats_selection_by_one(self):
        self.menu._selected = 1
        self.menu.handle_events([_keydown(pygame.K_UP)])
        assert self.menu._selected == 0

    def test_down_wraps_from_last_item_to_first(self):
        self.menu._selected = _ITEM_COUNT - 1
        self.menu.handle_events([_keydown(pygame.K_DOWN)])
        assert self.menu._selected == 0

    def test_up_wraps_from_first_item_to_last(self):
        self.menu._selected = 0
        self.menu.handle_events([_keydown(pygame.K_UP)])
        assert self.menu._selected == _ITEM_COUNT - 1

    def test_two_down_presses_advance_two_positions(self):
        self.menu._selected = 0
        self.menu.handle_events([_keydown(pygame.K_DOWN), _keydown(pygame.K_DOWN)])
        assert self.menu._selected == 2

    def test_unrelated_key_does_not_change_selection(self):
        self.menu._selected = 1
        self.menu.handle_events([_keydown(pygame.K_a)])
        assert self.menu._selected == 1

    def test_non_keydown_event_does_not_change_selection(self):
        self.menu._selected = 0
        mouse_event = pygame.event.Event(
            pygame.MOUSEMOTION,
            pos=(640, 360),
            rel=(0, 0),
            buttons=(0, 0, 0),
        )
        self.menu.handle_events([mouse_event])
        assert self.menu._selected == 0

    def test_empty_event_list_does_not_change_selection(self):
        self.menu._selected = 1
        self.menu.handle_events([])
        assert self.menu._selected == 1


# ── Escape key / should_quit ───────────────────────────────────────────────────

class TestMainMenuQuit:
    def setup_method(self):
        self.menu, _ = _make_menu()

    def test_escape_key_sets_should_quit_true(self):
        self.menu.handle_events([_keydown(pygame.K_ESCAPE)])
        assert self.menu.should_quit is True

    def test_should_quit_property_reflects_internal_flag(self):
        assert self.menu.should_quit is self.menu._quit

    def test_quit_item_activate_sets_should_quit(self):
        self.menu._selected = _IDX_QUIT
        self.menu._activate(_IDX_QUIT)
        assert self.menu.should_quit is True

    def test_enter_on_quit_item_sets_should_quit(self):
        self.menu._selected = _IDX_QUIT
        self.menu.handle_events([_keydown(pygame.K_RETURN)])
        assert self.menu.should_quit is True

    def test_space_on_quit_item_sets_should_quit(self):
        self.menu._selected = _IDX_QUIT
        self.menu.handle_events([_keydown(pygame.K_SPACE)])
        assert self.menu.should_quit is True


# ── EventBus emissions ────────────────────────────────────────────────────────

class TestMainMenuBusEvents:
    def setup_method(self):
        self.menu, self.bus = _make_menu()
        self.received: List[dict] = []
        self.bus.subscribe("scene_request", lambda **kw: self.received.append(dict(kw)))

    def test_start_game_emits_home_base_scene_request(self):
        self.menu._activate(_IDX_START)
        assert len(self.received) == 1
        assert self.received[0]["scene"] == "home_base"

    def test_settings_emits_settings_scene_request(self):
        self.menu._activate(_IDX_SETTS)
        assert len(self.received) == 1
        assert self.received[0]["scene"] == "settings"

    def test_quit_does_not_emit_any_scene_request(self):
        self.menu._activate(_IDX_QUIT)
        assert len(self.received) == 0

    def test_start_game_via_enter_key_emits_event(self):
        self.menu._selected = _IDX_START
        self.menu.handle_events([_keydown(pygame.K_RETURN)])
        assert any(e.get("scene") == "home_base" for e in self.received)

    def test_start_game_via_space_key_emits_event(self):
        self.menu._selected = _IDX_START
        self.menu.handle_events([_keydown(pygame.K_SPACE)])
        assert any(e.get("scene") == "home_base" for e in self.received)

    def test_settings_via_enter_key_emits_event(self):
        self.menu._selected = _IDX_SETTS
        self.menu.handle_events([_keydown(pygame.K_RETURN)])
        assert any(e.get("scene") == "settings" for e in self.received)

    def test_escape_does_not_emit_scene_request(self):
        self.menu.handle_events([_keydown(pygame.K_ESCAPE)])
        assert len(self.received) == 0

    def test_navigation_keys_do_not_emit_scene_request(self):
        self.menu.handle_events([_keydown(pygame.K_UP), _keydown(pygame.K_DOWN)])
        assert len(self.received) == 0

    def test_each_activate_emits_exactly_one_event(self):
        self.menu._activate(_IDX_START)
        assert len(self.received) == 1
        self.menu._activate(_IDX_START)
        assert len(self.received) == 2


# ── update / render ───────────────────────────────────────────────────────────

class TestMainMenuUpdateRender:
    def setup_method(self):
        self.menu, _ = _make_menu()
        self.screen  = pygame.Surface((1280, 720))

    def test_update_with_fixed_timestep_does_not_raise(self):
        self.menu.update(1 / 60)

    def test_update_with_zero_dt_does_not_raise(self):
        self.menu.update(0.0)

    def test_update_with_large_dt_does_not_raise(self):
        self.menu.update(1.0)

    def test_render_does_not_raise(self):
        self.menu.render(self.screen)

    def test_render_modifies_the_surface(self):
        """After render the surface must not be uniformly empty (all zeros)."""
        blank = pygame.Surface((1280, 720))
        self.menu.render(self.screen)
        # At minimum the background fill must differ from a blank (zeroed) surface
        assert self.screen.get_at((0, 0)) != blank.get_at((0, 0))

    def test_render_with_each_selection_does_not_raise(self):
        for idx in range(_ITEM_COUNT):
            self.menu._selected = idx
            self.menu.render(self.screen)
