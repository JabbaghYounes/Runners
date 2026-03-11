"""Reusable UI primitives for the Runners game.

Components:
    Button         — clickable rectangle with hover/disabled states
    ProgressBar    — horizontal fill bar
    IconSlot       — fixed-size tile for item icons with rarity border
    Label          — single-line text renderer
    Panel          — background rectangle (opaque or semi-transparent)
    Tooltip        — small floating text box
    TabBar         — horizontal tab selector
    StatCounter    — animated count-up display (PostRound summary rows)
    FacilityCard   — vertical card showing a home-base facility (HomeBase UI)
    ConfirmDialog  — two-button confirmation overlay

All components follow the same minimal contract:
    handle_event(event)   — process a pygame.event.Event; return True if consumed
    update(dt)            — advance animations (dt in seconds)
    render(surface)       — draw onto *surface*

Colors reference ``src/constants.py`` naming conventions but are defined
locally here to avoid a hard import dependency (constants may not exist in
test environments).
"""

from __future__ import annotations

import math
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Guard: pygame is optional for unit tests that only exercise pure-logic
# components.  The UI components themselves still need pygame at runtime.
# ---------------------------------------------------------------------------
try:
    import pygame
    _PYGAME_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYGAME_AVAILABLE = False

# ---------------------------------------------------------------------------
# Local color palette (mirrors constants.py to avoid circular imports)
# ---------------------------------------------------------------------------
COLOR_BG_PANEL = (20, 20, 30)
COLOR_BG_CARD = (28, 28, 42)
COLOR_BORDER = (60, 60, 80)
COLOR_BORDER_HOVER = (100, 160, 220)

COLOR_TEXT_PRIMARY = (220, 220, 230)
COLOR_TEXT_SECONDARY = (140, 140, 160)
COLOR_TEXT_DISABLED = (70, 70, 90)

COLOR_ACCENT_CYAN = (0, 220, 200)
COLOR_ACCENT_AMBER = (240, 180, 40)
COLOR_ACCENT_RED = (220, 60, 60)
COLOR_ACCENT_GREEN = (60, 200, 90)

COLOR_BTN_NORMAL = (40, 50, 70)
COLOR_BTN_HOVER = (55, 70, 100)
COLOR_BTN_DISABLED = (30, 35, 45)
COLOR_BTN_TEXT = (200, 210, 230)

COLOR_PIP_FILLED = COLOR_ACCENT_AMBER
COLOR_PIP_EMPTY = (50, 50, 65)


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------

class Button:
    """A rectangular clickable button.

    Args:
        rect:       ``pygame.Rect`` defining position and size.
        text:       Label rendered centred inside the button.
        on_click:   Callable invoked when the button is clicked.
        disabled:   If True the button does not respond to input.
        font_size:  Font size in pixels (default 16).
        color:      Background colour override.
        text_color: Text colour override.
    """

    def __init__(
        self,
        rect: Any,
        text: str,
        on_click: Callable[[], None] | None = None,
        *,
        disabled: bool = False,
        font_size: int = 16,
        color: tuple[int, int, int] | None = None,
        text_color: tuple[int, int, int] | None = None,
    ) -> None:
        self.rect = rect
        self.text = text
        self.on_click = on_click
        self.disabled = disabled
        self.font_size = font_size
        self._color = color
        self._text_color = text_color
        self._hovered = False
        self._font: Any = None

    def _get_font(self) -> Any:
        if self._font is None and _PYGAME_AVAILABLE:
            self._font = pygame.font.SysFont("monospace", self.font_size, bold=True)
        return self._font

    def handle_event(self, event: Any) -> bool:
        if not _PYGAME_AVAILABLE or self.disabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos) and self.on_click:
                self.on_click()
                return True
        return False

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: Any) -> None:
        if not _PYGAME_AVAILABLE:
            return
        if self.disabled:
            bg = self._color or COLOR_BTN_DISABLED
            tc = self._text_color or COLOR_TEXT_DISABLED
        elif self._hovered:
            bg = COLOR_BTN_HOVER
            tc = self._text_color or COLOR_BTN_TEXT
        else:
            bg = self._color or COLOR_BTN_NORMAL
            tc = self._text_color or COLOR_BTN_TEXT

        pygame.draw.rect(surface, bg, self.rect, border_radius=4)
        border_color = COLOR_BORDER_HOVER if self._hovered else COLOR_BORDER
        pygame.draw.rect(surface, border_color, self.rect, width=1, border_radius=4)

        font = self._get_font()
        if font:
            text_surf = font.render(self.text, True, tc)
            text_rect = text_surf.get_rect(center=self.rect.center)
            surface.blit(text_surf, text_rect)


