"""Challenge progress widget for the HUD.

Displays up to ``_MAX_VISIBLE`` active challenges with name, progress bar,
and fraction text.
"""
import pygame
from typing import List, Any, Optional
from src.constants import TEXT_BRIGHT, TEXT_DIM, ACCENT_GREEN, BORDER_DIM

_MAX_VISIBLE: int = 3
_ROW_H: int = 28
_PADDING: int = 8


class ChallengeWidget:
    """Renders active challenges inside a fixed rect on the HUD."""

    def __init__(self, rect: pygame.Rect | None = None) -> None:
        self._rect: pygame.Rect = rect or pygame.Rect(0, 0, 240, 120)
        self._challenges: List[Any] = []
        self._font: Optional[pygame.font.Font] = None

    def update(self, challenges: List[Any] | None) -> None:
        """Replace the displayed challenge list."""
        self._challenges = list(challenges) if challenges else []

    def draw(self, surface: pygame.Surface) -> None:
        if self._font is None:
            self._font = pygame.font.Font(None, 16)

        x = self._rect.x + _PADDING
        y = self._rect.y + _PADDING

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

            # Name
            color = ACCENT_GREEN if completed else TEXT_DIM
            name_surf = self._font.render(name, True, color)
            surface.blit(name_surf, (x, y))

            # Progress bar
            bar_x = x
            bar_y = y + 14
            bar_w = self._rect.width - 2 * _PADDING
            bar_h = 4
            pygame.draw.rect(surface, BORDER_DIM, (bar_x, bar_y, bar_w, bar_h))
            if target > 0:
                fill_val = target if completed else progress
                fill_w = int(bar_w * min(fill_val / target, 1.0))
                pygame.draw.rect(surface, ACCENT_GREEN, (bar_x, bar_y, fill_w, bar_h))

            # Fraction text
            frac = self._font.render(f"{progress}/{target}", True, TEXT_DIM)
            surface.blit(frac, (x + bar_w - frac.get_width(), y))

            y += _ROW_H
