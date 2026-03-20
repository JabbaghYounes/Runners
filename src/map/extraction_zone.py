"""Extraction zone value object.

Represents the rectangular area on the map where players can initiate
extraction.  It is a pure data object with no behaviour — the
:class:`~src.systems.extraction_system.ExtractionSystem` uses it only for
overlap detection.  A ``render`` method is provided so ``GameScene`` can
draw the zone highlight directly from this object.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pygame

from src.constants import (
    EXTRACTION_CHANNEL_BAR_COLOR,
    EXTRACTION_ZONE_ALPHA,
    EXTRACTION_ZONE_BORDER_COLOR,
    EXTRACTION_ZONE_COLOR,
    EXTRACTION_ZONE_PULSE_SPEED,
)


@dataclass
class ExtractionZone:
    """A named rectangular region that triggers extraction.

    Args:
        rect: World-space :class:`pygame.Rect` defining the zone boundary.
        name: Human-readable label shown on the map overlay.
    """

    rect: pygame.Rect
    name: str = "Extraction"

    # Convenience constructor -----------------------------------------------

    @classmethod
    def from_topleft(
        cls,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str = "Extraction",
    ) -> "ExtractionZone":
        """Build a zone from top-left coordinates and dimensions."""
        return cls(rect=pygame.Rect(x, y, width, height), name=name)

    # Rendering -------------------------------------------------------------

    def render(
        self,
        screen: pygame.Surface,
        camera_offset: tuple[int, int] = (0, 0),
        channel_progress: float = 0.0,
        pulse_time: float = 0.0,
    ) -> None:
        """Draw the zone highlight onto *screen*.

        Args:
            screen:          Target surface.
            camera_offset:   ``(ox, oy)`` world-space scroll offset.
            channel_progress: Current extraction channel fraction (0.0–1.0).
                             When > 0, a progress bar is drawn on the bottom
                             edge of the zone and the fill brightens.
            pulse_time:      Accumulated time (seconds) used to drive the
                             sinusoidal alpha pulse animation.
        """
        ox, oy = camera_offset
        screen_rect = pygame.Rect(
            self.rect.x - ox,
            self.rect.y - oy,
            self.rect.width,
            self.rect.height,
        )

        # ── Semi-transparent fill (pulsing when idle) ──────────────────────
        if channel_progress > 0:
            # Bright solid highlight during active channel.
            alpha = 200
        else:
            pulse = math.sin(pulse_time * EXTRACTION_ZONE_PULSE_SPEED * 2.0 * math.pi)
            alpha = int(EXTRACTION_ZONE_ALPHA + 30 * pulse)
            alpha = max(20, min(alpha, 180))

        r, g, b = EXTRACTION_ZONE_COLOR
        fill_surf = pygame.Surface(
            (self.rect.width, self.rect.height), pygame.SRCALPHA
        )
        fill_surf.fill((r, g, b, alpha))
        screen.blit(fill_surf, screen_rect.topleft)

        # ── Border ─────────────────────────────────────────────────────────
        pygame.draw.rect(screen, EXTRACTION_ZONE_BORDER_COLOR, screen_rect, 2)

        # ── Channel progress bar (bottom edge of the zone rect) ─────────────
        if channel_progress > 0 and self.rect.width > 0:
            bar_h = 6
            bar_w = int(self.rect.width * channel_progress)
            if bar_w > 0:
                bar_fill = pygame.Rect(
                    screen_rect.x,
                    screen_rect.bottom - bar_h,
                    bar_w,
                    bar_h,
                )
                pygame.draw.rect(screen, EXTRACTION_CHANNEL_BAR_COLOR, bar_fill)
            # Outline for the full bar track.
            bar_track = pygame.Rect(
                screen_rect.x,
                screen_rect.bottom - bar_h,
                self.rect.width,
                bar_h,
            )
            pygame.draw.rect(screen, EXTRACTION_ZONE_BORDER_COLOR, bar_track, 1)
