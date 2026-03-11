from typing import List, Any, Optional
import pygame

class ExtractionSystem:
    HOLD_DURATION = 2.0

    def __init__(self, extraction_rect: pygame.Rect, event_bus: Any,
                 total_time: float = 900.0):
        self.extraction_rect: pygame.Rect = extraction_rect
        self._event_bus = event_bus
        self.seconds_remaining: float = total_time
        self._hold_progress: float = 0.0
        self._failed: bool = False
        self._succeeded: bool = False

    @property
    def extraction_progress(self) -> float:
        return min(1.0, self._hold_progress / self.HOLD_DURATION)

    def is_player_in_zone(self, player: Any) -> bool:
        return player.rect.colliderect(self.extraction_rect)

    def update(self, players: List[Any], dt: float, e_held: bool = False) -> None:
        if self._failed or self._succeeded:
            return
        self.seconds_remaining -= dt
        if self.seconds_remaining <= 0:
            self.seconds_remaining = 0
            self._failed = True
            self._event_bus.emit('extraction_failed')
            return

        for player in players:
            if self.is_player_in_zone(player) and e_held:
                self._hold_progress += dt
                if self._hold_progress >= self.HOLD_DURATION:
                    self._succeeded = True
                    self._event_bus.emit('extraction_success', player=player)
                    self._hold_progress = 0.0
            else:
                self._hold_progress = max(0.0, self._hold_progress - dt * 2)
