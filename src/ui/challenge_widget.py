import pygame
from typing import List, Any, Optional
from src.constants import TEXT_BRIGHT, TEXT_DIM, ACCENT_GREEN, BORDER_DIM

class ChallengeWidget:
    def __init__(self):
        self._font: Optional[pygame.font.Font] = None

    def draw(self, surface: pygame.Surface, challenges: List[Any], x: int, y: int) -> None:
        if self._font is None:
            self._font = pygame.font.Font(None, 16)
        for i, ch in enumerate(challenges):
            text = str(ch)
            surf = self._font.render(text, True, TEXT_DIM)
            surface.blit(surf, (x, y + i * 18))
