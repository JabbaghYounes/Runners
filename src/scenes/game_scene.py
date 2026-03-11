"""GameScene — minimal stub for the in-round gameplay screen.

This scene exists to:
    1. Provide a valid target for the "START GAME" transition.
    2. Accept ESC key presses and push a PauseMenu on top.

The full implementation (physics, entities, HUD, etc.) is a separate feature.
"""
from __future__ import annotations

from typing import List

import pygame

from src.scenes.base_scene import BaseScene
from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.ui.widgets import Label
from src.constants import BG_DEEP, SCREEN_H, SCREEN_W, TEXT_SECONDARY


class GameScene(BaseScene):
    """Stub game scene: dark background + ESC → PauseMenu."""

    def __init__(
        self,
        scene_manager: SceneManager,
        settings: Settings,
        assets: AssetManager,
    ) -> None:
        self._sm = scene_manager
        self._settings = settings
        self._assets = assets

        font_main = assets.load_font(None, 24)
        font_hint = assets.load_font(None, 16)

        self._lbl_stub = Label(
            "GAME IN PROGRESS — STUB",
            font_main,
            TEXT_SECONDARY,
            (SCREEN_W // 2, SCREEN_H // 2),
        )
        self._lbl_hint = Label(
            "Press  ESC  to pause",
            font_hint,
            TEXT_SECONDARY,
            (SCREEN_W // 2, SCREEN_H // 2 + 40),
        )

    # ------------------------------------------------------------------
    # BaseScene implementation
    # ------------------------------------------------------------------

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                from src.scenes.pause_menu import PauseMenu
                self._sm.push(PauseMenu(self._sm, self._settings, self._assets))
                return  # Don't process further events this frame

    def update(self, dt: float) -> None:
        pass  # No-op until gameplay is implemented

    def render(self, screen: pygame.Surface) -> None:
        screen.fill(BG_DEEP)
        self._lbl_stub.draw(screen)
        self._lbl_hint.draw(screen)
