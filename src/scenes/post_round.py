"""Post-round scene — XP/money/loot summary, save, queue/exit."""
import pygame
from typing import List, Any, Optional

from src.scenes.base_scene import BaseScene
from src.ui.widgets import Button, Panel
from src.constants import (
    SCREEN_W, SCREEN_H, BG_DEEP, ACCENT_CYAN, ACCENT_GREEN, ACCENT_RED,
    TEXT_BRIGHT, TEXT_DIM, PANEL_BG, BORDER_DIM,
)


class PostRound(BaseScene):
    def __init__(self, sm: Any, settings: Any, assets: Any,
                 xp_system: Any, currency: Any, save_manager: Any,
                 extracted: bool = False,
                 loot_items: Optional[List[Any]] = None):
        self._sm = sm
        self._settings = settings
        self._assets = assets
        self._xp_system = xp_system
        self._currency = currency
        self._save_manager = save_manager
        self._extracted = extracted
        self._loot_items = loot_items or []
        self._font: Optional[pygame.font.Font] = None
        self._saved = False

        # Award currency on extraction success
        if extracted:
            currency.add(500)

        bw, bh = 260, 50
        bx = SCREEN_W // 2 - bw // 2

        self._buttons: List[Button] = [
            Button(pygame.Rect(bx, SCREEN_H - 130, bw, bh), "PLAY AGAIN", 'primary',
                   on_click=self._play_again),
            Button(pygame.Rect(bx, SCREEN_H - 70, bw, bh), "MAIN MENU", 'secondary',
                   on_click=self._main_menu),
        ]

    def on_enter(self) -> None:
        # Save progress
        if not self._saved:
            try:
                from src.progression.home_base import HomeBase
                # save_manager.save needs home_base — use a stub if not available
                hb = HomeBase()
                self._save_manager.save(hb, self._currency, self._xp_system)
            except Exception as e:
                print(f"[PostRound] Save failed: {e}")
            self._saved = True

    def _play_again(self) -> None:
        from src.scenes.game_scene import GameScene
        from src.core.event_bus import EventBus
        from src.progression.home_base import HomeBase
        eb = EventBus()
        hb = HomeBase()
        self._sm.replace_all(GameScene(
            self._sm, self._settings, self._assets, eb,
            self._xp_system, self._currency, hb))

    def _main_menu(self) -> None:
        from src.scenes.main_menu import MainMenu
        self._sm.replace_all(MainMenu(self._sm, self._settings, self._assets))

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            for btn in self._buttons:
                btn.handle_event(event)

    def update(self, dt: float) -> None:
        pass

    def render(self, screen: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.Font(None, 28)
        font_sm = pygame.font.Font(None, 20)

        screen.fill(BG_DEEP)

        # Panel
        panel = pygame.Rect(SCREEN_W // 2 - 300, 80, 600, SCREEN_H - 200)
        pygame.draw.rect(screen, PANEL_BG, panel, border_radius=8)
        pygame.draw.rect(screen, BORDER_DIM, panel, 2, border_radius=8)

        # Title
        cx = SCREEN_W // 2
        if self._extracted:
            title = self._font.render("EXTRACTION SUCCESSFUL", True, ACCENT_GREEN)
        else:
            title = self._font.render("ROUND ENDED", True, ACCENT_RED)
        screen.blit(title, (cx - title.get_width() // 2, 100))

        # Stats
        y = 160
        stats = [
            f"Level Reached:   {self._xp_system.level}",
            f"XP Banked:       {self._xp_system.xp}",
            f"Currency:        {self._currency.formatted()}",
            f"Items Collected: {len(self._loot_items)}",
        ]
        for stat in stats:
            surf = font_sm.render(stat, True, TEXT_BRIGHT)
            screen.blit(surf, (cx - 140, y))
            y += 28

        # Loot list (first 8 items)
        if self._loot_items:
            sep_surf = font_sm.render("— Loot —", True, ACCENT_CYAN)
            screen.blit(sep_surf, (cx - sep_surf.get_width() // 2, y + 10))
            y += 36
            for item in self._loot_items[:8]:
                name = getattr(item, 'name', str(item))
                s = font_sm.render(f"  {name}", True, TEXT_DIM)
                screen.blit(s, (cx - 140, y))
                y += 22

        for btn in self._buttons:
            btn.draw(screen)
