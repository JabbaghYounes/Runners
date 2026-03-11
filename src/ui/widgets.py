"""Reusable UI widget primitives for Runners.

Widgets:
    Slider      -- horizontal drag slider (used by SettingsScreen)
    Panel       -- rounded-rect background panel
    Label       -- text surface at a given position
    ProgressBar -- filled progress bar with optional value/max overlay
    IconSlot    -- icon display slot for HUD
    Button      -- interactive button with hover/press states
    ConfirmDialog -- modal two-button confirmation overlay
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

import pygame

from src.constants import (
    ACCENT_CYAN,
    BG_DEEP,
    BG_PANEL,
    BORDER_DIM,
    BORDER_BRIGHT,
    DANGER_RED,
    PANEL_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_BRIGHT,
    TEXT_DIM,
    ACCENT_GREEN,
    ACCENT_RED,
)


# ── Internal colour constants used by Slider ──────────────────────────────
_BG_PANEL  = (20,  24,  38)
_TRACK_CLR = (42,  48,  80)
_THUMB_CLR = (0,  245, 255)
_LABEL_CLR = (154, 163, 192)
_BORDER_CLR = (42,  48,  80)


# ---------------------------------------------------------------------------
# Slider
# ---------------------------------------------------------------------------
class Slider:
    """Horizontal drag slider.

    Supports two constructor styles:
    1. New (from HUD feature): Slider(rect=tuple, min_val, max_val, initial, label, on_change)
    2. Old (from settings feature): Slider(rect=pygame.Rect, value, on_change, *, min_val, max_val, initial)
    """

    HANDLE_RADIUS = 8
    TRACK_HEIGHT = 4

    def __init__(
        self,
        rect=None,
        value: float = 0.5,
        on_change: "Callable[[float], None] | None" = None,
        *,
        min_val: float = 0.0,
        max_val: float = 1.0,
        initial: "float | None" = None,
        label: str = '',
    ) -> None:
        self.rect = rect if rect is not None else (0, 0, 200, 20)
        self.min_val = min_val
        self.max_val = max_val
        self.label = label
        self.on_change = on_change
        self._dragging: bool = False

        # Determine initial value
        init_val = initial if initial is not None else value
        self.value: float = max(min_val, min(max_val, init_val))

    # ── Track geometry (work with both tuple and pygame.Rect) ─────────

    @property
    def _track_x(self) -> int:
        if isinstance(self.rect, (tuple, list)):
            return self.rect[0]
        return self.rect.x

    @property
    def _track_y(self) -> int:
        if isinstance(self.rect, (tuple, list)):
            return self.rect[1]
        return self.rect.y

    @property
    def _track_w(self) -> int:
        if isinstance(self.rect, (tuple, list)):
            return self.rect[2]
        return self.rect.width

    @property
    def _track_h(self) -> int:
        if isinstance(self.rect, (tuple, list)):
            return self.rect[3]
        return self.rect.height

    @property
    def _track_centery(self) -> int:
        return self._track_y + self._track_h // 2

    def _value_to_px(self, frac: "float | None" = None) -> int:
        """Map a fractional position (0-1) to a pixel x-coordinate on the track."""
        if frac is None:
            rng = self.max_val - self.min_val
            frac = (self.value - self.min_val) / max(rng, 1e-9) if rng != 0 else 0
        return self._track_x + int(frac * self._track_w)

    def _px_to_value(self, px: int) -> float:
        """Map a pixel x-coordinate to a value within [min_val, max_val]."""
        frac = (px - self._track_x) / max(self._track_w, 1)
        frac = max(0.0, min(1.0, frac))
        return self.min_val + frac * (self.max_val - self.min_val)

    def _set_from_px(self, px: int) -> None:
        new_val = self._px_to_value(px)
        if new_val == self.value:
            return
        self.value = new_val
        if self.on_change:
            self.on_change(self.value)

    def _set_value_from_x(self, mouse_x: int) -> None:
        """Legacy alias used by old API."""
        self._set_from_px(mouse_x)

    def _update_value(self, mx: int) -> None:
        """Legacy alias."""
        self._set_from_px(mx)

    def _handle_center(self) -> Tuple[int, int]:
        x = self._value_to_px()
        y = self._track_centery
        return (x, y)

    @property
    def normalized(self) -> float:
        return (self.value - self.min_val) / max(0.001, self.max_val - self.min_val)

    def _thumb_rect(self, pygame_mod) -> "pygame.Rect":
        cx = self._value_to_px()
        th = self._track_h
        return pygame_mod.Rect(cx - th // 2, self._track_y, th, th)

    def handle_event(self, event: "pygame.event.Event", pygame_mod=None) -> bool:
        """Handle mouse events. Accepts optional pygame module for new API."""
        pg = pygame_mod or pygame
        if event.type == pg.MOUSEBUTTONDOWN and getattr(event, 'button', 0) == 1:
            # Check if clicking on handle or track
            hx, hy = self._handle_center()
            pos = getattr(event, 'pos', (0, 0))
            dist = ((pos[0] - hx) ** 2 + (pos[1] - hy) ** 2) ** 0.5
            hit_handle = dist <= self.HANDLE_RADIUS + 6

            # Track hit test
            track_top = self._track_y - 8
            track_bottom = self._track_y + self._track_h + 8
            hit_track = (self._track_x <= pos[0] <= self._track_x + self._track_w and
                         track_top <= pos[1] <= track_bottom)

            if hit_handle or hit_track:
                self._dragging = True
                self._set_from_px(pos[0])
                return True
        elif event.type == pg.MOUSEBUTTONUP and getattr(event, 'button', 0) == 1:
            if self._dragging:
                self._dragging = False
                return True
        elif event.type == pg.MOUSEMOTION and self._dragging:
            self._set_from_px(event.pos[0])
            return True
        return False

    def render(self, surface, font, pygame_mod) -> None:
        """Render slider (new-style API from HUD feature)."""
        x, y, w, h = (self._track_x, self._track_y, self._track_w, self._track_h)
        cx = self._value_to_px()
        fill_w = cx - x

        # Track background
        pygame_mod.draw.rect(surface, _TRACK_CLR, (x, y, w, h), border_radius=h // 2)
        # Filled portion
        if fill_w > 0:
            pygame_mod.draw.rect(surface, _THUMB_CLR, (x, y, fill_w, h), border_radius=h // 2)
        # Thumb
        thumb = self._thumb_rect(pygame_mod)
        pygame_mod.draw.ellipse(surface, _THUMB_CLR, thumb)

        # Label
        if font and self.label:
            pct = (self.value - self.min_val) / max(self.max_val - self.min_val, 1e-9)
            text = f'{self.label}: {int(pct * 100)}%'
            surf = font.render(text, True, _LABEL_CLR)
            surface.blit(surf, (x, y - surf.get_height() - 2))

    def draw(self, surface: pygame.Surface) -> None:
        """Draw slider (old-style API)."""
        ty = self._track_centery - self.TRACK_HEIGHT // 2
        track = pygame.Rect(self._track_x, ty, self._track_w, self.TRACK_HEIGHT)
        pygame.draw.rect(surface, BORDER_DIM, track, border_radius=2)

        fill_w = int(self.normalized * self._track_w)
        if fill_w > 0:
            fill = pygame.Rect(self._track_x, ty, fill_w, self.TRACK_HEIGHT)
            pygame.draw.rect(surface, ACCENT_CYAN, fill, border_radius=2)

        hx, hy = self._handle_center()
        pygame.draw.circle(surface, ACCENT_CYAN, (hx, hy), self.HANDLE_RADIUS)
        pygame.draw.circle(surface, BG_DEEP, (hx, hy), self.HANDLE_RADIUS - 3)


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
class Panel:
    """Rounded-rect background panel."""

    def __init__(
        self,
        rect: "pygame.Rect" = None,
        bg_color=None,
        border_color: "Tuple[int, int, int] | None" = None,
        border_width: int = 1,
        corner_radius: int = 6,
        alpha: int = 220,
        # Legacy kwargs
        border_radius: int = 6,
        radius: int = 6,
    ) -> None:
        self.rect = rect or pygame.Rect(0, 0, 100, 100)
        self.bg_color = bg_color or BG_PANEL
        self.border_color: Tuple[int, int, int] = border_color or BORDER_DIM
        self.border_width = border_width
        self.alpha = alpha

        # Resolve corner_radius from multiple possible kwargs
        if corner_radius != 6:
            self.corner_radius = corner_radius
        elif border_radius != 6:
            self.corner_radius = border_radius
        elif radius != 6:
            self.corner_radius = radius
        else:
            self.corner_radius = 6

        # Legacy aliases
        self.radius = self.corner_radius

    def draw(self, surface: pygame.Surface) -> None:
        panel_surf = pygame.Surface(
            (self.rect.width, self.rect.height), pygame.SRCALPHA
        )
        r, g, b = self.bg_color[:3]
        pygame.draw.rect(
            panel_surf,
            (r, g, b, self.alpha),
            panel_surf.get_rect(),
            border_radius=self.corner_radius,
        )
        surface.blit(panel_surf, self.rect.topleft)
        # Border
        if self.border_width > 0:
            br, bg_, bb = self.border_color[:3]
            pygame.draw.rect(
                surface,
                (br, bg_, bb, 255),
                self.rect,
                width=self.border_width,
                border_radius=self.corner_radius,
            )


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------
class Label:
    """Text label with optional neon glow effect.

    Supports multiple constructor signatures:
    1. Label(text, font, color, pos, anchor=)      -- new HUD style
    2. Label(text, x, y, font=, color=)             -- old style
    3. Label(text, font_obj, color_or_y, pos_tuple)  -- mixed
    """

    def __init__(
        self,
        text: str,
        font_or_x=None,
        color_or_y=None,
        pos_or_font=None,
        *,
        pos: "Tuple[int, int] | None" = None,
        font: "pygame.font.Font | None" = None,
        color=TEXT_PRIMARY,
        x: int = 0,
        y: int = 0,
        align: str = "center",
        anchor: str = "topleft",
        center: bool = False,
        glow: bool = False,
    ) -> None:
        self.text = text
        self.glow = glow

        # Determine the anchor from both 'align' and 'anchor' params
        if anchor != "topleft":
            self.anchor = anchor
        elif align != "center":
            # Map old 'align' to 'anchor'
            if align == "left":
                self.anchor = "midleft"
            elif align == "right":
                self.anchor = "midright"
            else:
                self.anchor = "center"
        else:
            self.anchor = "topleft"

        # Support multiple constructor signatures
        if isinstance(font_or_x, pygame.font.Font):
            self.font = font_or_x
            self.color = color_or_y if color_or_y is not None else color
            if isinstance(pos_or_font, tuple):
                self.pos = pos_or_font
            elif pos is not None:
                self.pos = pos
            else:
                self.pos = (x, y)
        elif isinstance(font_or_x, (int, float)):
            self.pos = (int(font_or_x), int(color_or_y) if color_or_y is not None else y)
            self.font = (
                pos_or_font
                if isinstance(pos_or_font, pygame.font.Font)
                else (font or pygame.font.Font(None, 20))
            )
            self.color = color
        else:
            self.font = font or pygame.font.Font(None, 20)
            self.color = color
            self.pos = pos or (x, y)

        self.center = center
        self._cached_surf: "pygame.Surface | None" = None
        self._cached_text: str = ""

    def _rendered(self) -> pygame.Surface:
        if self._cached_surf is None or self._cached_text != self.text:
            self._cached_surf = self.font.render(self.text, True, self.color)
            self._cached_text = self.text
        return self._cached_surf

    def set_text(self, text: str) -> None:
        self.text = text
        self._cached_surf = None

    def draw(self, surface: pygame.Surface) -> None:
        surf = self._rendered()
        rect = surf.get_rect()

        # Set position using the anchor attribute
        try:
            setattr(rect, self.anchor, self.pos)
        except (AttributeError, ValueError):
            rect.topleft = self.pos

        if self.center:
            rect.center = self.pos

        if self.glow:
            glow_surf = self.font.render(self.text, True, self.color)
            glow_surf.set_alpha(70)
            offsets = [(-3, 0), (3, 0), (0, -3), (0, 3)]
            for dx, dy in offsets:
                surface.blit(glow_surf, (rect.x + dx, rect.y + dy))

        surface.blit(surf, rect)


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------
_BUTTON_STYLES: dict = {
    "primary": {
        "bg":       ACCENT_CYAN,
        "bg_hover": (0, 210, 220),
        "bg_press": (0, 175, 190),
        "text":     BG_DEEP,
        "border":   ACCENT_CYAN,
        "hover":    (0, 210, 220),
    },
    "secondary": {
        "bg":       BORDER_DIM,
        "bg_hover": (55, 65, 105),
        "bg_press": (40, 50, 85),
        "text":     TEXT_PRIMARY,
        "border":   BORDER_DIM,
        "hover":    (55, 65, 105),
    },
    "danger": {
        "bg":       (75, 10, 18),
        "bg_hover": (120, 22, 38),
        "bg_press": (100, 16, 28),
        "text":     DANGER_RED,
        "border":   DANGER_RED,
        "hover":    (120, 22, 38),
    },
    "ghost": {
        "bg":       (0, 0, 0, 0),
        "bg_hover": (40, 60, 80),
        "bg_press": (30, 50, 70),
        "text":     ACCENT_CYAN,
        "border":   (0, 0, 0, 0),
        "hover":    (40, 60, 80),
    },
}


class Button:
    """Interactive button with hover / press state tracking."""

    STYLES = _BUTTON_STYLES

    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        font_or_style=None,
        style_or_onclick=None,
        on_click: "Callable[[], None] | None" = None,
        *,
        font: "pygame.font.Font | None" = None,
        style: str = "secondary",
    ) -> None:
        self.rect = rect
        self.text = text

        # Support multiple call signatures:
        # Button(rect, text, font, style, on_click)  -- new style
        # Button(rect, text, style, on_click)         -- old style
        if isinstance(font_or_style, pygame.font.Font):
            self.font = font_or_style
            if isinstance(style_or_onclick, str):
                self.style = style_or_onclick
                self.on_click = on_click
            elif callable(style_or_onclick):
                self.style = style
                self.on_click = style_or_onclick
            else:
                self.style = style
                self.on_click = on_click
        elif isinstance(font_or_style, str):
            self.style = font_or_style
            self.font = font or pygame.font.Font(None, 22)
            self.on_click = style_or_onclick if callable(style_or_onclick) else on_click
        else:
            self.font = font or pygame.font.Font(None, 22)
            self.style = style
            self.on_click = on_click

        self._hovered: bool = False
        self._pressed: bool = False
        self._focused: bool = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            pos = getattr(event, "pos", None)
            if pos is not None:
                self._hovered = self.rect.collidepoint(pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", None) == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and getattr(event, "button", None) == 1:
            was_pressed = self._pressed
            self._pressed = False
            if was_pressed and self.rect.collidepoint(event.pos):
                if self.on_click:
                    self.on_click()
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        sdata = _BUTTON_STYLES.get(self.style, _BUTTON_STYLES["secondary"])

        if self._pressed:
            bg = sdata.get("bg_press", sdata["bg"])
        elif self._hovered:
            bg = sdata.get("bg_hover", sdata.get("hover", sdata["bg"]))
        else:
            bg = sdata["bg"]

        if isinstance(bg, tuple) and len(bg) == 4 and bg[3] == 0:
            pass
        else:
            pygame.draw.rect(surface, bg, self.rect, border_radius=4)

        border = ACCENT_CYAN if (self._hovered or self._focused) else sdata.get("border", BORDER_DIM)
        pygame.draw.rect(surface, border, self.rect, width=1, border_radius=4)

        text_surf = self.font.render(self.text, True, sdata["text"])
        surface.blit(text_surf, text_surf.get_rect(center=self.rect.center))


# ---------------------------------------------------------------------------
# ProgressBar
# ---------------------------------------------------------------------------
class ProgressBar:
    """Filled progress bar with optional value/max text overlay.

    Supports two APIs:
    1. New (HUD feature): ProgressBar(rect, value=num, max_value=num, fill_color=, ...)
    2. Old (existing): ProgressBar(rect, value=0-1 ratio, fg_color=, color=, ...)
    """

    def __init__(
        self,
        rect: "pygame.Rect" = None,
        value: float = 1.0,
        max_value: "float | None" = None,
        fg_color: "Tuple[int, int, int]" = ACCENT_CYAN,
        fill_color: "Tuple[int, int, int] | None" = None,
        bg_color: "Tuple[int, int, int]" = BORDER_DIM,
        border_color: "Tuple[int, int, int] | None" = BORDER_DIM,
        color=None,
        show_text: bool = False,
        font=None,
        text_color: "Tuple[int, int, int]" = (255, 255, 255),
        corner_radius: int = 3,
    ) -> None:
        self.rect = rect or pygame.Rect(0, 0, 100, 10)
        self.show_text = show_text
        self.font = font
        self.text_color = text_color
        self.corner_radius = corner_radius
        self.bg_color = bg_color
        self.border_color = border_color

        # Resolve fill color from multiple possible kwargs
        self.fill_color = fill_color or color or fg_color
        self.fg_color = self.fill_color
        self.color = self.fill_color

        # Handle max_value-based API vs ratio-based API
        if max_value is not None:
            # New API: value/max_value (absolute values)
            self._raw_value = value
            self.max_value = max(max_value, 1e-9)
            self.value = max(0.0, min(1.0, value / self.max_value))
        else:
            # Old API: value is already 0-1 ratio
            self._raw_value = value
            self.max_value = 1.0
            self.value = max(0.0, min(1.0, value))

    @property
    def fill_ratio(self) -> float:
        """Clamped fill ratio in [0.0, 1.0]."""
        return max(0.0, min(1.0, self._raw_value / self.max_value))

    def draw(self, surface: pygame.Surface) -> None:
        # Background
        pygame.draw.rect(surface, self.bg_color, self.rect,
                         border_radius=self.corner_radius)
        # Fill
        ratio = self.fill_ratio if self.max_value != 1.0 else self.value
        fill_w = max(0, int(self.rect.width * ratio))
        if fill_w > 0:
            fill_rect = pygame.Rect(
                self.rect.x, self.rect.y, fill_w, self.rect.height
            )
            pygame.draw.rect(surface, self.fill_color, fill_rect,
                             border_radius=self.corner_radius)
        # Border
        if self.border_color:
            pygame.draw.rect(surface, self.border_color, self.rect,
                             width=1, border_radius=self.corner_radius)
        # Text overlay
        if self.show_text and self.font:
            text = f'{int(self._raw_value)} / {int(self.max_value)}'
            txt_surf = self.font.render(text, True, self.text_color)
            txt_rect = txt_surf.get_rect(center=self.rect.center)
            surface.blit(txt_surf, txt_rect)


# ---------------------------------------------------------------------------
# IconSlot
# ---------------------------------------------------------------------------
class IconSlot:
    """Square icon display slot for the HUD."""

    def __init__(
        self,
        rect: "pygame.Rect" = None,
        icon: "pygame.Surface | None" = None,
        label: str = "",
        hotkey: str = "",
        empty_color: "Tuple[int, int, int]" = (30, 34, 50),
        count: int = 0,
        font: "pygame.font.Font | None" = None,
        selected: bool = False,
    ) -> None:
        self.rect = rect or pygame.Rect(0, 0, 48, 48)
        self.icon = icon
        self.label = label
        self.hotkey = hotkey
        self.empty_color = empty_color
        self.count = count
        self.font = font or pygame.font.Font(None, 16)
        self.selected = selected

    def draw(self, surface: pygame.Surface) -> None:
        # Slot background
        border_color = (0, 245, 255) if self.selected else (42, 48, 80)
        pygame.draw.rect(surface, self.empty_color, self.rect, border_radius=4)
        pygame.draw.rect(surface, border_color, self.rect,
                         width=2 if self.selected else 1, border_radius=4)

        # Icon
        if self.icon is not None:
            pad = 4
            inner = pygame.Rect(
                self.rect.x + pad, self.rect.y + pad,
                self.rect.width - 2 * pad, self.rect.height - 2 * pad,
            )
            try:
                scaled = pygame.transform.scale(self.icon, (inner.width, inner.height))
                surface.blit(scaled, inner)
            except Exception:
                pass

        # Hotkey badge (top-left corner)
        if self.hotkey and self.font:
            badge = self.font.render(self.hotkey, True, (255, 184, 0))
            surface.blit(badge, (self.rect.x + 2, self.rect.y + 2))

        # Count badge (bottom-right corner)
        if self.count > 0 and self.font:
            count_surf = self.font.render(str(self.count), True, (255, 255, 255))
            cx = self.rect.right - count_surf.get_width() - 2
            cy = self.rect.bottom - count_surf.get_height() - 2
            surface.blit(count_surf, (cx, cy))

        # Label below slot
        if self.label and self.font:
            lbl = self.font.render(self.label, True, (154, 163, 192))
            lbl_x = self.rect.centerx - lbl.get_width() // 2
            lbl_y = self.rect.bottom + 2
            surface.blit(lbl, (lbl_x, lbl_y))


# ---------------------------------------------------------------------------
# ConfirmDialog
# ---------------------------------------------------------------------------
class ConfirmDialog:
    """Modal confirmation dialog with CONFIRM and CANCEL buttons."""

    WIDTH = 360
    HEIGHT = 180

    def __init__(
        self,
        title_or_message: str = "",
        message: str = "",
        font_title=None,
        font_body=None,
        font_btn=None,
        on_confirm: "Callable[[], None] | None" = None,
        on_cancel: "Callable[[], None] | None" = None,
        *,
        screen_w: int = 1280,
        screen_h: int = 720,
    ) -> None:
        self.active: bool = False

        self._title = title_or_message
        self._message = message
        self._font_title = font_title
        self._font_body = font_body or font_title
        self._font_btn = font_btn or font_title

        self._rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self._panel = Panel(self._rect, alpha=245, border_color=DANGER_RED)

        self._lbl_title = None
        self._lbl_msg = None
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._btn_confirm = None
        self._btn_cancel = None

        if font_title is not None:
            self._build_widgets()

    def _build_widgets(self) -> None:
        ft = self._font_title or pygame.font.Font(None, 22)
        fb = self._font_body or ft
        fbtn = self._font_btn or ft

        self._lbl_title = Label(self._title, ft, DANGER_RED, (0, 0))
        self._lbl_msg = Label(self._message, fb, TEXT_SECONDARY, (0, 0))
        self._btn_confirm = Button(
            pygame.Rect(0, 0, 130, 38), "CONFIRM", fbtn, "danger", self._on_confirm
        )
        self._btn_cancel = Button(
            pygame.Rect(0, 0, 130, 38), "CANCEL", fbtn, "secondary", self._on_cancel
        )

    def _ensure_widgets(self) -> None:
        if self._btn_confirm is None:
            self._build_widgets()

    def _layout(self, screen_w: int, screen_h: int) -> None:
        self._ensure_widgets()
        self._rect.center = (screen_w // 2, screen_h // 2)
        self._panel.rect = self._rect

        cx = self._rect.centerx
        if self._lbl_title:
            self._lbl_title.pos = (cx, self._rect.y + 30)
        if self._lbl_msg:
            self._lbl_msg.pos = (cx, self._rect.y + 72)

        btn_y = self._rect.bottom - 52
        if self._btn_confirm:
            self._btn_confirm.rect = pygame.Rect(cx - 140, btn_y, 130, 38)
        if self._btn_cancel:
            self._btn_cancel.rect = pygame.Rect(cx + 10, btn_y, 130, 38)

    def show(self, screen_size: "Tuple[int, int]" = (1280, 720)) -> None:
        self._layout(*screen_size)
        self.active = True

    def hide(self) -> None:
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False
        self._ensure_widgets()
        if self._btn_confirm:
            self._btn_confirm.handle_event(event)
        if self._btn_cancel:
            self._btn_cancel.handle_event(event)
        return True

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        self._ensure_widgets()
        sw, sh = surface.get_size()
        self._layout(sw, sh)

        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, 0))

        self._panel.draw(surface)
        if self._lbl_title:
            self._lbl_title.draw(surface)
        if self._lbl_msg:
            self._lbl_msg.draw(surface)
        if self._btn_confirm:
            self._btn_confirm.draw(surface)
        if self._btn_cancel:
            self._btn_cancel.draw(surface)
