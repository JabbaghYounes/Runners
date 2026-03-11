"""Entry point — instantiate GameApp and start the main loop."""
from src.core.game import GameApp

if __name__ == "__main__":
    app = GameApp()
    app.run()
