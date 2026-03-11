"""Reusable UI widget primitives.

Design system colours:
    BG_DEEP      = (10, 14, 26)      # #0A0E1A
    BG_PANEL     = (20, 24, 38)      # #141826
    ACCENT_CYAN  = (0, 245, 255)     # #00F5FF
    ACCENT_AMBER = (255, 184, 0)     # #FFB800
    ACCENT_GREEN = (57, 255, 20)     # #39FF14
    DANGER_RED   = (255, 32, 64)     # #FF2040
    BORDER_DIM   = (42, 48, 80)      # #2A3050
    TEXT_PRIMARY = (255, 255, 255)
    TEXT_SECONDARY = (154, 163, 192) # #9AA3C0
    TEXT_DISABLED  = (58, 64, 96)    # #3A4060
"""
from __future__ import annotations
from typing import Callable, Optional, Tuple

# ---------------------------------------------------------------------------
# Design system palette (module-level constants)
# ---------------------------------------------------------------------------
BG_DEEP       = (10, 14, 26)
BG_PANEL      = (20, 24, 38)
ACCENT_CYAN   = (0, 245, 255)
ACCENT_AMBER  = (255, 184, 0)
ACCENT_GREEN  = (57, 255, 20)
ACCENT_MAGENTA= (255, 0, 128)
DANGER_RED    = (255, 32, 64)
BORDER_DIM    = (42, 48, 80)
TEXT_PRIMARY  = (255, 255, 255)
TEXT_SECONDARY= (154, 163, 192)
TEXT_DISABLED = (58, 64, 96)

# ---------------------------------------------------------------------------
# Legacy private names kept for backwards-compat with the Slider pyc artefact
# ---------------------------------------------------------------------------
_BG_PANEL  = BG_PANEL
_TRACK_CLR = (42, 48, 80)
_THUMB_CLR = ACCENT_CYAN
_LABEL_CLR = TEXT_SECONDARY
_BORDER_CLR = BORDER_DIM


