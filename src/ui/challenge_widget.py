"""ChallengeWidget — vertical list of active vendor challenges."""
from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.hud_state import ChallengeInfo

# Design colors
_PANEL_BG    = (20,  24,  38)
_BORDER      = (42,  48,  80)
_TEXT_HEAD   = (154, 163, 192)
_TEXT_NAME   = (255, 255, 255)
_TEXT_DONE   = (57,  255,  20)
_BAR_FILL    = (57,  255,  20)
_BAR_BG      = (42,  48,  80)
_MAX_VISIBLE = 3
_ROW_H       = 52
_HEADER_H    = 22
_PADDING     = 6


class ChallengeWidget:
    """Renders a panel showing active vendor challenge progress.

    Layout (per row):
        - Challenge name (truncated to fit)
        - Thin ProgressBar showing progress / target
        - On completed=True: text turns green, progress bar is full
    """

    def __init__(self, rect: object) -> None:
        """
        Args:
            rect: pygame.Rect for the widget's screen position and size.
        """
        self._rect = rect
        self._challenges: List["ChallengeInfo"] = []
        self._font: object = None
        self._small_font: object = None

    def update(self, challenges: List["ChallengeInfo"]) -> None:
        """Cache the latest challenge list."""
        self._challenges = challenges or []

    def _ensure_fonts(self) -> None:
        if self._font is None:
            import pygame
            self._font = pygame.font.SysFont('monospace', 11)
            self._small_font = pygame.font.SysFont('monospace', 10)

    def draw(self, surface: object) -> None:
        """Draw the challenge widget onto *surface*."""
        import pygame
        self._ensure_fonts()

        # Panel background
        panel_surf = pygame.Surface(
            (self._rect.width, self._rect.height), pygame.SRCALPHA
        )
        pygame.draw.rect(
            panel_surf, (*_PANEL_BG, 200),
            pygame.Rect(0, 0, self._rect.width, self._rect.height),
            border_radius=6,
        )
        surface.blit(panel_surf, (self._rect.x, self._rect.y))
        pygame.draw.rect(surface, _BORDER, self._rect, width=1, border_radius=6)

        # Header
        header = self._font.render('CHALLENGES', True, _TEXT_HEAD)
        surface.blit(header, (self._rect.x + _PADDING, self._rect.y + _PADDING))

        if not self._challenges:
            return

        visible = self._challenges[:_MAX_VISIBLE]

        for i, challenge in enumerate(visible):
            row_y = self._rect.y + _HEADER_H + i * _ROW_H

            # Completed row: use green + full bar
            if challenge.completed:
                name_color = _TEXT_DONE
                progress = challenge.target
            else:
                name_color = _TEXT_NAME
                progress = challenge.progress

            # Truncate name to fit widget width
            name = challenge.name
            name_surf = self._font.render(name, True, name_color)
            max_w = self._rect.width - 2 * _PADDING
            while name_surf.get_width() > max_w and len(name) > 4:
                name = name[:-1]
                name_surf = self._font.render(name + '…', True, name_color)

            surface.blit(name_surf, (self._rect.x + _PADDING, row_y + 4))

            # Progress bar
            bar_rect = pygame.Rect(
                self._rect.x + _PADDING,
                row_y + 22,
                self._rect.width - 2 * _PADDING,
                8,
            )
            pygame.draw.rect(surface, _BAR_BG, bar_rect, border_radius=3)
            target = max(challenge.target, 1)
            fill_w = int(bar_rect.width * min(1.0, progress / target))
            if fill_w > 0:
                fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, fill_w, bar_rect.height)
                pygame.draw.rect(surface, _BAR_FILL, fill_rect, border_radius=3)
            pygame.draw.rect(surface, _BORDER, bar_rect, width=1, border_radius=3)

            # Count label
            count_text = f'{progress}/{challenge.target}'
            count_surf = self._small_font.render(count_text, True, _TEXT_HEAD)
            surface.blit(
                count_surf,
                (self._rect.right - count_surf.get_width() - _PADDING,
                 row_y + 35),
            )
