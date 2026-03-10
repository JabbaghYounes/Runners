"""Unit tests for Settings dataclass and JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.settings import DEFAULT_KEYS, Settings


class TestSettingsDefaults:
    """Verify default values match spec."""

    def test_default_screen_size(self):
        s = Settings()
        assert s.screen_width == 1280
        assert s.screen_height == 720

    def test_default_fullscreen(self):
        assert Settings().fullscreen is False

    def test_default_volumes(self):
        s = Settings()
        assert s.music_volume == pytest.approx(0.7)
        assert s.sfx_volume == pytest.approx(0.7)

    def test_default_keybindings(self):
        s = Settings()
        assert s.keybindings == DEFAULT_KEYS

    def test_volume_fields_are_floats(self):
        s = Settings()
        assert isinstance(s.music_volume, float)
        assert isinstance(s.sfx_volume, float)


class TestSettingsPersistence:
    """Load/save round-trip and error handling."""

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        original = Settings(music_volume=0.3, sfx_volume=0.9, fullscreen=True)
        file = tmp_path / "settings.json"
        original.save(file)
        loaded = Settings.load(file)
        assert loaded.music_volume == pytest.approx(0.3)
        assert loaded.sfx_volume == pytest.approx(0.9)
        assert loaded.fullscreen is True
        assert loaded.screen_width == 1280

    def test_load_missing_file(self, tmp_path: Path):
        """Missing file should return defaults without error."""
        loaded = Settings.load(tmp_path / "nonexistent.json")
        assert loaded.music_volume == pytest.approx(0.7)
        assert loaded.screen_width == 1280

    def test_load_corrupt_file(self, tmp_path: Path):
        """Corrupt JSON should return defaults without error."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json!!!", encoding="utf-8")
        loaded = Settings.load(bad_file)
        assert loaded == Settings()

    def test_load_ignores_unknown_keys(self, tmp_path: Path):
        file = tmp_path / "settings.json"
        data = {"music_volume": 0.5, "unknown_key": True}
        file.write_text(json.dumps(data), encoding="utf-8")
        loaded = Settings.load(file)
        assert loaded.music_volume == pytest.approx(0.5)
        assert not hasattr(loaded, "unknown_key")

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        file = tmp_path / "subdir" / "deep" / "settings.json"
        Settings().save(file)
        assert file.exists()

    def test_to_dict_roundtrip(self):
        s = Settings(music_volume=0.4)
        d = s.to_dict()
        s2 = Settings.from_dict(d)
        assert s2.music_volume == pytest.approx(0.4)
        assert s2.screen_width == s.screen_width

    def test_save_overwrites_existing(self, tmp_path: Path):
        """Saving to an existing file should overwrite it completely."""
        file = tmp_path / "settings.json"
        Settings(music_volume=0.1).save(file)
        Settings(music_volume=0.9).save(file)
        loaded = Settings.load(file)
        assert loaded.music_volume == pytest.approx(0.9)

    def test_load_partial_json(self, tmp_path: Path):
        """JSON with only some fields should fill in defaults for the rest."""
        file = tmp_path / "settings.json"
        file.write_text(json.dumps({"sfx_volume": 0.2}), encoding="utf-8")
        loaded = Settings.load(file)
        assert loaded.sfx_volume == pytest.approx(0.2)
        assert loaded.music_volume == pytest.approx(0.7)  # default
        assert loaded.screen_width == 1280  # default
        assert loaded.fullscreen is False  # default

    def test_from_dict_empty(self):
        """from_dict with an empty dict should produce all defaults."""
        s = Settings.from_dict({})
        assert s == Settings()

    def test_keybindings_roundtrip(self, tmp_path: Path):
        """Keybindings should survive save/load roundtrip."""
        custom_keys = dict(DEFAULT_KEYS)
        custom_keys["move_up"] = "up"
        custom_keys["jump"] = "w"
        original = Settings(keybindings=custom_keys)
        file = tmp_path / "settings.json"
        original.save(file)
        loaded = Settings.load(file)
        assert loaded.keybindings == custom_keys

    def test_settings_equality(self):
        """Two Settings with identical fields should be equal (dataclass)."""
        a = Settings(music_volume=0.5, sfx_volume=0.3)
        b = Settings(music_volume=0.5, sfx_volume=0.3)
        assert a == b

    def test_settings_inequality(self):
        """Settings with different fields should not be equal."""
        a = Settings(music_volume=0.5)
        b = Settings(music_volume=0.6)
        assert a != b

    def test_load_empty_json_object(self, tmp_path: Path):
        """An empty JSON object should return defaults."""
        file = tmp_path / "settings.json"
        file.write_text("{}", encoding="utf-8")
        loaded = Settings.load(file)
        assert loaded == Settings()

    @pytest.mark.xfail(
        reason="Bug: Settings.load doesn't catch AttributeError from from_dict "
               "when JSON root is not a dict (e.g. list). from_dict calls "
               "data.items() which raises AttributeError on a list.",
        strict=True,
    )
    def test_load_json_array_returns_defaults(self, tmp_path: Path):
        """A JSON file containing an array (not object) should return defaults."""
        file = tmp_path / "settings.json"
        file.write_text("[1, 2, 3]", encoding="utf-8")
        loaded = Settings.load(file)
        assert loaded == Settings()

    def test_save_produces_valid_json(self, tmp_path: Path):
        """Saved file should be parseable JSON."""
        file = tmp_path / "settings.json"
        Settings().save(file)
        data = json.loads(file.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "music_volume" in data
        assert "sfx_volume" in data
