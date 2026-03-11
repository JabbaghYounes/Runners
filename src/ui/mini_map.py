"""MiniMap — scaled live map widget rendered in the HUD corner."""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.hud_state import HUDState

# Design colors
_BG         = (10,  14,  26)
_BORDER     = (42,  48,  80)
_PLAYER_DOT = (0,  245, 255)   # ACCENT_CYAN
_EXTRACT    = (57, 255,  20)   # ACCENT_GREEN
_ZONE_ALPHA = 80               # zone fill transparency 0-255


class MiniMap:
    """Renders a scaled-down live map in the HUD.

    World → minimap coordinate transform::

        mini_x = (world_x - map_rect.left) / map_rect.width  * mini_rect.width
        mini_y = (world_y - map_rect.top)  / map_rect.height * mini_rect.height

    Both coordinates are clamped to the minimap rect bounds.
    """

    def __init__(self, rect: object) -> None:
        """
        Args:
            rect: pygame.Rect for the minimap's screen position and size.
        """
        self._rect = rect
        self._state: Optional["HUDState"] = None

    def update(self, state: "HUDState") -> None:
        """Cache the latest HUD state snapshot."""
        self._state = state

    def _world_to_mini(self, wx: float, wy: float) -> tuple[int, int]:
        """Convert world-space coordinates to minimap pixel position."""
        state = self._state
        if state is None or state.map_world_rect is None:
            return (self._rect.x, self._rect.y)

        mr = state.map_world_rect
        map_w = max(mr.width, 1)
        map_h = max(mr.height, 1)

        rel_x = (wx - mr.left) / map_w
        rel_y = (wy - mr.top)  / map_h

        # Clamp to [0, 1]
        rel_x = max(0.0, min(1.0, rel_x))
        rel_y = max(0.0, min(1.0, rel_y))

        mini_x = self._rect.x + int(rel_x * self._rect.width)
        mini_y = self._rect.y + int(rel_y * self._rect.height)

        # Clamp to minimap rect
        mini_x = max(self._rect.x, min(self._rect.right  - 1, mini_x))
        mini_y = max(self._rect.y, min(self._rect.bottom - 1, mini_y))

        return (mini_x, mini_y)

    def draw(self, surface: object) -> None:
        """Draw the minimap onto *surface*."""
        import pygame

        state = self._state

        # Background panel
        pygame.draw.rect(surface, _BG, self._rect)
        pygame.draw.rect(surface, _BORDER, self._rect, width=1)

        if state is None:
            return

        # Zone fills
        if state.map_world_rect is not None:
            for zone in state.zones:
                try:
                    zr = zone.world_rect
                    mr = state.map_world_rect
                    map_w = max(mr.width, 1)
                    map_h = max(mr.height, 1)

                    # Convert zone world rect to minimap rect
                    rel_x = (zr.left - mr.left) / map_w
                    rel_y = (zr.top  - mr.top)  / map_h
                    rel_w = zr.width  / map_w
                    rel_h = zr.height / map_h

                    mini_zone = pygame.Rect(
                        self._rect.x + int(rel_x * self._rect.width),
                        self._rect.y + int(rel_y * self._rect.height),
                        max(1, int(rel_w * self._rect.width)),
                        max(1, int(rel_h * self._rect.height)),
                    )
                    mini_zone = mini_zone.clip(self._rect)

                    # Semi-transparent zone fill
                    zone_surf = pygame.Surface(
                        (mini_zone.width, mini_zone.height), pygame.SRCALPHA
                    )
                    fill_color = (*zone.color, _ZONE_ALPHA)
                    zone_surf.fill(fill_color)
                    surface.blit(zone_surf, mini_zone)

                    # Zone boundary outline
                    pygame.draw.rect(surface, (100, 110, 140), mini_zone, width=1)
                except Exception:
                    pass

        # Extraction point (green star / cross)
        if state.extraction_pos is not None:
            ex, ey = self._world_to_mini(*state.extraction_pos)
            # Draw a small + marker
            pygame.draw.line(surface, _EXTRACT, (ex - 4, ey), (ex + 4, ey), 2)
            pygame.draw.line(surface, _EXTRACT, (ex, ey - 4), (ex, ey + 4), 2)

        # Player dot (cyan)
        px, py = self._world_to_mini(*state.player_world_pos)
        pygame.draw.circle(surface, _PLAYER_DOT, (px, py), 3)
