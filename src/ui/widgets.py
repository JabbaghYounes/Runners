"""Reusable UI widget primitives."""
from __future__ import annotations

from typing import Callable, Optional, Tuple


# ---------------------------------------------------------------------------
# Colour palette (neon-retro style matching ux-spec.md)
# ---------------------------------------------------------------------------

_BG_PANEL    = (15, 20, 35)
_TRACK_CLR   = (40, 55, 70)
_THUMB_CLR   = (0, 210, 200)    # ACCENT_CYAN
_LABEL_CLR   = (200, 220, 240)
_BORDER_CLR  = (60, 80, 110)


class Slider:
    """Horizontal slider widget that maps to a float value in [min_val, max_val].

    Parameters
    ----------
    rect:
        ``(x, y, width, height)`` position and size of the slider track.
    min_val / max_val:
        Range of the float value this slider controls.
    initial:
        Starting value (clamped to [min_val, max_val]).
    label:
        Text rendered above the slider track.
    on_change:
        Called with the new float value whenever the user moves the thumb.
    """

    THUMB_HALF_W = 8
    THUMB_H_EXTRA = 6  # thumb is taller than track by this many px on each side

    def __init__(
        self,
        rect: Tuple[int, int, int, int],
        min_val: float,
        max_val: float,
        initial: float,
        label: str,
        on_change: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.rect = rect           # (x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.value = max(min_val, min(max_val, initial))
        self.label = label
        self.on_change = on_change
        self._dragging = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def _track_x(self) -> int:
        return self.rect[0]

    @property
    def _track_y(self) -> int:
        return self.rect[1]

    @property
    def _track_w(self) -> int:
        return self.rect[2]

    @property
    def _track_h(self) -> int:
        return self.rect[3]

    def _value_to_px(self) -> int:
        """Return the x-pixel position of the thumb centre."""
        frac = (self.value - self.min_val) / max(self.max_val - self.min_val, 1e-9)
        return self._track_x + int(frac * self._track_w)

    def _px_to_value(self, px: int) -> float:
        frac = (px - self._track_x) / max(self._track_w, 1)
        frac = max(0.0, min(1.0, frac))
        return self.min_val + frac * (self.max_val - self.min_val)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, event: object) -> None:
        """Process a single pygame event.  Call from the parent scene loop."""
        try:
            import pygame
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # type: ignore[union-attr]
                if self._thumb_rect().collidepoint(event.pos):  # type: ignore[union-attr]
                    self._dragging = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:  # type: ignore[union-attr]
                self._dragging = False
            elif event.type == pygame.MOUSEMOTION and self._dragging:  # type: ignore[union-attr]
                self._set_from_px(event.pos[0])  # type: ignore[union-attr]
        except Exception:
            pass

    def _thumb_rect(self) -> object:
        """Return a pygame.Rect for the thumb hit area."""
        try:
            import pygame
            cx = self._value_to_px()
            th = self._track_h + self.THUMB_H_EXTRA * 2
            return pygame.Rect(
                cx - self.THUMB_HALF_W,
                self._track_y - self.THUMB_H_EXTRA,
                self.THUMB_HALF_W * 2,
                th,
            )
        except Exception:
            return type("FakeRect", (), {"collidepoint": lambda *_: False})()

    def _set_from_px(self, px: int) -> None:
        new_val = self._px_to_value(px)
        if new_val != self.value:
            self.value = new_val
            if self.on_change:
                self.on_change(self.value)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, surface: object, font: object = None) -> None:  # type: ignore[assignment]
        """Draw the slider onto *surface* using pygame primitives."""
        try:
            import pygame

            x, y, w, h = self.rect

            # Track
            pygame.draw.rect(surface, _TRACK_CLR, (x, y, w, h), border_radius=4)
            pygame.draw.rect(surface, _BORDER_CLR, (x, y, w, h), 1, border_radius=4)

            # Filled portion (left of thumb)
            cx = self._value_to_px()
            fill_w = cx - x
            if fill_w > 0:
                pygame.draw.rect(
                    surface, _THUMB_CLR,
                    (x, y, fill_w, h),
                    border_radius=4,
                )

            # Thumb
            th = h + self.THUMB_H_EXTRA * 2
            pygame.draw.rect(
                surface, _THUMB_CLR,
                (cx - self.THUMB_HALF_W, y - self.THUMB_H_EXTRA,
                 self.THUMB_HALF_W * 2, th),
                border_radius=4,
            )

            # Label
            if font is not None:
                pct = int((self.value - self.min_val) / max(self.max_val - self.min_val, 1e-9) * 100)
                text = f"{self.label}: {pct}%"
                surf = font.render(text, True, _LABEL_CLR)
                surface.blit(surf, (x, y - surf.get_height() - 4))
        except Exception:
            pass
