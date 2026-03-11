"""Reusable UI widget library.

Widgets:
    Panel         — semi-transparent rounded-rect background
    Label         — rendered text with optional neon glow
    Button        — interactive button with hover/press states and style variants
    ProgressBar   — read-only filled bar
    Slider        — draggable value control (0–1 range)
    ConfirmDialog — modal two-button confirmation overlay
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import pygame

from src.constants import (
    ACCENT_CYAN,
    BG_DEEP,
    BG_PANEL,
    BORDER_DIM,
    DANGER_RED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class Panel:
    """Filled rounded-rect panel with a 1-px border."""

    def __init__(
        self,
        rect: pygame.Rect,
        alpha: int = 220,
        border_color: Optional[Tuple[int, int, int]] = None,
        radius: int = 6,
    ) -> None:
        self.rect = rect
        self.alpha = alpha
        self.border_color: Tuple[int, int, int] = border_color or BORDER_DIM
        self.radius = radius

    def draw(self, surface: pygame.Surface) -> None:
        panel_surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        r, g, b = BG_PANEL
        pygame.draw.rect(
            panel_surf,
            (r, g, b, self.alpha),
            panel_surf.get_rect(),
            border_radius=self.radius,
        )
        br, bg, bb = self.border_color
        pygame.draw.rect(
            panel_surf,
            (br, bg, bb, 255),
            panel_surf.get_rect(),
            width=1,
            border_radius=self.radius,
        )
        surface.blit(panel_surf, self.rect.topleft)


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------

class Label:
    """Text label with optional neon glow effect.

    Args:
        text:   String to render.
        font:   Pygame font object.
        color:  RGB text color tuple.
        pos:    Anchor position (meaning depends on *align*).
        align:  ``"center"`` | ``"left"`` | ``"right"``
        glow:   When ``True``, renders blurred copies behind the main text.
    """

    def __init__(
        self,
        text: str,
        font: pygame.font.Font,
        color: Tuple[int, int, int] = TEXT_PRIMARY,
        pos: Tuple[int, int] = (0, 0),
        align: str = "center",
        glow: bool = False,
    ) -> None:
        self.text = text
        self.font = font
        self.color = color
        self.pos = pos
        self.align = align
        self.glow = glow

        self._cached_surf: Optional[pygame.Surface] = None
        self._cached_text: str = ""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rendered(self) -> pygame.Surface:
        if self._cached_surf is None or self._cached_text != self.text:
            self._cached_surf = self.font.render(self.text, True, self.color)
            self._cached_text = self.text
        return self._cached_surf

    def _place_rect(self, surf: pygame.Surface) -> pygame.Rect:
        r = surf.get_rect()
        if self.align == "center":
            r.center = self.pos
        elif self.align == "left":
            r.midleft = self.pos
        else:
            r.midright = self.pos
        return r

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_text(self, text: str) -> None:
        """Update displayed text; clears the render cache."""
        self.text = text
        self._cached_surf = None

    def draw(self, surface: pygame.Surface) -> None:
        surf = self._rendered()
        r = self._place_rect(surf)

        if self.glow:
            glow_surf = self.font.render(self.text, True, self.color)
            glow_surf.set_alpha(70)
            offsets: List[Tuple[int, int]] = [
                (-3, 0), (3, 0), (0, -3), (0, 3),
                (-2, -2), (2, -2), (-2, 2), (2, 2),
            ]
            for dx, dy in offsets:
                surface.blit(glow_surf, (r.x + dx, r.y + dy))

        surface.blit(surf, r)


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
    },
    "secondary": {
        "bg":       BORDER_DIM,
        "bg_hover": (55, 65, 105),
        "bg_press": (40, 50, 85),
        "text":     TEXT_PRIMARY,
        "border":   BORDER_DIM,
    },
    "danger": {
        "bg":       (75, 10, 18),
        "bg_hover": (120, 22, 38),
        "bg_press": (100, 16, 28),
        "text":     DANGER_RED,
        "border":   DANGER_RED,
    },
}


class Button:
    """Interactive button with hover / press state tracking.

    ``handle_event`` returns ``True`` the frame a click is confirmed (mouse
    button released while both pressed and hovered).  The ``on_click``
    callback is also invoked at that moment if provided.
    """

    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        font: pygame.font.Font,
        style: str = "secondary",
        on_click: Optional[Callable[[], None]] = None,
    ) -> None:
        self.rect = rect
        self.text = text
        self.font = font
        self.style = style
        self.on_click = on_click

        self._hovered: bool = False
        self._pressed: bool = False
        self._focused: bool = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process a single Pygame event; returns ``True`` on confirmed click."""
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
        style = _BUTTON_STYLES.get(self.style, _BUTTON_STYLES["secondary"])

        if self._pressed:
            bg = style["bg_press"]
        elif self._hovered:
            bg = style["bg_hover"]
        else:
            bg = style["bg"]

        pygame.draw.rect(surface, bg, self.rect, border_radius=4)

        border = ACCENT_CYAN if (self._hovered or self._focused) else style["border"]
        pygame.draw.rect(surface, border, self.rect, width=1, border_radius=4)

        text_surf = self.font.render(self.text, True, style["text"])
        surface.blit(text_surf, text_surf.get_rect(center=self.rect.center))


