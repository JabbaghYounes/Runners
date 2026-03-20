"""InventoryScreen — full inventory panel with a 4×6 item grid and armor slot.

The screen is pushed as an overlay on top of GameScene (via SceneManager.push).
It holds a reference to the player's :class:`Inventory` and directly calls
:meth:`Inventory.equip_armor` / :meth:`Inventory.unequip_armor` on click.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.scenes.base_scene import BaseScene
from src.constants import (
    SCREEN_W, SCREEN_H,
    BG_PANEL, BORDER_DIM,
    TEXT_PRIMARY, TEXT_DIM,
    ACCENT_CYAN,
    RARITY_COLORS,
)

if TYPE_CHECKING:
    from src.inventory.inventory import Inventory
    from src.inventory.item import Item


# ── Layout constants ──────────────────────────────────────────────────────────

_SLOT_SIZE = 64       # px — each item cell (square)
_SLOT_GAP  =  6       # px — gap between cells
_COLS      =  6       # grid columns
_ROWS      =  4       # grid rows  (24 main slots total)

# Width of the main grid section
_GRID_W = _COLS * (_SLOT_SIZE + _SLOT_GAP) + _SLOT_GAP
# Width of the right armor-slot panel
_ARMOR_PANEL_W = _SLOT_SIZE + 48
# Total panel dimensions
_PANEL_W = _GRID_W + _ARMOR_PANEL_W + _SLOT_GAP * 2 + 20
_PANEL_H = _ROWS * (_SLOT_SIZE + _SLOT_GAP) + _SLOT_GAP + 70   # rows + header
_PANEL_X = (SCREEN_W - _PANEL_W) // 2
_PANEL_Y = (SCREEN_H - _PANEL_H) // 2


class InventoryScreen(BaseScene):
    """Inventory overlay with a 4×6 item grid and a dedicated armor slot panel.

    Construction:
        ``InventoryScreen(inventory=inv)``  — pass the player's
        :class:`Inventory` reference on creation; it can also be updated later
        via :attr:`inventory`.
    """

    def __init__(self, inventory: "Inventory | None" = None) -> None:
        self._inventory: Inventory | None = inventory
        self._font_title: pygame.font.Font | None = None
        self._font_body: pygame.font.Font | None = None
        self._font_small: pygame.font.Font | None = None
        self._hovered_slot: int | None = None   # index into main grid (0-based)

    @property
    def inventory(self) -> "Inventory | None":
        return self._inventory

    @inventory.setter
    def inventory(self, inv: "Inventory | None") -> None:
        self._inventory = inv

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self) -> None:
        self._font_title = pygame.font.Font(None, 28)
        self._font_body  = pygame.font.Font(None, 22)
        self._font_small = pygame.font.Font(None, 16)

    # ── Geometry helpers ──────────────────────────────────────────────────────

    def _slot_rect(self, idx: int) -> pygame.Rect:
        """Return the on-screen rect for main-grid slot *idx* (row-major)."""
        col = idx % _COLS
        row = idx // _COLS
        x = _PANEL_X + _SLOT_GAP + col * (_SLOT_SIZE + _SLOT_GAP)
        y = _PANEL_Y + 50 + _SLOT_GAP + row * (_SLOT_SIZE + _SLOT_GAP)
        return pygame.Rect(x, y, _SLOT_SIZE, _SLOT_SIZE)

    def _armor_slot_rect(self) -> pygame.Rect:
        """Return the on-screen rect for the dedicated armor slot."""
        ax = _PANEL_X + _GRID_W + _SLOT_GAP * 2 + 10
        ay = _PANEL_Y + 50 + _SLOT_GAP + 40
        return pygame.Rect(ax, ay, _SLOT_SIZE + 20, _SLOT_SIZE + 20)

    def _slot_at(self, pos: tuple[int, int]) -> int | None:
        """Return the main-grid slot index under screen position *pos*, or None."""
        if self._inventory is None:
            return None
        n = min(self._inventory.capacity, _COLS * _ROWS)
        for i in range(n):
            if self._slot_rect(i).collidepoint(pos):
                return i
        return None

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)
            elif event.type == pygame.MOUSEMOTION:
                self._hovered_slot = self._slot_at(event.pos)

    def _handle_click(self, pos: tuple[int, int]) -> None:
        inv = self._inventory
        if inv is None:
            return

        # Click on the armor slot → unequip and return to first free main slot
        if self._armor_slot_rect().collidepoint(pos):
            if inv.equipped_armor is not None:
                item = inv.unequip_armor()
                if item is not None:
                    result = inv.add_item(item)
                    if result is None:
                        # No room — emit an event so the caller can surface it
                        from src.core.event_bus import event_bus
                        event_bus.emit("inventory_full", item=item)
            return

        # Click on a main-grid slot
        slot_idx = self._slot_at(pos)
        if slot_idx is None:
            return
        item = inv.item_at(slot_idx)
        if item is None:
            return

        # Only armor items can be equipped from the grid
        from src.inventory.item import Armor
        if not isinstance(item, Armor):
            return

        # Remove from grid first, then equip (handles single-slot safety)
        inv.remove_item(slot_idx)
        displaced = inv.equip_armor(item)

        # If a piece was displaced, return it to the grid
        if displaced is not None:
            result = inv.add_item(displaced)
            if result is None:
                # No room for displaced armor; emit inventory_full
                from src.core.event_bus import event_bus
                event_bus.emit("inventory_full", item=displaced)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        pass  # static overlay — no per-frame logic needed

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, screen: pygame.Surface) -> None:
        # Lazy font init (defensive — on_enter may not have been called in tests)
        if self._font_title is None:
            self._font_title = pygame.font.Font(None, 28)
            self._font_body  = pygame.font.Font(None, 22)
            self._font_small = pygame.font.Font(None, 16)

        # Darken the scene behind the overlay
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        # Main panel background
        panel_surf = pygame.Surface((_PANEL_W, _PANEL_H), pygame.SRCALPHA)
        r, g, b = BG_PANEL
        panel_surf.fill((r, g, b, 235))
        screen.blit(panel_surf, (_PANEL_X, _PANEL_Y))
        pygame.draw.rect(
            screen, BORDER_DIM,
            (_PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H),
            width=1, border_radius=8,
        )

        # Title
        title_surf = self._font_title.render("INVENTORY", True, ACCENT_CYAN)
        screen.blit(title_surf, (_PANEL_X + 12, _PANEL_Y + 14))

        self._render_grid(screen)
        self._render_armor_slot(screen)

    # ── Sub-renderers ─────────────────────────────────────────────────────────

    def _render_grid(self, screen: pygame.Surface) -> None:
        inv = self._inventory
        for i in range(_COLS * _ROWS):
            rect = self._slot_rect(i)
            item: Item | None = inv.item_at(i) if inv is not None else None
            hovered = (self._hovered_slot == i)

            # Slot background + border
            bg_clr     = (30, 38, 55) if hovered else (20, 24, 38)
            border_clr = ACCENT_CYAN  if hovered else BORDER_DIM
            pygame.draw.rect(screen, bg_clr, rect, border_radius=4)
            pygame.draw.rect(screen, border_clr, rect, width=1, border_radius=4)

            if item is None:
                continue

            # Rarity-coloured border
            rarity_key = (
                item.rarity.value
                if hasattr(item.rarity, 'value')
                else str(item.rarity)
            )
            rarity_clr = RARITY_COLORS.get(rarity_key, (180, 180, 180))
            pygame.draw.rect(screen, rarity_clr, rect, width=2, border_radius=4)

            # Item name (truncated to fit)
            name = item.name[:9] if len(item.name) > 9 else item.name
            name_surf = self._font_small.render(name, True, TEXT_PRIMARY)
            screen.blit(name_surf, (rect.x + 4, rect.y + 4))

            # Item type tag in the lower-left corner
            tag = item.item_type[:6]
            tag_surf = self._font_small.render(tag, True, TEXT_DIM)
            screen.blit(tag_surf, (rect.x + 4, rect.bottom - tag_surf.get_height() - 3))

    def _render_armor_slot(self, screen: pygame.Surface) -> None:
        inv = self._inventory
        equipped = inv.equipped_armor if inv is not None else None
        rect = self._armor_slot_rect()

        # Label above the slot
        lbl_surf = self._font_body.render("ARMOR SLOT", True, ACCENT_CYAN)
        screen.blit(lbl_surf, (rect.x, rect.y - lbl_surf.get_height() - 4))

        # Slot background + border
        bg_clr     = (25, 32, 50) if equipped else (18, 22, 34)
        border_clr = ACCENT_CYAN  if equipped else BORDER_DIM
        border_w   = 2            if equipped else 1
        pygame.draw.rect(screen, bg_clr, rect, border_radius=6)
        pygame.draw.rect(screen, border_clr, rect, width=border_w, border_radius=6)

        if equipped is None:
            # Empty slot hint
            empty_surf = self._font_small.render("EMPTY", True, TEXT_DIM)
            cx = rect.x + (rect.width  - empty_surf.get_width())  // 2
            cy = rect.y + (rect.height - empty_surf.get_height()) // 2
            screen.blit(empty_surf, (cx, cy))
            return

        # Rarity border
        rarity_key = (
            equipped.rarity.value
            if hasattr(equipped.rarity, 'value')
            else str(equipped.rarity)
        )
        rarity_clr = RARITY_COLORS.get(rarity_key, (180, 180, 180))
        pygame.draw.rect(screen, rarity_clr, rect, width=3, border_radius=6)

        # Item name
        name = equipped.name[:10] if len(equipped.name) > 10 else equipped.name
        name_surf = self._font_body.render(name, True, TEXT_PRIMARY)
        screen.blit(name_surf, (rect.x + 6, rect.y + 8))

        # Armor rating
        rating_surf = self._font_small.render(
            f"DEF  {equipped.armor_rating}", True, ACCENT_CYAN
        )
        screen.blit(rating_surf, (rect.x + 6, rect.y + 32))

        # Unequip hint
        hint_surf = self._font_small.render("[click to unequip]", True, TEXT_DIM)
        screen.blit(
            hint_surf,
            (rect.x + 6, rect.bottom - hint_surf.get_height() - 4),
        )
