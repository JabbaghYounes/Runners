"""Challenge progress widget for the HUD.

Displays up to ``_MAX_VISIBLE`` active challenges with name, progress bar,
and fraction text.  When a challenge has a non-empty ``zone`` field (e.g.
``"Cargo Bay"``) a small dimmed zone label is rendered above the challenge
name.
"""
from __future__ import annotations

import pygame
from typing import List, Any, Optional
from src.constants import TEXT_BRIGHT, TEXT_DIM, ACCENT_GREEN, ACCENT_CYAN, BORDER_DIM

_MAX_VISIBLE: int = 3
_PADDING: int = 8
_ROW_H: int = 28          # height of the name + bar block
_ZONE_LABEL_H: int = 12   # extra height for the optional zone label


class ChallengeWidget:
    """Renders active challenges inside a fixed rect on the HUD."""

    def __init__(self, rect: pygame.Rect | None = None) -> None:
        self._rect: pygame.Rect = rect or pygame.Rect(0, 0, 240, 140)
        self._challenges: List[Any] = []
        self._font: Optional[pygame.font.Font] = None
        self._zone_font: Optional[pygame.font.Font] = None

    def update(self, challenges: List[Any] | None) -> None:
        """Replace the displayed challenge list."""
        self._challenges = list(challenges) if challenges else []

    def draw(self, surface: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.Font(None, 16)
        if self._zone_font is None:
            self._zone_font = pygame.font.Font(None, 14)

        x = self._rect.x + _PADDING
        y = self._rect.y + _PADDING
        bar_w = self._rect.width - 2 * _PADDING

        # Header
        header = self._font.render("CHALLENGES", True, TEXT_BRIGHT)
        surface.blit(header, (x, y))
        y += _ROW_H

        # Render up to _MAX_VISIBLE rows
        for challenge in self._challenges[:_MAX_VISIBLE]:
            name = getattr(challenge, "name", str(challenge))
            progress = getattr(challenge, "progress", 0)
            target = getattr(challenge, "target", 0)
            completed = getattr(challenge, "completed", False)
            zone = getattr(challenge, "zone", "")

            # Zone label (small, dimmed cyan) if present
            if zone:
                zone_surf = self._zone_font.render(f"[{zone.upper()}]", True, ACCENT_CYAN)
                surface.blit(zone_surf, (x, y))
                y += _ZONE_LABEL_H

            # Challenge name (right-aligns the fraction counter)
            color = ACCENT_GREEN if completed else TEXT_DIM
            name_surf = self._font.render(name, True, color)
            surface.blit(name_surf, (x, y))

            frac = self._font.render(f"{progress}/{target}", True, TEXT_DIM)
            surface.blit(frac, (x + bar_w - frac.get_width(), y))

            # Progress bar
            bar_y = y + 14
            bar_h = 4
            pygame.draw.rect(surface, BORDER_DIM, (x, bar_y, bar_w, bar_h))
            if target > 0:
                fill_val = target if completed else progress
                fill_w = int(bar_w * min(fill_val / target, 1.0))
                pygame.draw.rect(surface, ACCENT_GREEN, (x, bar_y, fill_w, bar_h))

            y += _ROW_H
