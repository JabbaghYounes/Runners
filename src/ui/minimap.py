"""Mini-map renderer — shows player position, extraction zones, and enemies."""

from __future__ import annotations

import math

import pygame

# Colours
MINIMAP_BG = (10, 14, 23, 200)    # semi-transparent dark
MINIMAP_BORDER = (60, 70, 90)
PLAYER_DOT = (0, 200, 255)        # bright cyan
EXTRACTION_MARKER = (105, 240, 174)  # accent-green #69F0AE
ENEMY_DOT = (255, 23, 68)           # accent-red


class Minimap:
    """Corner minimap showing a simplified view of the game world.

    Extraction zone markers are **always visible** (unlike enemies which
    only appear within detection range).
    """

    SIZE = 160             # minimap square side length
    MARGIN = 16            # distance from screen edge
    DIAMOND_SIZE = 5       # half-size of extraction diamond markers

    def __init__(self, screen_width: int = 1280, screen_height: int = 720) -> None:
        self._screen_w = screen_width
        self._screen_h = screen_height

        # Position (bottom-right corner)
        self._x = screen_width - self.SIZE - self.MARGIN
        self._y = screen_height - self.SIZE - self.MARGIN

        # World dimensions (in pixels)
        self._map_w = 2560
        self._map_h = 1920

        # Data
        self._player_pos: tuple[float, float] = (0, 0)
        self._extraction_zones: list = []
        self._is_extracting = False
        self._anim_time = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_map_size(self, width: int, height: int) -> None:
        self._map_w = max(1, width)
        self._map_h = max(1, height)

    def set_player_pos(self, pos) -> None:
        self._player_pos = (float(pos[0]) if hasattr(pos, '__getitem__') else float(getattr(pos, 'x', 0)),
                            float(pos[1]) if hasattr(pos, '__getitem__') else float(getattr(pos, 'y', 0)))

    def set_extraction_zones(self, zones: list) -> None:
        self._extraction_zones = list(zones)

    def set_extracting(self, extracting: bool) -> None:
        self._is_extracting = extracting

    # ------------------------------------------------------------------
    # Per-frame
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._anim_time += dt

    def draw(self, surface: pygame.Surface) -> None:
        # Background
        bg_surface = pygame.Surface((self.SIZE, self.SIZE), pygame.SRCALPHA)
        bg_surface.fill(MINIMAP_BG)
        surface.blit(bg_surface, (self._x, self._y))

        # Border
        pygame.draw.rect(
            surface,
            MINIMAP_BORDER,
            (self._x, self._y, self.SIZE, self.SIZE),
            width=1,
        )

        # Draw extraction zone markers (always visible)
        for zone in self._extraction_zones:
            self._draw_extraction_marker(surface, zone)

        # Draw player dot
        px, py = self._world_to_minimap(*self._player_pos)
        pygame.draw.circle(surface, PLAYER_DOT, (px, py), 3)

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _world_to_minimap(self, wx: float, wy: float) -> tuple[int, int]:
        """Convert world coordinates to minimap pixel position."""
        mx = self._x + int((wx / self._map_w) * self.SIZE)
        my = self._y + int((wy / self._map_h) * self.SIZE)
        # Clamp to minimap bounds
        mx = max(self._x, min(mx, self._x + self.SIZE - 1))
        my = max(self._y, min(my, self._y + self.SIZE - 1))
        return mx, my

    def _draw_extraction_marker(self, surface: pygame.Surface, zone) -> None:
        """Draw a green diamond marker at the extraction zone position."""
        # Get zone centre
        if hasattr(zone, "rect"):
            cx = float(zone.rect.centerx)
            cy = float(zone.rect.centery)
        else:
            return

        mx, my = self._world_to_minimap(cx, cy)
        s = self.DIAMOND_SIZE

        # Check if marker is within minimap bounds
        if not (self._x <= mx <= self._x + self.SIZE and
                self._y <= my <= self._y + self.SIZE):
            # Draw directional arrow at minimap edge
            self._draw_edge_arrow(surface, mx, my)
            return

        # Pulse effect when extracting
        if self._is_extracting:
            pulse = 0.5 + 0.5 * math.sin(self._anim_time * 6.0)
            alpha = int(160 + 95 * pulse)
            glow_s = s + 2
            glow_points = [
                (mx, my - glow_s),
                (mx + glow_s, my),
                (mx, my + glow_s),
                (mx - glow_s, my),
            ]
            glow_surface = pygame.Surface(
                (glow_s * 2 + 2, glow_s * 2 + 2), pygame.SRCALPHA
            )
            local_glow = [
                (glow_s + 1, 1),
                (glow_s * 2 + 1, glow_s + 1),
                (glow_s + 1, glow_s * 2 + 1),
                (1, glow_s + 1),
            ]
            pygame.draw.polygon(
                glow_surface, (*EXTRACTION_MARKER, alpha), local_glow
            )
            surface.blit(
                glow_surface, (mx - glow_s - 1, my - glow_s - 1)
            )

        # Draw diamond
        points = [
            (mx, my - s),
            (mx + s, my),
            (mx, my + s),
            (mx - s, my),
        ]
        pygame.draw.polygon(surface, EXTRACTION_MARKER, points)

    def _draw_edge_arrow(self, surface: pygame.Surface, mx: int, my: int) -> None:
        """Draw a small arrow at the minimap edge pointing toward an off-map marker."""
        # Clamp to minimap edge
        edge_x = max(self._x + 4, min(mx, self._x + self.SIZE - 4))
        edge_y = max(self._y + 4, min(my, self._y + self.SIZE - 4))

        # Small triangle pointing outward
        pygame.draw.circle(surface, EXTRACTION_MARKER, (edge_x, edge_y), 3)
