import pygame
import os
from typing import Dict, Optional

class AssetManager:
    def __init__(self):
        self._fonts: Dict[tuple, pygame.font.Font] = {}
        self._images: Dict[str, pygame.Surface] = {}
        self._sounds: Dict[str, Optional[pygame.mixer.Sound]] = {}

    def load_font(self, name: str, size: int) -> pygame.font.Font:
        key = (name, size)
        if key not in self._fonts:
            try:
                self._fonts[key] = pygame.font.Font(name, size)
            except Exception:
                try:
                    self._fonts[key] = pygame.font.SysFont('monospace', size)
                except Exception:
                    self._fonts[key] = pygame.font.Font(None, size)
        return self._fonts[key]

    def get_font(self, size: int = 16) -> pygame.font.Font:
        return self.load_font(None, size)

    def load_image(self, path: str) -> Optional[pygame.Surface]:
        if path not in self._images:
            try:
                self._images[path] = pygame.image.load(path).convert_alpha()
            except Exception as e:
                print(f"[AssetManager] Cannot load image {path}: {e}")
                self._images[path] = None
        return self._images[path]

    def load_sound(self, path: str) -> Optional[pygame.mixer.Sound]:
        if path not in self._sounds:
            try:
                self._sounds[path] = pygame.mixer.Sound(path)
            except Exception:
                self._sounds[path] = None
        return self._sounds[path]