# ---------------------------------------------------------------------------
# ProgressBar
# ---------------------------------------------------------------------------

class ProgressBar:
    """A horizontal fill bar representing a ratio (0.0 – 1.0).

    Args:
        rect:       Bounding rect.
        value:      Initial fill ratio in [0, 1].
        color:      Fill colour (defaults to accent cyan).
        bg_color:   Background colour.
        label:      Optional text drawn inside the bar.
    """

    def __init__(
        self,
        rect: Any,
        value: float = 0.0,
        *,
        color: tuple[int, int, int] | None = None,
        bg_color: tuple[int, int, int] | None = None,
        label: str = "",
        font_size: int = 13,
    ) -> None:
        self.rect = rect
        self.value = max(0.0, min(1.0, value))
        self.color = color or COLOR_ACCENT_CYAN
        self.bg_color = bg_color or COLOR_BG_PANEL
        self.label = label
        self.font_size = font_size
        self._font: Any = None

    def _get_font(self) -> Any:
        if self._font is None and _PYGAME_AVAILABLE:
            self._font = pygame.font.SysFont("monospace", self.font_size)
        return self._font

    def handle_event(self, event: Any) -> bool:
        return False

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: Any) -> None:
        if not _PYGAME_AVAILABLE:
            return
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=3)
        fill_width = int(self.rect.width * max(0.0, min(1.0, self.value)))
        if fill_width > 0:
            fill_rect = pygame.Rect(self.rect.left, self.rect.top, fill_width, self.rect.height)
            pygame.draw.rect(surface, self.color, fill_rect, border_radius=3)
        pygame.draw.rect(surface, COLOR_BORDER, self.rect, width=1, border_radius=3)
        if self.label:
            font = self._get_font()
            if font:
                text_surf = font.render(self.label, True, COLOR_TEXT_PRIMARY)
                text_rect = text_surf.get_rect(center=self.rect.center)
                surface.blit(text_surf, text_rect)


# ---------------------------------------------------------------------------
# IconSlot
# ---------------------------------------------------------------------------

class IconSlot:
    """A fixed-size slot tile for rendering an item icon with rarity border.

    Args:
        rect:         Bounding rect (typically 64×64).
        item:         ``Item`` instance or None (empty slot).
        on_click:     Callback invoked when the slot is clicked.
        show_tooltip: Whether to show a tooltip on hover.
    """

    EMPTY_COLOR = (30, 32, 44)

    def __init__(
        self,
        rect: Any,
        item: Any = None,
        *,
        on_click: Callable[[Any], None] | None = None,
        show_tooltip: bool = True,
    ) -> None:
        self.rect = rect
        self.item = item
        self.on_click = on_click
        self.show_tooltip = show_tooltip
        self._hovered = False

    def handle_event(self, event: Any) -> bool:
        if not _PYGAME_AVAILABLE:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos) and self.on_click:
                self.on_click(self.item)
                return True
        return False

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: Any) -> None:
        if not _PYGAME_AVAILABLE:
            return
        pygame.draw.rect(surface, self.EMPTY_COLOR, self.rect, border_radius=4)
        if self.item:
            border_color = self.item.rarity_color
            pygame.draw.rect(surface, border_color, self.rect, width=2, border_radius=4)
        else:
            pygame.draw.rect(surface, COLOR_BORDER, self.rect, width=1, border_radius=4)


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------

