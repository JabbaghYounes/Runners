"""Pause Menu — overlay on frozen GameScene."""
import pygame
import sys
from typing import List, Any, Optional

from src.scenes.base_scene import BaseScene
from src.ui.widgets import Button, Panel, ConfirmDialog
from src.constants import SCREEN_W, SCREEN_H, PANEL_BG, BORDER_BRIGHT, ACCENT_CYAN, TEXT_BRIGHT


class PauseMenu(BaseScene):
    def __init__(self, sm: Any, settings: Any, assets: Any):
        self._sm = sm
        self._settings = settings
        self._assets = assets
        self._confirm: Optional[ConfirmDialog] = None

        bw, bh = 260, 50
        bx = SCREEN_W // 2 - bw // 2
        by = SCREEN_H // 2 - 90

        self._buttons: List[Button] = [
            Button(pygame.Rect(bx, by, bw, bh), "RESUME", 'primary',
                   on_click=self._resume),
            Button(pygame.Rect(bx, by + 68, bw, bh), "RESTART", 'secondary',
                   on_click=self._confirm_restart),
            Button(pygame.Rect(bx, by + 136, bw, bh), "MAIN MENU", 'ghost',
                   on_click=self._confirm_exit),
        ]
        self._panel = Panel(pygame.Rect(SCREEN_W // 2 - 160, SCREEN_H // 2 - 130, 320, 260))

    def _resume(self) -> None:
        self._sm.pop()

    def _confirm_restart(self) -> None:
        self._confirm = ConfirmDialog(
            "Restart round?",
            on_confirm=self._do_restart,
            on_cancel=self._cancel_confirm,
        )

    def _confirm_exit(self) -> None:
        self._confirm = ConfirmDialog(
            "Return to Main Menu?",
            on_confirm=self._do_exit,
            on_cancel=self._cancel_confirm,
        )

    def _cancel_confirm(self) -> None:
        self._confirm = None

    def _do_restart(self) -> None:
        from src.scenes.game_scene import GameScene
        from src.core.event_bus import EventBus
        from src.progression.xp_system import XPSystem
        from src.progression.currency import Currency
        from src.progression.home_base import HomeBase
        eb = EventBus()
        xp = XPSystem()
        cur = Currency()
        hb = HomeBase()
        # Replace current + pause with a fresh GameScene
        self._sm.replace_all(GameScene(
            self._sm, self._settings, self._assets, eb, xp, cur, hb))

    def _do_exit(self) -> None:
        from src.scenes.main_menu import MainMenu
        self._sm.replace_all(MainMenu(self._sm, self._settings, self._assets))

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._resume()
                return
            if self._confirm:
                self._confirm.handle_event(event)
            else:
                for btn in self._buttons:
                    btn.handle_event(event)

    def update(self, dt: float) -> None:
        pass

    def render(self, screen: pygame.Surface) -> None:
        # Semi-transparent overlay
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        self._panel.draw(screen)

        font = pygame.font.Font(None, 36)
        title = font.render("PAUSED", True, ACCENT_CYAN)
        screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2,
                             SCREEN_H // 2 - 115))

        for btn in self._buttons:
            btn.draw(screen)

        if self._confirm:
            self._confirm.draw(screen)
