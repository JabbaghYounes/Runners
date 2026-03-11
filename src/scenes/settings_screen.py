"""Settings screen — audio sliders and display options."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.core.settings import Settings
    from src.systems.audio_system import AudioSystem

# Design system colours (local copies to avoid circular imports)
_BG = (10, 14, 26)
_PANEL_BG = (20, 24, 38)
_ACCENT_CYAN = (0, 245, 255)
_TEXT_MAIN = (255, 255, 255)
_BTN_NORMAL = (30, 40, 70)
_BTN_HOVER = (50, 60, 100)
_BTN_TEXT = (255, 255, 255)
_PANEL_W = 640
_PANEL_H = 480


class SettingsScreen:
    """Modal settings panel (audio sliders, display options).

    Constructor:
        settings: Settings object to read/write.
        audio: AudioSystem for live volume preview.
        on_close: Callable invoked when the screen should close.
    """

    def __init__(self, settings, audio, on_close) -> None:
        self._settings = settings
        self._audio = audio
        self._on_close = on_close
        self._sliders = []
        self._dirty = False
        self._initialized = False

    def _ensure_init(self, surface) -> None:
        if self._initialized:
            return
        import pygame
        sw, sh = surface.get_size()
        self._build_sliders(
            (sw - _PANEL_W) // 2, _PANEL_W
        )
        self._initialized = True

    def _build_sliders(self, px: int, pw: int, _=None) -> None:
        from src.ui.widgets import Slider
        import pygame

        def make_slider(label, val, on_change, y):
            return Slider(
                rect=pygame.Rect(px + 20, y, pw - 40, 36),
                min_val=0.0,
                max_val=1.0,
                initial=val,
                label=label,
                on_change=on_change,
            )

        self._sliders = [
            make_slider("Master Volume", self._settings.master_volume, self._set_master, 160),
            make_slider("Music Volume", self._settings.music_volume, self._set_music, 210),
            make_slider("SFX Volume", self._settings.sfx_volume, self._set_sfx, 260),
        ]

    def _set_master(self, val: float) -> None:
        self._settings.master_volume = val
        self._dirty = True
        if self._audio:
            self._audio.apply_volumes()

    def _set_music(self, val: float) -> None:
        self._settings.music_volume = val
        self._dirty = True
        if self._audio:
            self._audio.apply_volumes()

    def _set_sfx(self, val: float) -> None:
        self._settings.sfx_volume = val
        self._dirty = True

    def handle_events(self, events) -> None:
        import pygame
        for evt in events:
            if evt.type == pygame.KEYDOWN and evt.key == pygame.K_ESCAPE:
                self._on_close()
                return
            for slider in self._sliders:
                slider.handle_event(evt)

    def update(self, dt: float) -> None:
        pass

    def render(self, screen) -> None:
        import pygame
        self._ensure_init(screen)
        sw, sh = screen.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        px = (sw - _PANEL_W) // 2
        py = (sh - _PANEL_H) // 2
        pygame.draw.rect(screen, _PANEL_BG, (px, py, _PANEL_W, _PANEL_H), border_radius=8)
        pygame.draw.rect(screen, _ACCENT_CYAN, (px, py, _PANEL_W, _PANEL_H), 1, border_radius=8)
        font = pygame.font.SysFont("monospace", 24, bold=True)
        title_surf = font.render("SETTINGS", True, _ACCENT_CYAN)
        screen.blit(title_surf, (px + 20, py + 20))
        font_sm = pygame.font.SysFont("monospace", 14)
        for slider in self._sliders:
            slider.render(screen, font_sm)
        btn_w, btn_h = 120, 36
        apply_x = px + _PANEL_W - btn_w * 2 - 30
        apply_y = py + _PANEL_H - btn_h - 20
        apply_surf = font.render("APPLY", True, _BTN_TEXT)
        pygame.draw.rect(screen, _BTN_NORMAL, (apply_x, apply_y, btn_w, btn_h), border_radius=4)
        screen.blit(apply_surf, (apply_x + 10, apply_y + 8))
        close_x = apply_x + btn_w + 10
        close_surf = font.render("BACK", True, _BTN_TEXT)
        pygame.draw.rect(screen, _BTN_NORMAL, (close_x, apply_y, btn_w, btn_h), border_radius=4)
        screen.blit(close_surf, (close_x + 10, apply_y + 8))
