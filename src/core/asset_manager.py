"""Cache-backed loader for game assets.

Each asset type is stored in a separate dict keyed by the *path* string
passed to the loader, so the same file is never read from disk twice.
"""
from __future__ import annotations
from typing import Optional


class AssetManager:
    """Cache-backed loader for game assets.

    Each asset type is stored in a separate dict keyed by the *path* string
    passed to the loader, so the same file is never read from disk twice.
    """

    def __init__(self) -> None:
        self._sounds: dict[str, object] = {}
        self._images: dict[str, object] = {}
        self._fonts: dict[tuple[str, int], object] = {}

    def load_sound(self, path: str) -> Optional[object]:
        """Return a cached :class:`pygame.mixer.Sound` or *None*.

        Returns *None* without raising if pygame.mixer is unavailable or the
        file is missing, so callers can safely ignore audio in headless tests.
        """
        if path in self._sounds:
            return self._sounds[path]
        sound = self._try_load_sound(path)
        self._sounds[path] = sound
        return sound

    @staticmethod
    def _try_load_sound(path: str) -> Optional[object]:
        try:
            import pygame
            return pygame.mixer.Sound(path)
        except Exception:
            return None

    def load_image(self, path: str) -> Optional[object]:
        """Return a cached pygame Surface or *None* (stub)."""
        if path in self._images:
            return self._images[path]
        try:
            import pygame
            surface = pygame.image.load(path).convert_alpha()
            self._images[path] = surface
            return surface
        except Exception:
            self._images[path] = None
            return None

    def load_font(self, path: str, size: int) -> Optional[object]:
        """Return a cached pygame Font or *None* (stub)."""
        key = (path, size)
        if key in self._fonts:
            return self._fonts[key]
        try:
            import pygame
            font = pygame.font.Font(path, size)
            self._fonts[key] = font
            return font
        except Exception:
            self._fonts[key] = None
            return None
