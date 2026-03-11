"""Settings screen — pushed on top of the Main Menu scene.

Exposes:
    - Master / Music / SFX volume sliders
    - Resolution cycle button (1280×720 → 1600×900 → 1920×1080)
    - Fullscreen toggle
    - Read-only key-binding display

APPLY  : writes local state to Settings, saves settings.json, resizes window, pops.
BACK   : pops immediately when nothing changed; shows ConfirmDialog if dirty.
ESC    : same as BACK.

The scene renders a dim overlay over whatever is below it in the stack (the
SceneManager renders all scenes bottom-to-top, so the Main Menu is still drawn
before this scene paints its overlay).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import pygame

from src.scenes.base_scene import BaseScene
from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.core.asset_manager import AssetManager
from src.ui.widgets import Button, ConfirmDialog, Label, Panel, Slider
from src.constants import (
    ACCENT_CYAN,
    BORDER_DIM,
    SCREEN_H,
    SCREEN_W,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

# ---------------------------------------------------------------------------
# Resolution presets (cycle order)
# ---------------------------------------------------------------------------

_RESOLUTIONS: List[Tuple[int, int]] = [(1280, 720), (1600, 900), (1920, 1080)]

# ---------------------------------------------------------------------------
# Control labels for the read-only binding grid
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


def _res_idx(resolution: List[int]) -> int:
    """Return the index of *resolution* in the preset list, or 0."""
    key = (int(resolution[0]), int(resolution[1]))
    try:
        return _RESOLUTIONS.index(key)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# SettingsScreen scene
# ---------------------------------------------------------------------------

class SettingsScreen(BaseScene):
    """Modal settings panel pushed over the Main Menu."""

    _PANEL_W = 640
    _PANEL_H = 520

    def __init__(
        self,
        scene_manager: SceneManager,
        settings: Settings,
        assets: AssetManager,
    ) -> None:
        self._sm = scene_manager
        self._settings = settings
        self._assets = assets

        # ------------------------------------------------------------------
        # Snapshot current settings into local mutable state
        # ------------------------------------------------------------------
        self._local_master: float = settings.master_volume
        self._local_music: float = settings.music_volume
        self._local_sfx: float = settings.sfx_volume
        self._local_res_idx: int = _res_idx(settings.resolution)
        self._local_fullscreen: bool = settings.fullscreen
        self._dirty: bool = False

        # ------------------------------------------------------------------
        # Layout constants
        # ------------------------------------------------------------------
        pw, ph = self._PANEL_W, self._PANEL_H
        px = (SCREEN_W - pw) // 2       # panel left
        py = (SCREEN_H - ph) // 2       # panel top
        cx = SCREEN_W // 2              # horizontal centre

        # ------------------------------------------------------------------
        # Fonts
        # ------------------------------------------------------------------
        font_title = assets.load_font(None, 26)
        font_section = assets.load_font(None, 13)
        font_label = assets.load_font(None, 14)
        font_value = assets.load_font(None, 14)
        font_btn = assets.load_font(None, 18)

        # ------------------------------------------------------------------
        # Panel
        # ------------------------------------------------------------------
        self._panel = Panel(pygame.Rect(px, py, pw, ph), alpha=230)
        self._title = Label("SETTINGS", font_title, ACCENT_CYAN, (cx, py + 26))

        # ------------------------------------------------------------------
        # AUDIO section
        # ------------------------------------------------------------------
        ay = py + 60
        self._lbl_audio = Label("AUDIO", font_section, TEXT_SECONDARY, (px + 20, ay), align="left")

        slider_x = px + 210
        slider_w = pw - 240

        self._slider_master = Slider(
            pygame.Rect(slider_x, ay + 22, slider_w, 20),
            self._local_master,
            self._on_master,
        )
        self._slider_music = Slider(
            pygame.Rect(slider_x, ay + 50, slider_w, 20),
            self._local_music,
            self._on_music,
        )
        self._slider_sfx = Slider(
            pygame.Rect(slider_x, ay + 78, slider_w, 20),
            self._local_sfx,
            self._on_sfx,
        )
        self._sliders: List[Slider] = [self._slider_master, self._slider_music, self._slider_sfx]

        self._slider_labels: List[Label] = [
            Label("Master Volume", font_label, TEXT_SECONDARY, (px + 20, ay + 27), align="left"),
            Label("Music Volume",  font_label, TEXT_SECONDARY, (px + 20, ay + 55), align="left"),
            Label("SFX Volume",    font_label, TEXT_SECONDARY, (px + 20, ay + 83), align="left"),
        ]

        # ------------------------------------------------------------------
        # DISPLAY section
        # ------------------------------------------------------------------
        dy = ay + 110
        self._lbl_display = Label("DISPLAY", font_section, TEXT_SECONDARY, (px + 20, dy), align="left")

        res = _RESOLUTIONS[self._local_res_idx]
        self._btn_res = Button(
            pygame.Rect(px + 210, dy + 18, 210, 30),
            f"{res[0]} × {res[1]}",
            font_value,
            "secondary",
            self._cycle_resolution,
        )
        self._lbl_res = Label("Resolution", font_label, TEXT_SECONDARY, (px + 20, dy + 28), align="left")

        self._btn_fs = Button(
            pygame.Rect(px + 210, dy + 56, 80, 30),
            "ON" if self._local_fullscreen else "OFF",
            font_value,
            "secondary",
            self._toggle_fullscreen,
        )
        self._lbl_fs = Label("Fullscreen", font_label, TEXT_SECONDARY, (px + 20, dy + 66), align="left")

        # ------------------------------------------------------------------
        # CONTROLS section (read-only)
        # ------------------------------------------------------------------
        ky = dy + 100
        self._lbl_controls = Label(
            "CONTROLS  (view only)", font_section, TEXT_SECONDARY, (px + 20, ky), align="left"
        )

        self._key_labels: List[Label] = []
        spacing = 20
        for i, (action, key) in enumerate(_KEY_ROWS):
            row_y = ky + 20 + i * spacing
            if row_y + 14 >= py + ph - 58:
                break  # Don't overflow into button row
            self._key_labels.append(
                Label(action, font_label, TEXT_SECONDARY, (px + 20, row_y), align="left")
            )
            self._key_labels.append(
                Label(key, font_label, TEXT_PRIMARY, (px + 200, row_y), align="left")
            )

        # ------------------------------------------------------------------
        # APPLY / BACK buttons
        # ------------------------------------------------------------------
        btn_y = py + ph - 50
        self._btn_apply = Button(
            pygame.Rect(cx - 125, btn_y, 110, 36), "APPLY", font_btn, "primary", self._on_apply
        )
        self._btn_back = Button(
            pygame.Rect(cx + 15, btn_y, 110, 36), "BACK", font_btn, "secondary", self._on_back
        )

        # ------------------------------------------------------------------
        # Confirm dialog (shown when BACK pressed with unsaved changes)
        # ------------------------------------------------------------------
        self._confirm = ConfirmDialog(
            "Discard changes?",
            "Your unsaved changes will be lost.",
            font_section,
            font_label,
            font_btn,
            on_confirm=self._discard_and_pop,
            on_cancel=lambda: self._confirm.hide(),
        )

    # ------------------------------------------------------------------
    # Slider callbacks
    # ------------------------------------------------------------------

    def _on_master(self, v: float) -> None:
        self._local_master = v
        self._dirty = True

    def _on_music(self, v: float) -> None:
        self._local_music = v
        self._dirty = True

    def _on_sfx(self, v: float) -> None:
        self._local_sfx = v
        self._dirty = True

    # ------------------------------------------------------------------
    # Display callbacks
    # ------------------------------------------------------------------

    def _cycle_resolution(self) -> None:
        self._local_res_idx = (self._local_res_idx + 1) % len(_RESOLUTIONS)
        res = _RESOLUTIONS[self._local_res_idx]
        self._btn_res.text = f"{res[0]} × {res[1]}"
        self._dirty = True

    def _toggle_fullscreen(self) -> None:
        self._local_fullscreen = not self._local_fullscreen
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
        self._settings.save("settings.json")
        flags = pygame.FULLSCREEN if self._local_fullscreen else 0
        pygame.display.set_mode(res, flags)
        self._sm.pop()

    def _on_back(self) -> None:
        if self._dirty:
            self._confirm.show((SCREEN_W, SCREEN_H))
        else:
            self._sm.pop()

    def _discard_and_pop(self) -> None:
        self._confirm.hide()
        self._sm.pop()

    # ------------------------------------------------------------------
    # BaseScene implementation
    # ------------------------------------------------------------------

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            # Confirm dialog swallows all events while active
            if self._confirm.handle_event(event):
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._on_back()
                return

            for slider in self._sliders:
                slider.handle_event(event)
            self._btn_res.handle_event(event)
            self._btn_fs.handle_event(event)
            self._btn_apply.handle_event(event)
            self._btn_back.handle_event(event)

    def update(self, dt: float) -> None:
        pass  # No animation state in settings screen

    def render(self, screen: pygame.Surface) -> None:
        # Dim the scene(s) below (already rendered by SceneManager before us)
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (0, 0))

        # Panel background
        self._panel.draw(screen)
        self._title.draw(screen)

        # Audio
        self._lbl_audio.draw(screen)
        for lbl in self._slider_labels:
            lbl.draw(screen)
        for slider in self._sliders:
            slider.draw(screen)

        # Display
        self._lbl_display.draw(screen)
        self._lbl_res.draw(screen)
        self._btn_res.draw(screen)
        self._lbl_fs.draw(screen)
        self._btn_fs.draw(screen)

        # Controls
        self._lbl_controls.draw(screen)
        for lbl in self._key_labels:
            lbl.draw(screen)

        # Action buttons
        self._btn_apply.draw(screen)
        self._btn_back.draw(screen)

        # Confirm dialog (no-ops when inactive)
        self._confirm.draw(screen)
