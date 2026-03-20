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


class TestSettingsClamping:
    """Values loaded from settings.json must be clamped to safe ranges."""

    # ── FPS ───────────────────────────────────────────────────────────────────

    def test_load_zero_fps_clamped_to_minimum(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"fps": 0}), encoding="utf-8")
        s = Settings.load(path)
        assert s.target_fps >= 10

    def test_load_negative_fps_clamped(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"fps": -120}), encoding="utf-8")
        s = Settings.load(path)
        assert s.target_fps >= 10

    def test_load_fps_above_max_clamped(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"fps": 9999}), encoding="utf-8")
        s = Settings.load(path)
        assert s.target_fps <= 300

    def test_load_normal_fps_unchanged(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"fps": 60}), encoding="utf-8")
        s = Settings.load(path)
        assert s.target_fps == 60

    # ── Volumes ───────────────────────────────────────────────────────────────

    def test_load_volume_above_one_clamped(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"volume_master": 5.0, "volume_music": 3.5, "volume_sfx": 2.0}),
            encoding="utf-8",
        )
        s = Settings.load(path)
        assert s.master_volume == 1.0
        assert s.music_volume == 1.0
        assert s.sfx_volume == 1.0

    def test_load_negative_volume_clamped(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"volume_master": -1.0}),
            encoding="utf-8",
        )
        s = Settings.load(path)
        assert s.master_volume == 0.0

    def test_load_normal_volume_unchanged(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"volume_master": 0.8}),
            encoding="utf-8",
        )
        s = Settings.load(path)
        assert s.master_volume == 0.8

    # ── Resolution ────────────────────────────────────────────────────────────

    def test_load_negative_resolution_clamped(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"resolution": [-1, -1]}), encoding="utf-8")
        s = Settings.load(path)
        assert s.resolution[0] > 0
        assert s.resolution[1] > 0

    def test_load_zero_resolution_clamped(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"resolution": [0, 0]}), encoding="utf-8")
        s = Settings.load(path)
        assert s.resolution[0] >= 320
        assert s.resolution[1] >= 320

    def test_load_normal_resolution_unchanged(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"resolution": [1920, 1080]}), encoding="utf-8")
        s = Settings.load(path)
        assert s.resolution == (1920, 1080)

    # ── Programmatic construction ─────────────────────────────────────────────

    def test_direct_construction_clamps_fps(self):
        s = Settings(target_fps=0)
        assert s.target_fps >= 10

    def test_direct_construction_clamps_volume(self):
        s = Settings(master_volume=99.0, music_volume=-5.0)
        assert s.master_volume == 1.0
        assert s.music_volume == 0.0

    def test_direct_construction_clamps_resolution(self):
        s = Settings(resolution=(100, 50))
        assert s.resolution[0] >= 320
        assert s.resolution[1] >= 320


class TestSettingsKeyBindings:
    """Key-binding parsing, fallback, and persistence through save/load."""

    def test_empty_key_bindings_dict_uses_all_defaults(self, tmp_path):
        """When key_bindings is an empty JSON object all DEFAULT_KEYS must appear."""
        path = tmp_path / "s.json"
        path.write_text(json.dumps({"key_bindings": {}}), encoding="utf-8")
        s = Settings.load(path)
        from src.constants import DEFAULT_KEYS
        for action in DEFAULT_KEYS:
            assert action in s.key_bindings, (
                f"Action {action!r} missing from key_bindings after empty dict"
            )

    def test_unknown_key_name_falls_back_to_default_keycode(self, tmp_path):
        """An unrecognised key string in settings.json must silently use the default."""
        path = tmp_path / "s.json"
        path.write_text(
            json.dumps({"key_bindings": {"jump": "notarealkey99999"}}),
            encoding="utf-8",
        )
        s = Settings.load(path)
        from src.constants import DEFAULT_KEYS
        assert s.key_bindings["jump"] == DEFAULT_KEYS["jump"]

    def test_valid_key_name_is_parsed_to_pygame_constant(self, tmp_path):
        path = tmp_path / "s.json"
        path.write_text(
            json.dumps({"key_bindings": {"jump": "f"}}),
            encoding="utf-8",
        )
        s = Settings.load(path)
        assert s.key_bindings["jump"] == pygame.K_f

    def test_key_binding_roundtrip_through_save_and_load(self, tmp_path):
        """A key binding saved to disk must come back as the same pygame constant."""
        path = tmp_path / "settings.json"
        original = Settings(key_bindings={"jump": pygame.K_f})
        original.save(path)
        loaded = Settings.load(path)
        assert loaded.key_bindings.get("jump") == pygame.K_f

    def test_default_keys_contains_sprint_and_slide(self):
        """sprint and slide must be present so they can be rebound from settings.json."""
        from src.constants import DEFAULT_KEYS
        assert "sprint" in DEFAULT_KEYS
        assert "slide"  in DEFAULT_KEYS


class TestSettingsConvenienceProperties:
    """Aliases and computed properties must delegate to the canonical fields."""

    def test_fps_property_returns_target_fps(self):
        s = Settings(target_fps=120)
        assert s.fps == 120

    def test_fps_setter_updates_target_fps(self):
        s = Settings()
        s.fps = 30
        assert s.target_fps == 30

    def test_width_property_returns_first_resolution_component(self):
        s = Settings(resolution=(800, 600))
        assert s.width == 800

    def test_height_property_returns_second_resolution_component(self):
        s = Settings(resolution=(800, 600))
        assert s.height == 600

    def test_volume_master_alias_reads_master_volume(self):
        s = Settings(master_volume=0.5)
        assert s.volume_master == 0.5

    def test_volume_master_alias_writes_master_volume(self):
        s = Settings()
        s.volume_master = 0.3
        assert s.master_volume == 0.3

    def test_volume_music_alias_reads_music_volume(self):
        s = Settings(music_volume=0.4)
        assert s.volume_music == 0.4

    def test_volume_sfx_alias_reads_sfx_volume(self):
        s = Settings(sfx_volume=0.9)
        assert s.volume_sfx == 0.9

    def test_resolution_tuple_property_returns_int_pair(self):
        s = Settings(resolution=(1920, 1080))
        assert s.resolution_tuple == (1920, 1080)
