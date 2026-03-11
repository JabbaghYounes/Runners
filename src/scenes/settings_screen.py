"""Settings screen -- pushed on top of the Main Menu scene.

Supports two construction modes:
1. Modal (from scenes/test_settings_screen.py):
   SettingsScreen(scene_manager, settings, assets)
2. Standalone (from test_settings_screen.py):
   SettingsScreen(settings=settings, audio=audio, on_close=callback)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pygame

from src.core.settings import Settings
from src.scenes.base_scene import BaseScene

# ---------------------------------------------------------------------------
# Resolution presets (cycle order)
# ---------------------------------------------------------------------------

_RESOLUTIONS: List[Tuple[int, int]] = [(1280, 720), (1600, 900), (1920, 1080)]


def _res_idx(resolution) -> int:
    """Return the index of *resolution* in the preset list, or 0."""
    if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
        key = (int(resolution[0]), int(resolution[1]))
    else:
        key = (1280, 720)
    try:
        return _RESOLUTIONS.index(key)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Key binding labels
# ---------------------------------------------------------------------------

_KEY_ROWS: List[Tuple[str, str]] = [
    ("Move", "W  A  S  D"),
    ("Jump", "Space"),
    ("Crouch", "Ctrl"),
    ("Sprint", "Shift"),
    ("Slide", "C"),
    ("Interact", "E"),
    ("Inventory", "Tab"),
    ("Map", "M"),
    ("Pause", "Esc"),
]


# ---------------------------------------------------------------------------
# SettingsScreen
# ---------------------------------------------------------------------------

class SettingsScreen(BaseScene):
    """Settings screen supporting both modal and standalone modes."""

    _PANEL_W = 640
    _PANEL_H = 520

    def __init__(
        self,
        scene_manager_or_none=None,
        settings_pos: "Settings | None" = None,
        assets_pos=None,
        *,
        settings: "Settings | None" = None,
        audio: Any = None,
        on_close: Any = None,
    ) -> None:
        # Determine which calling convention was used
        if isinstance(scene_manager_or_none, Settings):
            # Called as SettingsScreen(settings=Settings(), audio=..., on_close=...)
            # where settings was passed positionally by mistake - unlikely but handle
            self._sm = None
            self._settings = scene_manager_or_none
            self._assets = None
            self._audio = audio
            self._on_close = on_close
        elif settings is not None:
            # Keyword-only mode: SettingsScreen(settings=s, audio=a, on_close=cb)
            self._sm = None
            self._settings = settings
            self._assets = None
            self._audio = audio
            self._on_close = on_close
        else:
            # Positional mode: SettingsScreen(sm, settings, assets)
            self._sm = scene_manager_or_none
            self._settings = settings_pos or Settings()
            self._assets = assets_pos
            self._audio = audio
            self._on_close = on_close

        # Lazy initialisation flag (pygame widgets only built on first render)
        self._initialised: bool = False

        # Local mutable state (snapshots)
        self._local_master: float = self._settings.master_volume
        self._local_music: float = self._settings.music_volume
        self._local_sfx: float = self._settings.sfx_volume
        self._local_res_idx: int = _res_idx(self._settings.resolution)
        self._local_fullscreen: bool = self._settings.fullscreen
        self._dirty: bool = False

        # Widgets (lazily built)
        self._panel = None
        self._title = None
        self._sliders: list = []
        self._slider_labels: list = []
        self._btn_res = None
        self._btn_fs = None
        self._btn_apply = None
        self._btn_back = None
        self._confirm = None
        self._key_labels: list = []

        # Eagerly init widgets when constructed with a scene manager (positional mode),
        # since tests may access widgets immediately. Keyword mode stays lazy.
        if self._sm is not None:
            self._ensure_init()

    # ------------------------------------------------------------------
    # Lazy widget init (only when render() is called the first time)
    # ------------------------------------------------------------------

    def _ensure_init(self) -> None:
        if self._initialised:
            return
        self._initialised = True

        from src.constants import (
            ACCENT_CYAN, BORDER_DIM, SCREEN_H, SCREEN_W,
            TEXT_PRIMARY, TEXT_SECONDARY,
        )
        from src.ui.widgets import Button, ConfirmDialog, Label, Panel, Slider

        pw, ph = self._PANEL_W, self._PANEL_H
        px = (SCREEN_W - pw) // 2
        py = (SCREEN_H - ph) // 2
        cx = SCREEN_W // 2

        if self._assets is not None:
            font_title = self._assets.load_font(None, 26)
            font_section = self._assets.load_font(None, 13)
            font_label = self._assets.load_font(None, 14)
            font_value = self._assets.load_font(None, 14)
            font_btn = self._assets.load_font(None, 18)
        else:
            font_title = pygame.font.Font(None, 26)
            font_section = pygame.font.Font(None, 13)
            font_label = pygame.font.Font(None, 14)
            font_value = pygame.font.Font(None, 14)
            font_btn = pygame.font.Font(None, 18)

        self._panel = Panel(pygame.Rect(px, py, pw, ph), alpha=230)
        self._title = Label("SETTINGS", font_title, ACCENT_CYAN, (cx, py + 26))

        ay = py + 60
        slider_x = px + 210
        slider_w = pw - 240

        self._sliders = [
            Slider(pygame.Rect(slider_x, ay + 22, slider_w, 20), self._local_master, self._on_master),
            Slider(pygame.Rect(slider_x, ay + 50, slider_w, 20), self._local_music, self._on_music),
            Slider(pygame.Rect(slider_x, ay + 78, slider_w, 20), self._local_sfx, self._on_sfx),
        ]

        self._slider_labels = [
            Label("Master Volume", font_label, TEXT_SECONDARY, (px + 20, ay + 27), align="left"),
            Label("Music Volume",  font_label, TEXT_SECONDARY, (px + 20, ay + 55), align="left"),
            Label("SFX Volume",    font_label, TEXT_SECONDARY, (px + 20, ay + 83), align="left"),
        ]

        dy = ay + 110
        res = _RESOLUTIONS[self._local_res_idx]
        self._btn_res = Button(
            pygame.Rect(px + 210, dy + 18, 210, 30),
            f"{res[0]} \u00d7 {res[1]}", font_value, "secondary", self._cycle_resolution,
        )
        self._btn_fs = Button(
            pygame.Rect(px + 210, dy + 56, 80, 30),
            "ON" if self._local_fullscreen else "OFF", font_value, "secondary", self._toggle_fullscreen,
        )

        btn_y = py + ph - 50
        self._btn_apply = Button(
            pygame.Rect(cx - 125, btn_y, 110, 36), "APPLY", font_btn, "primary", self._on_apply,
        )
        self._btn_back = Button(
            pygame.Rect(cx + 15, btn_y, 110, 36), "BACK", font_btn, "secondary", self._on_back,
        )

        self._confirm = ConfirmDialog(
            "Discard changes?", "Your unsaved changes will be lost.",
            font_section, font_label, font_btn,
            on_confirm=self._discard_and_pop, on_cancel=lambda: self._confirm.hide(),
        )

    # ------------------------------------------------------------------
    # Volume setters (used by both slider callbacks and test code)
    # ------------------------------------------------------------------

    def _set_master(self, v: float) -> None:
        self._local_master = v
        self._settings.volume_master = v
        self._dirty = True
        if self._audio is not None:
            self._audio.apply_volumes()

    def _set_music(self, v: float) -> None:
        self._local_music = v
        self._settings.volume_music = v
        self._dirty = True
        if self._audio is not None:
            self._audio.apply_volumes()

    def _set_sfx(self, v: float) -> None:
        self._local_sfx = v
        self._settings.volume_sfx = v
        self._dirty = True
        if self._audio is not None:
            self._audio.apply_volumes()

    # Slider callbacks
    def _on_master(self, v: float) -> None:
        self._set_master(v)

    def _on_music(self, v: float) -> None:
        self._set_music(v)

    def _on_sfx(self, v: float) -> None:
        self._set_sfx(v)

    # ------------------------------------------------------------------
    # Display callbacks
    # ------------------------------------------------------------------

    def _cycle_resolution(self) -> None:
        self._local_res_idx = (self._local_res_idx + 1) % len(_RESOLUTIONS)
        res = _RESOLUTIONS[self._local_res_idx]
        if self._btn_res:
            self._btn_res.text = f"{res[0]} \u00d7 {res[1]}"
        self._dirty = True

    def _toggle_fullscreen(self) -> None:
        self._local_fullscreen = not self._local_fullscreen
        if self._btn_fs:
            self._btn_fs.text = "ON" if self._local_fullscreen else "OFF"
        self._dirty = True

    # ------------------------------------------------------------------
    # Apply / Back / Discard
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        self._settings.master_volume = self._local_master
        self._settings.music_volume = self._local_music
        self._settings.sfx_volume = self._local_sfx
        res = _RESOLUTIONS[self._local_res_idx]
        self._settings.resolution = list(res)
        self._settings.fullscreen = self._local_fullscreen
        try:
            self._settings.save("settings.json")
        except Exception:
            pass
        try:
            flags = pygame.FULLSCREEN if self._local_fullscreen else 0
            pygame.display.set_mode(res, flags)
        except Exception:
            pass
        if self._sm:
            self._sm.pop()
        elif self._on_close:
            self._on_close()

    def _on_back(self) -> None:
        if self._dirty:
            if self._confirm:
                from src.constants import SCREEN_W, SCREEN_H
                self._confirm.show((SCREEN_W, SCREEN_H))
            else:
                self._discard_and_pop()
        else:
            if self._sm:
                self._sm.pop()
            elif self._on_close:
                self._on_close()

    def _discard_and_pop(self) -> None:
        if self._confirm:
            self._confirm.hide()
        if self._sm:
            self._sm.pop()
        elif self._on_close:
            self._on_close()

    # ------------------------------------------------------------------
    # BaseScene implementation
    # ------------------------------------------------------------------

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        self._ensure_init()
        for event in events:
            if self._confirm and self._confirm.handle_event(event):
                continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._on_back()
                return
            for slider in self._sliders:
                slider.handle_event(event)
            if self._btn_res:
                self._btn_res.handle_event(event)
            if self._btn_fs:
                self._btn_fs.handle_event(event)
            if self._btn_apply:
                self._btn_apply.handle_event(event)
            if self._btn_back:
                self._btn_back.handle_event(event)

    def update(self, dt: float) -> None:
        pass

    def render(self, screen: pygame.Surface) -> None:
        self._ensure_init()
        from src.constants import SCREEN_W, SCREEN_H

        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (0, 0))

        if self._panel:
            self._panel.draw(screen)
        if self._title:
            self._title.draw(screen)
        for lbl in self._slider_labels:
            lbl.draw(screen)
        for slider in self._sliders:
            slider.draw(screen)
        if self._btn_res:
            self._btn_res.draw(screen)
        if self._btn_fs:
            self._btn_fs.draw(screen)
        if self._btn_apply:
            self._btn_apply.draw(screen)
        if self._btn_back:
            self._btn_back.draw(screen)
        if self._confirm:
            self._confirm.draw(screen)
        for lbl in self._key_labels:
            lbl.draw(screen)
