"""Integration tests for src/core/game.py — GameApp initialisation and loop.

Tests are organised into three groups:

  TestGameAppInit      — constructor sets up state correctly; no run() call.
  TestGameAppShutdown  — _shutdown() releases resources and empties the stack.
  TestGameAppLoop      — run() terminates correctly for each exit path.

Exit paths exercised:
  1. Active scene's ``should_quit`` property returns True.
  2. A pygame.QUIT event is in the event queue.
  3. The scene stack is empty when the loop starts (active is None).

Each loop test must return in O(1) iterations (~16 ms due to clock.tick).

SDL_VIDEODRIVER=dummy + SDL_AUDIODRIVER=dummy keep the suite headless.
GameApp.__init__ calls pygame.init() internally, so the module-level setup
only needs the environment variables.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Must be set BEFORE any pygame import or GameApp import so SDL picks them up.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from src.core.game import GameApp          # noqa: E402
from src.scenes.main_menu import MainMenu  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fresh_app() -> GameApp:
    """Return a fully-initialised GameApp ready for testing."""
    return GameApp()


# ── Initialisation ────────────────────────────────────────────────────────────

class TestGameAppInit:
    """Constructor must wire up all subsystems without raising."""

    def test_init_does_not_raise(self):
        app = _fresh_app()
        app._shutdown()

    def test_initial_active_scene_is_main_menu(self):
        app = _fresh_app()
        assert isinstance(app.scenes.active, MainMenu)
        app._shutdown()

    def test_scene_stack_depth_is_one_on_launch(self):
        app = _fresh_app()
        assert app.scenes.depth() == 1
        app._shutdown()

    def test_scene_request_listener_is_registered_on_bus(self):
        app = _fresh_app()
        # GameApp subscribes _on_scene_request to "scene_request".
        assert app.bus.listener_count("scene_request") >= 1
        app._shutdown()

    def test_settings_default_resolution_is_1280x720(self):
        app = _fresh_app()
        assert app.settings.resolution == (1280, 720)
        app._shutdown()

    def test_settings_default_fps_is_60(self):
        app = _fresh_app()
        assert app.settings.target_fps == 60
        app._shutdown()

    def test_screen_surface_size_matches_settings_resolution(self):
        app = _fresh_app()
        assert app.screen.get_size() == app.settings.resolution
        app._shutdown()

    def test_running_is_false_before_run_is_called(self):
        app = _fresh_app()
        assert app._running is False
        app._shutdown()

    def test_assets_attribute_is_not_none(self):
        app = _fresh_app()
        assert app.assets is not None
        app._shutdown()

    def test_bus_attribute_is_not_none(self):
        app = _fresh_app()
        assert app.bus is not None
        app._shutdown()

    def test_audio_ok_attribute_exists(self):
        app = _fresh_app()
        assert hasattr(app, "_audio_ok")
        app._shutdown()

    def test_clock_attribute_exists(self):
        app = _fresh_app()
        assert isinstance(app.clock, pygame.time.Clock)
        app._shutdown()


# ── Shutdown ──────────────────────────────────────────────────────────────────

class TestGameAppShutdown:
    def test_shutdown_clears_scene_stack(self):
        app = _fresh_app()
        assert not app.scenes.is_empty()
        app._shutdown()
        assert app.scenes.is_empty()

    def test_shutdown_on_already_empty_stack_does_not_raise(self):
        app = _fresh_app()
        app.scenes.clear()
        app._shutdown()  # must not raise even with nothing on the stack

    def test_shutdown_can_be_called_after_scenes_were_manually_cleared(self):
        app = _fresh_app()
        app.scenes.clear()
        # At this point stack is empty; _shutdown should still call pygame.quit()
        app._shutdown()
        assert app.scenes.is_empty()


# ── Main loop termination ─────────────────────────────────────────────────────

class TestGameAppLoop:
    """run() must return promptly for each legal exit condition."""

    def test_run_exits_when_active_scene_should_quit_is_true(self):
        """Simulates the user selecting 'Quit' from the main menu."""
        app = _fresh_app()
        # Flip the flag before entering the loop.
        app.scenes.active._quit = True  # type: ignore[union-attr]
        app.run()  # must return; _shutdown() is called internally

    def test_run_exits_on_pygame_quit_event(self):
        """Simulates the OS close-window signal."""
        app = _fresh_app()
        # Post the QUIT event before run() so it is picked up in iteration 1.
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        app.run()

    def test_run_exits_when_scene_stack_is_empty(self):
        """active is None → loop exits; mirrors an 'Exit to Desktop' transition."""
        app = _fresh_app()
        app.scenes.clear()  # evict all scenes; active becomes None
        app.run()

    def test_running_is_false_after_run_returns(self):
        app = _fresh_app()
        app.scenes.active._quit = True  # type: ignore[union-attr]
        app.run()
        # _running is set to False before _shutdown() is called.
        assert app._running is False

    def test_scene_stack_empty_after_run_returns(self):
        """_shutdown() must clear the stack regardless of the exit path."""
        app = _fresh_app()
        app.scenes.active._quit = True  # type: ignore[union-attr]
        app.run()
        assert app.scenes.is_empty()
