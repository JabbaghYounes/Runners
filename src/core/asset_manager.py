"""Centralised asset loader and cache.

All asset loading goes through ``AssetManager``.
No module anywhere in the codebase should call ``pygame.image.load()``,
``pygame.mixer.Sound()``, or ``pygame.font.Font()`` directly.

Supported asset types
---------------------
* Images   — ``load_image(rel_path)``   → ``pygame.Surface``
* Sounds   — ``load_sound(rel_path)``   → ``pygame.mixer.Sound | None``
* Fonts    — ``load_font(name, size)``  → ``pygame.font.Font``

Missing images return a magenta 32×32 placeholder so broken assets are
immediately visible in-game without crashing.  Missing sounds return ``None``
so callers can guard with a simple ``if sound:`` check.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import pygame

# Assets root is two levels above this file:  src/core/ → src/ → project root
_ASSETS_ROOT = Path(__file__).resolve().parents[2] / "assets"

# Cache key types
_ImageKey = Tuple[str, bool, Optional[Tuple[int, int]]]  # (rel_path, alpha, scale)
_FontKey  = Tuple[str, int]                               # (name_or_empty, size)


class AssetManager:
    """Load-once, cache-forever asset store for the lifetime of the process."""

    def __init__(self) -> None:
        self._images: Dict[_ImageKey, pygame.Surface]       = {}
        self._sounds: Dict[str, pygame.mixer.Sound]         = {}
        self._fonts:  Dict[_FontKey,  pygame.font.Font]     = {}
        self._audio_available: bool = True

    # ── Images ────────────────────────────────────────────────────────────────

    def load_image(
        self,
        rel_path: str,
        *,
        alpha: bool = True,
        scale: Optional[Tuple[int, int]] = None,
    ) -> pygame.Surface:
        """Load and cache a sprite or texture.

        Args:
            rel_path: Path relative to ``assets/`` (e.g. ``"sprites/player/idle.png"``).
            alpha:    Preserve per-pixel transparency (``convert_alpha``).
                      Set to ``False`` for opaque backgrounds.
            scale:    If provided, scale the surface to ``(width, height)`` pixels.

        Returns:
            A cached ``pygame.Surface``.  Returns a magenta placeholder on any
            load failure so missing assets are visually obvious without a crash.
        """
        key: _ImageKey = (rel_path, alpha, scale)
        if key not in self._images:
            full_path = _ASSETS_ROOT / rel_path
            try:
                surf = pygame.image.load(str(full_path))
                surf = surf.convert_alpha() if alpha else surf.convert()
                if scale:
                    surf = pygame.transform.scale(surf, scale)
            except (FileNotFoundError, pygame.error):
                w, h = scale or (32, 32)
                surf = pygame.Surface((w, h), pygame.SRCALPHA if alpha else 0)
                surf.fill((255, 0, 255))  # magenta  ← missing-asset indicator
            self._images[key] = surf
        return self._images[key]

    # ── Sounds ────────────────────────────────────────────────────────────────

    def load_sound(self, rel_path: str) -> Optional[pygame.mixer.Sound]:
        """Load and cache a sound effect or music stinger.

        Args:
            rel_path: Path relative to ``assets/audio/``.

        Returns:
            A ``pygame.mixer.Sound``, or ``None`` if audio is unavailable or
            the file is missing.  Callers should guard: ``if sound: sound.play()``.
        """
        if not self._audio_available:
            return None
        if rel_path not in self._sounds:
            full_path = _ASSETS_ROOT / "audio" / rel_path
            try:
                self._sounds[rel_path] = pygame.mixer.Sound(str(full_path))
            except (FileNotFoundError, pygame.error):
                return None
        return self._sounds.get(rel_path)

    # ── Fonts ─────────────────────────────────────────────────────────────────

    def load_font(
        self,
        name: Optional[str],
        size: int,
    ) -> pygame.font.Font:
        """Load and cache a font.

        Args:
            name: Absolute path to a ``.ttf`` / ``.otf`` file, or ``None`` to
                  use pygame's built-in default font.
            size: Point size.

        Returns:
            A cached ``pygame.font.Font``.
        """
        key: _FontKey = (name or "", size)
        if key not in self._fonts:
            try:
                self._fonts[key] = (
                    pygame.font.Font(name, size)
                    if name
                    else pygame.font.Font(None, size)
                )
            except (FileNotFoundError, pygame.error):
                self._fonts[key] = pygame.font.Font(None, size)
        return self._fonts[key]

    # ── Audio toggle ──────────────────────────────────────────────────────────

    def set_audio_available(self, available: bool) -> None:
        """Called by ``GameApp`` after mixer initialisation to indicate whether
        audio is usable on this machine."""
        self._audio_available = available

    # ── Cache management ──────────────────────────────────────────────────────

    def clear_cache(self) -> None:
        """Release all cached assets.

        Normally called between major scene transitions to reclaim VRAM/RAM
        when the old assets are no longer needed.
        """
        self._images.clear()
        self._sounds.clear()
        self._fonts.clear()
