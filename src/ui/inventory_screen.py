import pygame
from src.scenes.base_scene import BaseScene
from src.constants import SCREEN_W, SCREEN_H, PANEL_BG, BORDER_DIM, TEXT_DIM

class InventoryScreen(BaseScene):
    def render(self, screen: pygame.Surface) -> None:
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        font = pygame.font.Font(None, 28)
        text = font.render("[INVENTORY — Coming Soon]", True, TEXT_DIM)
        screen.blit(text, (SCREEN_W // 2 - text.get_width() // 2, SCREEN_H // 2))
