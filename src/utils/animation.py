# AnimationController — loads and advances sprite-strip animations.
#
# Strip convention:
#   A strip is a single-row horizontal sprite sheet.
#   All frames have the same width; there is no padding between frames.
#   Strip width == frame_count * frame_width.
#
# Usage:
#   states = {
#       "idle":   ("assets/sprites/player/idle.png",   4, 8.0),
#       "run":    ("assets/sprites/player/run.png",    6, 12.0),
#       "crouch": ("assets/sprites/player/crouch.png", 2, 6.0),
#       "slide":  ("assets/sprites/player/slide.png",  3, 10.0),
#   }
#   ctrl = AnimationController(states, asset_manager, frame_w=48, frame_h=64)
#   ctrl.set_state("run")
#   ctrl.update(dt)
#   surface = ctrl.get_current_frame()

import pygame
from typing import Dict, List, Optional, Tuple

# Default frame dimensions used as fallback when a strip cannot be loaded.
_FALLBACK_W: int = 48
_FALLBACK_H: int = 64

# Fallback colours per state so placeholder frames are visually distinct.
_FALLBACK_COLORS: Dict[str, Tuple[int, int, int]] = {
    "idle":   (60,  120, 200),
    "run":    (60,  200, 120),
    "crouch": (200, 180,  60),
    "slide":  (200,  80,  60),
}
_DEFAULT_FALLBACK_COLOR: Tuple[int, int, int] = (100, 100, 100)


def _make_fallback_frame(state: str, w: int = _FALLBACK_W, h: int = _FALLBACK_H) -> pygame.Surface:
    """Return a solid-colour Surface used when the real asset is missing."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    color = _FALLBACK_COLORS.get(state, _DEFAULT_FALLBACK_COLOR)
    surf.fill(color)
    # Draw a subtle border so the frame boundary is visible during debugging.
    pygame.draw.rect(surf, (255, 255, 255, 80), surf.get_rect(), 1)
    return surf


class AnimationController:
    """Manages a set of named animation states backed by horizontal sprite strips.

    Parameters
    ----------
    states:
        Mapping of state_name -> (strip_path, frame_count, fps).
    asset_manager:
        ``AssetManager`` instance used to load image files.
    frame_w:
        Width of a single frame in pixels (default 48).
    frame_h:
        Height of a single frame in pixels (default 64).
    default_state:
        Which state to activate first.  Defaults to the first key in *states*.
    loop:
        If ``True`` (default) animations wrap; otherwise they clamp at the last frame.
    """

    def __init__(
        self,
        states: Dict[str, Tuple[str, int, float]],
        asset_manager,
        frame_w: int = _FALLBACK_W,
        frame_h: int = _FALLBACK_H,
        default_state: Optional[str] = None,
        loop: bool = True,
    ) -> None:
        self._frame_w = frame_w
        self._frame_h = frame_h
        self._loop = loop

        # Build frame lists for every state.
        self._frames: Dict[str, List[pygame.Surface]] = {}
        for state, (path, frame_count, _fps) in states.items():
            self._frames[state] = self._load_strip(state, path, frame_count, asset_manager)

        # Store FPS per state (frames per second, not game FPS).
        self._fps: Dict[str, float] = {
            state: max(1.0, fps) for state, (_path, _count, fps) in states.items()
        }

        # Runtime state.
        self._current_state: str = default_state or (next(iter(states)) if states else "")
        self._frame_index: int = 0
        self._frame_timer: float = 0.0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_strip(
        self,
        state: str,
        path: str,
        frame_count: int,
        asset_manager,
    ) -> List[pygame.Surface]:
        """Slice *path* into *frame_count* frames.

        Falls back to solid-colour placeholder frames if the image cannot be loaded.
        """
        strip: Optional[pygame.Surface] = asset_manager.load_image(path)
        if strip is None:
            return [_make_fallback_frame(state, self._frame_w, self._frame_h)
                    for _ in range(max(1, frame_count))]

        frames: List[pygame.Surface] = []
        for i in range(frame_count):
            frame_rect = pygame.Rect(i * self._frame_w, 0, self._frame_w, self._frame_h)
            try:
                frame = strip.subsurface(frame_rect).copy()
            except ValueError:
                # Strip is smaller than expected; use a fallback for this frame.
                frame = _make_fallback_frame(state, self._frame_w, self._frame_h)
            frames.append(frame)

        return frames if frames else [_make_fallback_frame(state, self._frame_w, self._frame_h)]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_state(self) -> str:
        return self._current_state

    def set_state(self, name: str) -> None:
        """Switch to animation state *name*.

        No-op if *name* is already the active state or is unknown.
        Resets the frame index and timer on a genuine state change.
        """
        if name not in self._frames:
            return
        if name == self._current_state:
            return
        self._current_state = name
        self._frame_index = 0
        self._frame_timer = 0.0

    def update(self, dt: float) -> None:
        """Advance the current animation by *dt* seconds."""
        frames = self._frames.get(self._current_state)
        if not frames or len(frames) <= 1:
            return

        fps = self._fps.get(self._current_state, 8.0)
        frame_duration = 1.0 / fps
        self._frame_timer += dt

        while self._frame_timer >= frame_duration:
            self._frame_timer -= frame_duration
            next_index = self._frame_index + 1
            if next_index >= len(frames):
                if self._loop:
                    self._frame_index = 0
                else:
                    self._frame_index = len(frames) - 1
            else:
                self._frame_index = next_index

    def get_current_frame(self) -> pygame.Surface:
        """Return the ``pygame.Surface`` for the current animation frame."""
        frames = self._frames.get(self._current_state)
        if not frames:
            return _make_fallback_frame(self._current_state, self._frame_w, self._frame_h)
        idx = min(self._frame_index, len(frames) - 1)
        return frames[idx]
