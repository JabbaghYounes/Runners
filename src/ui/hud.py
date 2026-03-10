"""HUD overlay — composites all screen-space UI elements during gameplay."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.ui.components import (
    ExtractionProgressBar,
    ExtractionPrompt,
    HealthBar,
    RoundTimer,
    XPBar,
)
from src.ui.minimap import Minimap

if TYPE_CHECKING:
    from src.events import EventBus


class HUD:
    """Gameplay heads-up display.

    Subscribes to ``EventBus`` events to keep widgets in sync with game
    state.  Call ``update(dt)`` and ``draw(surface)`` each frame.
    """

    def __init__(
        self,
        event_bus: EventBus,
        screen_width: int = 1280,
        screen_height: int = 720,
    ) -> None:
        self._event_bus = event_bus
        self._screen_w = screen_width
        self._screen_h = screen_height

        # Widgets
        self._timer = RoundTimer(x=screen_width // 2, y=16)
        self._health_bar = HealthBar(x=16, y=16)
        self._xp_bar = XPBar(x=16, y=36)
        self._extraction_bar = ExtractionProgressBar(screen_width, screen_height)
        self._extraction_prompt = ExtractionPrompt(screen_width, screen_height)
        self._minimap = Minimap(screen_width, screen_height)

        # State
        self._is_extracting = False
        self._is_near_extraction = False

        # Subscribe to events
        self._event_bus.subscribe("round_tick", self._on_round_tick)
        self._event_bus.subscribe("round_started", self._on_round_started)
        self._event_bus.subscribe("extraction_started", self._on_extraction_started)
        self._event_bus.subscribe("extraction_progress", self._on_extraction_progress)
        self._event_bus.subscribe("extraction_cancelled", self._on_extraction_cancelled)
        self._event_bus.subscribe("extraction_complete", self._on_extraction_complete)
        self._event_bus.subscribe("timer_warning", self._on_timer_warning)

    # ------------------------------------------------------------------
    # Per-frame
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._timer.update(dt)
        self._health_bar.update(dt)
        self._xp_bar.update(dt)
        self._extraction_bar.update(dt)
        self._extraction_prompt.update(dt)
        self._minimap.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        self._timer.draw(surface)
        self._health_bar.draw(surface)
        self._xp_bar.draw(surface)
        self._extraction_bar.draw(surface)
        self._extraction_prompt.draw(surface)
        self._minimap.draw(surface)

    # ------------------------------------------------------------------
    # Public API for GameplayScene
    # ------------------------------------------------------------------

    def set_player_health(self, current: int, maximum: int) -> None:
        self._health_bar.set_health(current, maximum)

    def set_near_extraction(self, near: bool) -> None:
        """Show/hide the extraction prompt based on player proximity."""
        self._is_near_extraction = near
        if not self._is_extracting:
            self._extraction_prompt.set_visible(near)

    def set_extraction_zones(self, zones: list) -> None:
        """Pass extraction zone data to the minimap."""
        self._minimap.set_extraction_zones(zones)

    def set_player_pos(self, pos) -> None:
        """Update player position for the minimap."""
        self._minimap.set_player_pos(pos)

    def set_map_size(self, width: int, height: int) -> None:
        """Tell the minimap the world dimensions."""
        self._minimap.set_map_size(width, height)

    def set_extracting(self, extracting: bool) -> None:
        """Tell the minimap whether extraction is in progress."""
        self._minimap.set_extracting(extracting)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_round_started(self, **data) -> None:
        timer = data.get("timer", 900.0)
        self._timer.set_time(timer, timer)

    def _on_round_tick(self, **data) -> None:
        remaining = data.get("remaining", 0.0)
        total = data.get("total", 900.0)
        self._timer.set_time(remaining, total)

    def _on_extraction_started(self, **data) -> None:
        self._is_extracting = True
        self._extraction_bar.set_visible(True)
        self._extraction_bar.set_progress(0.0, data.get("duration", 5.0))
        self._extraction_prompt.set_visible(False)

    def _on_extraction_progress(self, **data) -> None:
        progress = data.get("progress", 0.0)
        duration = data.get("duration", 5.0)
        self._extraction_bar.set_progress(progress, duration)

    def _on_extraction_cancelled(self, **data) -> None:
        self._is_extracting = False
        self._extraction_bar.set_visible(False)
        # Re-show the prompt if still near the zone
        if self._is_near_extraction:
            self._extraction_prompt.set_visible(True)

    def _on_extraction_complete(self, **data) -> None:
        self._is_extracting = False
        self._extraction_bar.set_visible(False)
        self._extraction_prompt.set_visible(False)

    def _on_timer_warning(self, **data) -> None:
        # Timer widget already handles visual changes based on remaining time.
        # This hook is available for audio SFX integration.
        pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Unsubscribe from all events."""
        self._event_bus.unsubscribe("round_tick", self._on_round_tick)
        self._event_bus.unsubscribe("round_started", self._on_round_started)
        self._event_bus.unsubscribe("extraction_started", self._on_extraction_started)
        self._event_bus.unsubscribe("extraction_progress", self._on_extraction_progress)
        self._event_bus.unsubscribe("extraction_cancelled", self._on_extraction_cancelled)
        self._event_bus.unsubscribe("extraction_complete", self._on_extraction_complete)
        self._event_bus.unsubscribe("timer_warning", self._on_timer_warning)
