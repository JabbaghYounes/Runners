"""Inventory overlay scene -- opened with Tab, closed with Tab / ESC.

Push/pop semantics: GameScene pushes this on K_TAB; InventoryScreen pops
itself when K_TAB or K_ESCAPE is pressed, resuming GameScene underneath.

Grid layout
-----------
6 columns × 4 rows = 24 general slots, each 56 × 56 px with a 6 px gap.
A quick-slot strip (4 slots, same size) sits below the main grid.
Right-clicking an occupied grid slot assigns it to the next free quick-slot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

import pygame

from src.scenes.base_scene import BaseScene
from src.constants import (
    ACCENT_CYAN,
    ACCENT_GREEN,
    BORDER_BRIGHT,
    BORDER_DIM,
    SCREEN_H,
    SCREEN_W,
    TEXT_DIM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

if TYPE_CHECKING:
    from src.core.asset_manager import AssetManager
    from src.core.scene_manager import SceneManager
    from src.inventory.inventory import Inventory

# ── Grid layout constants ──────────────────────────────────────────────────────
_SLOT_SIZE = 56
_SLOT_GAP = 6
_COLS = 6
_ROWS = 4
_GRID_W = _COLS * _SLOT_SIZE + (_COLS - 1) * _SLOT_GAP   # 366 px
_GRID_H = _ROWS * _SLOT_SIZE + (_ROWS - 1) * _SLOT_GAP   # 242 px

# Vertical layout: title → hint → grid → quick-slots
_TITLE_Y = (SCREEN_H - _GRID_H) // 2 - 60   # ≈ 179
_GRID_Y = _TITLE_Y + 52                       # ≈ 231
_QS_Y = _GRID_Y + _GRID_H + 28               # ≈ 501

# Horizontal centres
_GRID_X = (SCREEN_W - _GRID_W) // 2          # ≈ 457
_QS_W = 4 * _SLOT_SIZE + 3 * _SLOT_GAP       # 242 px
_QS_X = (SCREEN_W - _QS_W) // 2              # ≈ 519

# ── Dedicated armor-slot position (right of main grid, 20 px gap) ─────────────
_ARMOR_SLOT_X = _GRID_X + _GRID_W + 20
_ARMOR_SLOT_Y = _GRID_Y


class InventoryScreen(BaseScene):
    """Full-screen inventory overlay pushed over GameScene via Tab key."""

    def __init__(
        self,
        sm: Optional["SceneManager"] = None,
        inventory: Optional["Inventory"] = None,
        assets: Optional["AssetManager"] = None,
    ) -> None:
        self._sm = sm
        self._inventory = inventory
        self._assets = assets
        self._hovered_slot: Optional[int] = None

        # Fonts — lazy-initialised on first render() to avoid pre-init errors
        self._font_title: Optional[pygame.font.Font] = None
        self._font_item: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None
        self._fonts_ready: bool = False

    # ── Optional lifecycle hooks ───────────────────────────────────────────────

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    # ── Required BaseScene interface ───────────────────────────────────────────

    def handle_events(self, events: List[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_TAB, pygame.K_ESCAPE):
                    self._sm.pop()
                    return
            elif event.type == pygame.MOUSEMOTION:
                self._hovered_slot = self._slot_at(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 0) == 1:
                # Left-click: equip armor from grid, or interact with armor slot
                if self._inventory is not None:
                    pos = getattr(event, 'pos', None)
                    if pos is None:
                        continue
                    if self._armor_slot_rect().collidepoint(pos):
                        self._handle_armor_slot_click()
                    else:
                        slot_idx = self._slot_at(pos)
                        if slot_idx is not None:
                            self._handle_grid_slot_click(slot_idx)
            elif event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 0) == 3:
                # Right-click: assign hovered slot to next free quick-slot
                slot_idx = self._slot_at(event.pos)
                if slot_idx is not None and self._inventory is not None:
                    self._assign_to_quick_slot(slot_idx)

    def update(self, dt: float) -> None:
        pass  # Overlay — simulation is frozen beneath us

    def render(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()

        # Semi-transparent full-screen dimming
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        if self._inventory is None:
            msg = self._font_title.render("NO INVENTORY DATA", True, TEXT_DIM)
            screen.blit(msg, msg.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))
            return

        # ── Title ─────────────────────────────────────────────────────────────
        total_w = self._inventory.total_weight
        max_w = self._inventory.max_weight
        title_str = f"INVENTORY   [W: {total_w:.1f} / {max_w:.1f} kg]"
        title_surf = self._font_title.render(title_str, True, TEXT_PRIMARY)
        screen.blit(
            title_surf,
            title_surf.get_rect(centerx=SCREEN_W // 2, top=_TITLE_Y),
        )

        # ── Close / usage hint ────────────────────────────────────────────────
        hint_str = "[TAB / ESC] CLOSE   |   Right-click slot to assign quick-slot"
        hint_surf = self._font_sm.render(hint_str, True, TEXT_DIM)
        screen.blit(
            hint_surf,
            hint_surf.get_rect(centerx=SCREEN_W // 2, top=_TITLE_Y + 28),
        )

        # ── Main 6×4 grid ─────────────────────────────────────────────────────
        self._draw_grid(screen)

        # ── Quick-slot strip ──────────────────────────────────────────────────
        self._draw_quick_slots(screen)

        # ── Tooltip (drawn on top of everything) ──────────────────────────────
        if self._hovered_slot is not None:
            item = self._inventory.item_at(self._hovered_slot)
            if item is not None:
                self._draw_tooltip(screen, item, pygame.mouse.get_pos())

    # ── Private helpers ────────────────────────────────────────────────────────

    def _ensure_fonts(self) -> None:
        if self._fonts_ready:
            return
        self._font_title = pygame.font.SysFont("monospace", 18, bold=True)
        self._font_item = pygame.font.SysFont("monospace", 13)
        self._font_sm = pygame.font.SysFont("monospace", 11)
        self._fonts_ready = True

    def _slot_rect(self, idx: int) -> pygame.Rect:
        """Screen rect for general slot *idx* (0-based, row-major, 6-col grid)."""
        col = idx % _COLS
        row = idx // _COLS
        x = _GRID_X + col * (_SLOT_SIZE + _SLOT_GAP)
        y = _GRID_Y + row * (_SLOT_SIZE + _SLOT_GAP)
        return pygame.Rect(x, y, _SLOT_SIZE, _SLOT_SIZE)

    def _slot_at(self, pos: tuple) -> Optional[int]:
        """Return the slot index under screen position *pos*, or None."""
        if self._inventory is None:
            return None
        for i in range(self._inventory.capacity):
            if self._slot_rect(i).collidepoint(pos):
                return i
        return None

    def _draw_grid(self, screen: pygame.Surface) -> None:
        inv = self._inventory
        for i in range(inv.capacity):
            rect = self._slot_rect(i)
            item = inv.item_at(i)
            hovered = (i == self._hovered_slot)

            if item is not None:
                rarity_col = item.rarity_color

                # Tinted background in rarity colour
                bg = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                bg.fill((*rarity_col, 35))
                screen.blit(bg, rect.topleft)

                # Border — brighter when hovered
                border_col = (
                    tuple(min(255, c + 80) for c in rarity_col)
                    if hovered
                    else rarity_col
                )
                pygame.draw.rect(screen, border_col, rect, 2 if hovered else 1)

                # Icon or coloured fallback
                self._draw_item_icon(screen, item, rect)

                # Item name truncated to fit the slot width
                max_chars = max(1, (_SLOT_SIZE - 4) // 7)
                name_surf = self._font_sm.render(item.name[:max_chars], True, TEXT_PRIMARY)
                screen.blit(
                    name_surf,
                    (rect.x + 2, rect.bottom - name_surf.get_height() - 2),
                )

                # Quick-slot badge (top-right corner) if assigned
                for qi, slot_inv_idx in enumerate(inv.quick_slots):
                    if slot_inv_idx == i:
                        badge = self._font_sm.render(str(qi + 1), True, ACCENT_CYAN)
                        screen.blit(badge, (rect.right - badge.get_width() - 2, rect.y + 2))
                        break
            else:
                # Empty slot
                pygame.draw.rect(screen, (20, 24, 38), rect)
                pygame.draw.rect(
                    screen,
                    BORDER_BRIGHT if hovered else BORDER_DIM,
                    rect,
                    1,
                )

    def _draw_item_icon(
        self,
        screen: pygame.Surface,
        item: Any,
        rect: pygame.Rect,
    ) -> None:
        """Draw item icon via AssetManager, falling back to a rarity-coloured rect."""
        pad = 6
        # Reserve bottom 14 px for the name label
        icon_rect = pygame.Rect(
            rect.x + pad,
            rect.y + pad,
            rect.w - 2 * pad,
            rect.h - 2 * pad - 14,
        )

        icon_surf: Optional[pygame.Surface] = None
        if self._assets is not None and getattr(item, "sprite", ""):
            try:
                icon_surf = self._assets.load_image(
                    item.sprite, scale=(icon_rect.w, icon_rect.h)
                )
            except Exception:
                icon_surf = None

        if icon_surf is not None:
            try:
                screen.blit(icon_surf, icon_rect)
                return
            except Exception:
                pass

        # Fallback: solid rarity-coloured rectangle
        pygame.draw.rect(screen, item.rarity_color, icon_rect, border_radius=4)

    def _draw_quick_slots(self, screen: pygame.Surface) -> None:
        inv = self._inventory
        if inv is None:
            return

        for i in range(inv.QUICK_SLOT_COUNT):
            x = _QS_X + i * (_SLOT_SIZE + _SLOT_GAP)
            rect = pygame.Rect(x, _QS_Y, _SLOT_SIZE, _SLOT_SIZE)
            item = inv.quick_slot_item(i)

            # Hotkey number above each slot
            hk_surf = self._font_sm.render(str(i + 1), True, ACCENT_CYAN)
            screen.blit(
                hk_surf,
                hk_surf.get_rect(centerx=rect.centerx, bottom=rect.top - 2),
            )

            if item is not None:
                rarity_col = item.rarity_color
                bg = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                bg.fill((*rarity_col, 50))
                screen.blit(bg, rect.topleft)
                self._draw_item_icon(screen, item, rect)
                pygame.draw.rect(screen, ACCENT_CYAN, rect, 2)
                max_chars = max(1, (_SLOT_SIZE - 4) // 7)
                name_surf = self._font_sm.render(item.name[:max_chars], True, TEXT_PRIMARY)
                screen.blit(
                    name_surf,
                    (rect.x + 2, rect.bottom - name_surf.get_height() - 2),
                )
            else:
                pygame.draw.rect(screen, (20, 24, 38), rect)
                pygame.draw.rect(screen, BORDER_DIM, rect, 1)

        # Strip label
        lbl = self._font_sm.render(
            "QUICK SLOTS  [right-click grid slot to assign]", True, TEXT_DIM
        )
        screen.blit(
            lbl,
            lbl.get_rect(centerx=SCREEN_W // 2, top=_QS_Y + _SLOT_SIZE + 4),
        )

    def _draw_tooltip(
        self,
        screen: pygame.Surface,
        item: Any,
        mouse_pos: tuple,
    ) -> None:
        """Floating tooltip near the cursor with item stats."""
        lines: list[tuple[str, tuple]] = []

        lines.append((item.name, TEXT_PRIMARY))

        rarity_str = (
            item.rarity.value.upper()
            if hasattr(item.rarity, "value")
            else str(item.rarity).upper()
        )
        lines.append((rarity_str, item.rarity_color))
        lines.append((f"Type:   {item.item_type}", TEXT_SECONDARY))
        lines.append((f"Weight: {item.weight:.1f} kg", TEXT_SECONDARY))
        lines.append((f"Value:  ${item.monetary_value:.0f}", TEXT_SECONDARY))

        # Type-specific stats
        if item.item_type == "weapon":
            dmg = getattr(item, "damage", 0)
            if dmg:
                lines.append((f"Damage:    {dmg}", TEXT_PRIMARY))
            fr = getattr(item, "fire_rate", 0)
            if fr:
                lines.append((f"Fire rate: {fr:.1f}/s", TEXT_PRIMARY))
            mag = getattr(item, "magazine_size", 0)
            if mag:
                lines.append((f"Magazine:  {mag}", TEXT_PRIMARY))
        elif item.item_type == "armor":
            armor_val = getattr(item, "armor", 0) or getattr(item, "armor_rating", 0)
            if armor_val:
                lines.append((f"Armor: {armor_val}", TEXT_PRIMARY))
        elif item.item_type == "consumable":
            heal = getattr(item, "heal_amount", 0)
            if heal:
                lines.append((f"Heal: +{heal} HP", ACCENT_GREEN))

        # Compute tooltip dimensions
        line_h = self._font_item.get_height() + 2
        tip_w = max(160, max(self._font_item.size(t)[0] for t, _ in lines) + 16)
        tip_h = len(lines) * line_h + 12

        # Position near cursor; clamp to screen edges
        tx = mouse_pos[0] + 14
        ty = mouse_pos[1] + 14
        if tx + tip_w > SCREEN_W:
            tx = mouse_pos[0] - tip_w - 6
        if ty + tip_h > SCREEN_H:
            ty = mouse_pos[1] - tip_h - 6
        tx = max(0, tx)
        ty = max(0, ty)

        # Background panel
        tip_surf = pygame.Surface((tip_w, tip_h), pygame.SRCALPHA)
        tip_surf.fill((12, 16, 28, 225))
        pygame.draw.rect(tip_surf, BORDER_BRIGHT, (0, 0, tip_w, tip_h), 1)
        screen.blit(tip_surf, (tx, ty))

        # Text lines
        ly = ty + 6
        for text, color in lines:
            rendered = self._font_item.render(text, True, color)
            screen.blit(rendered, (tx + 8, ly))
            ly += line_h

    def _armor_slot_rect(self) -> pygame.Rect:
        """Screen rect for the dedicated armor equipment slot (right of main grid)."""
        return pygame.Rect(_ARMOR_SLOT_X, _ARMOR_SLOT_Y, _SLOT_SIZE, _SLOT_SIZE)

    def _handle_grid_slot_click(self, slot_idx: int) -> None:
        """Left-click on a main-grid slot: if the item is Armor, equip it.

        The item is removed from the grid first; any currently equipped armor
        is displaced back into the grid (or triggers an inventory_full event
        when no space is available).
        """
        from src.inventory.item import Armor
        from src.core.event_bus import event_bus as _global_bus

        if self._inventory is None:
            return
        item = self._inventory.item_at(slot_idx)
        if item is None or not isinstance(item, Armor):
            return

        # Remove from grid, then equip (equip_armor does not require grid presence)
        self._inventory.remove_item(slot_idx)
        displaced = self._inventory.equip_armor(item)

        # Return displaced armor to the grid if space allows
        if displaced is not None:
            result = self._inventory.add_item(displaced)
            if result is None:
                _global_bus.emit("inventory_full", item=displaced)

    def _handle_armor_slot_click(self) -> None:
        """Left-click on the dedicated armor slot: unequip the current armor.

        The removed piece is returned to the main grid when possible.  If the
        grid is full, an ``inventory_full`` event is emitted.
        """
        from src.core.event_bus import event_bus as _global_bus

        if self._inventory is None:
            return
        displaced = self._inventory.unequip_armor()
        if displaced is not None:
            result = self._inventory.add_item(displaced)
            if result is None:
                _global_bus.emit("inventory_full", item=displaced)

    def _assign_to_quick_slot(self, inv_slot_idx: int) -> None:
        """Assign item at *inv_slot_idx* to the next free quick-slot.

        If all four quick-slots are already occupied the assignment wraps to
        quick-slot 0 (oldest slot replaced).
        """
        if self._inventory is None:
            return
        if self._inventory.item_at(inv_slot_idx) is None:
            return

        # Find the first free quick-slot
        for qs_idx in range(self._inventory.QUICK_SLOT_COUNT):
            if self._inventory.quick_slots[qs_idx] is None:
                self._inventory.assign_quick_slot(inv_slot_idx, qs_idx)
                return

        # All quick-slots occupied — replace slot 0
        self._inventory.assign_quick_slot(inv_slot_idx, 0)
