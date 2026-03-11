"""GameApp — top-level application class."""
from __future__ import annotations

import sys

import pygame

from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.core.event_bus import EventBus
from src.core.scene_manager import SceneManager
from src.progression.currency import Currency
from src.progression.xp_system import XPSystem
from src.progression.home_base import HomeBase
from src.save.save_manager import SaveManager
from src.systems.audio_system import AudioSystem


class GameApp:
    """Top-level singleton that owns all application-tier state.

    Lifetime: process start → exit.
    Progression objects (currency, xp_system, home_base) survive rounds.
    """

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((1280, 720))
        pygame.display.set_caption("RUNNERS")
        self.clock = pygame.time.Clock()

        # Application-tier singletons
        self.settings = Settings.load()
        self.asset_manager = AssetManager()
        self.event_bus = EventBus()
        self.audio_system = AudioSystem(self.event_bus, self.asset_manager, self.settings)
        self.save_manager = SaveManager()

        # Progression-tier objects (survive multiple rounds)
        self.currency = Currency()
        self.xp_system = XPSystem()
        self.home_base = HomeBase("data/home_base.json")

        # Restore persisted save state
        save_data = self.save_manager.load()
        player_data = save_data.get("player", {})
        self.currency._balance = max(0, int(player_data.get("money", 0)))
        self.xp_system.load(player_data)
        self.home_base.from_save_dict(save_data.get("home_base", {}))

        # Scene stack — start at MainMenu
        self.scene_manager = SceneManager()
        from src.scenes.main_menu import MainMenu
        self.scene_manager.push(MainMenu(self))

    def run(self) -> None:
        """Main game loop: 60 FPS fixed-timestep."""
        while True:
            dt = self.clock.tick(60) / 1000.0

            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            self.scene_manager.handle_events(events)
            self.scene_manager.update(dt)

            self.screen.fill((10, 14, 26))
            self.scene_manager.render(self.screen)
            pygame.display.flip()