class Label:
    """Single-line text renderer.

    Args:
        pos:        (x, y) top-left or anchor position.
        text:       String to display.
        font_size:  Font size in pixels.
        color:      Text colour.
        anchor:     ``"topleft"`` (default), ``"center"``, ``"topright"``, etc.
                    Must be a valid ``pygame.Rect`` attribute name.
    """

    def __init__(
        self,
        pos: tuple[int, int],
        text: str,
        *,
        font_size: int = 16,
        color: tuple[int, int, int] | None = None,
        bold: bool = False,
        anchor: str = "topleft",
    ) -> None:
        self.pos = pos
        self.text = text
        self.font_size = font_size
        self.color = color or COLOR_TEXT_PRIMARY
        self.bold = bold
        self.anchor = anchor
        self._font: Any = None

    def _get_font(self) -> Any:
        if self._font is None and _PYGAME_AVAILABLE:
            self._font = pygame.font.SysFont("monospace", self.font_size, bold=self.bold)
        return self._font

    def handle_event(self, event: Any) -> bool:
        return False

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: Any) -> None:
        if not _PYGAME_AVAILABLE:
            return
        font = self._get_font()
        if not font:
            return
        text_surf = font.render(self.text, True, self.color)
        text_rect = text_surf.get_rect()
        setattr(text_rect, self.anchor, self.pos)
        surface.blit(text_surf, text_rect)


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class Panel:
    """A solid or semi-transparent filled rectangle.

    Args:
        rect:    Bounding rect.
        color:   Fill colour.
        alpha:   Opacity 0–255.  If < 255 a Surface with per-pixel alpha
                 is used.
        radius:  Border radius.
    """

    def __init__(
        self,
        rect: Any,
        color: tuple[int, int, int] | None = None,
        *,
        alpha: int = 255,
        radius: int = 0,
        border_color: tuple[int, int, int] | None = None,
        border_width: int = 0,
    ) -> None:
        self.rect = rect
        self.color = color or COLOR_BG_PANEL
        self.alpha = alpha
        self.radius = radius
        self.border_color = border_color
        self.border_width = border_width

    def handle_event(self, event: Any) -> bool:
        return False

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: Any) -> None:
        if not _PYGAME_AVAILABLE:
            return
        if self.alpha < 255:
            surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            r, g, b = self.color
            surf.fill((r, g, b, self.alpha))
            surface.blit(surf, self.rect.topleft)
        else:
            pygame.draw.rect(surface, self.color, self.rect, border_radius=self.radius)
        if self.border_color and self.border_width:
            pygame.draw.rect(
                surface, self.border_color, self.rect,
                width=self.border_width, border_radius=self.radius,
            )


# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------

class Tooltip:
    """Small floating text box.

    Args:
        text:      Tooltip content.
        font_size: Font size.
        padding:   Internal padding in pixels.
    """

    def __init__(self, text: str, *, font_size: int = 13, padding: int = 6) -> None:
        self.text = text
        self.font_size = font_size
        self.padding = padding
        self._font: Any = None
        self._visible = False
        self._pos: tuple[int, int] = (0, 0)

    def show(self, pos: tuple[int, int]) -> None:
        self._visible = True
        self._pos = pos

    def hide(self) -> None:
        self._visible = False

    def handle_event(self, event: Any) -> bool:
        return False

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: Any) -> None:
        if not _PYGAME_AVAILABLE or not self._visible:
            return
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self.font_size)
        text_surf = self._font.render(self.text, True, COLOR_TEXT_PRIMARY)
        p = self.padding
        w = text_surf.get_width() + p * 2
        h = text_surf.get_height() + p * 2
        rect = pygame.Rect(self._pos[0], self._pos[1], w, h)
        pygame.draw.rect(surface, COLOR_BG_CARD, rect, border_radius=4)
        pygame.draw.rect(surface, COLOR_BORDER, rect, width=1, border_radius=4)
        surface.blit(text_surf, (rect.left + p, rect.top + p))


