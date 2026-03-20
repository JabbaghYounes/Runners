"""Behavioural tests for the pause-menu feature.

Covers:
- GameScene ESC → sm.push(PauseMenu)
- Double-ESC guard (second push is a no-op)
- PauseMenu ESC → sm.pop()
- RESUME button → sm.pop()
- RESTART → confirm dialog shown → confirmed → sm.replace_all(GameScene)
- RESTART → cancel → dialog hidden, no replace_all
- EXIT TO MENU → confirm → sm.replace_all(MainMenu)
- SETTINGS button → sm.push(SettingsScreen)
- update() is a no-op (nothing ticks)
- SceneManager.render() calls every scene in stack order (bottom → top)
"""
from __future__ import annotations

import pygame
import pytest
from unittest.mock import MagicMock, call

from src.core.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _key_event(key: int) -> pygame.event.Event:
    """Build a minimal KEYDOWN event for *key*."""
    return pygame.event.Event(pygame.KEYDOWN, {"key": key, "mod": 0, "unicode": "", "scancode": 0})


def _make_pause_menu(sm=None):
    """Return a fresh PauseMenu bound to a MagicMock scene manager."""
    from src.scenes.pause_menu import PauseMenu
    if sm is None:
        sm = MagicMock()
    return PauseMenu(sm, Settings(), None), sm


def _make_game_scene_stub(sm=None):
    """Return a stub GameScene (no full init) bound to a MagicMock sm."""
    from src.scenes.game_scene import GameScene
    if sm is None:
        sm = MagicMock()
        sm.active = None  # simulate no PauseMenu already on top
    scene = GameScene(sm=sm, settings=Settings())
    return scene, sm


# ---------------------------------------------------------------------------
# ESC in GameScene pushes PauseMenu
# ---------------------------------------------------------------------------

class TestGameScenePushPause:
    def test_esc_pushes_pause_menu(self):
        from src.scenes.pause_menu import PauseMenu
        scene, sm = _make_game_scene_stub()
        sm.active = None

        scene.handle_events([_key_event(pygame.K_ESCAPE)])

        sm.push.assert_called_once()
        pushed = sm.push.call_args[0][0]
        assert isinstance(pushed, PauseMenu)

    def test_double_esc_does_not_push_twice(self):
        """If the active scene is already a PauseMenu, a second ESC is ignored."""
        from src.scenes.pause_menu import PauseMenu
        scene, sm = _make_game_scene_stub()

        # Simulate that the first ESC already put a PauseMenu on top
        sm.active = PauseMenu(sm, Settings(), None)

        scene.handle_events([_key_event(pygame.K_ESCAPE)])

        # push must not be called a second time
        sm.push.assert_not_called()

    def test_esc_with_map_open_closes_map_not_pause(self):
        """When the map overlay is visible, ESC dismisses the map, not the pause menu."""
        scene, sm = _make_game_scene_stub()
        scene._map_overlay_visible = True

        scene.handle_events([_key_event(pygame.K_ESCAPE)])

        sm.push.assert_not_called()
        assert scene._map_overlay_visible is False


# ---------------------------------------------------------------------------
# PauseMenu — ESC resumes
# ---------------------------------------------------------------------------

class TestPauseMenuEsc:
    def test_esc_calls_pop(self):
        pm, sm = _make_pause_menu()
        pm.handle_events([_key_event(pygame.K_ESCAPE)])
        sm.pop.assert_called_once()

    def test_esc_while_confirm_active_does_not_pop(self):
        """ESC while a confirm dialog is up should be eaten by the dialog, not resume."""
        pm, sm = _make_pause_menu()
        pm._confirm_restart.show((1280, 720))

        pm.handle_events([_key_event(pygame.K_ESCAPE)])

        # pop() must not have been called — ESC went to the dialog
        sm.pop.assert_not_called()


# ---------------------------------------------------------------------------
# RESUME button
# ---------------------------------------------------------------------------

