"""
Root conftest.py — adds the project root to sys.path so that
``from src.foo import ...`` imports resolve correctly when pytest is
invoked from any working directory.
"""
from __future__ import annotations

import os
import sys

# Ensure SDL does not try to open a real video/audio device in any test.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Project root on path so ``import src.*`` works everywhere.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
