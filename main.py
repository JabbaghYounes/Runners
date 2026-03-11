"""Entry point for Runners."""
import pygame
from src.core.game import GameApp


def main() -> None:
    pygame.init()
    GameApp().run()


if __name__ == "__main__":
    main()
