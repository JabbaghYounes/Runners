"""Runners — entry point.

Launch the game::

    python main.py          # from the project root
    python -m runners       # if a __main__.py is added later

Cross-platform notes
--------------------
Linux:
    Set ``SDL_VIDEODRIVER=offscreen`` and ``SDL_AUDIODRIVER=dummy`` for
    headless / CI runs (no display or audio device required).

Windows:
    pygame will use WASAPI by default.  If no audio device is present the
    GameApp silently disables audio and continues.
"""

from __future__ import annotations

import os
import sys

# Force SDL to skip OpenGL if the driver is unavailable (prevents GLX errors).
os.environ.setdefault("SDL_RENDER_DRIVER", "software")

# Ensure the project root is on sys.path so ``import src.xxx`` works regardless
# of the current working directory.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.core.game import GameApp  # noqa: E402  (import after path setup)


def main() -> None:
    app = GameApp()
    app.run()


if __name__ == "__main__":
    main()
