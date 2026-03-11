"""Main Menu scene — entry point of the game.

Layout:
    - Particle background (40 drifting cyan/magenta dots)
    - "RUNNERS" logotype with neon glow
    - Three stacked buttons: START GAME (primary), SETTINGS (secondary), EXIT (danger)
    - Version label in bottom-right corner

Keyboard navigation: Up/Down (or W/S) cycles focus; Enter/Space activates.
"""
from __future__ import annotations

import random
import sys
from typing import List

import pygame

from src.scenes.base_scene import BaseScene
from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.ui.widgets import Button, Label
from src.constants import (
    ACCENT_CYAN,
    ACCENT_MAGENTA,
    BG_DEEP,
    SCREEN_H,
    SCREEN_W,
    TEXT_DISABLED,
    VERSION,
)


# ---------------------------------------------------------------------------
# Particle helpers
# ---------------------------------------------------------------------------

class _Particle:
    """A single drifting particle for the animated background."""

    def __init__(self) -> None:
        self._randomise()

    def _randomise(self) -> None:
        self.x: float = random.uniform(0.0, SCREEN_W)
        self.y: float = random.uniform(0.0, SCREEN_H)
        self.vx: float = random.uniform(-25.0, 25.0)
        self.vy: float = random.uniform(-18.0, 18.0)
        self.radius: int = random.randint(1, 3)
        self.color = random.choice([ACCENT_CYAN, ACCENT_MAGENTA])
        self.alpha: int = random.randint(55, 170)

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        # Wrap at edges with a small margin so particles don't teleport visibly
        if self.x < -8 or self.x > SCREEN_W + 8 or self.y < -8 or self.y > SCREEN_H + 8:
            self._randomise()


class _ParticleSystem:
    """Manages and renders a fixed pool of particles."""

    COUNT = 40

    def __init__(self) -> None:
        self._particles: List[_Particle] = [_Particle() for _ in range(self.COUNT)]

    def update(self, dt: float) -> None:
        for p in self._particles:
            p.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        for p in self._particles:
            dot = pygame.Surface((p.radius * 2, p.radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(dot, (*p.color, p.alpha), (p.radius, p.radius), p.radius)
            surface.blit(dot, (int(p.x) - p.radius, int(p.y) - p.radius))


# ---------------------------------------------------------------------------
# MainMenu scene
# ---------------------------------------------------------------------------

class MainMenu(BaseScene):
    """The game's entry screen with START GAME / SETTINGS / EXIT buttons."""

    _BTN_W = 240
    _BTN_H = 44
    _BTN_GAP = 12

    def __init__(
        self,
        scene_manager: SceneManager,
        settings: Settings,
        assets: AssetManager,
    ) -> None:
        self._sm = scene_manager
        self._settings = settings
        self._assets = assets

        self._particles = _ParticleSystem()

        # Fonts
        font_logo = assets.load_font(None, 48)
        font_btn = assets.load_font(None, 20)
        font_ver = assets.load_font(None, 12)

        # Logo
        cx = SCREEN_W // 2
        self._logo = Label(
            "RUNNERS",
            font_logo,
            ACCENT_CYAN,
            (cx, int(SCREEN_H * 0.28)),
            align="center",
            glow=True,
        )

        # Buttons — stacked vertically starting at 55 % screen height
        y0 = int(SCREEN_H * 0.55)
        bx = cx - self._BTN_W // 2
        step = self._BTN_H + self._BTN_GAP
        self._buttons: List[Button] = [
            Button(
                pygame.Rect(bx, y0, self._BTN_W, self._BTN_H),
                "START GAME",
                font_btn,
                "primary",
                self._on_start,
            ),
            Button(
                pygame.Rect(bx, y0 + step, self._BTN_W, self._BTN_H),
                "SETTINGS",
                font_btn,
                "secondary",
                self._on_settings,
            ),
            Button(
                pygame.Rect(bx, y0 + step * 2, self._BTN_W, self._BTN_H),
                "EXIT",
                font_btn,
                "danger",
                self._on_exit,
            ),
        ]

        # Version label (bottom-right)
        self._version = Label(
            VERSION,
            font_ver,
            TEXT_DISABLED,
            (SCREEN_W - 16, SCREEN_H - 16),
            align="right",
        )

        # Keyboard navigation state
        self._focus_idx: int = 0
        self._buttons[self._focus_idx]._focused = True

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        from src.scenes.game_scene import GameScene
        self._sm.replace(GameScene(self._sm, self._settings, self._assets))

    def _on_settings(self) -> None:
        from src.scenes.settings_screen import SettingsScreen
        self._sm.push(SettingsScreen(self._sm, self._settings, self._assets))

    def _on_exit(self) -> None:
        pygame.quit()
        sys.exit()

    # ------------------------------------------------------------------
    # Keyboard focus helpers
    # ------------------------------------------------------------------

    def _move_focus(self, delta: int) -> None:
        self._buttons[self._focus_idx]._focused = False
        self._focus_idx = (self._focus_idx + delta) % len(self._buttons)
        self._buttons[self._focus_idx]._focused = True

    # ------------------------------------------------------------------
    # BaseScene implementation
    # ------------------------------------------------------------------

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self._move_focus(-1)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self._move_focus(1)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    cb = self._buttons[self._focus_idx].on_click
                    if cb:
                        cb()
            # Route mouse events to all buttons
            for btn in self._buttons:
                btn.handle_event(event)

    def update(self, dt: float) -> None:
        self._particles.update(dt)

    def render(self, screen: pygame.Surface) -> None:
        screen.fill(BG_DEEP)
        self._particles.draw(screen)
        self._logo.draw(screen)
        for btn in self._buttons:
            btn.draw(screen)
        self._version.draw(screen)
