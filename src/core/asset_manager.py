"""Asset loading with in-memory cache for fonts, images, and sounds."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import pygame


class AssetManager:
    """Centralised asset loader with first-call caching.

    All ``load_*`` methods return a cached object on subsequent calls with
    the same arguments, avoiding redundant disk reads.
    """

    def __init__(self) -> None:
        self._font_cache: Dict[Tuple[Optional[str], int], pygame.font.Font] = {}
        self._image_cache: Dict[str, pygame.Surface] = {}
        self._sound_cache: Dict[str, Optional[pygame.mixer.Sound]] = {}

    # ------------------------------------------------------------------
    # Fonts
    # ------------------------------------------------------------------

    def load_font(self, name: Optional[str], size: int) -> pygame.font.Font:
        """Return a font for *name* at *size* px.

        Falls back to the system ``monospace`` font when *name* is ``None``
        or the file cannot be found.
        """
        key = (name, size)
        if key not in self._font_cache:
            font: pygame.font.Font
            if name is None:
                font = pygame.font.SysFont("monospace", size)
            else:
                try:
                    font = pygame.font.Font(name, size)
                except (FileNotFoundError, pygame.error):
                    font = pygame.font.SysFont("monospace", size)
            self._font_cache[key] = font
        return self._font_cache[key]

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def load_image(self, path: str) -> pygame.Surface:
        """Return a per-pixel-alpha surface loaded from *path*."""
        if path not in self._image_cache:
            self._image_cache[path] = pygame.image.load(path).convert_alpha()
        return self._image_cache[path]

    # ------------------------------------------------------------------
    # Sounds
    # ------------------------------------------------------------------

    def load_sound(self, path: str) -> Optional[pygame.mixer.Sound]:
        """Return a ``pygame.mixer.Sound`` loaded from *path*, or ``None``
        when the mixer is unavailable or the file cannot be found."""
        if path not in self._sound_cache:
            try:
                self._sound_cache[path] = pygame.mixer.Sound(path)
            except (pygame.error, FileNotFoundError):
                self._sound_cache[path] = None
        return self._sound_cache[path]