class TestResumeButton:
    def test_resume_button_calls_pop(self):
        pm, sm = _make_pause_menu()
        pm._on_resume()
        sm.pop.assert_called_once()


# ---------------------------------------------------------------------------
# SETTINGS button
# ---------------------------------------------------------------------------

class TestSettingsButton:
    def test_settings_button_pushes_settings_screen(self):
        from src.scenes.settings_screen import SettingsScreen
        pm, sm = _make_pause_menu()
        pm._on_settings()
        sm.push.assert_called_once()
        pushed = sm.push.call_args[0][0]
        assert isinstance(pushed, SettingsScreen)


# ---------------------------------------------------------------------------
# RESTART flow
# ---------------------------------------------------------------------------

class TestRestartFlow:
    def test_restart_shows_confirm_dialog(self):
        pm, sm = _make_pause_menu()
        assert not pm._confirm_restart.active

        pm._on_restart()

        assert pm._confirm_restart.active

    def test_restart_confirmed_calls_replace_all_with_game_scene(self):
        from src.scenes.game_scene import GameScene
        pm, sm = _make_pause_menu()
        pm._on_restart()

        pm._on_restart_confirmed()

        sm.replace_all.assert_called_once()
        arg = sm.replace_all.call_args[0][0]
        assert isinstance(arg, GameScene)

    def test_restart_confirmed_hides_dialog(self):
        pm, sm = _make_pause_menu()
        pm._on_restart()
        pm._on_restart_confirmed()
        assert not pm._confirm_restart.active

    def test_restart_cancel_hides_dialog_no_replace_all(self):
        pm, sm = _make_pause_menu()
        pm._on_restart()
        assert pm._confirm_restart.active

        # Simulate pressing cancel (calls the on_cancel lambda)
        pm._confirm_restart.hide()

        assert not pm._confirm_restart.active
        sm.replace_all.assert_not_called()


# ---------------------------------------------------------------------------
# EXIT TO MENU flow
# ---------------------------------------------------------------------------

class TestExitFlow:
    def test_exit_shows_confirm_dialog(self):
        pm, sm = _make_pause_menu()
        pm._on_exit()
        assert pm._confirm_exit.active

    def test_exit_confirmed_calls_replace_all_with_main_menu(self):
        from src.scenes.main_menu import MainMenu
        pm, sm = _make_pause_menu()
        pm._on_exit()

        pm._on_exit_confirmed()

        sm.replace_all.assert_called_once()
        arg = sm.replace_all.call_args[0][0]
        assert isinstance(arg, MainMenu)

    def test_exit_confirmed_hides_dialog(self):
        pm, sm = _make_pause_menu()
        pm._on_exit()
        pm._on_exit_confirmed()
        assert not pm._confirm_exit.active

    def test_exit_cancel_hides_dialog_no_replace_all(self):
        pm, sm = _make_pause_menu()
        pm._on_exit()
        pm._confirm_exit.hide()
        assert not pm._confirm_exit.active
        sm.replace_all.assert_not_called()


# ---------------------------------------------------------------------------
# Keyboard navigation
# ---------------------------------------------------------------------------

class TestKeyboardNavigation:
    def test_down_arrow_moves_focus_forward(self):
        pm, sm = _make_pause_menu()
        assert pm._focused_idx == 0  # RESUME selected by default

        pm.handle_events([_key_event(pygame.K_DOWN)])

        assert pm._focused_idx == 1  # SETTINGS

    def test_up_arrow_wraps_around(self):
        pm, sm = _make_pause_menu()
        # Focus wraps from 0 back to last index
        pm.handle_events([_key_event(pygame.K_UP)])

        assert pm._focused_idx == len(pm._nav_btns) - 1

    def test_enter_activates_focused_button(self):
        """Enter on the focused button triggers its callback."""
        pm, sm = _make_pause_menu()
        # Navigate to SETTINGS (index 1)
        pm._focused_idx = 1

        pm.handle_events([_key_event(pygame.K_RETURN)])

        sm.push.assert_called_once()

    def test_space_activates_resume(self):
        pm, sm = _make_pause_menu()
        pm._focused_idx = 0  # RESUME

        pm.handle_events([_key_event(pygame.K_SPACE)])

        sm.pop.assert_called_once()

    def test_nav_blocked_while_confirm_active(self):
        """Arrow keys must not change focus while a confirm dialog is visible."""
        pm, sm = _make_pause_menu()
        pm._focused_idx = 0
        pm._confirm_restart.show((1280, 720))

        pm.handle_events([_key_event(pygame.K_DOWN)])

        # focused_idx unchanged because the dialog ate the event
        assert pm._focused_idx == 0


# ---------------------------------------------------------------------------
# update() is a no-op
# ---------------------------------------------------------------------------

class TestUpdateNoop:
    def test_update_does_not_change_focused_idx(self):
        pm, _ = _make_pause_menu()
        original_idx = pm._focused_idx
        for _ in range(1000):
            pm.update(1 / 60)
        assert pm._focused_idx == original_idx

    def test_update_does_not_activate_dialogs(self):
        pm, _ = _make_pause_menu()
        for _ in range(1000):
            pm.update(1 / 60)
        assert not pm._confirm_restart.active
        assert not pm._confirm_exit.active


# ---------------------------------------------------------------------------
# SceneManager renders full stack in order
# ---------------------------------------------------------------------------

class TestSceneManagerRenderStack:
    def test_renders_all_scenes_bottom_to_top(self):
        from src.core.scene_manager import SceneManager

        sm = SceneManager()
        screen = MagicMock()

        scene_a = MagicMock()
        scene_b = MagicMock()

        render_order: list = []
        scene_a.render.side_effect = lambda s: render_order.append("a")
        scene_b.render.side_effect = lambda s: render_order.append("b")

        sm._stack = [scene_a, scene_b]
        sm.render(screen)

        assert render_order == ["a", "b"]

    def test_render_called_with_same_screen(self):
        from src.core.scene_manager import SceneManager

        sm = SceneManager()
        screen = MagicMock()

        scene_a = MagicMock()
        scene_b = MagicMock()
        sm._stack = [scene_a, scene_b]

        sm.render(screen)

        scene_a.render.assert_called_once_with(screen)
        scene_b.render.assert_called_once_with(screen)

    def test_empty_stack_render_is_noop(self):
        from src.core.scene_manager import SceneManager

        sm = SceneManager()
        screen = MagicMock()
        sm.render(screen)  # should not raise


# ---------------------------------------------------------------------------
# RoundTimer wired into GameScene
# ---------------------------------------------------------------------------

class TestRoundTimerWiring:
    def test_round_timer_created_in_stub_mode(self):
        """Stub mode sets _round_timer to None (no tick needed without full map)."""
        from src.scenes.game_scene import GameScene
        scene = GameScene(settings=Settings())
        assert scene._round_timer is None

    def test_on_enter_starts_timer_when_present(self):
        """on_enter() calls start() on a non-None timer."""
        from src.scenes.game_scene import GameScene
        scene = GameScene(settings=Settings())
        mock_timer = MagicMock()
        scene._round_timer = mock_timer

        scene.on_enter()

        mock_timer.start.assert_called_once()

    def test_on_enter_safe_without_timer_attr(self):
        """on_enter() must not raise when _round_timer is absent (stub safety)."""
        from src.scenes.game_scene import GameScene
        scene = GameScene(settings=Settings())
        if hasattr(scene, '_round_timer'):
            del scene._round_timer

        scene.on_enter()  # must not raise AttributeError


# ---------------------------------------------------------------------------
# W / S key navigation (alternatives to UP / DOWN arrows)
# ---------------------------------------------------------------------------

