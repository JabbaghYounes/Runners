"""Settings screen — volume sliders, resolution cycle."""
import pygame
from typing import List, Any, Optional

from src.scenes.base_scene import BaseScene
from src.ui.widgets import Button, Slider, Label, Panel
from src.constants import SCREEN_W, SCREEN_H, BG_MID, ACCENT_CYAN, TEXT_BRIGHT, TEXT_DIM, PANEL_BG


class SettingsScreen(BaseScene):
    RESOLUTIONS = ["1280x720", "1920x1080"]

    def __init__(self, sm: Any, settings: Any, assets: Any):
        self._sm = sm
        self._settings = settings
        self._assets = assets
        self._dirty = False
        self._font: Optional[pygame.font.Font] = None
        self._res_index = (
            self.RESOLUTIONS.index(settings.resolution)
            if settings.resolution in self.RESOLUTIONS else 0
        )

        cx = SCREEN_W // 2

        self._sliders = {
            'master': Slider(pygame.Rect(cx - 150, 260, 300, 16),
                             value=settings.master_volume,
                             on_change=self._on_master),
            'music':  Slider(pygame.Rect(cx - 150, 320, 300, 16),
                             value=settings.music_volume,
                             on_change=self._on_music),
            'sfx':    Slider(pygame.Rect(cx - 150, 380, 300, 16),
                             value=settings.sfx_volume,
                             on_change=self._on_sfx),
        }

        self._buttons: List[Button] = [
            Button(pygame.Rect(cx - 80, 450, 160, 46), "CYCLE RES", 'secondary',
                   on_click=self._cycle_res),
            Button(pygame.Rect(cx - 190, 520, 180, 46), "APPLY", 'primary',
                   on_click=self._apply),
            Button(pygame.Rect(cx + 10, 520, 180, 46), "BACK", 'ghost',
                   on_click=self._back),
        ]
        self._panel = Panel(pygame.Rect(cx - 220, 180, 440, 420))

    def _on_master(self, v: float) -> None:
        self._settings.master_volume = v
        self._dirty = True

    def _on_music(self, v: float) -> None:
        self._settings.music_volume = v
        self._dirty = True

    def _on_sfx(self, v: float) -> None:
        self._settings.sfx_volume = v
        self._dirty = True

    def _cycle_res(self) -> None:
        self._res_index = (self._res_index + 1) % len(self.RESOLUTIONS)
        self._settings.resolution = self.RESOLUTIONS[self._res_index]
        self._dirty = True

    def _apply(self) -> None:
        import os
        _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        self._settings.save(os.path.join(_ROOT, 'settings.json'))
        self._dirty = False

    def _back(self) -> None:
        self._sm.pop()

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._back()
                return
            for sl in self._sliders.values():
                sl.handle_event(event)
            for btn in self._buttons:
                btn.handle_event(event)

    def update(self, dt: float) -> None:
        pass

    def render(self, screen: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.Font(None, 22)
        screen.fill(BG_MID)
        self._panel.draw(screen)

        cx = SCREEN_W // 2
        title_font = pygame.font.Font(None, 36)
        title = title_font.render("SETTINGS", True, ACCENT_CYAN)
        screen.blit(title, (cx - title.get_width() // 2, 196))

        labels = [
            (240, "Master Volume"),
            (300, "Music Volume"),
            (360, "SFX Volume"),
            (430, f"Resolution: {self._settings.resolution}"),
        ]
        for y, text in labels:
            surf = self._font.render(text, True, TEXT_BRIGHT)
            screen.blit(surf, (cx - 150, y))

        for sl in self._sliders.values():
            sl.draw(screen)

        for btn in self._buttons:
            btn.draw(screen)

        if self._dirty:
            hint = self._font.render("Unsaved changes", True, (255, 180, 60))
            screen.blit(hint, (cx - hint.get_width() // 2, 578))
