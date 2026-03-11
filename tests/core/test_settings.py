"""Unit tests for src/core/settings.py.

All tests use tmp_path (pytest fixture) so they never write to the real
settings.json on disk.  A display is not required.
"""

import json
import os
import sys
from pathlib import Path

# Ensure project root is on path (mirrors main.py bootstrapping)
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Minimal pygame stub so Settings can be imported without a display
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()  # required for pygame.key.name() / pygame.key.key_code()

from src.core.settings import Settings


class TestSettingsDefaults:
    def test_default_resolution(self):
        s = Settings()
        assert s.resolution == (1280, 720)

    def test_default_fps(self):
        s = Settings()
        assert s.target_fps == 60

    def test_width_height_properties(self):
        s = Settings(resolution=(800, 600))
        assert s.width == 800
        assert s.height == 600

    def test_default_fullscreen_is_false(self):
        s = Settings()
        assert s.fullscreen is False


class TestSettingsLoad:
    def test_load_missing_file_returns_defaults(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        s = Settings.load(path)
        assert s.resolution == (1280, 720)
        assert s.target_fps == 60

    def test_load_corrupt_file_returns_defaults(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{{NOT JSON}}", encoding="utf-8")
        s = Settings.load(path)
        assert s.resolution == (1280, 720)

    def test_load_custom_resolution(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"resolution": [1920, 1080]}), encoding="utf-8")
        s = Settings.load(path)
        assert s.resolution == (1920, 1080)

    def test_load_partial_file_fills_defaults(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"fullscreen": True}), encoding="utf-8")
        s = Settings.load(path)
        assert s.fullscreen is True
        assert s.target_fps == 60  # default preserved


class TestSettingsSave:
    def test_roundtrip(self, tmp_path):
        path = tmp_path / "settings.json"
        original = Settings(resolution=(1024, 768), target_fps=30, fullscreen=True)
        original.save(path)

        loaded = Settings.load(path)
        assert loaded.resolution == (1024, 768)
        assert loaded.target_fps == 30
        assert loaded.fullscreen is True

    def test_save_creates_valid_json(self, tmp_path):
        path = tmp_path / "settings.json"
        Settings().save(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "resolution" in data
        assert "target_fps" in data
