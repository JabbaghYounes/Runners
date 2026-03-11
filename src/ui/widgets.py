"""Reusable UI widget primitives."""
from __future__ import annotations

from typing import Optional, Tuple

import pygame

# Tiny tolerance so that floating-point accumulation of 60 × (1/60) s ticks
# is treated as "complete" just like a single update(1.0) tick.
_EPSILON = 1e-9


class StatCounter:
    """Animated count-up widget using an ease-out curve: 1 − (1 − t)².

    Usage::

        counter = StatCounter("XP Earned", 1000, "+", (57, 255, 20),
                              duration=1.0, delay=0.5)
        counter.start()          # begin / reset
        counter.update(dt)       # call every frame
        counter.render(surface)  # draw to screen
    """

    def __init__(
        self,
        label: str,
        target_value: int,
        prefix: str,
        color: Tuple[int, int, int],
        duration: float,
        delay: float,
    ) -> None:
        self.label = label
        self.target_value = target_value
        self.prefix = prefix
        self.color = color
        self.duration = duration
        self.delay = delay

        self.current_value: int = 0
        self.is_done: bool = False
        self._elapsed: float = -1.0  # negative → not yet started

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin (or restart) the count-up animation."""
        self.current_value = 0
        self.is_done = False
        self._elapsed = 0.0

    def update(self, dt: float) -> None:
        """Advance the animation by *dt* seconds."""
        if self._elapsed < 0:
            return  # start() has not been called yet

        self._elapsed += dt
        anim_elapsed = self._elapsed - self.delay

        if anim_elapsed <= 0:
            return  # still in the delay window

        # Snap to completion when the animation time is exhausted.
        if self.duration <= 0 or anim_elapsed >= self.duration - _EPSILON:
            self.current_value = self.target_value
            self.is_done = True
            return

        t = anim_elapsed / self.duration
        ease = 1.0 - (1.0 - t) ** 2
        self.current_value = round(ease * self.target_value)

    # ── Rendering ───────────────────────────────────────────────────────────

    def render(
        self,
        surface: pygame.Surface,
        x: int = 0,
        y: int = 0,
    ) -> Optional[pygame.Rect]:
        """Draw the counter onto *surface* and return the blit rect."""
        font = pygame.font.Font(None, 28)
        text = f"{self.label}: {self.prefix}{self.current_value}"
        img = font.render(text, True, self.color)
        return surface.blit(img, (x, y))
