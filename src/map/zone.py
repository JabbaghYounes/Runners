import pygame
from typing import List, Tuple, Optional, Dict, Any

class Zone:
    def __init__(self, name: str, rect: pygame.Rect,
                 spawn_points: Optional[List[Tuple[float, float]]] = None,
                 music_track: Optional[str] = None):
        self.name: str = name
        self.rect: pygame.Rect = rect
        self.spawn_points: List[Tuple[float, float]] = spawn_points or []
        self.music_track: Optional[str] = music_track
        self.enemy_spawns: List[Dict[str, Any]] = []

    def contains(self, pos: Tuple[float, float]) -> bool:
        return self.rect.collidepoint(int(pos[0]), int(pos[1]))

    def __repr__(self) -> str:
        return f"Zone({self.name!r}, {self.rect})"
