# Run: pytest tests/scenes/test_main_menu.py
"""Unit and integration tests for src/scenes/main_menu.py.

Unit tests (~60 %):
  * Initial state — should_quit=False, first item selected, 4-item menu
  * Keyboard navigation — UP / DOWN, wrapping, multi-press, unrelated keys
  * Activation via Enter and Space keys
  * ESC directly sets should_quit
  * "Exit" item sets should_quit without emitting a bus event
  * "Start Game" emits scene_request(scene="game") on the bus  (no-SM path)
  * "Home Base" emits scene_request(scene="home_base")          (no-SM path)
  * "Settings" emits scene_request(scene="settings")            (no-SM path)
  * Non-navigation / non-keydown events are silently ignored
  * update() and render() smoke tests across dt values and resolutions
  * All three constructor signatures accept the 4-item menu

Integration tests (~35 %):
  * With SceneManager: Start Game calls sm.replace(GameScene) — NOT sm.push
  * With SceneManager: Start Game does NOT fall back to the bus
  * With SceneManager: Settings calls sm.push(SettingsScreen) — NOT sm.replace
  * With SceneManager: Settings does NOT fall back to the bus
  * With SceneManager: Home Base calls sm.replace(HomeBaseScene) — NOT sm.push
  * With SceneManager: Home Base does NOT fall back to the bus
  * With SceneManager: Exit calls neither sm.replace nor sm.push
  * Keyboard-triggered activation honours the same SM routing
  * Scene lifecycle hooks (on_enter, on_exit, on_pause, on_resume) do not raise

SDL_VIDEODRIVER=dummy + SDL_AUDIODRIVER=dummy keep the suite headless.
A display surface is created so font rendering and blitting work correctly.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

import pytest

from src.core.asset_manager import AssetManager   # noqa: E402
from src.core.event_bus import EventBus           # noqa: E402
from src.core.scene_manager import SceneManager   # noqa: E402
from src.core.settings import Settings            # noqa: E402
from src.scenes.main_menu import MainMenu         # noqa: E402


# ── Module-level index constants (derived after import) ───────────────────────

_ITEM_COUNT    = len(MainMenu._MENU_ITEMS)
_IDX_START     = MainMenu._MENU_ITEMS.index("Start Game")
_IDX_HOME_BASE = MainMenu._MENU_ITEMS.index("Home Base")
_IDX_SETTS     = MainMenu._MENU_ITEMS.index("Settings")
_IDX_EXIT      = MainMenu._MENU_ITEMS.index("Exit")


# ── Shared helpers ────────────────────────────────────────────────────────────

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
    """Return a fresh (MainMenu, EventBus) pair backed by default Settings.

    Uses Style 1 constructor (no SceneManager) so bus-fallback logic is active.
    """
    settings = Settings()
    assets   = AssetManager()
    bus      = EventBus()
    menu     = MainMenu(settings, assets, bus)
    return menu, bus


# ══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — no SceneManager injected; bus-fallback path exercised
# ══════════════════════════════════════════════════════════════════════════════

# ── Initial state ─────────────────────────────────────────────────────────────

class TestMainMenuInitialState:
    def test_should_quit_is_false_on_creation(self):
        menu, _ = _make_menu()
        assert menu.should_quit is False

    def test_initial_selection_is_first_item(self):
        menu, _ = _make_menu()
        assert menu._selected == 0

    def test_menu_has_four_items(self):
        assert _ITEM_COUNT == 4

    def test_start_game_is_among_menu_items(self):
        assert "Start Game" in MainMenu._MENU_ITEMS

    def test_home_base_is_among_menu_items(self):
        assert "Home Base" in MainMenu._MENU_ITEMS

    def test_settings_is_among_menu_items(self):
        assert "Settings" in MainMenu._MENU_ITEMS

    def test_exit_is_among_menu_items(self):
        assert "Exit" in MainMenu._MENU_ITEMS

    def test_quit_is_not_a_menu_item(self):
        """Spec renames 'Quit' → 'Exit'; the old label must not linger."""
        assert "Quit" not in MainMenu._MENU_ITEMS

    def test_menu_items_are_in_expected_order(self):
        assert list(MainMenu._MENU_ITEMS) == ["Start Game", "Home Base", "Settings", "Exit"]


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

    def test_full_cycle_down_returns_to_start(self):
        self.menu._selected = 0
        for _ in range(_ITEM_COUNT):
            self.menu.handle_events([_keydown(pygame.K_DOWN)])
        assert self.menu._selected == 0

    def test_full_cycle_up_returns_to_start(self):
        self.menu._selected = 0
        for _ in range(_ITEM_COUNT):
            self.menu.handle_events([_keydown(pygame.K_UP)])
        assert self.menu._selected == 0

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

    def test_navigation_does_not_set_should_quit(self):
        self.menu.handle_events([_keydown(pygame.K_UP), _keydown(pygame.K_DOWN)])
        assert self.menu.should_quit is False


# ── Escape key / should_quit ───────────────────────────────────────────────────

class TestMainMenuQuit:
    def setup_method(self):
        self.menu, _ = _make_menu()

    def test_escape_key_sets_should_quit_true(self):
        self.menu.handle_events([_keydown(pygame.K_ESCAPE)])
        assert self.menu.should_quit is True

    def test_should_quit_property_reflects_internal_flag(self):
        assert self.menu.should_quit is self.menu._quit

    def test_exit_item_activate_sets_should_quit(self):
        self.menu._activate(_IDX_EXIT)
        assert self.menu.should_quit is True

    def test_enter_on_exit_item_sets_should_quit(self):
        self.menu._selected = _IDX_EXIT
        self.menu.handle_events([_keydown(pygame.K_RETURN)])
        assert self.menu.should_quit is True

    def test_space_on_exit_item_sets_should_quit(self):
        self.menu._selected = _IDX_EXIT
        self.menu.handle_events([_keydown(pygame.K_SPACE)])
        assert self.menu.should_quit is True

    def test_out_of_bounds_activate_does_not_raise(self):
        self.menu._activate(99)
        self.menu._activate(-1)
        assert self.menu.should_quit is False

    def test_activating_non_exit_item_does_not_set_should_quit(self):
        self.menu._activate(_IDX_START)
        assert self.menu.should_quit is False

    def test_activating_settings_does_not_set_should_quit(self):
        self.menu._activate(_IDX_SETTS)
        assert self.menu.should_quit is False


# ── EventBus emissions (no-SM / bus-fallback path) ────────────────────────────

class TestMainMenuBusEvents:
    def setup_method(self):
        self.menu, self.bus = _make_menu()
        self.received: List[dict] = []
        self.bus.subscribe("scene_request", lambda **kw: self.received.append(dict(kw)))

    def test_start_game_emits_game_scene_request(self):
        self.menu._activate(_IDX_START)
        assert len(self.received) == 1
        assert self.received[0]["scene"] == "game"

    def test_home_base_emits_home_base_scene_request(self):
        self.menu._activate(_IDX_HOME_BASE)
        assert len(self.received) == 1
        assert self.received[0]["scene"] == "home_base"

    def test_settings_emits_settings_scene_request(self):
        self.menu._activate(_IDX_SETTS)
        assert len(self.received) == 1
        assert self.received[0]["scene"] == "settings"

    def test_exit_does_not_emit_any_scene_request(self):
        self.menu._activate(_IDX_EXIT)
        assert len(self.received) == 0

    def test_start_game_via_enter_key_emits_event(self):
        self.menu._selected = _IDX_START
        self.menu.handle_events([_keydown(pygame.K_RETURN)])
        assert any(e.get("scene") == "game" for e in self.received)

    def test_start_game_via_space_key_emits_event(self):
        self.menu._selected = _IDX_START
        self.menu.handle_events([_keydown(pygame.K_SPACE)])
        assert any(e.get("scene") == "game" for e in self.received)

    def test_home_base_via_enter_key_emits_event(self):
        self.menu._selected = _IDX_HOME_BASE
        self.menu.handle_events([_keydown(pygame.K_RETURN)])
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

    def test_start_game_emits_game_not_home_base(self):
        """Regression: original implementation emitted 'home_base' for Start Game."""
        self.menu._activate(_IDX_START)
        assert self.received[0]["scene"] != "home_base"

    def test_home_base_emits_home_base_not_game(self):
        self.menu._activate(_IDX_HOME_BASE)
        assert self.received[0]["scene"] != "game"


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
        assert self.screen.get_at((0, 0)) != blank.get_at((0, 0))

    def test_render_with_each_selection_does_not_raise(self):
        for idx in range(_ITEM_COUNT):
            self.menu._selected = idx
            self.menu.render(self.screen)

    def test_render_at_each_supported_resolution(self):
        """render() must not raise at any supported resolution and must be non-blank."""
        for w, h in [(1280, 720), (1600, 900), (1920, 1080)]:
            surface = pygame.Surface((w, h))
            self.menu.render(surface)
            assert surface.get_at((0, 0)) != pygame.Surface((w, h)).get_at((0, 0))

    def test_update_then_render_does_not_raise(self):
        self.menu.update(1 / 60)
        self.menu.render(self.screen)


# ── Constructor styles ─────────────────────────────────────────────────────────

class TestMainMenuAllConstructors:
    """All three constructor call styles must produce a valid 4-item menu."""

    def _assert_valid(self, menu: MainMenu) -> None:
        assert len(menu._MENU_ITEMS) == 4
        assert menu.should_quit is False
        assert menu._selected == 0

    def test_style1_settings_assets_bus(self):
        settings = Settings()
        assets   = AssetManager()
        bus      = EventBus()
        menu = MainMenu(settings, assets, bus)
        self._assert_valid(menu)

    def test_style2_sm_settings_assets(self):
        """SceneManager-style (sm has push/pop/replace) without explicit bus."""
        sm = types.SimpleNamespace(
            push=lambda s: None,
            pop=lambda: None,
            replace=lambda s: None,
        )
        menu = MainMenu(sm, Settings(), AssetManager())
        self._assert_valid(menu)

    def test_style3_sm_settings_assets_bus(self):
        sm = types.SimpleNamespace(
            push=lambda s: None,
            pop=lambda: None,
            replace=lambda s: None,
        )
        bus = EventBus()
        menu = MainMenu(sm, Settings(), AssetManager(), bus)
        self._assert_valid(menu)

    def test_style1_stores_no_scene_manager(self):
        menu, _ = _make_menu()
        assert menu._sm is None

    def test_style2_stores_scene_manager(self):
        sm = types.SimpleNamespace(push=lambda s: None, replace=lambda s: None)
        menu = MainMenu(sm, Settings(), AssetManager())
        assert menu._sm is sm


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — SceneManager injected; replace/push routing verified
# ══════════════════════════════════════════════════════════════════════════════

class TestMainMenuSceneManagerIntegration:
    """When a real (mock) SceneManager is injected the menu must route via
    sm.replace() for peer transitions and sm.push() for overlay transitions —
    and must NOT fall back to the event bus.

    Spec requirements tested here:
      - Start Game  → sm.replace(GameScene)       [NOT push, NOT bus]
      - Settings    → sm.push(SettingsScreen)     [NOT replace, NOT bus]
      - Home Base   → sm.replace(HomeBaseScene)   [NOT push, NOT bus]
      - Exit        → sm unchanged; should_quit=True
    """

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.sm       = MagicMock(spec=SceneManager)
        self.settings = Settings()
        self.assets   = AssetManager()
        self.bus      = EventBus()

        # Track any scene_request events that should NOT be emitted via SM path
        self.bus_events: List[dict] = []
        self.bus.subscribe(
            "scene_request",
            lambda **kw: self.bus_events.append(dict(kw)),
        )

        self.menu = MainMenu(self.sm, self.settings, self.assets, self.bus)

    # -- Start Game → sm.replace(GameScene) -----------------------------------

    def test_start_game_with_sm_calls_replace_once(self):
        self.menu._activate(_IDX_START)
        self.sm.replace.assert_called_once()

    def test_start_game_with_sm_does_not_call_push(self):
        """replace, not push — Start Game is a peer transition, not an overlay."""
        self.menu._activate(_IDX_START)
        self.sm.push.assert_not_called()

    def test_start_game_with_sm_passes_game_scene_to_replace(self):
        from src.scenes.game_scene import GameScene
        self.menu._activate(_IDX_START)
        replaced = self.sm.replace.call_args[0][0]
        assert isinstance(replaced, GameScene)

    def test_start_game_with_sm_new_scene_shares_settings(self):
        self.menu._activate(_IDX_START)
        created = self.sm.replace.call_args[0][0]
        assert created._settings is self.settings

    def test_start_game_with_sm_new_scene_shares_scene_manager(self):
        self.menu._activate(_IDX_START)
        created = self.sm.replace.call_args[0][0]
        assert created._sm is self.sm

    def test_start_game_with_sm_does_not_emit_bus_event(self):
        """SM path must be silent on the bus — no redundant scene_request."""
        self.menu._activate(_IDX_START)
        assert len(self.bus_events) == 0

    # -- Settings → sm.push(SettingsScreen) -----------------------------------

    def test_settings_with_sm_calls_push_once(self):
        self.menu._activate(_IDX_SETTS)
        self.sm.push.assert_called_once()

    def test_settings_with_sm_does_not_call_replace(self):
        """Settings is an overlay — it must use push, never replace."""
        self.menu._activate(_IDX_SETTS)
        self.sm.replace.assert_not_called()

    def test_settings_with_sm_passes_settings_screen_to_push(self):
        from src.scenes.settings_screen import SettingsScreen
        self.menu._activate(_IDX_SETTS)
        pushed = self.sm.push.call_args[0][0]
        assert isinstance(pushed, SettingsScreen)

    def test_settings_screen_shares_same_settings(self):
        from src.scenes.settings_screen import SettingsScreen
        self.menu._activate(_IDX_SETTS)
        pushed = self.sm.push.call_args[0][0]
        assert isinstance(pushed, SettingsScreen)
        assert pushed._settings is self.settings

    def test_settings_with_sm_does_not_emit_bus_event(self):
        self.menu._activate(_IDX_SETTS)
        assert len(self.bus_events) == 0

    # -- Home Base → sm.replace(HomeBaseScene) --------------------------------

    def test_home_base_with_sm_calls_replace_once(self):
        """Home Base is a peer transition (replace), not an overlay (push)."""
        with patch("src.scenes.home_base_scene.HomeBaseScene") as MockHBS:
            MockHBS.return_value = MagicMock()
            self.menu._activate(_IDX_HOME_BASE)
        self.sm.replace.assert_called_once()

    def test_home_base_with_sm_does_not_call_push(self):
        with patch("src.scenes.home_base_scene.HomeBaseScene") as MockHBS:
            MockHBS.return_value = MagicMock()
            self.menu._activate(_IDX_HOME_BASE)
        self.sm.push.assert_not_called()

    def test_home_base_with_sm_passes_home_base_scene_to_replace(self):
        with patch("src.scenes.home_base_scene.HomeBaseScene") as MockHBS:
            instance = MagicMock()
            MockHBS.return_value = instance
            self.menu._activate(_IDX_HOME_BASE)
        replaced = self.sm.replace.call_args[0][0]
        assert replaced is instance

    def test_home_base_with_sm_does_not_emit_bus_event(self):
        with patch("src.scenes.home_base_scene.HomeBaseScene") as MockHBS:
            MockHBS.return_value = MagicMock()
            self.menu._activate(_IDX_HOME_BASE)
        assert len(self.bus_events) == 0

    # -- Exit → no SM calls, should_quit=True ---------------------------------

    def test_exit_with_sm_does_not_call_replace(self):
        self.menu._activate(_IDX_EXIT)
        self.sm.replace.assert_not_called()

    def test_exit_with_sm_does_not_call_push(self):
        self.menu._activate(_IDX_EXIT)
        self.sm.push.assert_not_called()

    def test_exit_with_sm_sets_should_quit(self):
        self.menu._activate(_IDX_EXIT)
        assert self.menu.should_quit is True

    def test_exit_with_sm_does_not_emit_bus_event(self):
        self.menu._activate(_IDX_EXIT)
        assert len(self.bus_events) == 0

    # -- Keyboard-triggered routing -------------------------------------------

    def test_start_game_via_enter_key_calls_sm_replace(self):
        self.menu._selected = _IDX_START
        self.menu.handle_events([_keydown(pygame.K_RETURN)])
        self.sm.replace.assert_called_once()

    def test_start_game_via_space_key_calls_sm_replace(self):
        self.menu._selected = _IDX_START
        self.menu.handle_events([_keydown(pygame.K_SPACE)])
        self.sm.replace.assert_called_once()

    def test_settings_via_enter_key_calls_sm_push(self):
        self.menu._selected = _IDX_SETTS
        self.menu.handle_events([_keydown(pygame.K_RETURN)])
        self.sm.push.assert_called_once()

    def test_navigation_keys_do_not_trigger_any_sm_call(self):
        self.menu.handle_events([_keydown(pygame.K_UP), _keydown(pygame.K_DOWN)])
        self.sm.replace.assert_not_called()
        self.sm.push.assert_not_called()

    def test_escape_key_with_sm_does_not_trigger_any_sm_call(self):
        """ESC quits the process — it must not pop or replace via the SM."""
        self.menu.handle_events([_keydown(pygame.K_ESCAPE)])
        self.sm.replace.assert_not_called()
        self.sm.push.assert_not_called()
        self.sm.pop.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — Scene lifecycle hooks
# ══════════════════════════════════════════════════════════════════════════════

class TestMainMenuLifecycleHooks:
    """BaseScene lifecycle hooks must not raise — SceneManager calls them
    during push / pop / replace operations."""

    def setup_method(self):
        self.menu, _ = _make_menu()

    def test_on_enter_does_not_raise(self):
        self.menu.on_enter()

    def test_on_exit_does_not_raise(self):
        self.menu.on_exit()

    def test_on_pause_does_not_raise(self):
        self.menu.on_pause()

    def test_on_resume_does_not_raise(self):
        self.menu.on_resume()

    def test_on_enter_does_not_change_should_quit(self):
        self.menu.on_enter()
        assert self.menu.should_quit is False

    def test_on_resume_after_settings_overlay_preserves_selection(self):
        """Selection must survive an overlay push/pop cycle."""
        self.menu._selected = _IDX_SETTS
        self.menu.on_pause()
        self.menu.on_resume()
        assert self.menu._selected == _IDX_SETTS
