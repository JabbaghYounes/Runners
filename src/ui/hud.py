"""In-game HUD: health bar, buff icon strip, and quick-slot bar.

Three public classes:

- ``BuffIconStrip`` — subscribes to EventBus buff events and renders a
  row of active buff icons with countdown labels in the top-left corner.
- ``QuickSlotBar``  — renders 4 quick-slot panels in the bottom-right
  corner, showing the assigned item (or a dimmed placeholder).
- ``HUD``           — composite owner of both widgets; ``GameScene``
  calls ``hud.render(screen, player)`` once per frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.core.event_bus import event_bus

if TYPE_CHECKING:
    from src.entities.player import Player
    from src.inventory.inventory import Inventory
    from src.systems.buff_system import ActiveBuff


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

_C_BG       = (30,  30,  30)
_C_HEALTH   = (60, 180,  60)
_C_SLOT_BG  = (50,  50,  50)
_C_SLOT_HL  = (200, 200,  60)
_C_WHITE    = (255, 255, 255)
_C_DIM      = (100, 100, 100)
_C_SPEED    = (60,  180, 255)
_C_DAMAGE   = (255, 100,  60)
_C_GENERIC  = (180, 180, 180)


def _buff_colour(buff_type: str) -> tuple[int, int, int]:
    return {"speed": _C_SPEED, "damage": _C_DAMAGE}.get(buff_type, _C_GENERIC)


# ---------------------------------------------------------------------------
# BuffIconStrip
# ---------------------------------------------------------------------------


class BuffIconStrip:
    """Displays active buffs as a horizontal row of icon + countdown text.

    Subscribes to ``buff_applied`` / ``buff_expired`` EventBus events to
    maintain its display list in sync with the actual buff state on the
    player.  The actual ``time_remaining`` is read live from
    ``player.active_buffs`` each frame so the countdown is always accurate.

    Position: top-left of the HUD status region (below any health bar row).
    """

    ICON_SIZE: int = 32
    ICON_GAP:  int = 6
    ORIGIN_X:  int = 8
    ORIGIN_Y:  int = 56   # Sits below the health bar row

    def __init__(self) -> None:
        # List of dicts: {"buff_type": str, "icon_key": str}
        self._active: list[dict] = []
        self._font: pygame.font.Font | None = None
        event_bus.subscribe("buff_applied", self._on_buff_applied)
        event_bus.subscribe("buff_expired",  self._on_buff_expired)

    # ------------------------------------------------------------------
    # EventBus handlers
    # ------------------------------------------------------------------

    def _on_buff_applied(self, payload: dict) -> None:
        self._active.append(
            {
                "buff_type": payload.get("buff_type", ""),
                "icon_key":  payload.get("icon_key", ""),
                "duration":  payload.get("duration", 0.0),
            }
        )

    def _on_buff_expired(self, payload: dict) -> None:
        expired_type = payload.get("buff_type", "")
        for i, entry in enumerate(self._active):
            if entry["buff_type"] == expired_type:
                self._active.pop(i)
                return

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _font_obj(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 12, bold=True)
        return self._font

    def render(self, surface: pygame.Surface, player: "Player") -> None:
        """Draw buff icons left-to-right starting at (ORIGIN_X, ORIGIN_Y)."""
        font = self._font_obj()
        for col, entry in enumerate(self._active):
            x = self.ORIGIN_X + col * (self.ICON_SIZE + self.ICON_GAP)
            y = self.ORIGIN_Y

            # Background square
            bg_rect = pygame.Rect(x, y, self.ICON_SIZE, self.ICON_SIZE)
            pygame.draw.rect(surface, _C_BG, bg_rect, border_radius=4)
            pygame.draw.rect(surface, _C_DIM, bg_rect, width=1, border_radius=4)

            # Coloured inner icon placeholder
            colour = _buff_colour(entry["buff_type"])
            inner = bg_rect.inflate(-8, -8)
            pygame.draw.rect(surface, colour, inner, border_radius=2)

            # Countdown label — read live time_remaining from player state
            time_left = _time_remaining(player, entry["buff_type"])
            label = f"{int(time_left) + 1}s" if time_left > 0 else "—"
            text_surf = font.render(label, True, _C_WHITE)
            text_rect = text_surf.get_rect(
                centerx=x + self.ICON_SIZE // 2,
                top=y + self.ICON_SIZE + 2,
            )
            surface.blit(text_surf, text_rect)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def teardown(self) -> None:
        event_bus.unsubscribe("buff_applied", self._on_buff_applied)
        event_bus.unsubscribe("buff_expired",  self._on_buff_expired)


# ---------------------------------------------------------------------------
# QuickSlotBar
# ---------------------------------------------------------------------------


class QuickSlotBar:
    """4 quick-slot panels anchored to the bottom-right of the screen.

    Shows the assigned consumable icon when an item occupies the slot,
    or a dimmed placeholder otherwise.  The last-pressed slot is
    highlighted with a gold border.
    """

    SLOT_SIZE: int = 48
    SLOT_GAP:  int = 6
    MARGIN:    int = 14   # Pixels from screen right / bottom edges

    def __init__(self) -> None:
        self._active_slot: int | None = None
        self._font: pygame.font.Font | None = None

    def _font_obj(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 13, bold=True)
        return self._font

    def set_active_slot(self, slot_idx: int | None) -> None:
        """Highlight *slot_idx* (0-based).  Pass ``None`` to clear."""
        self._active_slot = slot_idx

    def render(self, surface: pygame.Surface, inventory: "Inventory") -> None:
        """Draw 4 slot panels anchored bottom-right."""
        screen_w, screen_h = surface.get_size()
        font = self._font_obj()

        total_w = 4 * self.SLOT_SIZE + 3 * self.SLOT_GAP
        start_x = screen_w - self.MARGIN - total_w
        start_y = screen_h - self.MARGIN - self.SLOT_SIZE

        for i in range(4):
            x = start_x + i * (self.SLOT_SIZE + self.SLOT_GAP)
            slot_rect = pygame.Rect(x, start_y, self.SLOT_SIZE, self.SLOT_SIZE)

            # Background
            pygame.draw.rect(surface, _C_SLOT_BG, slot_rect, border_radius=6)

            # Border — gold when active, dim otherwise
            border_col = _C_SLOT_HL if i == self._active_slot else _C_DIM
            pygame.draw.rect(surface, border_col, slot_rect, width=2, border_radius=6)

            # Key number in top-left of slot
            key_surf = font.render(str(i + 1), True, _C_WHITE)
            surface.blit(key_surf, (x + 3, start_y + 3))

            # Item representation
            item = inventory.quick_slot_item(i)
            if item is not None:
                # Coloured block placeholder (replace with sprite blit later)
                icon_rect = slot_rect.inflate(-12, -12)
                pygame.draw.rect(surface, _C_HEALTH, icon_rect, border_radius=3)
                # Abbreviated item name centred in slot
                abbr = item.name[:5]
                abbr_surf = font.render(abbr, True, _C_WHITE)
                abbr_rect = abbr_surf.get_rect(center=slot_rect.center)
                surface.blit(abbr_surf, abbr_rect)
            else:
                # Empty placeholder
                ph = font.render("—", True, _C_DIM)
                surface.blit(ph, ph.get_rect(center=slot_rect.center))


# ---------------------------------------------------------------------------
# HUD — composite owner
# ---------------------------------------------------------------------------


class HUD:
    """Composite in-game overlay.

    Owns ``BuffIconStrip`` and ``QuickSlotBar``.  ``GameScene`` calls
    ``hud.render(screen, player)`` each frame after all world rendering.
    """

    BAR_HEIGHT: int = 14
    BAR_WIDTH:  int = 200

    def __init__(self) -> None:
        self._buff_strip  = BuffIconStrip()
        self._quick_slots = QuickSlotBar()
        self._font: pygame.font.Font | None = None

    def _font_obj(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 13)
        return self._font

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_active_quick_slot(self, slot_idx: int | None) -> None:
        """Forward active-slot highlight to the QuickSlotBar."""
        self._quick_slots.set_active_slot(slot_idx)

    def render(self, surface: pygame.Surface, player: "Player") -> None:
        """Render all HUD elements onto *surface*."""
        self._render_health_bar(surface, player)
        self._buff_strip.render(surface, player)
        if player.inventory is not None:
            self._quick_slots.render(surface, player.inventory)

    def teardown(self) -> None:
        """Unsubscribe event handlers — call when the scene is destroyed."""
        self._buff_strip.teardown()

    # ------------------------------------------------------------------
    # Health bar
    # ------------------------------------------------------------------

    def _render_health_bar(self, surface: pygame.Surface, player: "Player") -> None:
        font = self._font_obj()
        x, y = 8, 8

        # Background track
        bg = pygame.Rect(x, y, self.BAR_WIDTH, self.BAR_HEIGHT)
        pygame.draw.rect(surface, _C_BG, bg, border_radius=3)

        # Health fill
        ratio = max(0.0, player.health / player.max_health)
        fill_w = int(self.BAR_WIDTH * ratio)
        if fill_w > 0:
            fill = pygame.Rect(x, y, fill_w, self.BAR_HEIGHT)
            pygame.draw.rect(surface, _C_HEALTH, fill, border_radius=3)

        # Label
        label = f"HP {player.health}/{player.max_health}"
        label_surf = font.render(label, True, _C_WHITE)
        surface.blit(label_surf, (x + 4, y + 1))


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _time_remaining(player: "Player", buff_type: str) -> float:
    """Return the time_remaining of the first matching buff on *player*."""
    for buff in player.active_buffs:
        if buff.buff_type == buff_type:
            return buff.time_remaining
    return 0.0
