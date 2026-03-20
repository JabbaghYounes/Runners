from __future__ import annotations

import math
from typing import Any, List, Optional, Tuple

import pygame

from src.constants import (
    SCREEN_W, SCREEN_H, BG_DEEP, ACCENT_CYAN, ACCENT_GREEN, ACCENT_MAGENTA,
    BORDER_DIM, BORDER_BRIGHT, PANEL_BG, TEXT_BRIGHT, TEXT_DIM,
)


class MapOverlay:
    ZONE_COLORS = [
        (60, 120, 180),
        (180, 80, 60),
        (60, 160, 80),
    ]

    def __init__(self, screen_w: int = SCREEN_W, screen_h: int = SCREEN_H) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._font_lg: Optional[pygame.font.Font] = None
        self._font_md: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None
        self._overlay_surf: Optional[pygame.Surface] = None

    def _ensure_fonts(self) -> None:
        if self._font_lg is None:
            self._font_lg = pygame.font.Font(None, 28)
            self._font_md = pygame.font.Font(None, 20)
            self._font_sm = pygame.font.Font(None, 16)

    def _get_overlay(self) -> pygame.Surface:
        if self._overlay_surf is None:
            self._overlay_surf = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
            self._overlay_surf.fill((0, 0, 0, 0))
        return self._overlay_surf

    def render(
        self,
        screen: pygame.Surface,
        zones: List[Any],
        player_pos: Tuple[float, float],
        extraction_rect: Optional[pygame.Rect],
        enemies: List[Any],
        seconds_remaining: float,
        map_rect: pygame.Rect,
    ) -> None:
        self._ensure_fonts()

        # Dark overlay
        dark = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 200))
        screen.blit(dark, (0, 0))

        # Panel
        PANEL_W, PANEL_H = 900, 520
        panel_x = (self.screen_w - PANEL_W) // 2
        panel_y = (self.screen_h - PANEL_H) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, PANEL_W, PANEL_H)

        pygame.draw.rect(screen, PANEL_BG, panel_rect, border_radius=8)
        pygame.draw.rect(screen, BORDER_BRIGHT, panel_rect, 2, border_radius=8)

        # Scale factors
        MAP_MARGIN = 20
        map_draw_x = panel_x + MAP_MARGIN
        map_draw_y = panel_y + MAP_MARGIN + 30  # leave space for title
        map_draw_w = PANEL_W - MAP_MARGIN * 2
        map_draw_h = PANEL_H - MAP_MARGIN * 2 - 60  # leave space for legend

        if map_rect.w > 0 and map_rect.h > 0:
            scale_x = map_draw_w / map_rect.w
            scale_y = map_draw_h / map_rect.h
        else:
            scale_x = scale_y = 1.0

        def world_to_panel(wx: float, wy: float) -> Tuple[int, int]:
            return (
                int(map_draw_x + (wx - map_rect.x) * scale_x),
                int(map_draw_y + (wy - map_rect.y) * scale_y),
            )

        # Title
        title = self._font_lg.render("TACTICAL MAP — NEXUS STATION", True, ACCENT_CYAN)
        screen.blit(title, (panel_x + MAP_MARGIN, panel_y + 8))

        # Map background
        map_bg_rect = pygame.Rect(map_draw_x, map_draw_y, map_draw_w, map_draw_h)
        pygame.draw.rect(screen, (6, 10, 18), map_bg_rect)
        pygame.draw.rect(screen, BORDER_DIM, map_bg_rect, 1)

        # Zones — prefer zone.color if available, fall back to indexed palette
        for i, zone in enumerate(zones):
            color = getattr(zone, 'color', self.ZONE_COLORS[i % len(self.ZONE_COLORS)])
            # Normalise rect: accept pygame.Rect or (x, y, w, h) tuple
            raw_rect = getattr(zone, 'rect', None)
            if raw_rect is None:
                continue
            r = raw_rect if isinstance(raw_rect, pygame.Rect) else pygame.Rect(raw_rect)
            zx1, zy1 = world_to_panel(r.left, r.top)
            zx2, zy2 = world_to_panel(r.right, r.bottom)
            zw = max(1, zx2 - zx1)
            zh = max(1, zy2 - zy1)
            zone_surf = pygame.Surface((zw, zh), pygame.SRCALPHA)
            zone_surf.fill((*color, 40))
            screen.blit(zone_surf, (zx1, zy1))
            pygame.draw.rect(screen, (*color, 180), (zx1, zy1, zw, zh), 1)
            # Zone name label
            label = self._font_md.render(zone.name, True, ACCENT_CYAN)
            cx = zx1 + zw // 2 - label.get_width() // 2
            cy = zy1 + zh // 2 - label.get_height() // 2
            cx = max(map_draw_x, min(cx, map_draw_x + map_draw_w - label.get_width()))
            cy = max(map_draw_y, min(cy, map_draw_y + map_draw_h - label.get_height()))
            screen.blit(label, (cx, cy))

        # Extraction zone
        if extraction_rect is not None:
            ex1, ey1 = world_to_panel(extraction_rect.left, extraction_rect.top)
            ex2, ey2 = world_to_panel(extraction_rect.right, extraction_rect.bottom)
            ecx = (ex1 + ex2) // 2
            ecy = (ey1 + ey2) // 2
            pulse = abs(math.sin(pygame.time.get_ticks() / 500.0))
            r = int(8 + pulse * 4)
            diamond = [
                (ecx, ecy - r),
                (ecx + r, ecy),
                (ecx, ecy + r),
                (ecx - r, ecy),
            ]
            pygame.draw.polygon(screen, ACCENT_GREEN, diamond)
            pygame.draw.polygon(screen, (255, 255, 255), diamond, 1)

        # Enemy dots
        for enemy in enemies:
            if not getattr(enemy, 'alive', True):
                continue
            ex, ey = world_to_panel(*enemy.center)
            if map_draw_x <= ex <= map_draw_x + map_draw_w and map_draw_y <= ey <= map_draw_y + map_draw_h:
                pygame.draw.circle(screen, ACCENT_MAGENTA, (ex, ey), 3)

        # Player dot
        px, py = world_to_panel(*player_pos)
        px = max(map_draw_x + 4, min(px, map_draw_x + map_draw_w - 4))
        py = max(map_draw_y + 4, min(py, map_draw_y + map_draw_h - 4))
        pygame.draw.circle(screen, ACCENT_CYAN, (px, py), 5)
        pygame.draw.circle(screen, (255, 255, 255), (px, py), 5, 1)

        # Timer (top-right of panel)
        mins = int(seconds_remaining) // 60
        secs = int(seconds_remaining) % 60
        timer_str = f"{mins:02d}:{secs:02d}"
        timer_color = (255, 80, 80) if seconds_remaining < 60 else TEXT_BRIGHT
        timer_surf = self._font_lg.render(timer_str, True, timer_color)
        screen.blit(timer_surf, (panel_x + PANEL_W - timer_surf.get_width() - MAP_MARGIN, panel_y + 8))

        # Legend
        legend_y = panel_y + PANEL_H - 30
        legend_items = [
            (ACCENT_CYAN, "● You"),
            (ACCENT_GREEN, "◆ Extraction"),
            (ACCENT_MAGENTA, "● Enemy"),
        ]
        lx = panel_x + MAP_MARGIN
        for color, text in legend_items:
            surf = self._font_sm.render(text, True, color)
            screen.blit(surf, (lx, legend_y))
            lx += surf.get_width() + 24

        # Close hint
        hint = self._font_sm.render("M or ESC to close", True, TEXT_DIM)
        screen.blit(hint, (self.screen_w // 2 - hint.get_width() // 2, self.screen_h - 24))
