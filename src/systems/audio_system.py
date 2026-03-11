"""AudioSystem — zone-aware music and SFX playback."""
from __future__ import annotations
from typing import Optional


class AudioSystem:
    """Manages background music and one-shot SFX via pygame.mixer.

    Falls back silently when no audio device is available (headless tests).
    """

    def __init__(self) -> None:
        self._current_track: Optional[str] = None
        self._master = 1.0
        self._music = 1.0
        self._sfx = 1.0
        self._mixer_ok = self._init_mixer()

    @staticmethod
    def _init_mixer() -> bool:
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            return True
        except Exception:
            return False

    def apply_volumes(self, master: float, music: float, sfx: float) -> None:
        """Apply volume levels (0.0–1.0)."""
        self._master = max(0.0, min(1.0, master))
        self._music = max(0.0, min(1.0, music))
        self._sfx = max(0.0, min(1.0, sfx))
        if self._mixer_ok:
            try:
                import pygame
                pygame.mixer.music.set_volume(self._master * self._music)
            except Exception:
                pass

    def play_music(self, track: Optional[str]) -> None:
        """Start playing *track*; no-op if already playing the same track."""
        if track == self._current_track:
            return
        self._current_track = track
        if not self._mixer_ok or not track:
            return
        try:
            import pygame
            pygame.mixer.music.load(track)
            pygame.mixer.music.play(-1)
            pygame.mixer.music.set_volume(self._master * self._music)
        except Exception:
            pass

    def play_sfx(self, name: str) -> None:
        """Play a one-shot SFX by name (no-op if mixer unavailable)."""

    def update(self, dt: float, *, player_zone: object = None,
               player_is_moving: bool = False) -> None:
        """Per-frame update hook."""
