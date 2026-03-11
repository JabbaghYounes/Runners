"""GameApp — top-level application object that owns the main loop.

Constructs all long-lived singletons (EventBus, Settings, AssetManager,
AudioSystem) and drives the SceneManager at a fixed frame rate.
"""
from __future__ import annotations

import sys


class SceneManager:
    """Minimal scene stack.  Each scene exposes handle_events / update / render."""

    def __init__(self) -> None:
        self._stack: list = []

    def push(self, scene: object) -> None:
        self._stack.append(scene)

    def pop(self) -> None:
        if self._stack:
            self._stack.pop()

    @property
    def current(self) -> object | None:
        return self._stack[-1] if self._stack else None

    def handle_events(self, events: list) -> None:
        if self.current:
            self.current.handle_events(events)  # type: ignore[union-attr]

    def update(self, dt: float) -> None:
        if self.current:
            self.current.update(dt)  # type: ignore[union-attr]

    def render(self, screen: object) -> None:
        if self.current:
            self.current.render(screen)  # type: ignore[union-attr]


class GameApp:
    """Owns all long-lived systems and runs the main game loop."""

    def __init__(self) -> None:
        import pygame

        pygame.init()

        from src.core.event_bus import EventBus
        from src.core.settings import Settings
        from src.core.asset_manager import AssetManager
        from src.systems.audio_system import AudioSystem

        self.event_bus = EventBus()
        self.settings = Settings.load()
        self.asset_manager = AssetManager()
        self.audio = AudioSystem(self.event_bus, self.asset_manager, self.settings)

        w, h = self.settings.resolution
        self.screen = pygame.display.set_mode((w, h))
        pygame.display.set_caption("Runners")
        self.clock = pygame.time.Clock()

        self.scene_manager = SceneManager()
        self._push_main_menu()

    # ------------------------------------------------------------------

    def _push_main_menu(self) -> None:
        """Push the initial scene (stub until MainMenuScene is implemented)."""
        from src.scenes.game_scene import GameScene
        self.scene_manager.push(
            GameScene(self.event_bus, self.audio, self.settings)
        )

    def run(self) -> None:
        """Enter the main loop; returns when the window is closed."""
        import pygame

        while True:
            # --- Events ---
            raw_events = pygame.event.get()
            for evt in raw_events:
                if evt.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

            self.scene_manager.handle_events(raw_events)

            # --- Update ---
            dt_ms = self.clock.tick(self.settings.fps)
            dt = dt_ms / 1000.0
            self.scene_manager.update(dt)

            # --- Render ---
            self.screen.fill((10, 10, 20))
            self.scene_manager.render(self.screen)
            pygame.display.flip()
