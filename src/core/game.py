"""GameApp — initialises Pygame, singletons, and runs the main loop."""
import pygame
import sys
import os

from src.constants import SCREEN_W, SCREEN_H, FPS, BG_DEEP
from src.constants import _init_key_bindings
from src.core.event_bus import EventBus
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.core.scene_manager import SceneManager
from src.inventory.item_database import ItemDatabase
from src.data.enemy_database import EnemyDatabase
from src.progression.xp_system import XPSystem
from src.progression.currency import Currency
from src.progression.skill_tree import SkillTree
from src.progression.home_base import HomeBase
from src.save.save_manager import SaveManager


# Resolve paths relative to the project root
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _path(*parts: str) -> str:
    return os.path.join(_ROOT, *parts)


class GameApp:
    def __init__(self):
        pygame.init()
        _init_key_bindings()

        # Mixer (optional — fail silently)
        try:
            pygame.mixer.init()
        except pygame.error:
            pass

        # Settings
        self._settings = Settings.load(_path('settings.json'))
        w, h = self._settings.resolution_tuple

        flags = pygame.FULLSCREEN if self._settings.fullscreen else 0
        self.screen = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption("Runners — Nexus Station")
        self.clock = pygame.time.Clock()

        # Core singletons
        self._event_bus = EventBus()
        self._assets = AssetManager()
        self._sm = SceneManager()

        # Databases (pre-load so scenes can share the singleton)
        self._item_db = ItemDatabase.instance()
        if os.path.exists(_path('data', 'items.json')):
            self._item_db.load(_path('data', 'items.json'))

        # Progression singletons
        self._xp_system = XPSystem()
        self._currency = Currency()
        self._skill_tree = SkillTree()
        self._home_base = HomeBase()

        if os.path.exists(_path('data', 'skill_tree.json')):
            self._skill_tree.load(_path('data', 'skill_tree.json'))
        if os.path.exists(_path('data', 'home_base.json')):
            self._home_base.load(_path('data', 'home_base.json'))

        # Save
        self._save_manager = SaveManager(_path('saves', 'save.json'))
        save_data = self._save_manager.load()
        self._currency.load(save_data.get('currency', {}))
        self._xp_system.load(save_data.get('xp', {}))
        self._home_base.load_state(save_data.get('home_base', {}))

        # Initial scene
        from src.scenes.main_menu import MainMenu
        self._sm.push(MainMenu(self._sm, self._settings, self._assets))

    # ------------------------------------------------------------------ #
    #  Main loop                                                           #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        running = True
        while running and not self._sm.is_empty:
            elapsed_ms = self.clock.tick(FPS)
            dt = min(elapsed_ms / 1000.0, 0.05)  # cap at 50 ms

            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False

            if not running:
                break

            self._sm.handle_events(events)
            self._sm.update(dt)

            self.screen.fill(BG_DEEP)
            self._sm.render(self.screen)
            pygame.display.flip()

        self._shutdown()

    def _shutdown(self) -> None:
        try:
            self._save_manager.save(self._home_base, self._currency, self._xp_system)
        except Exception as e:
            print(f"[GameApp] Save on exit failed: {e}")
        pygame.quit()
        sys.exit(0)