class TestWSKeyNavigation:
    def test_s_key_moves_focus_down(self):
        pm, _ = _make_pause_menu()
        assert pm._focused_idx == 0  # RESUME is pre-selected
        pm.handle_events([_key_event(pygame.K_s)])
        assert pm._focused_idx == 1  # SETTINGS

    def test_w_key_moves_focus_up(self):
        pm, _ = _make_pause_menu()
        pm._focused_idx = 2  # RESTART
        pm.handle_events([_key_event(pygame.K_w)])
        assert pm._focused_idx == 1  # SETTINGS

    def test_s_key_wraps_from_last_to_first(self):
        pm, _ = _make_pause_menu()
        pm._focused_idx = len(pm._nav_btns) - 1
        pm.handle_events([_key_event(pygame.K_s)])
        assert pm._focused_idx == 0

    def test_w_key_wraps_from_first_to_last(self):
        pm, _ = _make_pause_menu()
        pm._focused_idx = 0
        pm.handle_events([_key_event(pygame.K_w)])
        assert pm._focused_idx == len(pm._nav_btns) - 1

    def test_s_nav_blocked_while_confirm_active(self):
        """S key must not shift focus while a confirm dialog is open."""
        pm, _ = _make_pause_menu()
        pm._focused_idx = 0
        pm._confirm_restart.show((1280, 720))
        pm.handle_events([_key_event(pygame.K_s)])
        assert pm._focused_idx == 0


# ---------------------------------------------------------------------------
# KP_ENTER activates the focused button
# ---------------------------------------------------------------------------

class TestKpEnterActivation:
    def test_kp_enter_activates_resume(self):
        pm, sm = _make_pause_menu()
        pm._focused_idx = 0  # RESUME
        pm.handle_events([_key_event(pygame.K_KP_ENTER)])
        sm.pop.assert_called_once()

    def test_kp_enter_activates_settings(self):
        from src.scenes.settings_screen import SettingsScreen
        pm, sm = _make_pause_menu()
        pm._focused_idx = 1  # SETTINGS
        pm.handle_events([_key_event(pygame.K_KP_ENTER)])
        sm.push.assert_called_once()
        assert isinstance(sm.push.call_args[0][0], SettingsScreen)


# ---------------------------------------------------------------------------
# PauseMenu lifecycle hooks (inherited BaseScene no-ops)
# ---------------------------------------------------------------------------

class TestPauseMenuLifecycleHooks:
    def test_on_enter_does_not_raise(self):
        pm, _ = _make_pause_menu()
        pm.on_enter()

    def test_on_exit_does_not_raise(self):
        pm, _ = _make_pause_menu()
        pm.on_exit()

    def test_on_pause_does_not_raise(self):
        pm, _ = _make_pause_menu()
        pm.on_pause()

    def test_on_resume_does_not_raise(self):
        pm, _ = _make_pause_menu()
        pm.on_resume()


# ---------------------------------------------------------------------------
# Scene stack lifecycle — integration with a real SceneManager
# ---------------------------------------------------------------------------

