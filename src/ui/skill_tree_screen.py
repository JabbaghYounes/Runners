"""SkillTreeScreen -- node-graph widget for the HomeBase SKILL TREE tab.

This is a plain widget (not a BaseScene).  HomeBaseScene owns it and calls:
  - handle_event(event, area)  -- hit-test and click-to-unlock
  - render(screen, area)       -- draw branch columns inside *area* Rect

Visual states per node card:
  UNLOCKED  -- ACCENT_GREEN left-bar accent, "✓ UNLOCKED" label
  AVAILABLE -- ACCENT_CYAN border, "UNLOCK [N SP]" button, hover highlight
  LOCKED    -- TEXT_DIM text and border, "LOCKED" label
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import pygame

from src.constants import (
    ACCENT_CYAN, ACCENT_GREEN, BORDER_DIM, BORDER_BRIGHT,
    TEXT_BRIGHT, TEXT_DIM, PANEL_BG,
)

if TYPE_CHECKING:
    from src.progression.skill_tree import SkillTree
    from src.progression.xp_system import XPSystem

# Node state sentinels
_UNLOCKED  = "unlocked"
_AVAILABLE = "available"
_LOCKED    = "locked"

# Colours
_CARD_BG        = (18, 24, 36)
_HOVER_ACCENT   = (0, 160, 160)
_TOOLTIP_BG     = (12, 18, 30)

# Layout
_CARD_H       = 90
_CARD_GAP     = 10
_COLUMN_GAP   = 30
_PADDING      = 14
_BRANCH_HDR_H = 28
_BAR_W        = 4


class SkillTreeScreen:
    """Branch-column skill tree widget."""

    def __init__(self, skill_tree: "SkillTree", xp_system: "XPSystem") -> None:
        self._skill_tree = skill_tree
        self._xp_system  = xp_system
        # Populated each render() call for hit-testing
        self._card_rects: Dict[str, pygame.Rect] = {}
        self._hovered_node_id: Optional[str] = None
        self._font_cache: Dict[int, pygame.font.Font] = {}

    # ------------------------------------------------------------------
    # Font helper
    # ------------------------------------------------------------------

    def _font(self, size: int) -> pygame.font.Font:
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.Font(None, size)
        return self._font_cache[size]

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event,
                     area: pygame.Rect) -> bool:
        """Process *event*.  Returns True if the event was consumed."""
        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self._hovered_node_id = None
            for node_id, rect in self._card_rects.items():
                if rect.collidepoint(mx, my):
                    self._hovered_node_id = node_id
                    break
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for node_id, rect in self._card_rects.items():
                if rect.collidepoint(mx, my):
                    if self._node_state(node_id) == _AVAILABLE:
                        self._skill_tree.unlock(node_id, self._xp_system)
                    return True
        return False

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, screen: pygame.Surface, area: pygame.Rect) -> None:
        """Render the full skill tree inside *area*."""
        self._card_rects.clear()

        branches = self._skill_tree.branches
        if not branches:
            return

        n_cols   = len(branches)
        usable_w = area.w - _PADDING * 2 - _COLUMN_GAP * (n_cols - 1)
        col_w    = usable_w // n_cols

        for col_idx, branch in enumerate(branches):
            col_x = area.x + _PADDING + col_idx * (col_w + _COLUMN_GAP)
            self._render_branch_column(screen, branch, col_x, col_w, area)

        # Tooltip drawn on top of everything else
        if self._hovered_node_id and self._hovered_node_id in self._card_rects:
            self._render_tooltip(screen, self._hovered_node_id)

    # ------------------------------------------------------------------
    # Branch column
    # ------------------------------------------------------------------

    def _render_branch_column(self, screen: pygame.Surface, branch: str,
                               col_x: int, col_w: int,
                               area: pygame.Rect) -> None:
        title_font = self._font(22)
        name_font  = self._font(19)
        desc_font  = self._font(16)

        # Branch title
        cy = area.y + _PADDING
        title_surf = title_font.render(branch.upper(), True, TEXT_BRIGHT)
        screen.blit(title_surf, (col_x + (col_w - title_surf.get_width()) // 2, cy))
        cy += _BRANCH_HDR_H + 4

        nodes = self._skill_tree.get_branch_nodes(branch)
        prev_rect: Optional[pygame.Rect] = None

        for node in nodes:
            node_id: str = node["id"]
            state = self._node_state(node_id)
            card_rect = pygame.Rect(col_x, cy, col_w, _CARD_H)
            self._card_rects[node_id] = card_rect

            # Prerequisite connector line
            if prev_rect is not None:
                lx = col_x + col_w // 2
                pygame.draw.line(
                    screen, BORDER_DIM,
                    (lx, prev_rect.bottom),
                    (lx, card_rect.top),
                    2,
                )

            self._render_card(screen, card_rect, node, state, name_font, desc_font)
            prev_rect = card_rect
            cy += _CARD_H + _CARD_GAP

    # ------------------------------------------------------------------
    # Node card
    # ------------------------------------------------------------------

    def _node_state(self, node_id: str) -> str:
        if self._skill_tree.is_unlocked(node_id):
            return _UNLOCKED
        if self._skill_tree.can_unlock(node_id, self._xp_system):
            return _AVAILABLE
        return _LOCKED

    def _render_card(self, screen: pygame.Surface, card_rect: pygame.Rect,
                     node: dict, state: str,
                     name_font: pygame.font.Font,
                     desc_font: pygame.font.Font) -> None:
        node_id    = node["id"]
        is_hovered = (node_id == self._hovered_node_id)

        # Choose accent colour
        if state == _UNLOCKED:
            accent = ACCENT_GREEN
        elif state == _AVAILABLE:
            accent = _HOVER_ACCENT if is_hovered else ACCENT_CYAN
        else:
            accent = BORDER_DIM

        # Card background + border
        pygame.draw.rect(screen, _CARD_BG, card_rect, border_radius=6)
        pygame.draw.rect(screen, accent,   card_rect, 1, border_radius=6)

        # Left accent bar
        bar = pygame.Rect(card_rect.x, card_rect.y + 4, _BAR_W, card_rect.h - 8)
        pygame.draw.rect(screen, accent, bar, border_radius=2)

        tx = card_rect.x + _PADDING
        ty = card_rect.y + 10

        # Node name
        name_color = TEXT_BRIGHT if state != _LOCKED else TEXT_DIM
        name_surf  = name_font.render(node.get("name", node_id), True, name_color)
        screen.blit(name_surf, (tx, ty))
        ty += name_surf.get_height() + 4

        # Description
        desc_surf = desc_font.render(node.get("description", ""), True, TEXT_DIM)
        screen.blit(desc_surf, (tx, ty))

        # Status / action label at bottom of card
        label_font = self._font(16)
        if state == _UNLOCKED:
            label       = "\u2713 UNLOCKED"
            label_color = ACCENT_GREEN
        elif state == _AVAILABLE:
            cost_sp     = node.get("cost_sp", 1)
            label       = f"UNLOCK  [{cost_sp} SP]"
            label_color = ACCENT_CYAN
        else:
            label       = "LOCKED"
            label_color = TEXT_DIM

        label_surf = label_font.render(label, True, label_color)
        screen.blit(
            label_surf,
            (tx, card_rect.bottom - label_surf.get_height() - 8),
        )

    # ------------------------------------------------------------------
    # Hover tooltip
    # ------------------------------------------------------------------

    def _render_tooltip(self, screen: pygame.Surface, node_id: str) -> None:
        node = self._skill_tree.get_node(node_id)
        if node is None:
            return

        stat_bonus = node.get("stat_bonus", {})
        lines = [_format_bonus(k, v) for k, v in stat_bonus.items() if _format_bonus(k, v)]
        if not lines:
            return

        tip_font = self._font(16)
        line_h   = tip_font.get_height() + 2
        tip_w    = 188
        tip_h    = 8 + len(lines) * line_h + 8

        card_rect = self._card_rects[node_id]
        tip_x     = card_rect.right + 8
        tip_y     = card_rect.top

        # Clamp to screen bounds
        sw, sh = screen.get_size()
        if tip_x + tip_w > sw:
            tip_x = card_rect.left - tip_w - 8
        if tip_y + tip_h > sh:
            tip_y = sh - tip_h - 4

        tip_rect = pygame.Rect(tip_x, tip_y, tip_w, tip_h)
        pygame.draw.rect(screen, _TOOLTIP_BG, tip_rect, border_radius=4)
        pygame.draw.rect(screen, BORDER_DIM,  tip_rect, 1, border_radius=4)

        ly = tip_y + 8
        for line in lines:
            surf = tip_font.render(line, True, TEXT_BRIGHT)
            screen.blit(surf, (tip_x + 8, ly))
            ly += line_h


# ---------------------------------------------------------------------------
# Bonus formatter
# ---------------------------------------------------------------------------

def _format_bonus(key: str, val: float) -> str:
    """Convert a stat_bonus key/value to a human-readable string."""
    _PCT_KEYS = {
        "damage_mult":  "weapon damage",
        "speed_mult":   "move speed",
        "crit_chance":  "crit chance",
        "dodge_chance": "dodge chance",
    }
    _FLAT_KEYS = {
        "extra_hp":    "max HP",
        "extra_armor": "starting armor",
    }
    if key in _PCT_KEYS:
        return f"+{int(val * 100)}% {_PCT_KEYS[key]}"
    if key in _FLAT_KEYS:
        return f"+{int(val)} {_FLAT_KEYS[key]}"
    # Generic fallback
    if isinstance(val, float) and val < 1.0:
        return f"+{int(val * 100)}% {key.replace('_', ' ')}"
    return f"+{val} {key.replace('_', ' ')}"
