"""MainMenu scene — entry point, routes START GAME → HomeBaseScene."""
from __future__ import annotations

import pygame

from src.scenes.base_scene import BaseScene
from src.ui.widgets import (
    ACCENT_CYAN, BG_DEEP, TEXT_SECONDARY, TEXT_DISABLED,
    Button, Label,
)


class MainMenu(BaseScene):
    """Main menu with START GAME, SETTINGS, and EXIT buttons.

    Args:
        game_app: The GameApp instance (provides home_base, currency,
                  xp_system, scene_manager, save_manager).
    """

    def __init__(self, game_app) -> None:
        self._app = game_app
        self._buttons: list[Button] = []
        self._initialized = False

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    def _ensure_init(self, surface) -> None:
        if self._initialized:
            return
        sw, sh = surface.get_size()
        btn_w, btn_h = 240, 44
        btn_x = (sw - btn_w) // 2
        btn_y_start = int(sh * 0.55)
        gap = 12

        self._buttons = [
            Button(
                "START GAME",
                pygame.Rect(btn_x, btn_y_start, btn_w, btn_h),
                style="primary",
                on_click=self._on_start,
            ),
            Button(
                "SETTINGS",
                pygame.Rect(btn_x, btn_y_start + btn_h + gap, btn_w, btn_h),
                style="secondary",
                on_click=self._on_settings,
            ),
            Button(
                "EXIT",
                pygame.Rect(btn_x, btn_y_start + (btn_h + gap) * 2, btn_w, btn_h),
                style="danger",
                on_click=self._on_exit,
            ),
        ]
        self._initialized = True

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        """Route START GAME → HomeBaseScene."""
        from src.scenes.home_base_scene import HomeBaseScene
        scene = HomeBaseScene(
            home_base=self._app.home_base,
            currency=self._app.currency,
            xp_system=self._app.xp_system,
            scene_manager=self._app.scene_manager,
            save_manager=self._app.save_manager,
        )
        self._app.scene_manager.replace(scene)

    def _on_settings(self) -> None:
        """Push SettingsScreen onto the scene stack."""
        from src.scenes.settings_screen import SettingsScreen
        settings_scene = _SettingsSceneWrapper(
            self._app.settings, self._app.audio_system,
            on_close=lambda: self._app.scene_manager.pop(),
        )
        self._app.scene_manager.push(settings_scene)

    def _on_exit(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ------------------------------------------------------------------
    # BaseScene interface
    # ------------------------------------------------------------------

    def handle_events(self, events: list) -> None:
        self._ensure_init_stub()
        for event in events:
            for btn in self._buttons:
                btn.handle_event(event)

    def _ensure_init_stub(self) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def render(self, screen) -> None:
        self._ensure_init(screen)
        sw, sh = screen.get_size()
        screen.fill(BG_DEEP)

        # Logotype
        font_logo = pygame.font.SysFont("monospace", 48, bold=True)
        logo_surf = font_logo.render("R U N N E R S", True, ACCENT_CYAN)
        logo_rect = logo_surf.get_rect(centerx=sw // 2, y=int(sh * 0.28))
        screen.blit(logo_surf, logo_rect)

        # Subtle subtitle
        font_sub = pygame.font.SysFont("monospace", 14)
        sub_surf = font_sub.render("EXTRACTION ROGUELITE", True, TEXT_SECONDARY)
        sub_rect = sub_surf.get_rect(centerx=sw // 2, y=logo_rect.bottom + 8)
        screen.blit(sub_surf, sub_rect)

        # Buttons
        for btn in self._buttons:
            btn.render(screen)

        # Version label
        ver_font = pygame.font.SysFont("monospace", 12)
        ver_surf = ver_font.render("v0.1.0", True, TEXT_DISABLED)
        screen.blit(ver_surf, (sw - ver_surf.get_width() - 16, sh - ver_surf.get_height() - 12))


class _SettingsSceneWrapper(BaseScene):
    """Wraps SettingsScreen (which is not a BaseScene) in a scene interface."""

    def __init__(self, settings, audio, on_close) -> None:
        from src.scenes.settings_screen import SettingsScreen
        self._screen = SettingsScreen(settings, audio, on_close)

    def handle_events(self, events: list) -> None:
        self._screen.handle_events(events)

    def update(self, dt: float) -> None:
        self._screen.update(dt)

    def render(self, screen) -> None:
        self._screen.render(screen)
