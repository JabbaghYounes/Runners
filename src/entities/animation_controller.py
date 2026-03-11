"""AnimationController — drives sprite frame sequencing per MovementState.

Loads per-state frame lists from assets/sprites/player/<state>/frame_*.png.
Falls back to solid-colour pygame.Surfaces when image files are absent.
"""
from __future__ import annotations

import glob
import os
from typing import Dict, List

import pygame

from src.constants import (
    ACCENT_CYAN, ACCENT_GREEN, ACCENT_ORANGE, ACCENT_MAGENTA,
    NORMAL_HEIGHT, CROUCH_HEIGHT,
)

# Fallback colours keyed by animation state name
_FALLBACK_COLOURS: dict[str, tuple] = {
    "idle":        ACCENT_CYAN,
    "walk":        ACCENT_CYAN,
    "sprint":      ACCENT_GREEN,
    "crouch":      ACCENT_ORANGE,
    "crouch_walk": ACCENT_ORANGE,
    "slide":       ACCENT_ORANGE,
    "jump":        ACCENT_MAGENTA,
    "fall":        ACCENT_MAGENTA,
}

_PLAYER_W = 28


def _fallback_surface(state: str, height: int = NORMAL_HEIGHT) -> pygame.Surface:
    colour = _FALLBACK_COLOURS.get(state, ACCENT_CYAN)
    surf = pygame.Surface((_PLAYER_W, height))
    surf.fill(colour)
    return surf


class AnimationController:
    """Frame-based sprite animator.

    Parameters
    ----------
    states_config:
        Mapping of state name → ``{"frames": [Surface, ...], "fps": int}``.
    """

    def __init__(self, states_config: Dict[str, dict]) -> None:
        self._states_config = states_config
        self._current_state: str = next(iter(states_config))
        self._frame_index: float = 0.0
        self._facing_right: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def from_sprite_dir(
        cls,
        sprite_dir: str,
        state_fps_map: Dict[str, int],
    ) -> "AnimationController":
        """Build an AnimationController from a directory of per-state PNGs.

        If the directory or frames are absent, solid-colour fallback surfaces
        are used so the game runs without assets.
        """
        states_config: Dict[str, dict] = {}
        for state, fps in state_fps_map.items():
            pattern = os.path.join(sprite_dir, state, "frame_*.png")
            paths = sorted(glob.glob(pattern))
            if paths:
                frames: List[pygame.Surface] = [
                    pygame.image.load(p).convert_alpha() for p in paths
                ]
            else:
                height = CROUCH_HEIGHT if state in ("crouch", "crouch_walk", "slide") else NORMAL_HEIGHT
                frames = [_fallback_surface(state, height)]
            states_config[state] = {"frames": frames, "fps": fps}
        return cls(states_config)

    def set_state(self, state: str, *, facing_right: bool = True) -> None:
        """Switch to *state*, resetting frame counter if the state changed."""
        if state != self._current_state:
            self._current_state = state
            self._frame_index = 0.0
        self._facing_right = facing_right

    def update(self, dt: float) -> None:
        """Advance the frame index by *dt* seconds."""
        cfg = self._states_config.get(self._current_state)
        if cfg is None or not cfg["frames"]:
            return
        self._frame_index += cfg["fps"] * dt
        self._frame_index %= len(cfg["frames"])

    def get_current_frame(self) -> pygame.Surface:
        """Return the current animation frame, flipped if facing left."""
        cfg = self._states_config.get(self._current_state)
        if cfg is None or not cfg["frames"]:
            return _fallback_surface(self._current_state)
        frames = cfg["frames"]
        idx = int(self._frame_index) % len(frames)
        surface = frames[idx]
        if not self._facing_right:
            return pygame.transform.flip(surface, True, False)
        return surface

    # Expose for tests
    @property
    def _states_config(self) -> Dict[str, dict]:
        return self.__states_config

    @_states_config.setter
    def _states_config(self, v: Dict[str, dict]) -> None:
        self.__states_config = v