# ---------------------------------------------------------------------------
# TabBar
# ---------------------------------------------------------------------------

class TabBar:
    """Horizontal tab selector.

    Args:
        rect:        Bounding rect for the entire tab bar.
        tabs:        List of tab label strings.
        on_change:   Callable(selected_index) called when active tab changes.
        font_size:   Font size.
    """

    def __init__(
        self,
        rect: Any,
        tabs: list[str],
        *,
        on_change: Callable[[int], None] | None = None,
        font_size: int = 15,
    ) -> None:
        self.rect = rect
        self.tabs = tabs
        self.on_change = on_change
        self.font_size = font_size
        self.active_index: int = 0
        self._font: Any = None

    def _get_font(self) -> Any:
        if self._font is None and _PYGAME_AVAILABLE:
            self._font = pygame.font.SysFont("monospace", self.font_size, bold=True)
        return self._font

    def _tab_rect(self, index: int) -> Any:
        tab_width = self.rect.width // len(self.tabs)
        return pygame.Rect(
            self.rect.left + index * tab_width,
            self.rect.top,
            tab_width,
            self.rect.height,
        )

    def handle_event(self, event: Any) -> bool:
        if not _PYGAME_AVAILABLE:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in range(len(self.tabs)):
                if self._tab_rect(i).collidepoint(event.pos):
                    self.active_index = i
                    if self.on_change:
                        self.on_change(i)
                    return True
        return False

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: Any) -> None:
        if not _PYGAME_AVAILABLE:
            return
        font = self._get_font()
        for i, tab_label in enumerate(self.tabs):
            trect = self._tab_rect(i)
            is_active = i == self.active_index
            bg = COLOR_BG_CARD if is_active else COLOR_BG_PANEL
            border = COLOR_ACCENT_CYAN if is_active else COLOR_BORDER
            tc = COLOR_ACCENT_CYAN if is_active else COLOR_TEXT_SECONDARY
            pygame.draw.rect(surface, bg, trect)
            pygame.draw.rect(surface, border, trect, width=1)
            if font:
                ts = font.render(tab_label, True, tc)
                surface.blit(ts, ts.get_rect(center=trect.center))


# ---------------------------------------------------------------------------
# StatCounter  (animated count-up for PostRound summary)
# ---------------------------------------------------------------------------

