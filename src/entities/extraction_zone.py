"""ExtractionZoneMarker — world-space visual indicator at extraction zones."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from src.entities.base import Entity

if TYPE_CHECKING:
    from src.map import Camera, Zone

# Colours (futuristic retro neon palette)
CYAN_ACCENT = (0, 229, 255)       # #00E5FF
CYAN_DIM = (0, 229, 255, 60)      # translucent fill
CYAN_BORDER = (0, 229, 255, 180)  # border glow


class ExtractionZoneMarker(Entity):
    """World-space visual indicator drawn at each extraction zone.

    Renders a translucent cyan pad with pulsing vertical beam lines
    and a glowing border outline.
    """

    def __init__(self, zone: Zone) -> None:
        cx = float(zone.rect.centerx)
        cy = float(zone.rect.centery)
        super().__init__(
            x=cx,
            y=cy,
            health=1,
            width=zone.rect.width,
            height=zone.rect.height,
        )
        self.zone = zone
        self._anim_time = 0.0

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float, **kwargs) -> None:
        """Advance the pulsing glow animation."""
        self._anim_time += dt

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        """Render the extraction zone visual on *surface*."""
        zone_rect = self.zone.rect
        screen_pos = camera.world_to_screen(
            pygame.math.Vector2(zone_rect.x, zone_rect.y)
        )
        screen_rect = pygame.Rect(
            int(screen_pos.x),
            int(screen_pos.y),
            zone_rect.width,
            zone_rect.height,
        )

        # (a) Translucent cyan fill
        pulse = 0.5 + 0.5 * math.sin(self._anim_time * 2.0)
        fill_alpha = int(30 + 30 * pulse)
        fill_surface = pygame.Surface(
            (zone_rect.width, zone_rect.height), pygame.SRCALPHA
        )
        fill_surface.fill((*CYAN_ACCENT, fill_alpha))
        surface.blit(fill_surface, screen_rect.topleft)

        # (b) Vertical beam lines at centre with animated alpha
        beam_alpha = int(80 + 80 * pulse)
        beam_surface = pygame.Surface((4, zone_rect.height), pygame.SRCALPHA)
        beam_surface.fill((*CYAN_ACCENT, beam_alpha))
        beam_x = screen_rect.centerx - 2
        surface.blit(beam_surface, (beam_x, screen_rect.top))

        # Second thinner beam offset
        beam2_alpha = int(40 + 60 * pulse)
        beam2_surface = pygame.Surface((2, zone_rect.height), pygame.SRCALPHA)
        beam2_surface.fill((*CYAN_ACCENT, beam2_alpha))
        surface.blit(beam2_surface, (beam_x - 8, screen_rect.top))
        surface.blit(beam2_surface, (beam_x + 10, screen_rect.top))

        # (c) Border outline with pulsing glow intensity
        border_alpha = int(100 + 80 * pulse)
        border_surface = pygame.Surface(
            (zone_rect.width, zone_rect.height), pygame.SRCALPHA
        )
        pygame.draw.rect(
            border_surface,
            (*CYAN_ACCENT, border_alpha),
            pygame.Rect(0, 0, zone_rect.width, zone_rect.height),
            width=2,
        )
        surface.blit(border_surface, screen_rect.topleft)

    # ------------------------------------------------------------------
    # Off-screen indicator
    # ------------------------------------------------------------------

    def draw_indicator(
        self,
        surface: pygame.Surface,
        camera: Camera,
        player_pos: pygame.math.Vector2,
    ) -> None:
        """Draw a directional arrow at the screen edge when the zone is off-screen.

        This serves as a hook for the HUD system.
        """
        screen_w = surface.get_width()
        screen_h = surface.get_height()
        zone_centre = pygame.math.Vector2(
            self.zone.rect.centerx, self.zone.rect.centery
        )
        screen_pos = camera.world_to_screen(zone_centre)

        # Only draw if the zone is outside the viewport
        margin = 40
        if (
            margin <= screen_pos.x <= screen_w - margin
            and margin <= screen_pos.y <= screen_h - margin
        ):
            return

        # Clamp to screen edge
        arrow_x = max(margin, min(screen_pos.x, screen_w - margin))
        arrow_y = max(margin, min(screen_pos.y, screen_h - margin))

        # Draw a small directional diamond
        pulse = 0.5 + 0.5 * math.sin(self._anim_time * 3.0)
        alpha = int(160 + 80 * pulse)
        size = 8
        points = [
            (arrow_x, arrow_y - size),
            (arrow_x + size, arrow_y),
            (arrow_x, arrow_y + size),
            (arrow_x - size, arrow_y),
        ]
        indicator_surface = pygame.Surface(
            (size * 2 + 2, size * 2 + 2), pygame.SRCALPHA
        )
        local_points = [
            (size + 1, 1),
            (size * 2 + 1, size + 1),
            (size + 1, size * 2 + 1),
            (1, size + 1),
        ]
        pygame.draw.polygon(indicator_surface, (*CYAN_ACCENT, alpha), local_points)
        surface.blit(
            indicator_surface,
            (int(arrow_x) - size - 1, int(arrow_y) - size - 1),
        )
