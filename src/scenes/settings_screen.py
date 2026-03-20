"""Settings screen -- pushed on top of the Main Menu or Pause Menu scene.

Supports two construction modes:
1. Modal (from scenes):
   SettingsScreen(scene_manager, settings, assets)
2. Standalone (from tests):
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

# ---------------------------------------------------------------------------
# FPS presets (cycle order)
# ---------------------------------------------------------------------------

_FPS_PRESETS: List[int] = [30, 60, 120, 144, 240]


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


def _fps_idx(fps: int) -> int:
    """Return the index of *fps* in _FPS_PRESETS, defaulting to the 60-fps slot."""
    try:
        return _FPS_PRESETS.index(fps)
    except ValueError:
        return 1  # 60 fps


def _fmt_action(action: str) -> str:
    """Format an action key for display: 'move_left' → 'Move Left'."""
    return action.replace("_", " ").title()


# ---------------------------------------------------------------------------
# SettingsScreen
# ---------------------------------------------------------------------------

class SettingsScreen(BaseScene):
    """Settings screen supporting both modal and standalone modes.

    All local state is snapshotted at construction time.  APPLY commits
    changes; BACK/Discard restores from the snapshot.
    """

    _PANEL_W = 640
    _PANEL_H = 640

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
        # ── Constructor-mode detection ────────────────────────────────────
        if isinstance(scene_manager_or_none, Settings):
            # Accidentally passed Settings as first positional arg
            self._sm = None
            self._settings = scene_manager_or_none
            self._assets = None
            self._audio = audio
            self._on_close = on_close
        elif settings is not None:
            # Keyword mode: SettingsScreen(settings=s, audio=a, on_close=cb)
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

        # Lazy initialisation flag
        self._initialised: bool = False

        # ── Local mutable state ──────────────────────────────────────────
        self._local_master: float = self._settings.master_volume
        self._local_music: float = self._settings.music_volume
        self._local_sfx: float = self._settings.sfx_volume
        self._local_res_idx: int = _res_idx(self._settings.resolution)
        self._local_fullscreen: bool = self._settings.fullscreen
        self._local_fps_idx: int = _fps_idx(self._settings.target_fps)

        # Key bindings: start from runtime KEY_BINDINGS, overlay with saved
        from src.constants import KEY_BINDINGS as _KB
        self._local_bindings: Dict[str, int] = dict(_KB)
        if self._settings.key_bindings:
            self._local_bindings.update(self._settings.key_bindings)

        # ── Snapshots for cancel/discard ─────────────────────────────────
        self._snap_master: float = self._local_master
        self._snap_music: float = self._local_music
        self._snap_sfx: float = self._local_sfx
        self._snap_res_idx: int = self._local_res_idx
        self._snap_fullscreen: bool = self._local_fullscreen
        self._snap_fps_idx: int = self._local_fps_idx
        self._snap_bindings: Dict[str, int] = dict(self._local_bindings)

        self._dirty: bool = False

        # ── Rebind FSM ───────────────────────────────────────────────────
        self._awaiting_action: Optional[str] = None

        # ── Notification timers ──────────────────────────────────────────
        self._conflict_timer: float = 0.0
        self._restart_timer: float = 0.0

        # ── Widget references (lazily populated) ─────────────────────────
        self._panel = None
        self._title = None
        self._sliders: list = []
        self._slider_labels: list = []
        self._lbl_sections: list = []
        self._lbl_row_labels: list = []
        self._btn_res = None
        self._btn_fs = None
        self._btn_fps = None
        self._btn_apply = None
        self._btn_back = None
        self._confirm = None
        self._key_labels: list = []          # legacy name kept for render compat
        self._btn_binding_rows: list = []
        self._lbl_binding_rows: list = []
        self._lbl_conflict = None
        self._lbl_restart = None

        # Eagerly init when constructed with a scene manager (positional mode)
        if self._sm is not None:
            self._ensure_init()

    # ------------------------------------------------------------------
    # Lazy widget init
    # ------------------------------------------------------------------

    def _ensure_init(self) -> None:
        if self._initialised:
            return
        self._initialised = True

        from src.constants import (
            ACCENT_CYAN, ACCENT_ORANGE, BORDER_DIM,
            SCREEN_H, SCREEN_W, TEXT_PRIMARY, TEXT_SECONDARY,
        )
        from src.ui.widgets import Button, ConfirmDialog, Label, Panel, Slider

        pw, ph = self._PANEL_W, self._PANEL_H
        px = (SCREEN_W - pw) // 2
        py = (SCREEN_H - ph) // 2
        cx = SCREEN_W // 2

        if self._assets is not None:
            font_title   = self._assets.load_font(None, 26)
            font_section = self._assets.load_font(None, 13)
            font_label   = self._assets.load_font(None, 14)
            font_value   = self._assets.load_font(None, 14)
            font_btn     = self._assets.load_font(None, 18)
        else:
            font_title   = pygame.font.Font(None, 26)
            font_section = pygame.font.Font(None, 13)
            font_label   = pygame.font.Font(None, 14)
            font_value   = pygame.font.Font(None, 14)
            font_btn     = pygame.font.Font(None, 18)

        self._panel = Panel(pygame.Rect(px, py, pw, ph), alpha=230)
        self._title = Label("SETTINGS", font_title, ACCENT_CYAN, (cx, py + 26))

        # ── AUDIO section ─────────────────────────────────────────────────
        ay = py + 52  # top of audio block
        self._lbl_sections.append(
            Label("AUDIO", font_section, TEXT_SECONDARY, (px + 20, ay), align="left")
        )

        slider_x = px + 210
        slider_w = pw - 240

        self._sliders = [
            Slider(pygame.Rect(slider_x, ay + 22, slider_w, 20), self._local_master, self._on_master),
            Slider(pygame.Rect(slider_x, ay + 50, slider_w, 20), self._local_music,  self._on_music),
            Slider(pygame.Rect(slider_x, ay + 78, slider_w, 20), self._local_sfx,    self._on_sfx),
        ]

        self._slider_labels = [
            Label("Master Volume", font_label, TEXT_SECONDARY, (px + 20, ay + 27), align="left"),
            Label("Music Volume",  font_label, TEXT_SECONDARY, (px + 20, ay + 55), align="left"),
            Label("SFX Volume",    font_label, TEXT_SECONDARY, (px + 20, ay + 83), align="left"),
        ]

        # ── DISPLAY section ───────────────────────────────────────────────
        dy = ay + 108  # top of display block
        self._lbl_sections.append(
            Label("DISPLAY", font_section, TEXT_SECONDARY, (px + 20, dy), align="left")
        )

        res = _RESOLUTIONS[self._local_res_idx]
        self._btn_res = Button(
            pygame.Rect(px + 210, dy + 18, 210, 30),
            f"{res[0]} \u00d7 {res[1]}", font_value, "secondary", self._cycle_resolution,
        )
        self._btn_fs = Button(
            pygame.Rect(px + 210, dy + 56, 80, 30),
            "ON" if self._local_fullscreen else "OFF", font_value, "secondary", self._toggle_fullscreen,
        )
        self._btn_fps = Button(
            pygame.Rect(px + 210, dy + 94, 100, 30),
            str(_FPS_PRESETS[self._local_fps_idx]), font_value, "secondary", self._cycle_fps,
        )

        self._lbl_row_labels = [
            Label("Resolution", font_label, TEXT_SECONDARY, (px + 20, dy + 23), align="left"),
            Label("Fullscreen",  font_label, TEXT_SECONDARY, (px + 20, dy + 61), align="left"),
            Label("FPS Cap",     font_label, TEXT_SECONDARY, (px + 20, dy + 99), align="left"),
        ]

        # ── KEY BINDINGS section ──────────────────────────────────────────
        ky = dy + 128  # top of key bindings block
        self._lbl_sections.append(
            Label("KEY BINDINGS", font_section, TEXT_SECONDARY, (px + 20, ky), align="left")
        )

        self._btn_binding_rows = []
        self._lbl_binding_rows = []

        for i, (action, keycode) in enumerate(self._local_bindings.items()):
            row_y = ky + 18 + i * 24
            self._lbl_binding_rows.append(
                Label(_fmt_action(action), font_label, TEXT_SECONDARY,
                      (px + 20, row_y + 2), align="left")
            )
            self._btn_binding_rows.append(
                Button(
                    pygame.Rect(px + 210, row_y, 180, 20),
                    pygame.key.name(keycode), font_value, "secondary",
                    self._make_rebind_callback(action, i),
                )
            )

        # Legacy alias so render() loop still works
        self._key_labels = self._lbl_binding_rows

        # ── Notification labels ───────────────────────────────────────────
        notice_y = py + ph - 68
        self._lbl_conflict = Label(
            "", font_section, ACCENT_ORANGE, (cx, notice_y), center=True,
        )
        self._lbl_restart = Label(
            "", font_section, ACCENT_ORANGE, (cx, notice_y + 14), center=True,
        )

        # ── Action buttons ────────────────────────────────────────────────
        btn_y = py + ph - 50
        self._btn_apply = Button(
            pygame.Rect(cx - 125, btn_y, 110, 36), "APPLY", font_btn, "primary", self._on_apply,
        )
        self._btn_back = Button(
            pygame.Rect(cx + 15,  btn_y, 110, 36), "BACK",  font_btn, "secondary", self._on_back,
        )

        self._confirm = ConfirmDialog(
            "Discard changes?", "Your unsaved changes will be lost.",
            font_section, font_label, font_btn,
            on_confirm=self._discard_and_pop, on_cancel=lambda: self._confirm.hide(),
        )

    def _make_rebind_callback(self, action: str, index: int):
        """Return a closure that initiates rebinding for *action*."""
        def _on_click() -> None:
            self._awaiting_action = action
            self._btn_binding_rows[index].text = "Press key\u2026"
        return _on_click

    # ------------------------------------------------------------------
    # Volume setters  (mutate settings immediately for live audio preview)
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

    def _cycle_fps(self) -> None:
        self._local_fps_idx = (self._local_fps_idx + 1) % len(_FPS_PRESETS)
        if self._btn_fps:
            self._btn_fps.text = str(_FPS_PRESETS[self._local_fps_idx])
        self._dirty = True

    # ------------------------------------------------------------------
    # Apply / Back / Discard
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        """Commit all local state to the Settings object and persist."""
        # Volume
        self._settings.master_volume = self._local_master
        self._settings.music_volume  = self._local_music
        self._settings.sfx_volume    = self._local_sfx

        # FPS
        self._settings.target_fps = _FPS_PRESETS[self._local_fps_idx]

        # Display — remember prior values for failure recovery
        old_res = (
            tuple(self._settings.resolution[:2])
            if isinstance(self._settings.resolution, (list, tuple))
            else (1280, 720)
        )
        old_fs = self._settings.fullscreen
        res = _RESOLUTIONS[self._local_res_idx]
        self._settings.resolution = list(res)
        self._settings.fullscreen = self._local_fullscreen

        # Key bindings
        self._settings.key_bindings = dict(self._local_bindings)

        # Sync runtime KEY_BINDINGS dict in-place so running systems see the change
        import src.constants as _C
        _C.KEY_BINDINGS.update(self._local_bindings)

        # Persist to disk
        try:
            self._settings.save("settings.json")
        except Exception:
            pass

        # Apply display mode
        display_changed = (
            tuple(res) != tuple(old_res)
            or self._local_fullscreen != old_fs
        )
        try:
            flags = pygame.FULLSCREEN if self._local_fullscreen else 0
            pygame.display.set_mode(res, flags)
            if display_changed and self._lbl_restart:
                self._lbl_restart.text = "Restart may be needed for full effect"
                self._restart_timer = 3.0
        except Exception:
            # Revert display settings on failure
            self._settings.resolution = list(old_res)
            self._settings.fullscreen = old_fs
            self._local_res_idx = _res_idx(old_res)
            self._local_fullscreen = old_fs
            if self._btn_res:
                self._btn_res.text = f"{old_res[0]} \u00d7 {old_res[1]}"
            if self._btn_fs:
                self._btn_fs.text = "ON" if old_fs else "OFF"
            if self._lbl_conflict:
                self._lbl_conflict.text = "Display mode not supported"
                self._conflict_timer = 2.0
            return  # Don't close; let user correct the selection

        self._close()

    def _on_back(self) -> None:
        if self._dirty:
            if self._confirm:
                from src.constants import SCREEN_W, SCREEN_H
                self._confirm.show((SCREEN_W, SCREEN_H))
            else:
                self._discard_and_pop()
        else:
            self._close()

    def _discard_and_pop(self) -> None:
        """Restore all Settings fields from the entry snapshots, then close."""
        self._settings.master_volume = self._snap_master
        self._settings.music_volume  = self._snap_music
        self._settings.sfx_volume    = self._snap_sfx
        # Restore audio immediately so there is no audible pop on cancel
        if self._audio is not None:
            self._audio.apply_volumes()
        if self._confirm:
            self._confirm.hide()
        self._close()

    def _close(self) -> None:
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
            # ── Rebind FSM: intercept the next KEYDOWN when awaiting ──────
            if self._awaiting_action is not None and event.type == pygame.KEYDOWN:
                action = self._awaiting_action
                if event.key == pygame.K_ESCAPE:
                    # Cancel rebind — restore button label, don't trigger back
                    self._awaiting_action = None
                    keys = list(self._local_bindings.keys())
                    if action in keys:
                        idx = keys.index(action)
                        if idx < len(self._btn_binding_rows):
                            self._btn_binding_rows[idx].text = pygame.key.name(
                                self._local_bindings[action]
                            )
                    return  # swallow ESC — do NOT fall through to _on_back

                # Accept new binding
                new_key = event.key
                old_key = self._local_bindings.get(action, new_key)
                self._awaiting_action = None

                # Conflict detection: swap if the key is already in use
                conflict_action: Optional[str] = None
                for other_action, other_key in self._local_bindings.items():
                    if other_action != action and other_key == new_key:
                        conflict_action = other_action
                        break

                if conflict_action is not None:
                    # Swap: the conflicting action inherits the displaced key
                    self._local_bindings[conflict_action] = old_key
                    ca_keys = list(self._local_bindings.keys())
                    ca_idx = ca_keys.index(conflict_action)
                    if ca_idx < len(self._btn_binding_rows):
                        self._btn_binding_rows[ca_idx].text = pygame.key.name(old_key)
                    if self._lbl_conflict:
                        self._lbl_conflict.text = (
                            f"'{pygame.key.name(new_key)}' swapped with"
                            f" {_fmt_action(conflict_action)}"
                        )
                        self._conflict_timer = 2.0

                # Store new binding and update row button
                self._local_bindings[action] = new_key
                act_keys = list(self._local_bindings.keys())
                act_idx = act_keys.index(action)
                if act_idx < len(self._btn_binding_rows):
                    self._btn_binding_rows[act_idx].text = pygame.key.name(new_key)
                self._dirty = True
                return  # event consumed

            # ── Confirm dialog takes priority ─────────────────────────────
            if self._confirm and self._confirm.handle_event(event):
                continue

            # ── ESC → back ────────────────────────────────────────────────
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._on_back()
                return

            # ── Widget events ─────────────────────────────────────────────
            for slider in self._sliders:
                slider.handle_event(event)
            if self._btn_res:
                self._btn_res.handle_event(event)
            if self._btn_fs:
                self._btn_fs.handle_event(event)
            if self._btn_fps:
                self._btn_fps.handle_event(event)
            if self._btn_apply:
                self._btn_apply.handle_event(event)
            if self._btn_back:
                self._btn_back.handle_event(event)
            for btn in self._btn_binding_rows:
                btn.handle_event(event)

    def update(self, dt: float) -> None:
        if self._conflict_timer > 0.0:
            self._conflict_timer = max(0.0, self._conflict_timer - dt)
            if self._conflict_timer == 0.0 and self._lbl_conflict:
                self._lbl_conflict.text = ""
        if self._restart_timer > 0.0:
            self._restart_timer = max(0.0, self._restart_timer - dt)
            if self._restart_timer == 0.0 and self._lbl_restart:
                self._lbl_restart.text = ""

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

        for lbl in self._lbl_sections:
            lbl.draw(screen)
        for lbl in self._slider_labels:
            lbl.draw(screen)
        for slider in self._sliders:
            slider.draw(screen)

        for lbl in self._lbl_row_labels:
            lbl.draw(screen)
        if self._btn_res:
            self._btn_res.draw(screen)
        if self._btn_fs:
            self._btn_fs.draw(screen)
        if self._btn_fps:
            self._btn_fps.draw(screen)

        for lbl in self._lbl_binding_rows:
            lbl.draw(screen)
        for btn in self._btn_binding_rows:
            btn.draw(screen)

        if self._lbl_conflict and self._lbl_conflict.text:
            self._lbl_conflict.draw(screen)
        if self._lbl_restart and self._lbl_restart.text:
            self._lbl_restart.draw(screen)

        if self._btn_apply:
            self._btn_apply.draw(screen)
        if self._btn_back:
            self._btn_back.draw(screen)
        if self._confirm:
            self._confirm.draw(screen)
