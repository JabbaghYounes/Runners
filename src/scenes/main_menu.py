"""Main Menu scene — particle background, logo, button stack."""
import pygame
import math
import random
from typing import List, Any, Optional

from src.scenes.base_scene import BaseScene
from src.ui.widgets import Button
from src.constants import (
    SCREEN_W, SCREEN_H, BG_DEEP, BG_MID, ACCENT_CYAN, ACCENT_GREEN,
    TEXT_BRIGHT, TEXT_DIM, BORDER_DIM, PANEL_BG,
)


class _Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max_life', 'size')

    def __init__(self):
        self.x = random.uniform(0, SCREEN_W)
        self.y = random.uniform(0, SCREEN_H)
        self.vx = random.uniform(-20, 20)
        self.vy = random.uniform(-40, -10)
        self.max_life = random.uniform(3.0, 8.0)
        self.life = self.max_life
        self.size = random.randint(1, 3)

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

    @property
    def alive(self) -> bool:
        return self.life > 0

    @property
    def alpha(self) -> int:
        return int(200 * (self.life / self.max_life))


class MainMenu(BaseScene):
    def __init__(self, sm: Any, settings: Any, assets: Any):
        self._sm = sm
        self._settings = settings
        self._assets = assets
        self._font_title: Optional[pygame.font.Font] = None
        self._font_sub: Optional[pygame.font.Font] = None
        self._particles: List[_Particle] = [_Particle() for _ in range(80)]
        self._tick: float = 0.0

        bw, bh = 280, 52
        bx = SCREEN_W // 2 - bw // 2

        self._buttons: List[Button] = [
            Button(pygame.Rect(bx, 340, bw, bh), "START GAME", 'primary',
                   on_click=self._start_game),
            Button(pygame.Rect(bx, 408, bw, bh), "SETTINGS", 'secondary',
                   on_click=self._open_settings),
            Button(pygame.Rect(bx, 476, bw, bh), "EXIT", 'danger',
                   on_click=self._exit_game),
        ]

    def _ensure_fonts(self) -> None:
        if self._font_title is None:
            self._font_title = pygame.font.Font(None, 72)
            self._font_sub = pygame.font.Font(None, 24)

    def _start_game(self) -> None:
        try:
            from src.scenes.home_base_scene import HomeBaseScene
            from src.progression.xp_system import XPSystem
            from src.progression.currency import Currency
            from src.progression.skill_tree import SkillTree
            from src.progression.home_base import HomeBase
            from src.save.save_manager import SaveManager
            import os
            _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))
            def _p(*p): return os.path.join(_ROOT, *p)
            xp = XPSystem()
            cur = Currency()
            sk = SkillTree()
            if os.path.exists(_p('data', 'skill_tree.json')):
                sk.load(_p('data', 'skill_tree.json'))
            hb = HomeBase()
            if os.path.exists(_p('data', 'home_base.json')):
                hb.load(_p('data', 'home_base.json'))
            sv = SaveManager(_p('saves', 'save.json'))
            save = sv.load()
            cur.load(save.get('currency', {}))
            xp.load(save.get('xp', {}))
            hb.load_state(save.get('home_base', {}))
            self._sm.replace(HomeBaseScene(
                self._sm, self._settings, self._assets, hb, sk, cur, xp))
        except Exception as e:
            print(f"[MainMenu] Failed to push HomeBase: {e}")
            self._start_game_direct()

    def _start_game_direct(self) -> None:
        from src.scenes.game_scene import GameScene
        from src.core.event_bus import EventBus
        from src.progression.xp_system import XPSystem
        from src.progression.currency import Currency
        from src.progression.home_base import HomeBase
        eb = EventBus()
        xp = XPSystem()
        cur = Currency()
        hb = HomeBase()
        self._sm.replace(GameScene(
            self._sm, self._settings, self._assets, eb, xp, cur, hb))

    def _open_settings(self) -> None:
        from src.scenes.settings_screen import SettingsScreen
        self._sm.push(SettingsScreen(self._sm, self._settings, self._assets))

    def _exit_game(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            for btn in self._buttons:
                btn.handle_event(event)

    def update(self, dt: float) -> None:
        self._tick += dt
        for p in self._particles:
            p.update(dt)
            if not p.alive or p.x < -10 or p.x > SCREEN_W + 10 or p.y < -10:
                # Respawn
                p.__init__()
                p.y = SCREEN_H + 5

    def render(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        screen.fill(BG_DEEP)

        # Particle field
        for p in self._particles:
            if p.alive:
                color = (0, int(180 * p.life / p.max_life), int(255 * p.life / p.max_life))
                pygame.draw.circle(screen, color, (int(p.x), int(p.y)), p.size)

        # Title glow (simple)
        pulse = 0.7 + 0.3 * math.sin(self._tick * 1.5)
        c = int(pulse * 255)
        title = self._font_title.render("RUNNERS", True, (0, c, 255))
        tx = SCREEN_W // 2 - title.get_width() // 2
        screen.blit(title, (tx, 180))

        sub = self._font_sub.render("NEXUS STATION", True, ACCENT_GREEN)
        screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 260))

        # Buttons
        for btn in self._buttons:
            btn.draw(screen)

        # Version / hint
        hint = self._font_sub.render("A — D to move  |  W to jump  |  M for map", True, TEXT_DIM)
        screen.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H - 30))
