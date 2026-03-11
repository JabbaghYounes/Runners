import pygame
from typing import List

class BaseScene:
    def handle_events(self, events: List[pygame.event.Event]) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def render(self, screen: pygame.Surface) -> None:
        pass

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass
