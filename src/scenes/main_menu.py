"""Main menu scene -- the first scene shown on launch.

Renders three menu options (Start Game / Settings / Quit) using the neon-retro
colour palette.  Arrow keys navigate; Enter/Space activates.
"""

from __future__ import annotations

from typing import List

import pygame

from src import constants as C
from src.core.event_bus import EventBus
from src.core.settings import Settings
from src.scenes.base_scene import BaseScene


def _safe_font(assets, name, size):
    """Try assets.load_font, fall back to pygame defaults."""
    if not pygame.font.get_init():
        pygame.font.init()
    if assets is not None and hasattr(assets, 'load_font'):
        try:
            return assets.load_font(name, size)
        except Exception:
            pass
    try:
        return pygame.font.Font(name, size)
    except Exception:
        return pygame.font.SysFont('monospace', size)


class MainMenu(BaseScene):
    """Neon main menu with keyboard navigation.

    Supports two constructor signatures:
    1. MainMenu(settings, assets, bus)         -- original
    2. MainMenu(sm, settings, assets)          -- from PauseMenu (sm is scene manager)
    3. MainMenu(sm, settings, assets, bus)     -- explicit
    """

    _MENU_ITEMS = ("Start Game", "Settings", "Quit")

    def __init__(
        self,
        first=None,
        second=None,
        third=None,
        fourth=None,
        **kwargs,
    ) -> None:
        # Detect call style by argument types
        if isinstance(first, Settings):
            # Style 1: MainMenu(settings, assets, bus)
            self._sm = None
            self._settings = first
            self._assets = second
            self._bus = third if isinstance(third, EventBus) else EventBus()
        elif isinstance(second, Settings):
            # Style 2/3: MainMenu(sm, settings, assets, [bus])
            self._sm = first
            self._settings = second
            self._assets = third
            self._bus = fourth if isinstance(fourth, EventBus) else EventBus()
        elif hasattr(first, 'push') or hasattr(first, 'pop'):
            # Style 2: MainMenu(sm, settings_or_none, assets_or_none)
            self._sm = first
            self._settings = second if second is not None else Settings()
            self._assets = third
            self._bus = fourth if fourth is not None else EventBus()
        else:
            # Fallback
            self._sm = first
            self._settings = second if isinstance(second, Settings) else Settings()
            self._assets = third
            self._bus = fourth if isinstance(fourth, EventBus) else EventBus()

        self._selected = 0
        self._quit = False
        self._buttons = []  # Placeholder for test compat (no actual Button widgets here)

        self._font_title = _safe_font(self._assets, None, 80)
        self._font_item = _safe_font(self._assets, None, 38)
        self._font_hint = _safe_font(self._assets, None, 22)

    # -- Public query --

    @property
    def should_quit(self) -> bool:
        return self._quit

    # -- BaseScene implementation --

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
        pass

    def render(self, screen: pygame.Surface) -> None:
        screen.fill(C.BG_DEEP)
        w, h = screen.get_size()

        # Title
        title_surf = self._font_title.render("RUNNERS", True, C.ACCENT_CYAN)
        screen.blit(title_surf, title_surf.get_rect(center=(w // 2, h // 4)))

        # Subtitle rule
        pygame.draw.line(
            screen, C.ACCENT_CYAN,
            (w // 2 - 160, h // 4 + 52),
            (w // 2 + 160, h // 4 + 52),
            1,
        )

        # Menu items
        for i, label in enumerate(self._MENU_ITEMS):
            is_active = i == self._selected
            color = C.ACCENT_GREEN if is_active else C.TEXT_PRIMARY

            text_surf = self._font_item.render(label, True, color)
            rect = text_surf.get_rect(center=(w // 2, h // 2 + i * 58))

            if is_active:
                pad = 12
                pygame.draw.rect(
                    screen, C.ACCENT_GREEN,
                    rect.inflate(pad * 2, pad),
                    1,
                    border_radius=4,
                )

            screen.blit(text_surf, rect)

        # Keyboard hint
        hint = self._font_hint.render(
            "Arrow navigate  Enter select  Esc quit", True, C.TEXT_SECONDARY
        )
        screen.blit(hint, hint.get_rect(center=(w // 2, h - 32)))

    def _on_start(self) -> None:
        """Start a new game -- replace the menu with a GameScene."""
        from src.scenes.game_scene import GameScene
        if self._sm is not None:
            self._sm.replace(GameScene(self._sm, self._settings, self._assets))
        else:
            self._bus.emit("scene_request", scene="home_base")

    def _on_settings(self) -> None:
        """Push the settings screen on top of the menu."""
        from src.scenes.settings_screen import SettingsScreen
        if self._sm is not None:
            self._sm.push(SettingsScreen(self._sm, self._settings, self._assets))
        else:
            self._bus.emit("scene_request", scene="settings")

    def _activate(self, index: int) -> None:
        label = self._MENU_ITEMS[index]
        if label == "Quit":
            self._quit = True
        elif label == "Start Game":
            self._on_start()
        elif label == "Settings":
            self._on_settings()
