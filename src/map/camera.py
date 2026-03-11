"""Camera — tracks player and converts world↔screen coordinates."""
from __future__ import annotations


class Camera:
    """Tracks the player position and provides coordinate transforms."""

    def __init__(self, screen_w: int, screen_h: int) -> None:
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self._screen_w = screen_w
        self._screen_h = screen_h

    def update(self, target_rect: object) -> None:
        """Center camera on *target_rect*."""
        self.offset_x = target_rect.centerx - self._screen_w // 2
        self.offset_y = target_rect.centery - self._screen_h // 2

    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        return (int(wx - self.offset_x), int(wy - self.offset_y))