# ---------------------------------------------------------------------------
# Slider (preserved from original)
# ---------------------------------------------------------------------------
class Slider:
    """Horizontal drag slider for numeric settings (e.g. volume)."""

    def __init__(
        self,
        rect,
        min_val: float,
        max_val: float,
        initial: float,
        label: str = "",
        on_change: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.rect = rect
        self.min_val = min_val
        self.max_val = max_val
        self.value = float(initial)
        self.label = label
        self.on_change = on_change
        self._dragging = False

    # ------------------------------------------------------------------
    # Internal geometry helpers
    # ------------------------------------------------------------------
    def _track_x(self) -> int:   return self.rect.x + 8
    def _track_y(self) -> int:   return self.rect.y + self.rect.height // 2
    def _track_w(self) -> int:   return self.rect.width - 16
    def _track_h(self) -> int:   return 4

    def _value_to_px(self, frac: float) -> int:
        return self._track_x() + int(frac * self._track_w())

    def _px_to_value(self, px: int) -> float:
        frac = (px - self._track_x()) / max(1, self._track_w())
        frac = max(0.0, min(1.0, frac))
        return self.min_val + frac * (self.max_val - self.min_val)

    def _thumb_rect(self, pygame):
        frac = (self.value - self.min_val) / max(1e-9, self.max_val - self.min_val)
        cx = self._value_to_px(frac)
        th = 14
        return pygame.Rect(cx - th // 2, self._track_y() - th // 2, th, th)

    def _set_from_px(self, px: int) -> None:
        new_val = self._px_to_value(px)
        if new_val != self.value:
            self.value = new_val
            if self.on_change:
                self.on_change(self.value)

    # ------------------------------------------------------------------
    # Event & render
    # ------------------------------------------------------------------
    def handle_event(self, event) -> bool:
        import pygame
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._thumb_rect(pygame).collidepoint(event.pos):
                self._dragging = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self._set_from_px(event.pos[0])
            return True
        return False

    def render(self, surface, font=None) -> None:
        import pygame
        x, y, w, h = self.rect
        tx = self._track_x()
        ty = self._track_y()
        tw = self._track_w()
        # Track background
        pygame.draw.rect(surface, _TRACK_CLR, (tx, ty - 2, tw, 4), border_radius=2)
        # Filled portion
        frac = (self.value - self.min_val) / max(1e-9, self.max_val - self.min_val)
        fill_w = int(frac * tw)
        pygame.draw.rect(surface, _THUMB_CLR, (tx, ty - 2, fill_w, 4), border_radius=2)
        # Thumb
        th_rect = self._thumb_rect(pygame)
        pygame.draw.ellipse(surface, _THUMB_CLR, th_rect)
        # Label + value
        if font:
            pct = int(frac * 100)
            text = f"{self.label}: {pct}%"
            surf = font.render(text, True, _LABEL_CLR)
            surface.blit(surf, (x, y + 2))


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------
_BUTTON_STYLES = {
    "primary":   {"bg": (0, 100, 130),   "hover": (0, 150, 180),  "text": TEXT_PRIMARY,  "border": ACCENT_CYAN},
    "secondary": {"bg": (42, 48, 80),    "hover": (62, 70, 110),  "text": TEXT_PRIMARY,  "border": BORDER_DIM},
    "danger":    {"bg": (120, 20, 40),   "hover": (180, 30, 60),  "text": TEXT_PRIMARY,  "border": DANGER_RED},
    "ghost":     {"bg": (0, 0, 0, 0),    "hover": (30, 36, 60),   "text": TEXT_SECONDARY,"border": BORDER_DIM},
}


class Button:
    """Clickable button widget.

    Args:
        label: Display text.
        rect: pygame.Rect for position and size.
        style: "primary" | "secondary" | "danger" | "ghost".
        enabled: Whether the button responds to input.
        on_click: Callable invoked on left-click.
    """

    def __init__(
        self,
        label: str,
        rect,
        style: str = "primary",
        enabled: bool = True,
        on_click: Optional[Callable] = None,
    ) -> None:
        self.label = label
        self.rect = rect
        self.style = style
        self.enabled = enabled
        self.on_click = on_click
        self._hovered = False
        self._pressed = False

    def handle_event(self, event) -> bool:
        import pygame
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self.rect.collidepoint(event.pos):
                self._pressed = False
                if self.on_click:
                    self.on_click()
                return True
            self._pressed = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            if self._hovered and self.on_click:
                self.on_click()
                return True
        return False

    def render(self, surface) -> None:
        import pygame
        style = _BUTTON_STYLES.get(self.style, _BUTTON_STYLES["secondary"])
        if not self.enabled:
            bg_color = (30, 34, 50)
            text_color = TEXT_DISABLED
            border_color = BORDER_DIM
        elif self._hovered or self._pressed:
            bg_color = style["hover"]
            text_color = style["text"]
            border_color = style["border"]
        else:
            bg_color = style["bg"]
            text_color = style["text"]
            border_color = style["border"]

        pygame.draw.rect(surface, bg_color, self.rect, border_radius=4)
        pygame.draw.rect(surface, border_color, self.rect, 1, border_radius=4)

        font = pygame.font.SysFont("monospace", 15, bold=True)
        text_surf = font.render(self.label, True, text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
class Panel:
    """Rectangular background panel (base for cards, modals, HUD regions).

    Args:
        rect: Bounding rectangle.
        bg_color: Fill colour.
        border_color: Border colour.
        border_width: Border thickness (default 1).
        corner_radius: Rounded corner radius (default 6).
        glow: If True, draws a second slightly-larger border for bloom effect.
    """

    def __init__(
        self,
        rect,
        bg_color: Tuple = BG_PANEL,
        border_color: Tuple = BORDER_DIM,
        border_width: int = 1,
        corner_radius: int = 6,
        glow: bool = False,
    ) -> None:
        self.rect = rect
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        self.corner_radius = corner_radius
        self.glow = glow

    def handle_event(self, event) -> bool:
        return False

    def render(self, surface) -> None:
        import pygame
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=self.corner_radius)
        if self.border_width > 0:
            pygame.draw.rect(
                surface, self.border_color, self.rect,
                self.border_width, border_radius=self.corner_radius
            )
        if self.glow:
            glow_rect = self.rect.inflate(4, 4)
            glow_color = (*self.border_color[:3], 80)
            glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(
                glow_surf, glow_color,
                glow_surf.get_rect(), 2, border_radius=self.corner_radius + 2
            )
            surface.blit(glow_surf, glow_rect.topleft)


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------
class Label:
    """Text label widget.

    Args:
        text: Display string.
        rect: Bounding rect (used for alignment).
        font_size: Pixel font size.
        color: Text colour.
        bold: Whether to use bold weight.
        align: "left" | "center" | "right".
        glow: Render a subtle neon glow.
    """

    def __init__(
        self,
        text: str,
        rect,
        font_size: int = 16,
        color: Tuple = TEXT_PRIMARY,
        bold: bool = False,
        align: str = "left",
        glow: bool = False,
    ) -> None:
        self.text = text
        self.rect = rect
        self.font_size = font_size
        self.color = color
        self.bold = bold
        self.align = align
        self.glow = glow

    def handle_event(self, event) -> bool:
        return False

    def render(self, surface) -> None:
        import pygame
        font = pygame.font.SysFont("monospace", self.font_size, bold=self.bold)
        text_surf = font.render(self.text, True, self.color)
        if self.align == "center":
            text_rect = text_surf.get_rect(centerx=self.rect.centerx, y=self.rect.y)
        elif self.align == "right":
            text_rect = text_surf.get_rect(right=self.rect.right, y=self.rect.y)
        else:
            text_rect = text_surf.get_rect(x=self.rect.x, y=self.rect.y)
        surface.blit(text_surf, text_rect)


# ---------------------------------------------------------------------------
# ProgressBar
# ---------------------------------------------------------------------------
_BAR_VARIANTS = {
    "health": {"fill": (0, 245, 255), "bg": (30, 34, 50)},
    "armor":  {"fill": (100, 150, 200), "bg": (30, 34, 50)},
    "xp":     {"fill": ACCENT_GREEN, "bg": (20, 30, 20)},
    "reload": {"fill": ACCENT_AMBER, "bg": (40, 34, 20)},
    "timer":  {"fill": ACCENT_AMBER, "bg": (30, 34, 50)},
    "generic":{"fill": (100, 140, 200), "bg": (30, 34, 50)},
}


class ProgressBar:
    """Horizontal progress bar.

    Args:
        value: Current value.
        max_value: Maximum value.
        rect: Bounding rectangle.
        fill_color: Bar fill colour (overrides variant default).
        bg_color: Bar background colour.
        show_text: Display "value / max_value" overlay text.
        variant: Pre-configured style variant.
    """

    def __init__(
        self,
        value: float,
        max_value: float,
        rect,
        fill_color: Optional[Tuple] = None,
        bg_color: Optional[Tuple] = None,
        show_text: bool = False,
        variant: str = "generic",
    ) -> None:
        self.value = value
        self.max_value = max_value
        self.rect = rect
        _v = _BAR_VARIANTS.get(variant, _BAR_VARIANTS["generic"])
        self.fill_color = fill_color or _v["fill"]
        self.bg_color   = bg_color   or _v["bg"]
        self.show_text = show_text
        self.variant = variant

    def handle_event(self, event) -> bool:
        return False

    def render(self, surface) -> None:
        import pygame
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=3)
        if self.max_value > 0:
            frac = max(0.0, min(1.0, self.value / self.max_value))
            fill_w = int(self.rect.width * frac)
            if fill_w > 0:
                fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_w, self.rect.height)
                pygame.draw.rect(surface, self.fill_color, fill_rect, border_radius=3)
        if self.show_text:
            font = pygame.font.SysFont("monospace", 12)
            text = f"{int(self.value)}/{int(self.max_value)}"
            surf = font.render(text, True, TEXT_PRIMARY)
            r = surf.get_rect(center=self.rect.center)
            surface.blit(surf, r)


# ---------------------------------------------------------------------------
# TabBar
# ---------------------------------------------------------------------------
class TabBar:
    """Horizontal tab bar widget.

    Args:
        tabs: List of tab label strings.
        active_index: Index of the currently active tab.
        rect: Bounding rectangle for the full tab bar.
        on_change: Callable(new_index: int) called when tab changes.
    """

    def __init__(
        self,
        tabs: list[str],
        active_index: int,
        rect,
        on_change: Optional[Callable[[int], None]] = None,
    ) -> None:
        self.tabs = tabs
        self.active_index = active_index
        self.rect = rect
        self.on_change = on_change
        self._hovered: Optional[int] = None

    def handle_event(self, event) -> bool:
        import pygame
        tab_w = self.rect.width // max(1, len(self.tabs))
        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            if self.rect.collidepoint(mx, my):
                idx = (mx - self.rect.x) // tab_w
                self._hovered = idx if 0 <= idx < len(self.tabs) else None
            else:
                self._hovered = None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self.rect.collidepoint(mx, my):
                idx = (mx - self.rect.x) // tab_w
                if 0 <= idx < len(self.tabs) and idx != self.active_index:
                    self.active_index = idx
                    if self.on_change:
                        self.on_change(idx)
                    return True
        return False

    def render(self, surface) -> None:
        import pygame
        tab_w = self.rect.width // max(1, len(self.tabs))
        font = pygame.font.SysFont("monospace", 15, bold=True)
        for i, tab in enumerate(self.tabs):
            tx = self.rect.x + i * tab_w
            ty = self.rect.y
            is_active = (i == self.active_index)
            is_hovered = (i == self._hovered)
            color = ACCENT_CYAN if is_active else (TEXT_PRIMARY if is_hovered else TEXT_SECONDARY)
            surf = font.render(tab, True, color)
            r = surf.get_rect(centerx=tx + tab_w // 2, centery=ty + self.rect.height // 2)
            surface.blit(surf, r)
            if is_active:
                underline_y = ty + self.rect.height - 3
                pygame.draw.line(
                    surface, ACCENT_CYAN,
                    (tx + 4, underline_y),
                    (tx + tab_w - 4, underline_y),
                    2,
                )


# ---------------------------------------------------------------------------
# FacilityCard
# ---------------------------------------------------------------------------
class FacilityCard:
    """Vertical facility upgrade card (~180×220px).

    Layout (top to bottom):
        facility name  →  pip row (level indicators)  →  bonus description
        →  cost badge  →  UPGRADE button
    """

    def __init__(
        self,
        facility_id: str,
        name: str,
        level: int,
        max_level: int,
        upgrade_cost: Optional[int],
        bonus_description: str,
        can_afford: bool,
        on_upgrade: Optional[Callable],
        rect,
    ) -> None:
        self.facility_id = facility_id
        self.name = name
        self.level = level
        self.max_level = max_level
        self.upgrade_cost = upgrade_cost
        self.bonus_description = bonus_description
        self.can_afford = can_afford
        self.on_upgrade = on_upgrade
        self.rect = rect
        self._build_widgets()

    def _build_widgets(self) -> None:
        import pygame
        is_maxed = (self.upgrade_cost is None)
        btn_label = "MAXED OUT" if is_maxed else "UPGRADE"
        btn_enabled = (not is_maxed) and self.can_afford
        btn_style = "secondary" if is_maxed else ("primary" if self.can_afford else "danger")

        btn_rect = pygame.Rect(
            self.rect.x + 10,
            self.rect.y + self.rect.height - 44,
            self.rect.width - 20,
            34,
        )
        self._btn = Button(
            label=btn_label,
            rect=btn_rect,
            style=btn_style,
            enabled=btn_enabled,
            on_click=self._on_click,
        )

    def _on_click(self) -> None:
        if self.on_upgrade:
            self.on_upgrade(self.facility_id)

    def update(
        self,
        level: int,
        upgrade_cost: Optional[int],
        bonus_description: str,
        can_afford: bool,
    ) -> None:
        """Refresh displayed values after an upgrade."""
        self.level = level
        self.upgrade_cost = upgrade_cost
        self.bonus_description = bonus_description
        self.can_afford = can_afford
        self._build_widgets()

    def handle_event(self, event) -> bool:
        return self._btn.handle_event(event)

    def render(self, surface) -> None:
        import pygame
        # Card background
        panel = Panel(self.rect, bg_color=BG_PANEL, border_color=BORDER_DIM,
                      border_width=1, corner_radius=6)
        panel.render(surface)

        font_title = pygame.font.SysFont("monospace", 14, bold=True)
        font_body  = pygame.font.SysFont("monospace", 12)

        # Facility name
        name_surf = font_title.render(self.name, True, ACCENT_CYAN)
        name_rect = name_surf.get_rect(centerx=self.rect.centerx, y=self.rect.y + 10)
        surface.blit(name_surf, name_rect)

        # Pip row (filled = upgraded, empty = not yet)
        pip_y = self.rect.y + 36
        pip_r = 6
        pip_spacing = 16
        total_w = self.max_level * pip_spacing - (pip_spacing - pip_r * 2)
        pip_x_start = self.rect.centerx - total_w // 2
        for i in range(self.max_level):
            cx = pip_x_start + i * pip_spacing + pip_r
            filled = (i < self.level)
            color = ACCENT_CYAN if filled else BORDER_DIM
            pygame.draw.circle(surface, color, (cx, pip_y), pip_r)
            if not filled:
                pygame.draw.circle(surface, BORDER_DIM, (cx, pip_y), pip_r, 1)

        # Level text
        lvl_text = f"Lv {self.level}/{self.max_level}"
        lvl_surf = font_body.render(lvl_text, True, TEXT_SECONDARY)
        surface.blit(lvl_surf, (self.rect.centerx - lvl_surf.get_width() // 2, pip_y + 14))

        # Bonus description
        desc_surf = font_body.render(self.bonus_description, True, TEXT_SECONDARY)
        desc_rect = desc_surf.get_rect(centerx=self.rect.centerx, y=self.rect.y + 75)
        surface.blit(desc_surf, desc_rect)

        # Cost badge
        if self.upgrade_cost is not None:
            cost_color = ACCENT_AMBER if self.can_afford else DANGER_RED
            cost_text = f"${self.upgrade_cost:,}"
        else:
            cost_color = TEXT_DISABLED
            cost_text = "MAX"
        cost_surf = font_title.render(cost_text, True, cost_color)
        cost_rect = cost_surf.get_rect(centerx=self.rect.centerx, y=self.rect.y + 100)
        surface.blit(cost_surf, cost_rect)

        # Upgrade button
        self._btn.render(surface)


# ---------------------------------------------------------------------------
# ConfirmDialog
# ---------------------------------------------------------------------------
class ConfirmDialog:
    """Modal confirmation dialog with dark overlay.

    Args:
        title: Heading text.
        body: Explanatory message.
        confirm_label: Confirm button label (default "CONFIRM").
        cancel_label: Cancel button label (default "CANCEL").
        on_confirm: Callable invoked on confirm.
        on_cancel: Callable invoked on cancel / ESC.
        danger: Apply DANGER_RED styling to the confirm button.
    """

    _DIALOG_W = 380
    _DIALOG_H = 180

    def __init__(
        self,
        title: str,
        body: str,
        confirm_label: str = "CONFIRM",
        cancel_label: str = "CANCEL",
        on_confirm: Optional[Callable] = None,
        on_cancel: Optional[Callable] = None,
        danger: bool = False,
    ) -> None:
        self.title = title
        self.body = body
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.danger = danger
        self._initialized = False
        self._confirm_btn: Optional[Button] = None
        self._cancel_btn: Optional[Button] = None

    def _ensure_init(self, surface) -> None:
        if self._initialized:
            return
        import pygame
        sw, sh = surface.get_size()
        cx = (sw - self._DIALOG_W) // 2
        cy = (sh - self._DIALOG_H) // 2
        btn_w = 140
        btn_h = 36
        gap = 16
        total_btn_w = btn_w * 2 + gap
        btn_start_x = cx + (self._DIALOG_W - total_btn_w) // 2
        btn_y = cy + self._DIALOG_H - btn_h - 16
        self._confirm_btn = Button(
            label=confirm_label if hasattr(self, '_confirm_label_cached') else "CONFIRM",
            rect=pygame.Rect(btn_start_x, btn_y, btn_w, btn_h),
            style="danger" if self.danger else "primary",
            on_click=self._on_confirm_click,
        )
        self._cancel_btn = Button(
            label="CANCEL",
            rect=pygame.Rect(btn_start_x + btn_w + gap, btn_y, btn_w, btn_h),
            style="secondary",
            on_click=self._on_cancel_click,
        )
        self._dialog_rect = pygame.Rect(cx, cy, self._DIALOG_W, self._DIALOG_H)
        self._initialized = True

    def _build(self, surface) -> None:
        """Force re-init (useful after label change)."""
        self._initialized = False
        self._ensure_init(surface)

    def _on_confirm_click(self) -> None:
        if self.on_confirm:
            self.on_confirm()

    def _on_cancel_click(self) -> None:
        if self.on_cancel:
            self.on_cancel()

    def handle_event(self, event) -> bool:
        import pygame
        self._ensure_init_stub()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.on_cancel:
                self.on_cancel()
            return True
        consumed = False
        if self._confirm_btn:
            consumed = self._confirm_btn.handle_event(event) or consumed
        if self._cancel_btn:
            consumed = self._cancel_btn.handle_event(event) or consumed
        return consumed

    def _ensure_init_stub(self) -> None:
        """Called from handle_event before we have a surface."""
        pass

    def render(self, surface) -> None:
        import pygame
        self._ensure_init(surface)
        sw, sh = surface.get_size()
        # Dark overlay
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        # Dialog panel
        panel = Panel(
            self._dialog_rect,
            bg_color=BG_PANEL,
            border_color=DANGER_RED if self.danger else ACCENT_CYAN,
            border_width=2,
            corner_radius=8,
        )
        panel.render(surface)
        # Title
        font_title = pygame.font.SysFont("monospace", 16, bold=True)
        font_body  = pygame.font.SysFont("monospace", 13)
        title_surf = font_title.render(self.title, True, DANGER_RED if self.danger else ACCENT_CYAN)
        surface.blit(title_surf, (self._dialog_rect.x + 20, self._dialog_rect.y + 18))
        # Body
        body_surf = font_body.render(self.body, True, TEXT_SECONDARY)
        surface.blit(body_surf, (self._dialog_rect.x + 20, self._dialog_rect.y + 50))
        # Buttons
        if self._confirm_btn:
            self._confirm_btn.render(surface)
        if self._cancel_btn:
            self._cancel_btn.render(surface)

    def set_labels(self, confirm: str, cancel: str) -> None:
        """Update button labels (forces re-init on next render)."""
        self._confirm_label = confirm
        self._cancel_label = cancel
        self._initialized = False