class TestSceneStackLifecycle:
    """Verify that push/pop/replace_all trigger the correct lifecycle hooks
    on the scenes involved, using a real SceneManager and mock scenes."""

    def _sm_with_two_scenes(self):
        """Return (sm, game_mock, pause_mock) with game on bottom, pause on top."""
        from src.core.scene_manager import SceneManager
        from src.scenes.base_scene import BaseScene
        sm = SceneManager()
        game = MagicMock(spec=BaseScene)
        pause = MagicMock(spec=BaseScene)
        sm.push(game)
        sm.push(pause)
        return sm, game, pause

    def test_pushing_pause_menu_calls_game_scene_on_pause(self):
        from src.core.scene_manager import SceneManager
        from src.scenes.base_scene import BaseScene
        sm = SceneManager()
        game = MagicMock(spec=BaseScene)
        pause = MagicMock(spec=BaseScene)

        sm.push(game)
        sm.push(pause)

        game.on_pause.assert_called_once()
        pause.on_enter.assert_called_once()

    def test_popping_pause_menu_resumes_game_scene(self):
        sm, game, pause = self._sm_with_two_scenes()
        sm.pop()

        pause.on_exit.assert_called_once()
        game.on_resume.assert_called_once()

    def test_update_does_not_tick_game_scene_while_pause_menu_is_on_top(self):
        """SceneManager.update routes exclusively to the top scene; the game scene
        below is frozen and must not receive any update calls."""
        sm, game, pause = self._sm_with_two_scenes()

        sm.update(1 / 60)

        pause.update.assert_called_once_with(1 / 60)
        game.update.assert_not_called()

    def test_render_calls_both_scenes_bottom_to_top(self):
        """SceneManager.render must call GameScene.render then PauseMenu.render
        so the vignette is drawn on top of the frozen game world."""
        from src.core.scene_manager import SceneManager
        from src.scenes.base_scene import BaseScene
        sm = SceneManager()
        game = MagicMock(spec=BaseScene)
        pause = MagicMock(spec=BaseScene)
        order: list = []
        game.render.side_effect = lambda s: order.append("game")
        pause.render.side_effect = lambda s: order.append("pause")

        sm.push(game)
        sm.push(pause)
        sm.render(MagicMock())

        assert order == ["game", "pause"]

    def test_replace_all_on_restart_clears_entire_stack_and_enters_fresh_scene(self):
        """replace_all must call on_exit on every scene currently on the stack
        (both PauseMenu and the original GameScene) before entering the new scene."""
        sm, game, pause = self._sm_with_two_scenes()
        fresh = MagicMock()

        sm.replace_all(fresh)

        pause.on_exit.assert_called_once()
        game.on_exit.assert_called_once()
        fresh.on_enter.assert_called_once()
        assert sm.depth() == 1
        assert sm.active is fresh


# ---------------------------------------------------------------------------
# GameScene event-bus cleanup on exit
# ---------------------------------------------------------------------------

class TestGameSceneEventCleanup:
    def test_on_exit_unsubscribes_three_handlers_when_full_init(self):
        """on_exit() must unsubscribe enemy_killed, extraction_success, and
        extraction_failed when the scene was fully initialised."""
        from src.scenes.game_scene import GameScene

        scene = GameScene(settings=Settings())  # stub mode (no map)
        mock_bus = MagicMock()
        scene._event_bus = mock_bus
        scene._full_init = True  # pretend full init ran

        scene.on_exit()

        assert mock_bus.unsubscribe.call_count == 3
        unsubscribed_events = {c[0][0] for c in mock_bus.unsubscribe.call_args_list}
        assert unsubscribed_events == {
            "enemy_killed",
            "extraction_success",
            "extraction_failed",
        }

    def test_on_exit_does_not_unsubscribe_in_stub_mode(self):
        """In stub mode (_full_init=False) there are no subscriptions to clean up,
        so unsubscribe must never be called."""
        from src.scenes.game_scene import GameScene

        scene = GameScene(settings=Settings())  # _full_init stays False
        mock_bus = MagicMock()
        scene._event_bus = mock_bus

        scene.on_exit()

        mock_bus.unsubscribe.assert_not_called()

    def test_handlers_no_longer_fire_after_on_exit(self):
        """After on_exit() the real event bus must not invoke the GameScene
        handlers — verify with an actual EventBus instance."""
        from src.core.event_bus import EventBus
        from src.scenes.game_scene import GameScene

        bus = EventBus()
        scene = GameScene(settings=Settings())
        scene._event_bus = bus
        scene._full_init = True
        # Register the three handlers the same way _init_full does
        bus.subscribe("enemy_killed", scene._on_enemy_killed)
        bus.subscribe("extraction_success", scene._on_extract)
        bus.subscribe("extraction_failed", scene._on_extract_failed)

        scene.on_exit()

        # After cleanup none of the GameScene handlers remain
        assert bus.listener_count("enemy_killed") == 0
        assert bus.listener_count("extraction_success") == 0
        assert bus.listener_count("extraction_failed") == 0


