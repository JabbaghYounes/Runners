"""Main menu scene — the first scene shown on launch.

Renders three menu options (Start Game / Settings / Quit) using the neon-retro
colour palette.  Arrow keys navigate; Enter/Space activates.

This is a functional placeholder.  The full implementation will add:
  * Animated background / parallax
  * Controller input support
  * Transition animations between menu items
"""

from __future__ import annotations

from typing import List

import pygame

from src import constants as C
from src.core.asset_manager import AssetManager
from src.core.event_bus import EventBus
from src.core.settings import Settings
from src.scenes.base_scene import BaseScene


class MainMenu(BaseScene):
    """Neon main menu with keyboard navigation."""

    _MENU_ITEMS = ("Start Game", "Settings", "Quit")

    def __init__(
        self,
        settings: Settings,
        assets: AssetManager,
        bus: EventBus,
    ) -> None:
        self._settings  = settings
        self._assets    = assets
        self._bus       = bus
        self._selected  = 0
        self._quit      = False

        self._font_title = assets.load_font(None, 80)
        self._font_item  = assets.load_font(None, 38)
        self._font_hint  = assets.load_font(None, 22)

    # ── Public query ──────────────────────────────────────────────────────────

    @property
    def should_quit(self) -> bool:
        """``True`` when the user has chosen to exit the application."""
        return self._quit

    # ── BaseScene implementation ──────────────────────────────────────────────

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_UP:
                self._selected = (self._selected - 1) % len(self._MENU_ITEMS)
            elif event.key == pygame.K_DOWN:
                self._selected = (self._selected + 1) % len(self._MENU_ITEMS)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(self._selected)
            elif event.key == pygame.K_ESCAPE:
                self._quit = True

    def update(self, dt: float) -> None:
        pass  # no animation state yet

    def render(self, screen: pygame.Surface) -> None:
        screen.fill(C.DARK_BG)
        w, h = screen.get_size()

        # ── Title ─────────────────────────────────────────────────────────────
        title_surf = self._font_title.render("RUNNERS", True, C.NEON_CYAN)
        screen.blit(title_surf, title_surf.get_rect(center=(w // 2, h // 4)))

        # ── Subtitle rule ─────────────────────────────────────────────────────
        pygame.draw.line(
            screen, C.NEON_CYAN,
            (w // 2 - 160, h // 4 + 52),
            (w // 2 + 160, h // 4 + 52),
            1,
        )

        # ── Menu items ────────────────────────────────────────────────────────
        for i, label in enumerate(self._MENU_ITEMS):
            is_active = i == self._selected
            color = C.NEON_GREEN if is_active else C.TEXT_PRIMARY

            text_surf = self._font_item.render(label, True, color)
            rect      = text_surf.get_rect(center=(w // 2, h // 2 + i * 58))

            if is_active:
                # Draw a subtle selection bracket
                pad = 12
                pygame.draw.rect(
                    screen, C.NEON_GREEN,
                    rect.inflate(pad * 2, pad),
                    1,  # outline only
                    border_radius=4,
                )

            screen.blit(text_surf, rect)

        # ── Keyboard hint ─────────────────────────────────────────────────────
        hint = self._font_hint.render("↑ ↓ navigate   Enter select   Esc quit", True, C.TEXT_DIM)
        screen.blit(hint, hint.get_rect(center=(w // 2, h - 32)))

    # ── Private helpers ───────────────────────────────────────────────────────

    def _activate(self, index: int) -> None:
        label = self._MENU_ITEMS[index]
        if label == "Quit":
            self._quit = True
        elif label == "Start Game":
            self._bus.emit("scene_request", scene="home_base")
        elif label == "Settings":
            self._bus.emit("scene_request", scene="settings")
