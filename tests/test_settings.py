"""Tests for Settings dataclass and load/save round-trip."""
import json
import os
import tempfile
import pytest

from src.core.settings import Settings


def test_default_values():
    s = Settings()
    assert s.volume_master == 1.0
    assert s.volume_music == 0.7
    assert s.volume_sfx == 1.0
    assert list(s.resolution) == [1280, 720]
    assert s.fps == 60


def test_load_missing_file_returns_defaults():
    s = Settings.load(path="/tmp/nonexistent_runners_settings_xyz.json")
    assert s.volume_master == 1.0
    assert s.fps == 60


def test_load_overrides_fields(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"volume_master": 0.5, "fps": 30}))
    s = Settings.load(path=str(cfg))
    assert s.volume_master == 0.5
    assert s.fps == 30
    # Unspecified fields stay at defaults
    assert s.volume_music == 0.7


def test_save_round_trip(tmp_path):
    cfg = tmp_path / "settings.json"
    s = Settings()
    s.volume_master = 0.3
    s.fps = 120
    s.save(path=str(cfg))

    loaded = Settings.load(path=str(cfg))
    assert loaded.volume_master == pytest.approx(0.3)
    assert loaded.fps == 120


def test_load_malformed_json_returns_defaults(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text("not valid json{{")
    s = Settings.load(path=str(cfg))
    assert s.volume_master == 1.0


def test_save_creates_file(tmp_path):
    cfg = tmp_path / "new_settings.json"
    assert not cfg.exists()
    Settings().save(path=str(cfg))
    assert cfg.exists()


def test_resolution_loaded_correctly(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"resolution": [1920, 1080]}))
    s = Settings.load(path=str(cfg))
    assert list(s.resolution) == [1920, 1080]
