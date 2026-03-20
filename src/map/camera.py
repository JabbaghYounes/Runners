from __future__ import annotations

from typing import Tuple

import pygame


class Camera:
    def __init__(self, screen_w: int, screen_h: int, map_w: int, map_h: int) -> None:
        self.screen_w: int = screen_w
        self.screen_h: int = screen_h
        self.map_w: int = map_w
        self.map_h: int = map_h
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0

    @property
    def offset(self) -> Tuple[int, int]:
        return (int(self.offset_x), int(self.offset_y))

    def update(self, player_rect: pygame.Rect) -> None:
        target_x = player_rect.centerx - self.screen_w // 2
        target_y = player_rect.centery - self.screen_h // 2
        # Smooth follow
        self.offset_x += (target_x - self.offset_x) * 0.12
        self.offset_y += (target_y - self.offset_y) * 0.12
        self._clamp()

    def _clamp(self) -> None:
        # max(0, ...) on the upper bound handles maps narrower/shorter than the
        # viewport without producing a negative clamp range.
        max_x = max(0.0, float(self.map_w - self.screen_w))
        max_y = max(0.0, float(self.map_h - self.screen_h))
        self.offset_x = max(0.0, min(self.offset_x, max_x))
        self.offset_y = max(0.0, min(self.offset_y, max_y))

    def clamp(self, map_w: int, map_h: int) -> None:
        self.map_w = map_w
        self.map_h = map_h
        self._clamp()

    def world_to_screen(self, wx: float, wy: float) -> Tuple[int, int]:
        return (int(wx - self.offset_x), int(wy - self.offset_y))

    def screen_to_world(self, sx: float, sy: float) -> Tuple[float, float]:
        return (sx + self.offset_x, sy + self.offset_y)