# ---------------------------------------------------------------------------
# Round timer ticked by _update_full (when not paused)
# ---------------------------------------------------------------------------

class TestGameSceneRoundTimerUpdate:
    def _scene_with_mock_timer(self):
        """Return a stub GameScene with _full_init=True and a mock timer."""
        from src.scenes.game_scene import GameScene

        scene = GameScene(settings=Settings())  # stub: _full_init=False
        mock_timer = MagicMock()
        scene._round_timer = mock_timer
        # Override to full-init path so _update_full is exercised
        scene._full_init = True
        # Neutralise optional systems to keep the test fast and isolated
        scene._physics = None
        scene._combat = None
        scene._ai = None
        scene._loot_sys = None
        scene._extraction = None
        scene._buff = None
        scene._hud = None
        scene._audio = None
        scene.projectiles = []
        scene.loot_items = []
        scene.enemies = []
        scene._zones = []  # skip zone-detection loop
        return scene, mock_timer

    def test_update_full_ticks_round_timer_each_frame(self):
        """_update_full must call round_timer.update(dt) once per frame."""
        scene, mock_timer = self._scene_with_mock_timer()

        scene._update_full(1 / 60)

        mock_timer.update.assert_called_once_with(1 / 60)

    def test_update_full_ticks_timer_multiple_frames(self):
        """Each call to _update_full must forward its dt to the timer."""
        scene, mock_timer = self._scene_with_mock_timer()

        for _ in range(5):
            scene._update_full(1 / 60)

        assert mock_timer.update.call_count == 5

    def test_timer_not_ticked_in_stub_mode(self):
        """In stub mode (_full_init=False) _update_stub runs instead; the timer
        must never be called because it is None and the stub path skips it."""
        from src.scenes.game_scene import GameScene

        scene = GameScene(settings=Settings())
        assert scene._round_timer is None  # stub never creates a timer

        # Calling update() in stub mode must not raise
        scene.update(1 / 60)

    def test_timer_frozen_when_pause_menu_is_on_stack(self):
        """SceneManager.update routes only to the top scene; with PauseMenu on top
        GameScene.update is never called, so the timer cannot advance."""
        from src.core.scene_manager import SceneManager
        from src.scenes.base_scene import BaseScene

        sm = SceneManager()
        game = MagicMock(spec=BaseScene)
        pause = MagicMock(spec=BaseScene)

        sm.push(game)
        sm.push(pause)
        sm.update(1 / 60)

        # The game scene — and therefore its timer — never received an update
        game.update.assert_not_called()


# ---------------------------------------------------------------------------
# SETTINGS button forwards correct sm / settings / assets to SettingsScreen
# ---------------------------------------------------------------------------

class TestSettingsButtonArgForwarding:
    def test_settings_screen_receives_same_settings_object(self):
        """The SettingsScreen pushed by SETTINGS must reference the same Settings
        instance that PauseMenu was given — not a freshly constructed copy."""
        from src.scenes.settings_screen import SettingsScreen

        custom_settings = Settings()
        sm = MagicMock()
        pm = __import__("src.scenes.pause_menu", fromlist=["PauseMenu"]).PauseMenu(
            sm, custom_settings, None
        )

        pm._on_settings()

        pushed = sm.push.call_args[0][0]
        assert isinstance(pushed, SettingsScreen)
        assert pushed._settings is custom_settings

    def test_settings_screen_receives_same_scene_manager(self):
        """The SettingsScreen pushed by SETTINGS must reference the same
        SceneManager so that it can pop itself when the user closes it."""
        from src.scenes.settings_screen import SettingsScreen
        from src.scenes.pause_menu import PauseMenu

        sm = MagicMock()
        pm = PauseMenu(sm, Settings(), None)

        pm._on_settings()

        pushed = sm.push.call_args[0][0]
        assert isinstance(pushed, SettingsScreen)
        assert pushed._sm is sm
