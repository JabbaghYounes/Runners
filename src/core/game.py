"""GameApp — Pygame initialisation, shared singletons, and the main loop."""
from __future__ import annotations

import sys

import pygame

from src.constants import FPS, SCREEN_H, SCREEN_W, _init_key_bindings
from src.core.asset_manager import AssetManager
from src.core.event_bus import EventBus
from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.scenes.main_menu import MainMenu


class GameApp:
    """Top-level application object.

    Responsibilities:
        - Initialise Pygame and the audio mixer.
        - Load / own all application-lifetime singletons (Settings, AssetManager,
          EventBus, SceneManager).
        - Push the initial scene (MainMenu).
        - Run the fixed-timestep game loop.

    Usage::

        app = GameApp()
        app.run()
    """

    def __init__(self) -> None:
        pygame.init()
        _init_key_bindings()  # Populate KEY_BINDINGS now that pygame is ready

        # Optional audio mixer — fail gracefully if unavailable
        try:
            pygame.mixer.init()
        except pygame.error:
            pass

        # ------------------------------------------------------------------
        # Settings — load before creating the window so the resolution is known
        # ------------------------------------------------------------------
        self._settings = Settings.load("settings.json")

        # ------------------------------------------------------------------
        # Display
        # ------------------------------------------------------------------
        res = self._settings.resolution_tuple
        flags = pygame.FULLSCREEN if self._settings.fullscreen else 0
        self._screen = pygame.display.set_mode(res, flags)
        pygame.display.set_caption("Runners")

        # ------------------------------------------------------------------
        # Shared singletons
        # ------------------------------------------------------------------
        self._clock = pygame.time.Clock()
        self._assets = AssetManager()
        self._event_bus = EventBus()
        self._sm = SceneManager()

        # Push the entry scene
        self._sm.push(MainMenu(self._sm, self._settings, self._assets))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Enter the game loop; does not return until the application exits."""
        while True:
            # Tick at target FPS; get elapsed ms since last frame
            elapsed_ms = self._clock.tick(FPS)

            # Cap dt to prevent the spiral-of-death on a slow frame
            dt = min(elapsed_ms / 1000.0, 0.05)

            # ------------------------------------------------------------------
            # Event processing — pygame.QUIT handled at app level as a hard exit
            # ------------------------------------------------------------------
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            # If the stack is empty there is nothing left to show
            if self._sm.is_empty:
                pygame.quit()
                sys.exit()

            # ------------------------------------------------------------------
            # Per-frame dispatch
            # ------------------------------------------------------------------
            self._sm.handle_events(events)
            self._sm.update(dt)

            # ------------------------------------------------------------------
            # Rendering
            # ------------------------------------------------------------------
            self._screen.fill((0, 0, 0))   # Clear before SceneManager paints
            self._sm.render(self._screen)
            pygame.display.flip()
