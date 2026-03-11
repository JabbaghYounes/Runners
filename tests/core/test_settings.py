"""Unit tests for src.core.settings.Settings.

No Pygame dependency — pure-Python dataclass and JSON I/O.
"""
import json

import pytest

from src.core.settings import Settings


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

def test_default_resolution():
    s = Settings()
    assert s.resolution == [1280, 720]


def test_default_fullscreen_is_false():
    s = Settings()
    assert s.fullscreen is False


def test_default_master_volume():
    s = Settings()
    assert s.master_volume == pytest.approx(0.8)


def test_default_music_volume():
    s = Settings()
    assert s.music_volume == pytest.approx(0.6)


def test_default_sfx_volume():
    s = Settings()
    assert s.sfx_volume == pytest.approx(0.8)


def test_default_key_bindings_contains_pause():
    s = Settings()
    assert "pause" in s.key_bindings
    assert s.key_bindings["pause"] == "K_ESCAPE"


def test_default_key_bindings_has_all_movement_keys():
    s = Settings()
    for action in ("move_up", "move_down", "move_left", "move_right"):
        assert action in s.key_bindings, f"Missing key binding: {action}"


def test_default_key_bindings_has_all_action_keys():
    s = Settings()
    for action in ("jump", "crouch", "sprint", "slide", "interact", "inventory", "map"):
        assert action in s.key_bindings, f"Missing key binding: {action}"


# ---------------------------------------------------------------------------
# resolution_tuple property
# ---------------------------------------------------------------------------

def test_resolution_tuple_returns_tuple_of_ints():
    s = Settings(resolution=[1920, 1080])
    assert s.resolution_tuple == (1920, 1080)


def test_resolution_tuple_type_is_tuple():
    s = Settings()
    assert isinstance(s.resolution_tuple, tuple)


def test_resolution_tuple_coerces_to_int():
    # Even if the list contains float-like values from JSON
    s = Settings(resolution=[1280.0, 720.0])
    w, h = s.resolution_tuple
    assert isinstance(w, int)
    assert isinstance(h, int)


# ---------------------------------------------------------------------------
# Settings.load — happy path
# ---------------------------------------------------------------------------

def test_load_from_valid_json_file(tmp_path):
    data = {
        "resolution": [1600, 900],
        "fullscreen": True,
        "master_volume": 0.5,
        "music_volume": 0.3,
        "sfx_volume": 0.7,
        "key_bindings": {"pause": "K_ESCAPE"},
    }
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(data))
    s = Settings.load(str(p))
    assert s.resolution == [1600, 900]
    assert s.fullscreen is True
    assert s.master_volume == pytest.approx(0.5)
    assert s.music_volume == pytest.approx(0.3)
    assert s.sfx_volume == pytest.approx(0.7)


def test_load_partial_json_fills_missing_fields_with_defaults(tmp_path):
    # Only override one field; the rest should come from defaults.
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"master_volume": 0.1}))
    s = Settings.load(str(p))
    assert s.master_volume == pytest.approx(0.1)
    assert s.resolution == [1280, 720]   # default preserved


def test_load_ignores_unknown_keys(tmp_path):
    data = {"resolution": [1280, 720], "totally_unknown_key": "ignored"}
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(data))
    s = Settings.load(str(p))          # Must not raise
    assert s.resolution == [1280, 720]


# ---------------------------------------------------------------------------
# Settings.load — error / edge cases
# ---------------------------------------------------------------------------

def test_load_missing_file_returns_defaults():
    s = Settings.load("/does/not/exist/settings.json")
    assert s.resolution == [1280, 720]
    assert s.fullscreen is False


def test_load_invalid_json_returns_defaults(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{ this is not valid JSON ~~~")
    s = Settings.load(str(p))
    assert s.resolution == [1280, 720]


def test_load_empty_file_returns_defaults(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text("")
    s = Settings.load(str(p))
    assert s.resolution == [1280, 720]


def test_load_returns_settings_instance():
    s = Settings.load("/no/file")
    assert isinstance(s, Settings)


# ---------------------------------------------------------------------------
# Settings.save
# ---------------------------------------------------------------------------

def test_save_writes_valid_json(tmp_path):
    s = Settings(master_volume=0.42)
    path = str(tmp_path / "out.json")
    s.save(path)
    with open(path) as fh:
        data = json.load(fh)
    assert data["master_volume"] == pytest.approx(0.42)


def test_save_and_load_roundtrip(tmp_path):
    s = Settings(master_volume=0.33, music_volume=0.11, sfx_volume=0.77,
                 resolution=[1920, 1080], fullscreen=True)
    path = str(tmp_path / "round.json")
    s.save(path)
    s2 = Settings.load(path)
    assert s2.master_volume == pytest.approx(0.33)
    assert s2.music_volume == pytest.approx(0.11)
    assert s2.sfx_volume == pytest.approx(0.77)
    assert s2.resolution == [1920, 1080]
    assert s2.fullscreen is True


def test_save_writes_pretty_json(tmp_path):
    s = Settings()
    path = str(tmp_path / "pretty.json")
    s.save(path)
    raw = open(path).read()
    # Pretty-printed JSON contains newlines.
    assert "\n" in raw


# ---------------------------------------------------------------------------
# Settings.reload
# ---------------------------------------------------------------------------

def test_reload_restores_saved_values(tmp_path):
    path = str(tmp_path / "settings.json")
    s = Settings(master_volume=0.8)
    s.save(path)
    s.master_volume = 0.1        # Mutate in-memory
    s.reload(path)               # Reload from disk
    assert s.master_volume == pytest.approx(0.8)


def test_reload_updates_all_fields(tmp_path):
    path = str(tmp_path / "settings.json")
    s = Settings()
    s.save(path)
    # Mutate every field
    s.master_volume = 0.0
    s.music_volume = 0.0
    s.sfx_volume = 0.0
    s.resolution = [800, 600]
    s.fullscreen = True
    s.reload(path)
    # All should be back to the saved defaults
    assert s.master_volume == pytest.approx(0.8)
    assert s.music_volume == pytest.approx(0.6)
    assert s.resolution == [1280, 720]
    assert s.fullscreen is False


def test_reload_same_object_identity(tmp_path):
    """reload() must update in-place, not replace the object reference."""
    path = str(tmp_path / "settings.json")
    s = Settings()
    s.save(path)
    original_id = id(s)
    s.reload(path)
    assert id(s) == original_id
