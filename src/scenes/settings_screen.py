"""SettingsScreen — in-game settings overlay.

Renders three volume sliders (Master / Music / SFX) and an [APPLY] button.
Volume changes are applied immediately to :class:`AudioSystem`; [APPLY]
persists them to ``settings.json``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.core.settings import Settings
    from src.systems.audio_system import AudioSystem


_BG           = (10, 15, 28)
_PANEL_BG     = (18, 26, 45)
_ACCENT_CYAN  = (0, 210, 200)
_TEXT_MAIN    = (200, 220, 240)
_BTN_NORMAL   = (30, 50, 80)
_BTN_HOVER    = (50, 90, 130)
_BTN_TEXT     = (0, 210, 200)

_PANEL_W = 480
_PANEL_H = 320


class SettingsScreen:
    """Standalone settings scene/overlay.

    Parameters
    ----------
    settings:
        Live :class:`Settings` instance (mutated in place on slider drag).
    audio:
        Live :class:`AudioSystem` — :meth:`apply_volumes` called on every
        volume change.
    on_close:
        Optional callable invoked when the player closes the settings panel.
    """

    def __init__(
        self,
        settings: "Settings",
        audio: "AudioSystem",
        on_close: Optional[callable] = None,  # type: ignore[type-arg]
    ) -> None:
        self._settings = settings
        self._audio = audio
        self._on_close = on_close
        self._font: Optional[object] = None
        self._btn_font: Optional[object] = None
        self._sliders: list = []
        self._apply_hover = False
        self._close_hover = False
        self._initialised = False

    # ------------------------------------------------------------------
    # Lazy pygame initialisation (avoids import at module level)
    # ------------------------------------------------------------------

    def _ensure_init(self, surface: object) -> None:
        if self._initialised:
            return
        try:
            import pygame
            self._font = pygame.font.SysFont("monospace", 16)
            self._btn_font = pygame.font.SysFont("monospace", 18, bold=True)
            sw, sh = surface.get_size()  # type: ignore[union-attr]
            self._panel_rect = (
                (sw - _PANEL_W) // 2,
                (sh - _PANEL_H) // 2,
                _PANEL_W,
                _PANEL_H,
            )
            self._build_sliders()
            self._initialised = True
        except Exception:
            pass

    def _build_sliders(self) -> None:
        from src.ui.widgets import Slider
        px, py, pw, _ = self._panel_rect
        s = self._settings

        slider_w = pw - 80
        slider_x = px + 40
        slider_h = 12
        gap = 70

        def make_slider(idx: int, label: str, initial: float, setter) -> "Slider":
            y = py + 60 + idx * gap
            return Slider(
                rect=(slider_x, y, slider_w, slider_h),
                min_val=0.0,
                max_val=1.0,
                initial=initial,
                label=label,
                on_change=setter,
            )

        self._sliders = [
            make_slider(0, "Master Volume", s.volume_master, self._set_master),
            make_slider(1, "Music Volume",  s.volume_music,  self._set_music),
            make_slider(2, "SFX Volume",    s.volume_sfx,    self._set_sfx),
        ]

    # Volume setters (called by sliders on drag)

    def _set_master(self, val: float) -> None:
        self._settings.volume_master = val
        self._audio.apply_volumes()

    def _set_music(self, val: float) -> None:
        self._settings.volume_music = val
        self._audio.apply_volumes()

    def _set_sfx(self, val: float) -> None:
        self._settings.volume_sfx = val
        self._audio.apply_volumes()

    # ------------------------------------------------------------------
    # Scene protocol
    # ------------------------------------------------------------------

    def handle_events(self, events: list) -> None:
        for slider in self._sliders:
            for evt in events:
                slider.handle_event(evt)

        try:
            import pygame
            for evt in events:
                if evt.type == pygame.MOUSEBUTTONDOWN and evt.button == 1:
                    if hasattr(self, "_apply_rect") and self._apply_rect.collidepoint(evt.pos):
                        self._settings.save()
                    if hasattr(self, "_close_rect") and self._close_rect.collidepoint(evt.pos):
                        if self._on_close:
                            self._on_close()
                elif evt.type == pygame.MOUSEMOTION:
                    self._apply_hover = (
                        hasattr(self, "_apply_rect")
                        and self._apply_rect.collidepoint(evt.pos)
                    )
                    self._close_hover = (
                        hasattr(self, "_close_rect")
                        and self._close_rect.collidepoint(evt.pos)
                    )
                elif evt.type == pygame.KEYDOWN and evt.key == pygame.K_ESCAPE:
                    if self._on_close:
                        self._on_close()
        except Exception:
            pass

    def update(self, dt: float) -> None:  # noqa: ARG002
        pass

    def render(self, screen: object) -> None:
        self._ensure_init(screen)
        try:
            import pygame

            sw, sh = screen.get_size()  # type: ignore[union-attr]

            # Dim overlay
            overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            # Panel
            px, py, pw, ph = self._panel_rect
            pygame.draw.rect(screen, _PANEL_BG, self._panel_rect, border_radius=8)
            pygame.draw.rect(screen, _ACCENT_CYAN, self._panel_rect, 2, border_radius=8)

            # Title
            title_surf = self._btn_font.render("SETTINGS", True, _ACCENT_CYAN)  # type: ignore[union-attr]
            screen.blit(title_surf, (px + (pw - title_surf.get_width()) // 2, py + 16))

            # Sliders
            for slider in self._sliders:
                slider.render(screen, self._font)

            # [APPLY] button
            btn_w, btn_h = 120, 36
            apply_x = px + pw - btn_w - 16
            apply_y = py + ph - btn_h - 16
            self._apply_rect = pygame.Rect(apply_x, apply_y, btn_w, btn_h)
            pygame.draw.rect(
                screen,
                _BTN_HOVER if self._apply_hover else _BTN_NORMAL,
                self._apply_rect, border_radius=4,
            )
            pygame.draw.rect(screen, _ACCENT_CYAN, self._apply_rect, 1, border_radius=4)
            apply_surf = self._btn_font.render("APPLY", True, _BTN_TEXT)  # type: ignore[union-attr]
            screen.blit(
                apply_surf,
                (apply_x + (btn_w - apply_surf.get_width()) // 2,
                 apply_y + (btn_h - apply_surf.get_height()) // 2),
            )

            # [CLOSE] button
            close_x = px + 16
            self._close_rect = pygame.Rect(close_x, apply_y, btn_w, btn_h)
            pygame.draw.rect(
                screen,
                _BTN_HOVER if self._close_hover else _BTN_NORMAL,
                self._close_rect, border_radius=4,
            )
            pygame.draw.rect(screen, _ACCENT_CYAN, self._close_rect, 1, border_radius=4)
            close_surf = self._btn_font.render("CLOSE", True, _BTN_TEXT)  # type: ignore[union-attr]
            screen.blit(
                close_surf,
                (close_x + (btn_w - close_surf.get_width()) // 2,
                 apply_y + (btn_h - close_surf.get_height()) // 2),
            )
        except Exception:
            pass
