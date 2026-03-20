"""Pause Menu -- pushed over the GameScene when ESC is pressed.

Stack state while paused:  [GameScene, PauseMenu]

The SceneManager renders the frozen GameScene first (bottom of stack), then
PauseMenu draws a semi-transparent vignette over it followed by the panel.

Buttons:
    RESUME       -- pops PauseMenu, GameScene resumes.
    SETTINGS     -- pushes SettingsScreen overlay.
    RESTART      -- ConfirmDialog -> replace_all(GameScene).
    EXIT TO MENU -- ConfirmDialog -> replace_all(MainMenu).

ESC key is equivalent to RESUME.
Arrow keys / W / S navigate between buttons; Enter / Space activates.
"""
from __future__ import annotations

from typing import List

import pygame

from src.scenes.base_scene import BaseScene
from src.ui.widgets import Button, ConfirmDialog, Label, Panel
from src.constants import ACCENT_CYAN, BG_DEEP, SCREEN_H, SCREEN_W, TEXT_SECONDARY


def _load_font(assets, name, size):
    """Load a font via assets or fall back to pygame default."""
    if assets is not None and hasattr(assets, 'load_font'):
        try:
            return assets.load_font(name, size)
        except Exception:
            pass
    try:
        return pygame.font.Font(name, size)
    except Exception:
        return pygame.font.SysFont('monospace', size)


class PauseMenu(BaseScene):
    """Semi-transparent pause overlay with RESUME / SETTINGS / RESTART / EXIT TO MENU."""

    _PANEL_W = 260
    _PANEL_H = 294  # 4 buttons × 52 px row + top padding + bottom margin

    def __init__(
        self,
        scene_manager,
        settings=None,
        assets=None,
    ) -> None:
        self._sm = scene_manager
        self._settings = settings
        self._assets = assets

        # Fonts
        font_title = _load_font(assets, None, 30)
        font_btn = _load_font(assets, None, 18)
        font_dialog = _load_font(assets, None, 14)

        # Full-screen vignette (70% alpha dark overlay)
        self._vignette = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        r, g, b = BG_DEEP
        self._vignette.fill((r, g, b, 178))

        # Central panel
        px = (SCREEN_W - self._PANEL_W) // 2
        py = (SCREEN_H - self._PANEL_H) // 2
        self._panel = Panel(pygame.Rect(px, py, self._PANEL_W, self._PANEL_H), alpha=235)

        # "PAUSED" heading
        self._lbl_title = Label(
            "PAUSED",
            font_title,
            ACCENT_CYAN,
            (SCREEN_W // 2, py + 38),
            glow=True,
        )

        # Buttons (52 px stride starting at py + 90)
        bw, bh = 210, 40
        bx = SCREEN_W // 2 - bw // 2

        self._btn_resume = Button(
            pygame.Rect(bx, py + 90, bw, bh),
            "RESUME",
            font_btn,
            "primary",
            self._on_resume,
        )
        self._btn_settings = Button(
            pygame.Rect(bx, py + 142, bw, bh),
            "SETTINGS",
            font_btn,
            "secondary",
            self._on_settings,
        )
        self._btn_restart = Button(
            pygame.Rect(bx, py + 194, bw, bh),
            "RESTART",
            font_btn,
            "secondary",
            self._on_restart,
        )
        self._btn_exit = Button(
            pygame.Rect(bx, py + 246, bw, bh),
            "EXIT TO MENU",
            font_btn,
            "secondary",
            self._on_exit,
        )

        # Ordered list used by keyboard navigation (index → button)
        self._nav_btns: List[Button] = [
            self._btn_resume,
            self._btn_settings,
            self._btn_restart,
            self._btn_exit,
        ]
        self._focused_idx: int = 0  # 0 = RESUME pre-selected

        # Confirm dialogs
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

    def _on_settings(self) -> None:
        try:
            from src.scenes.settings_screen import SettingsScreen
            self._sm.push(SettingsScreen(self._sm, self._settings, self._assets))
        except Exception as e:
            print(f"[PauseMenu] SettingsScreen push failed: {e}")

    def _on_restart(self) -> None:
        self._confirm_restart.show((SCREEN_W, SCREEN_H))

    def _on_exit(self) -> None:
        self._confirm_exit.show((SCREEN_W, SCREEN_H))

    def _on_restart_confirmed(self) -> None:
        self._confirm_restart.hide()
        from src.scenes.game_scene import GameScene
        self._sm.replace_all(GameScene(self._sm, self._settings, self._assets))

    def _on_exit_confirmed(self) -> None:
        self._confirm_exit.hide()
        from src.scenes.main_menu import MainMenu
        self._sm.replace_all(MainMenu(self._sm, self._settings, self._assets))

    # ------------------------------------------------------------------
    # BaseScene implementation
    # ------------------------------------------------------------------

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            # Active confirm dialogs intercept all input
            if self._confirm_restart.active:
                self._confirm_restart.handle_event(event)
                continue
            if self._confirm_exit.active:
                self._confirm_exit.handle_event(event)
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._on_resume()
                    return
                # Keyboard navigation
                if event.key in (pygame.K_UP, pygame.K_w):
                    self._focused_idx = (self._focused_idx - 1) % len(self._nav_btns)
                    continue
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    self._focused_idx = (self._focused_idx + 1) % len(self._nav_btns)
                    continue
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    btn = self._nav_btns[self._focused_idx]
                    if btn.on_click:
                        btn.on_click()
                    continue

            self._btn_resume.handle_event(event)
            self._btn_settings.handle_event(event)
            self._btn_restart.handle_event(event)
            self._btn_exit.handle_event(event)

    def update(self, dt: float) -> None:
        pass  # Paused -- nothing to advance

    def render(self, screen: pygame.Surface) -> None:
        # Vignette over the frozen game world
        screen.blit(self._vignette, (0, 0))

        # Sync keyboard-focus highlight on buttons before drawing
        for i, btn in enumerate(self._nav_btns):
            btn._focused = (i == self._focused_idx)

        # Panel and controls
        self._panel.draw(screen)
        self._lbl_title.draw(screen)
        self._btn_resume.draw(screen)
        self._btn_settings.draw(screen)
        self._btn_restart.draw(screen)
        self._btn_exit.draw(screen)

        # Active confirm dialog
        if self._confirm_restart.active:
            self._confirm_restart.draw(screen)
        if self._confirm_exit.active:
            self._confirm_exit.draw(screen)
