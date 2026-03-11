"""Asset loading and caching layer.

All load methods are safe to call even when the relevant pygame subsystem is
unavailable — they return *None* instead of raising.
"""
from __future__ import annotations

from typing import Optional


class AssetManager:
    """Cache-backed loader for game assets.

    Each asset type is stored in a separate dict keyed by the *path* string
    passed to the loader, so the same file is never read from disk twice.
    """

    def __init__(self) -> None:
        self._sounds: dict[str, object] = {}   # path → pygame.mixer.Sound | None
        self._images: dict[str, object] = {}   # path → pygame.Surface | None
        self._fonts: dict[tuple, object] = {}  # (path, size) → pygame.font.Font | None

    # ------------------------------------------------------------------
    # Sound
    # ------------------------------------------------------------------

    def load_sound(self, path: str) -> Optional["pygame.mixer.Sound"]:  # type: ignore[name-defined]
        """Return a cached :class:`pygame.mixer.Sound` or *None*.

        Returns *None* when:
        * ``pygame.mixer`` was not initialised (no audio device).
        * The file does not exist or cannot be decoded.
        """
        if path in self._sounds:
            return self._sounds[path]  # type: ignore[return-value]

        sound = self._try_load_sound(path)
        self._sounds[path] = sound
        return sound  # type: ignore[return-value]

    @staticmethod
    def _try_load_sound(path: str) -> Optional[object]:
        try:
            import pygame  # local import — keeps module importable without pygame
            if not pygame.mixer.get_init():
                return None
            return pygame.mixer.Sound(path)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Image (stub — filled out by map/sprite feature)
    # ------------------------------------------------------------------

    def load_image(self, path: str) -> Optional[object]:
        """Return a cached pygame Surface or *None* (stub)."""
        if path in self._images:
            return self._images[path]
        self._images[path] = None
        return None

    # ------------------------------------------------------------------
    # Font (stub — filled out by UI feature)
    # ------------------------------------------------------------------

    def load_font(self, path: str, size: int) -> Optional[object]:
        """Return a cached pygame Font or *None* (stub)."""
        key = (path, size)
        if key in self._fonts:
            return self._fonts[key]
        self._fonts[key] = None
        return None
