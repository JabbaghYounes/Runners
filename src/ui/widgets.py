"""Reusable UI widget primitives for Runners.

Existing widget:
    Slider  — horizontal drag slider (used by SettingsScreen)

New HUD widgets (stateless draw helpers):
    Panel       — rounded-rect background panel
    Label       — text surface at a given position
    ProgressBar — filled rect with optional value/max overlay
    IconSlot    — 48×48 icon box with hotkey badge and count label
"""
from __future__ import annotations
from typing import Callable, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Internal colour constants used by Slider (keep unchanged)
# ──────────────────────────────────────────────────────────────────────────────
_BG_PANEL  = (20,  24,  38)
_TRACK_CLR = (42,  48,  80)
_THUMB_CLR = (0,  245, 255)
_LABEL_CLR = (154, 163, 192)
_BORDER_CLR = (42,  48,  80)


# ──────────────────────────────────────────────────────────────────────────────
# Slider (pre-existing — DO NOT CHANGE INTERFACE)
# ──────────────────────────────────────────────────────────────────────────────
class Slider:
    """Horizontal drag slider.

    Args:
        rect:      (x, y, w, h) position and size of the slider track.
        min_val:   Minimum value.
        max_val:   Maximum value.
        initial:   Initial value (clamped to [min_val, max_val]).
        label:     Display label rendered to the left.
        on_change: Optional callback called with the new value on change.
    """

    def __init__(
        self,
        rect: Tuple[int, int, int, int],
        min_val: float,
        max_val: float,
        initial: float,
        label: str = '',
        on_change: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.rect = rect
        self.min_val = min_val
        self.max_val = max_val
        self.value = max(min_val, min(max_val, initial))
        self.label = label
        self.on_change = on_change
        self._dragging = False

    # ── internal geometry helpers ──────────────────────────────────

    def _track_x(self) -> int:
        return self.rect[0]

    def _track_y(self) -> int:
        return self.rect[1]

    def _track_w(self) -> int:
        return self.rect[2]

    def _track_h(self) -> int:
        return self.rect[3]

    def _value_to_px(self, frac: float | None = None) -> int:
        """Map a fractional position (0–1) to a pixel x-coordinate on the track."""
        if frac is None:
            frac = (self.value - self.min_val) / max(self.max_val - self.min_val, 1e-9)
        return self._track_x() + int(frac * self._track_w())

    def _px_to_value(self, px: int) -> float:
        """Map a pixel x-coordinate to a value within [min_val, max_val]."""
        frac = (px - self._track_x()) / max(self._track_w(), 1)
        frac = max(0.0, min(1.0, frac))
        return self.min_val + frac * (self.max_val - self.min_val)

    def _set_from_px(self, px: int) -> None:
        new_val = self._px_to_value(px)
        if new_val == self.value:
            return
        self.value = new_val
        if self.on_change:
            self.on_change(self.value)

    def _thumb_rect(self, pygame: object) -> object:
        cx = self._value_to_px()
        th = self._track_h()
        return pygame.Rect(cx - th // 2, self._track_y(), th, th)

    # ── public API ────────────────────────────────────────────────

    def handle_event(self, event: object, pygame: object) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            thumb = self._thumb_rect(pygame)
            if thumb.collidepoint(event.pos):
                self._dragging = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self._set_from_px(event.pos[0])

    def render(self, surface: object, font: object, pygame: object) -> None:
        x, y, w, h = self.rect
        cx = self._value_to_px()
        th = h
        fill_w = cx - x

        # Track background
        pygame.draw.rect(surface, _TRACK_CLR, (x, y, w, h), border_radius=h // 2)
        # Filled portion
        if fill_w > 0:
            pygame.draw.rect(surface, _THUMB_CLR, (x, y, fill_w, h), border_radius=h // 2)
        # Thumb
        thumb = self._thumb_rect(pygame)
        pygame.draw.ellipse(surface, _THUMB_CLR, thumb)

        # Label
        if font and self.label:
            pct = (self.value - self.min_val) / max(self.max_val - self.min_val, 1e-9)
            text = f'{self.label}: {int(pct * 100)}%'
            surf = font.render(text, True, _LABEL_CLR)
            surface.blit(surf, (x, y - surf.get_height() - 2))


# ──────────────────────────────────────────────────────────────────────────────
# HUD primitive widgets
# ──────────────────────────────────────────────────────────────────────────────

class Panel:
    """Rounded-rect background panel.

    Stateless draw helper — pass all values on construction, call draw().
    """

    def __init__(
        self,
        rect: object,                              # pygame.Rect
        bg_color: Tuple[int, int, int] = (20, 24, 38),
        border_color: Tuple[int, int, int] = (42, 48, 80),
        border_width: int = 1,
        corner_radius: int = 6,
        alpha: int = 220,
    ) -> None:
        self.rect = rect
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        self.corner_radius = corner_radius
        self.alpha = alpha

    def draw(self, surface: object) -> None:
        """Draw this panel onto *surface*."""
        import pygame
        # Semi-transparent background using a temporary surface
        panel_surf = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        bg_with_alpha = (*self.bg_color, self.alpha)
        pygame.draw.rect(
            panel_surf, bg_with_alpha,
            pygame.Rect(0, 0, self.rect.width, self.rect.height),
            border_radius=self.corner_radius,
        )
        surface.blit(panel_surf, (self.rect.x, self.rect.y))
        # Border
        if self.border_width > 0:
            pygame.draw.rect(
                surface, self.border_color, self.rect,
                width=self.border_width, border_radius=self.corner_radius,
            )


class Label:
    """Text label rendered at a given anchor position.

    Args:
        text:       String to render.
        font:       pygame.font.Font object.
        color:      RGB color tuple.
        pos:        (x, y) position.
        anchor:     One of 'topleft', 'center', 'topright', 'bottomleft',
                    'bottomright', 'midleft', 'midright', 'midtop', 'midbottom'.
    """

    def __init__(
        self,
        text: str,
        font: object,
        color: Tuple[int, int, int],
        pos: Tuple[int, int],
        anchor: str = 'topleft',
    ) -> None:
        self.text = text
        self.font = font
        self.color = color
        self.pos = pos
        self.anchor = anchor

    def draw(self, surface: object) -> None:
        import pygame
        surf = self.font.render(self.text, True, self.color)
        rect = surf.get_rect()
        setattr(rect, self.anchor, self.pos)
        surface.blit(surf, rect)


class ProgressBar:
    """Filled progress bar with optional value/max text overlay.

    Args:
        rect:        pygame.Rect for the bar area.
        value:       Current value.
        max_value:   Maximum value (clamped; must be > 0).
        fill_color:  Bar fill RGB color.
        bg_color:    Bar background RGB color.
        border_color:Border RGB color (None = no border).
        show_text:   If True, render "value / max_value" centered on the bar.
        font:        pygame.font.Font for text (required if show_text=True).
        text_color:  RGB color for text overlay.
        corner_radius: Rounded corner radius.
    """

    def __init__(
        self,
        rect: object,
        value: float,
        max_value: float,
        fill_color: Tuple[int, int, int] = (57, 255, 20),
        bg_color: Tuple[int, int, int] = (20, 24, 38),
        border_color: Optional[Tuple[int, int, int]] = (42, 48, 80),
        show_text: bool = False,
        font: object = None,
        text_color: Tuple[int, int, int] = (255, 255, 255),
        corner_radius: int = 3,
    ) -> None:
        self.rect = rect
        self.value = value
        self.max_value = max(max_value, 1e-9)
        self.fill_color = fill_color
        self.bg_color = bg_color
        self.border_color = border_color
        self.show_text = show_text
        self.font = font
        self.text_color = text_color
        self.corner_radius = corner_radius

    @property
    def fill_ratio(self) -> float:
        """Clamped fill ratio in [0.0, 1.0]."""
        return max(0.0, min(1.0, self.value / self.max_value))

    def draw(self, surface: object) -> None:
        import pygame
        # Background
        pygame.draw.rect(surface, self.bg_color, self.rect,
                         border_radius=self.corner_radius)
        # Fill
        fill_w = int(self.rect.width * self.fill_ratio)
        if fill_w > 0:
            fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_w, self.rect.height)
            pygame.draw.rect(surface, self.fill_color, fill_rect,
                             border_radius=self.corner_radius)
        # Border
        if self.border_color:
            pygame.draw.rect(surface, self.border_color, self.rect,
                             width=1, border_radius=self.corner_radius)
        # Text overlay
        if self.show_text and self.font:
            text = f'{int(self.value)} / {int(self.max_value)}'
            txt_surf = self.font.render(text, True, self.text_color)
            txt_rect = txt_surf.get_rect(center=self.rect.center)
            surface.blit(txt_surf, txt_rect)


class IconSlot:
    """Square icon slot with optional hotkey badge and count label.

    Args:
        rect:         pygame.Rect for the slot area.
        icon:         pygame.Surface icon image, or None for empty.
        label:        Text label shown below the slot (e.g. item name).
        hotkey:       Single-character hotkey badge in corner (e.g. '1').
        empty_color:  RGB fill color when slot is empty.
        count:        Optional stack count to show in corner.
        font:         pygame.font.Font for labels.
        selected:     If True, draw a bright highlight ring.
    """

    def __init__(
        self,
        rect: object,
        icon: object = None,
        label: str = '',
        hotkey: str = '',
        empty_color: Tuple[int, int, int] = (30, 34, 50),
        count: int = 0,
        font: object = None,
        selected: bool = False,
    ) -> None:
        self.rect = rect
        self.icon = icon
        self.label = label
        self.hotkey = hotkey
        self.empty_color = empty_color
        self.count = count
        self.font = font
        self.selected = selected

    def draw(self, surface: object) -> None:
        import pygame
        # Slot background
        border_color = (0, 245, 255) if self.selected else (42, 48, 80)
        pygame.draw.rect(surface, self.empty_color, self.rect, border_radius=4)
        pygame.draw.rect(surface, border_color, self.rect,
                         width=2 if self.selected else 1, border_radius=4)

        # Icon (scaled to fit with 4px padding)
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
