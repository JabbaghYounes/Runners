"""GameApp — Pygame initialisation and fixed-timestep main loop.

The application object is created once in ``main.py``.  Calling ``run()``
starts the loop and blocks until the user quits.

Fixed-timestep design
---------------------
Physics and logic always advance by exactly ``FIXED_TIMESTEP`` seconds per
tick regardless of rendering frame rate.  An accumulator absorbs variable
real-world time between frames and drains it in fixed chunks::

    accumulator += clamped_real_dt

    while accumulator >= FIXED_TIMESTEP:
        scene_manager.update(FIXED_TIMESTEP)
        accumulator -= FIXED_TIMESTEP

Clamping ``real_dt`` to ``MAX_FRAME_TIME`` (0.25 s) prevents the simulation
from running away ("spiral of death") after a temporary freeze, e.g. when the
OS suspends the process or a debugger pauses execution.
"""

from __future__ import annotations

import sys

import pygame

from src import constants as C
from src.core.asset_manager import AssetManager
from src.core.event_bus import EventBus
from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.scenes.main_menu import MainMenu


class GameApp:
    """Top-level application.  Create one instance, then call ``.run()``."""

    def __init__(self) -> None:
        # ── Pygame subsystems (must init before loading settings/key bindings) ─
        pygame.init()

        # ── Load user settings (resolution, fps, volume, key bindings) ────────
        self.settings: Settings = Settings.load()
        self._init_display()
        self._audio_ok = self._init_audio()
        pygame.display.set_caption("Runners")

        self.clock: pygame.time.Clock = pygame.time.Clock()

        # ── Shared services (owned here, passed into scenes by reference) ─────
        self.bus:    EventBus    = EventBus()
        self.assets: AssetManager = AssetManager()
        self.assets.set_audio_available(self._audio_ok)

        # ── Scene stack ───────────────────────────────────────────────────────
        self.scenes: SceneManager = SceneManager()

        # Listen for scene-transition requests emitted by scenes via the bus
        self.bus.subscribe("scene_request", self._on_scene_request)

        # Boot into the main menu
        self.scenes.push(MainMenu(self.settings, self.assets, self.bus))

        self._running: bool = False

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the main loop.  Returns only when the game is closed."""
        self._running = True
        accumulator   = 0.0

        while self._running:
            # ── Time bookkeeping ──────────────────────────────────────────────
            # clock.tick() returns elapsed milliseconds; convert to seconds.
            raw_dt = self.clock.tick(self.settings.target_fps) / 1000.0
            # Cap dt to guard against spiral-of-death after a freeze / debug pause.
            dt = min(raw_dt, C.MAX_FRAME_TIME)
            accumulator += dt

            # ── Pygame event pump ─────────────────────────────────────────────
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self._running = False

            if not self._running:
                break

            # Route events to the active scene
            self.scenes.handle_events(events)

            # Check whether the active scene has requested an application exit
            active = self.scenes.active
            if active is None or (
                hasattr(active, "should_quit") and active.should_quit
            ):
                self._running = False
                break

            # ── Fixed-step logic updates ──────────────────────────────────────
            while accumulator >= C.FIXED_TIMESTEP:
                self.scenes.update(C.FIXED_TIMESTEP)
                accumulator -= C.FIXED_TIMESTEP

            # ── Rendering ─────────────────────────────────────────────────────
            self.screen.fill(C.BLACK)
            self.scenes.render(self.screen)
            pygame.display.flip()

        self._shutdown()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _init_display(self) -> None:
        """Create the display surface according to user settings."""
        w, h  = self.settings.resolution
        flags = pygame.FULLSCREEN if self.settings.fullscreen else 0
        self.screen: pygame.Surface = pygame.display.set_mode((w, h), flags)

    def _init_audio(self) -> bool:
        """Initialise the pygame mixer.

        Returns:
            ``True`` if audio is available, ``False`` for a silent fallback
            (e.g. headless CI, no audio device).
        """
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            return True
        except pygame.error:
            print(
                "[Runners] Warning: audio device unavailable — running silently.",
                file=sys.stderr,
            )
            return False

    def _shutdown(self) -> None:
        """Clean up resources before the process exits."""
        self.scenes.clear()
        if self._audio_ok:
            pygame.mixer.quit()
        pygame.quit()

    def _on_scene_request(self, *, scene: str, **_kwargs: object) -> None:
        """Handle scene-transition requests broadcast over the event bus.

        Scenes emit ``bus.emit("scene_request", scene="home_base")`` instead of
        importing concrete scene classes directly.  This handler is the single
        place that knows the scene graph topology.

        Full routing will be wired up as each scene is implemented.
        """
        # Stub — full routing added when individual scenes are implemented.
        pass
