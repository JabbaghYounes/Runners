import pygame
from typing import Optional, Tuple
from src.ui.hud_state import HUDState
from src.constants import ACCENT_CYAN, ACCENT_GREEN, ACCENT_MAGENTA, BORDER_DIM, PANEL_BG

ZONE_COLORS = [
    (60, 120, 180),
    (180, 80, 60),
    (60, 160, 80),
]

class MiniMap:
    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self._base_surf: Optional[pygame.Surface] = None
        self._state: Optional[HUDState] = None

    def update(self, state: HUDState) -> None:
        self._state = state

    def _world_to_mini(self, wx: float, wy: float) -> Tuple[int, int]:
        if self._state is None or self._state.map_world_rect is None:
            return (self.rect.x, self.rect.y)
        mr = self._state.map_world_rect
        scale_x = self.rect.w / max(1, mr.w)
        scale_y = self.rect.h / max(1, mr.h)
        mx = self.rect.x + int((wx - mr.x) * scale_x)
        my = self.rect.y + int((wy - mr.y) * scale_y)
        # Clamp to minimap bounds
        mx = max(self.rect.x, min(mx, self.rect.right - 1))
        my = max(self.rect.y, min(my, self.rect.bottom - 1))
        return (mx, my)

    def draw(self, surface: pygame.Surface) -> None:
        if self._state is None:
            return
        # Background
        pygame.draw.rect(surface, (6, 10, 18), self.rect)
        pygame.draw.rect(surface, BORDER_DIM, self.rect, 1)
        # Zones
        for i, zone in enumerate(self._state.zones):
            color = getattr(zone, 'color', ZONE_COLORS[i % len(ZONE_COLORS)])
            # Support both world_rect (new) and rect_tuple (legacy)
            wr = getattr(zone, 'world_rect', None)
            rt = getattr(zone, 'rect_tuple', None)
            if wr is not None:
                r = pygame.Rect(wr) if not isinstance(wr, pygame.Rect) else wr
            elif rt is not None:
                r = pygame.Rect(*rt)
            else:
                continue
            if self._state.map_world_rect and self._state.map_world_rect.w > 0:
                mr = self._state.map_world_rect
                sx = self.rect.x + int((r.x - mr.x) / mr.w * self.rect.w)
                sy = self.rect.y + int((r.y - mr.y) / mr.h * self.rect.h)
                sw = max(1, int(r.w / mr.w * self.rect.w))
                sh = max(1, int(r.h / mr.h * self.rect.h))
                zone_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
                zone_surf.fill((*color, 60))
                surface.blit(zone_surf, (sx, sy))
        # Extraction
        if self._state.extraction_pos:
            ex, ey = self._world_to_mini(*self._state.extraction_pos)
            pygame.draw.circle(surface, ACCENT_GREEN, (ex, ey), 4)
        # Player
        if self._state.player_world_pos:
            px, py = self._world_to_mini(*self._state.player_world_pos)
            px = max(self.rect.x + 2, min(px, self.rect.right - 2))
            py = max(self.rect.y + 2, min(py, self.rect.bottom - 2))
            pygame.draw.circle(surface, ACCENT_CYAN, (px, py), 3)