class StatCounter:
    """Animated count-up widget for the post-round results screen.

    Counts from 0 to ``target_value`` using an ease-out curve over
    ``duration`` seconds.  An optional ``delay`` postpones the animation
    start, allowing multiple counters to be staggered.

    Args:
        pos:          (x, y) top-left of the row.
        label:        Description text shown on the left, e.g. ``"Money Earned"``.
        target_value: The final integer value to count up to.
        prefix:       String prepended to the value, e.g. ``"$"`` or ``""``.
        color:        Colour of the animated value text.
        duration:     Animation duration in seconds (default 1.5).
        delay:        Seconds to wait before animation starts (default 0.0).
        font_size:    Font size for the value text.
        label_font_size: Font size for the label text.
        width:        Row width used for right-aligning the value.
    """

    def __init__(
        self,
        pos: tuple[int, int],
        label: str,
        target_value: int,
        *,
        prefix: str = "",
        color: tuple[int, int, int] | None = None,
        duration: float = 1.5,
        delay: float = 0.0,
        font_size: int = 22,
        label_font_size: int = 16,
        width: int = 500,
    ) -> None:
        self.pos = pos
        self.label = label
        self.target_value = max(0, target_value)
        self.prefix = prefix
        self.color = color or COLOR_ACCENT_AMBER
        self.duration = max(0.01, duration)
        self.delay = delay
        self.font_size = font_size
        self.label_font_size = label_font_size
        self.width = width

        self._elapsed: float = 0.0
        self._started: bool = False
        self._finished: bool = False
        self._current_value: int = 0

        self._val_font: Any = None
        self._lbl_font: Any = None

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin (or restart) the count-up animation."""
        self._elapsed = 0.0
        self._started = True
        self._finished = False
        self._current_value = 0

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def current_value(self) -> int:
        return self._current_value

    # ------------------------------------------------------------------
    # Component interface
    # ------------------------------------------------------------------

    def handle_event(self, event: Any) -> bool:
        return False

    def update(self, dt: float) -> None:
        if not self._started or self._finished:
            return

        self._elapsed += dt
        effective = self._elapsed - self.delay
        if effective <= 0:
            self._current_value = 0
            return

        t = min(effective / self.duration, 1.0)
        # Ease-out quad: t' = 1 - (1 - t)^2
        t_eased = 1.0 - (1.0 - t) ** 2
        self._current_value = int(self.target_value * t_eased)

        if t >= 1.0:
            self._current_value = self.target_value
            self._finished = True

    def render(self, surface: Any) -> None:
        if not _PYGAME_AVAILABLE:
            return

        if self._val_font is None:
            self._val_font = pygame.font.SysFont("monospace", self.font_size, bold=True)
        if self._lbl_font is None:
            self._lbl_font = pygame.font.SysFont("monospace", self.label_font_size)

        x, y = self.pos

        # Label on the left.
        lbl_surf = self._lbl_font.render(self.label, True, COLOR_TEXT_SECONDARY)
        surface.blit(lbl_surf, (x, y + (self.font_size - self.label_font_size) // 2))

        # Animated value on the right, right-aligned within *width*.
        val_text = f"{self.prefix}{self._current_value:,}"
        val_surf = self._val_font.render(val_text, True, self.color)
        val_rect = val_surf.get_rect()
        val_rect.right = x + self.width
        val_rect.top = y
        surface.blit(val_surf, val_rect)


# ---------------------------------------------------------------------------
# FacilityCard  (HomeBase upgrade UI)
# ---------------------------------------------------------------------------

class FacilityCard:
    """Vertical card displaying a single home-base facility and its upgrade.

    Size: 180 × 220 px by default.

    Args:
        rect:              Bounding rect (should be 180×220 or similar).
        facility_id:       Internal ID, e.g. ``"armory"``.
        name:              Display name, e.g. ``"Armory"``.
        level:             Current facility level (0 = not yet upgraded).
        max_level:         Maximum upgrade level.
        upgrade_cost:      Cost of the next upgrade in currency units.
                           Ignored when ``level >= max_level``.
        bonus_description: Short description of the next-level bonus.
        can_afford:        Whether the player has enough money for the upgrade.
        on_upgrade:        Callable invoked when the upgrade button is clicked.
        icon_surface:      Optional pre-loaded ``pygame.Surface`` for the icon.
        font_size:         Base font size.
    """

    CARD_WIDTH: int = 180
    CARD_HEIGHT: int = 220
    PIP_RADIUS: int = 5
    PIP_GAP: int = 4

    def __init__(
        self,
        rect: Any,
        facility_id: str,
        name: str,
        level: int,
        max_level: int,
        upgrade_cost: int,
        bonus_description: str,
        *,
        can_afford: bool = True,
        on_upgrade: Callable[[], None] | None = None,
        icon_surface: Any = None,
        font_size: int = 14,
    ) -> None:
        self.rect = rect
        self.facility_id = facility_id
        self.name = name
        self.level = level
        self.max_level = max_level
        self.upgrade_cost = upgrade_cost
        self.bonus_description = bonus_description
        self.can_afford = can_afford
        self.on_upgrade = on_upgrade
        self.icon_surface = icon_surface
        self.font_size = font_size

        self._font: Any = None
        self._small_font: Any = None
        self._btn: Button | None = None
        self._build_button()

    def _build_button(self) -> None:
        """Create or recreate the upgrade button based on current state."""
        if not _PYGAME_AVAILABLE:
            return
        btn_w, btn_h = 140, 30
        btn_x = self.rect.left + (self.rect.width - btn_w) // 2
        btn_y = self.rect.bottom - btn_h - 10
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

        is_maxed = self.level >= self.max_level
        disabled = is_maxed or not self.can_afford

        if is_maxed:
            text = "MAX LEVEL"
        elif not self.can_afford:
            text = f"${self.upgrade_cost:,}  (NEED MORE)"
        else:
            text = f"UPGRADE  ${self.upgrade_cost:,}"

        self._btn = Button(
            rect=btn_rect,
            text=text,
            on_click=self._on_upgrade_clicked if not disabled else None,
            disabled=disabled,
            font_size=11,
            color=COLOR_ACCENT_AMBER if (not disabled) else None,
            text_color=(20, 15, 5) if (not disabled) else None,
        )

    def _on_upgrade_clicked(self) -> None:
        if self.on_upgrade:
            self.on_upgrade()

    # ------------------------------------------------------------------
    # Public helpers to refresh state from outside
    # ------------------------------------------------------------------

    def refresh(
        self,
        level: int,
        upgrade_cost: int,
        bonus_description: str,
        can_afford: bool,
    ) -> None:
        """Update card data and rebuild the button."""
        self.level = level
        self.upgrade_cost = upgrade_cost
        self.bonus_description = bonus_description
        self.can_afford = can_afford
        self._build_button()

    # ------------------------------------------------------------------
    # Component interface
    # ------------------------------------------------------------------

    def handle_event(self, event: Any) -> bool:
        if self._btn:
            return self._btn.handle_event(event)
        return False

    def update(self, dt: float) -> None:
        if self._btn:
            self._btn.update(dt)

    def render(self, surface: Any) -> None:
        if not _PYGAME_AVAILABLE:
            return

        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self.font_size, bold=True)
        if self._small_font is None:
            self._small_font = pygame.font.SysFont("monospace", self.font_size - 2)

        # Card background.
        pygame.draw.rect(surface, COLOR_BG_CARD, self.rect, border_radius=6)
        pygame.draw.rect(surface, COLOR_BORDER, self.rect, width=1, border_radius=6)

        cx = self.rect.centerx
        y = self.rect.top + 10

        # Icon placeholder (or actual icon if loaded).
        icon_size = 48
        icon_rect = pygame.Rect(cx - icon_size // 2, y, icon_size, icon_size)
        if self.icon_surface:
            scaled = pygame.transform.smoothscale(self.icon_surface, (icon_size, icon_size))
            surface.blit(scaled, icon_rect)
        else:
            pygame.draw.rect(surface, COLOR_BORDER, icon_rect, border_radius=4)
        y += icon_size + 8

        # Facility name.
        name_surf = self._font.render(self.name, True, COLOR_TEXT_PRIMARY)
        surface.blit(name_surf, name_surf.get_rect(centerx=cx, top=y))
        y += name_surf.get_height() + 8

        # Level pip row.
        total_pip_width = self.max_level * (self.PIP_RADIUS * 2) + (self.max_level - 1) * self.PIP_GAP
        pip_x = cx - total_pip_width // 2 + self.PIP_RADIUS
        for i in range(self.max_level):
            color = COLOR_PIP_FILLED if i < self.level else COLOR_PIP_EMPTY
            pygame.draw.circle(surface, color, (pip_x, y + self.PIP_RADIUS), self.PIP_RADIUS)
            pip_x += self.PIP_RADIUS * 2 + self.PIP_GAP
        y += self.PIP_RADIUS * 2 + 10

        # Level text.
        if self.level >= self.max_level:
            lvl_text = "MAX"
            lvl_color = COLOR_ACCENT_AMBER
        else:
            lvl_text = f"Lv {self.level} / {self.max_level}"
            lvl_color = COLOR_TEXT_SECONDARY
        lvl_surf = self._small_font.render(lvl_text, True, lvl_color)
        surface.blit(lvl_surf, lvl_surf.get_rect(centerx=cx, top=y))
        y += lvl_surf.get_height() + 6

        # Bonus description (next level or current max bonus).
        if self.bonus_description:
            desc_color = COLOR_ACCENT_CYAN if self.level < self.max_level else COLOR_TEXT_SECONDARY
            desc_surf = self._small_font.render(self.bonus_description, True, desc_color)
            surface.blit(desc_surf, desc_surf.get_rect(centerx=cx, top=y))

        # Upgrade button.
        if self._btn:
            self._btn.render(surface)


# ---------------------------------------------------------------------------
# ConfirmDialog
# ---------------------------------------------------------------------------

class ConfirmDialog:
    """A centered two-button confirmation overlay.

    Args:
        screen_rect:   Full-screen rect (used to center the dialog).
        message:       Primary question text.
        on_confirm:    Callable invoked when the player confirms.
        on_cancel:     Callable invoked when the player cancels.
        confirm_text:  Confirm button label (default ``"CONFIRM"``).
        cancel_text:   Cancel button label (default ``"CANCEL"``).
        width:         Dialog width in pixels.
        height:        Dialog height in pixels.
    """

    def __init__(
        self,
        screen_rect: Any,
        message: str,
        *,
        on_confirm: Callable[[], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        confirm_text: str = "CONFIRM",
        cancel_text: str = "CANCEL",
        width: int = 400,
        height: int = 180,
        font_size: int = 16,
    ) -> None:
        self.message = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.font_size = font_size
        self._font: Any = None

        if _PYGAME_AVAILABLE:
            dx = screen_rect.centerx - width // 2
            dy = screen_rect.centery - height // 2
            self.rect = pygame.Rect(dx, dy, width, height)

            btn_w, btn_h = 130, 36
            gap = 20
            total_btn_w = btn_w * 2 + gap
            btn_y = self.rect.bottom - btn_h - 20
            btn_x_start = self.rect.centerx - total_btn_w // 2

            self._confirm_btn = Button(
                rect=pygame.Rect(btn_x_start, btn_y, btn_w, btn_h),
                text=confirm_text,
                on_click=self._do_confirm,
                color=COLOR_ACCENT_CYAN,
                text_color=(5, 20, 20),
                font_size=14,
            )
            self._cancel_btn = Button(
                rect=pygame.Rect(btn_x_start + btn_w + gap, btn_y, btn_w, btn_h),
                text=cancel_text,
                on_click=self._do_cancel,
                font_size=14,
            )
        else:
            self.rect = None
            self._confirm_btn = None
            self._cancel_btn = None

    def _do_confirm(self) -> None:
        if self.on_confirm:
            self.on_confirm()

    def _do_cancel(self) -> None:
        if self.on_cancel:
            self.on_cancel()

    def handle_event(self, event: Any) -> bool:
        consumed = False
        if self._confirm_btn:
            consumed = self._confirm_btn.handle_event(event) or consumed
        if self._cancel_btn:
            consumed = self._cancel_btn.handle_event(event) or consumed
        # Eat all events while the dialog is open.
        return True

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: Any) -> None:
        if not _PYGAME_AVAILABLE or self.rect is None:
            return
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self.font_size, bold=True)

        # Dim the background.
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        pygame.draw.rect(surface, COLOR_BG_CARD, self.rect, border_radius=8)
        pygame.draw.rect(surface, COLOR_ACCENT_CYAN, self.rect, width=2, border_radius=8)

        msg_surf = self._font.render(self.message, True, COLOR_TEXT_PRIMARY)
        surface.blit(msg_surf, msg_surf.get_rect(centerx=self.rect.centerx, top=self.rect.top + 30))

        self._confirm_btn.render(surface)
        self._cancel_btn.render(surface)
