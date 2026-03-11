import pygame
from src.scenes.base_scene import BaseScene
from src.constants import SCREEN_W, SCREEN_H, TEXT_DIM

class SkillTreeScreen(BaseScene):
    def render(self, screen: pygame.Surface) -> None:
        font = pygame.font.Font(None, 28)
        text = font.render("[SKILL TREE — Coming Soon]", True, TEXT_DIM)
        screen.blit(text, (SCREEN_W // 2 - text.get_width() // 2, SCREEN_H // 2))
