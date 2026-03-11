"""Pause Menu — pushed over the GameScene when ESC is pressed.

Stack state while paused:  [GameScene, PauseMenu]

The SceneManager renders the frozen GameScene first (bottom of stack), then
PauseMenu draws a semi-transparent vignette over it followed by the panel.

Buttons:
    RESUME       — pops PauseMenu, GameScene resumes.
    RESTART      — ConfirmDialog → replace(GameScene).
    EXIT TO MENU — ConfirmDialog → replace_all(MainMenu).

ESC key is equivalent to RESUME.
"""
from __future__ import annotations

from typing import List

import pygame

from src.scenes.base_scene import BaseScene
from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.ui.widgets import Button, ConfirmDialog, Label, Panel
from src.constants import ACCENT_CYAN, BG_DEEP, SCREEN_H, SCREEN_W, TEXT_SECONDARY


class PauseMenu(BaseScene):
    """Semi-transparent pause overlay with RESUME / RESTART / EXIT TO MENU."""

    _PANEL_W = 260
    _PANEL_H = 240

    def __init__(
        self,
        scene_manager: SceneManager,
        settings: Settings,
        assets: AssetManager,
    ) -> None:
        self._sm = scene_manager
        self._settings = settings
        self._assets = assets

        # Fonts
        font_title = assets.load_font(None, 30)
        font_btn = assets.load_font(None, 18)
        font_dialog = assets.load_font(None, 14)

        # ------------------------------------------------------------------
        # Full-screen vignette (70 % alpha dark overlay)
        # ------------------------------------------------------------------
        self._vignette = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        r, g, b = BG_DEEP
        self._vignette.fill((r, g, b, 178))  # ≈ 70 % opacity

        # ------------------------------------------------------------------
        # Central panel
        # ------------------------------------------------------------------
        px = (SCREEN_W - self._PANEL_W) // 2
        py = (SCREEN_H - self._PANEL_H) // 2
        self._panel = Panel(pygame.Rect(px, py, self._PANEL_W, self._PANEL_H), alpha=235)

        # ------------------------------------------------------------------
        # "PAUSED" heading
        # ------------------------------------------------------------------
        self._lbl_title = Label(
            "PAUSED",
            font_title,
            ACCENT_CYAN,
            (SCREEN_W // 2, py + 38),
            glow=True,
        )

        # ------------------------------------------------------------------
        # Buttons  (centred within panel)
        # ------------------------------------------------------------------
        bw, bh = 210, 40
        bx = SCREEN_W // 2 - bw // 2

        self._btn_resume = Button(
            pygame.Rect(bx, py + 90, bw, bh),
            "RESUME",
            font_btn,
            "primary",
            self._on_resume,
        )
        self._btn_restart = Button(
            pygame.Rect(bx, py + 142, bw, bh),
            "RESTART",
            font_btn,
            "secondary",
            self._on_restart,
        )
        self._btn_exit = Button(
            pygame.Rect(bx, py + 194, bw, bh),
            "EXIT TO MENU",
            font_btn,
            "secondary",
            self._on_exit,
        )

        # ------------------------------------------------------------------
        # Confirm dialogs
        # ------------------------------------------------------------------
        _msg = "You will lose all loot\ncollected this run."

        self._confirm_restart = ConfirmDialog(
            "Are you sure?",
            "You will lose all loot this run.",
            font_dialog,
            font_dialog,
            font_dialog,
            on_confirm=self._on_restart_confirmed,
            on_cancel=lambda: self._confirm_restart.hide(),
        )
        self._confirm_exit = ConfirmDialog(
            "Are you sure?",
            "You will lose all loot this run.",
            font_dialog,
            font_dialog,
            font_dialog,
            on_confirm=self._on_exit_confirmed,
            on_cancel=lambda: self._confirm_exit.hide(),
        )

    # ------------------------------------------------------------------
    # Button / dialog callbacks
    # ------------------------------------------------------------------

    def _on_resume(self) -> None:
        self._sm.pop()

    def _on_restart(self) -> None:
        self._confirm_restart.show((SCREEN_W, SCREEN_H))

    def _on_exit(self) -> None:
        self._confirm_exit.show((SCREEN_W, SCREEN_H))

    def _on_restart_confirmed(self) -> None:
        self._confirm_restart.hide()
        from src.scenes.game_scene import GameScene
        self._sm.replace(GameScene(self._sm, self._settings, self._assets))

    def _on_exit_confirmed(self) -> None:
        self._confirm_exit.hide()
        from src.scenes.main_menu import MainMenu
        self._sm.replace_all(MainMenu(self._sm, self._settings, self._assets))

    # ------------------------------------------------------------------
    # BaseScene implementation
    # ------------------------------------------------------------------

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            # Confirm dialogs take priority
            if self._confirm_restart.active:
                self._confirm_restart.handle_event(event)
                continue
            if self._confirm_exit.active:
                self._confirm_exit.handle_event(event)
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._on_resume()
                return

            self._btn_resume.handle_event(event)
            self._btn_restart.handle_event(event)
            self._btn_exit.handle_event(event)

    def update(self, dt: float) -> None:
        pass  # Paused — nothing to advance

    def render(self, screen: pygame.Surface) -> None:
        # Vignette over the frozen game world (already rendered below us)
        screen.blit(self._vignette, (0, 0))

        # Panel and controls
        self._panel.draw(screen)
        self._lbl_title.draw(screen)
        self._btn_resume.draw(screen)
        self._btn_restart.draw(screen)
        self._btn_exit.draw(screen)

        # Active confirm dialog (draws its own dim overlay + panel)
        if self._confirm_restart.active:
            self._confirm_restart.draw(screen)
        if self._confirm_exit.active:
            self._confirm_exit.draw(screen)
