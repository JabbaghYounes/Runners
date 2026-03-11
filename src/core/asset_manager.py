"""Asset loader with in-memory caching."""
from __future__ import annotations
from typing import Optional


class AssetManager:
    """Load and cache pygame Surfaces, Sounds, and Fonts.

    Never loads the same file twice — results are cached by path key.
    All pygame imports are deferred so this module can be imported without
    a display (useful in tests).
    """

    def __init__(self) -> None:
        self._sounds: dict = {}
        self._images: dict = {}
        self._fonts: dict = {}

    def load_sound(self, path: str):
        """Return a cached pygame.mixer.Sound, or None on failure."""
        if path not in self._sounds:
            self._sounds[path] = self._try_load_sound(path)
        return self._sounds[path]

    @staticmethod
    def _try_load_sound(path: str):
        try:
            import pygame
            return pygame.mixer.Sound(path)
        except Exception:
            return None

    def load_image(self, path: str):
        """Return a cached pygame.Surface loaded from *path*."""
        if path not in self._images:
            try:
                import pygame
                self._images[path] = pygame.image.load(path).convert_alpha()
            except Exception:
                import pygame
                surf = pygame.Surface((32, 32))
                surf.fill((255, 0, 255))
                self._images[path] = surf
        return self._images[path]

    def load_font(self, path: Optional[str], size: int):
        """Return a cached pygame.font.Font."""
        key = (path, size)
        if key not in self._fonts:
            try:
                import pygame
                self._fonts[key] = pygame.font.Font(path, size)
            except Exception:
                import pygame
                self._fonts[key] = pygame.font.SysFont("monospace", size)
        return self._fonts[key]