# ---------------------------------------------------------------------------
# ProgressBar
# ---------------------------------------------------------------------------

class ProgressBar:
    """Read-only horizontal progress bar."""

    def __init__(
        self,
        rect: pygame.Rect,
        value: float = 1.0,
        fg_color: Tuple[int, int, int] = ACCENT_CYAN,
        bg_color: Tuple[int, int, int] = BORDER_DIM,
        border_color: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        self.rect = rect
        self.value: float = max(0.0, min(1.0, value))
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.border_color: Tuple[int, int, int] = border_color or BORDER_DIM

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=2)
        if self.value > 0:
            fill = pygame.Rect(
                self.rect.x,
                self.rect.y,
                max(1, int(self.rect.width * self.value)),
                self.rect.height,
            )
            pygame.draw.rect(surface, self.fg_color, fill, border_radius=2)
        pygame.draw.rect(surface, self.border_color, self.rect, width=1, border_radius=2)


# ---------------------------------------------------------------------------
# Slider
# ---------------------------------------------------------------------------

class Slider:
    """Draggable value slider (range 0–1).

    Mouse-down on the track or handle begins drag mode; mouse-up ends it.
    ``on_change`` is called with the new float value whenever it changes.
    """

    HANDLE_RADIUS = 8
    TRACK_HEIGHT = 4

    def __init__(
        self,
        rect: pygame.Rect,
        value: float = 0.5,
        on_change: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.rect = rect
        self.value: float = max(0.0, min(1.0, value))
        self.on_change = on_change
        self._dragging: bool = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_center(self) -> Tuple[int, int]:
        x = self.rect.x + int(self.value * self.rect.width)
        y = self.rect.centery
        return (x, y)

    def _set_value_from_x(self, mouse_x: int) -> None:
        relative = mouse_x - self.rect.x
        new_val = max(0.0, min(1.0, relative / max(1, self.rect.width)))
        if new_val != self.value:
            self.value = new_val
            if self.on_change:
                self.on_change(self.value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Returns ``True`` when the slider consumed the event."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hx, hy = self._handle_center()
            dist = ((event.pos[0] - hx) ** 2 + (event.pos[1] - hy) ** 2) ** 0.5
            hit_handle = dist <= self.HANDLE_RADIUS + 6
            inflated = self.rect.inflate(0, 16)
            hit_track = inflated.top <= event.pos[1] <= inflated.bottom
            if hit_handle or hit_track:
                self._dragging = True
                self._set_value_from_x(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._dragging = False
                return True
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self._set_value_from_x(event.pos[0])
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        # Track background
        ty = self.rect.centery - self.TRACK_HEIGHT // 2
        track = pygame.Rect(self.rect.x, ty, self.rect.width, self.TRACK_HEIGHT)
        pygame.draw.rect(surface, BORDER_DIM, track, border_radius=2)

        # Filled portion
        fill_w = int(self.value * self.rect.width)
        if fill_w > 0:
            fill = pygame.Rect(self.rect.x, ty, fill_w, self.TRACK_HEIGHT)
            pygame.draw.rect(surface, ACCENT_CYAN, fill, border_radius=2)

        # Handle (outer ring + dark centre)
        hx, hy = self._handle_center()
        pygame.draw.circle(surface, ACCENT_CYAN, (hx, hy), self.HANDLE_RADIUS)
        pygame.draw.circle(surface, BG_DEEP, (hx, hy), self.HANDLE_RADIUS - 3)


# ---------------------------------------------------------------------------
# ConfirmDialog
# ---------------------------------------------------------------------------

class ConfirmDialog:
    """Modal confirmation dialog with CONFIRM and CANCEL buttons.

    Set ``active = True`` via :meth:`show` to display; ``handle_event`` will
    consume all events while active.  The dialog centres itself on the screen.

    Args:
        title:      Short heading text (displayed in ``DANGER_RED``).
        message:    One-line body text.
        font_title: Font for the heading.
        font_body:  Font for the body message.
        font_btn:   Font for both buttons.
        on_confirm: Callback invoked when CONFIRM is clicked.
        on_cancel:  Callback invoked when CANCEL is clicked.
    """

    WIDTH = 360
    HEIGHT = 180

    def __init__(
        self,
        title: str,
        message: str,
        font_title: pygame.font.Font,
        font_body: pygame.font.Font,
        font_btn: pygame.font.Font,
        on_confirm: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        self.active: bool = False

        self._title = title
        self._message = message

        self._rect = pygame.Rect(0, 0, self.WIDTH, self.HEIGHT)
        self._panel = Panel(self._rect, alpha=245, border_color=DANGER_RED)

        self._lbl_title = Label(title, font_title, DANGER_RED, (0, 0))
        self._lbl_msg = Label(message, font_body, TEXT_SECONDARY, (0, 0))

        self._btn_confirm = Button(
            pygame.Rect(0, 0, 130, 38), "CONFIRM", font_btn, "danger", on_confirm
        )
        self._btn_cancel = Button(
            pygame.Rect(0, 0, 130, 38), "CANCEL", font_btn, "secondary", on_cancel
        )

    # ------------------------------------------------------------------
    # Positioning
    # ------------------------------------------------------------------

    def _layout(self, screen_w: int, screen_h: int) -> None:
        """Position all child elements relative to the centred dialog rect."""
        self._rect.center = (screen_w // 2, screen_h // 2)
        self._panel.rect = self._rect

        cx = self._rect.centerx
        self._lbl_title.pos = (cx, self._rect.y + 30)
        self._lbl_msg.pos = (cx, self._rect.y + 72)

        btn_y = self._rect.bottom - 52
        self._btn_confirm.rect = pygame.Rect(cx - 140, btn_y, 130, 38)
        self._btn_cancel.rect = pygame.Rect(cx + 10, btn_y, 130, 38)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self, screen_size: Tuple[int, int] = (1280, 720)) -> None:
        """Make the dialog visible and lay out its children."""
        self._layout(*screen_size)
        self.active = True

    def hide(self) -> None:
        """Dismiss the dialog."""
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Forward event to buttons; returns ``True`` (consuming it) when active."""
        if not self.active:
            return False
        self._btn_confirm.handle_event(event)
        self._btn_cancel.handle_event(event)
        return True  # Swallow all events while dialog is visible

    def draw(self, surface: pygame.Surface) -> None:
        """Render the dialog; no-ops when inactive."""
        if not self.active:
            return

        sw, sh = surface.get_size()
        self._layout(sw, sh)

        # Dim overlay behind the dialog
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, 0))

        self._panel.draw(surface)
        self._lbl_title.draw(surface)
        self._lbl_msg.draw(surface)
        self._btn_confirm.draw(surface)
        self._btn_cancel.draw(surface)
