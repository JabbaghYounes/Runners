"""Unit tests for src/save/save_manager.py.

Tests cover:
- _new_game(): canonical zero-state schema (money=0, all keys present)
- load(): missing file → new-game fallback without raising
- load(): corrupt / empty JSON → new-game fallback without raising
- save() + load(): round-trip preserves every field, including money
- Atomic write: no .tmp file left on disk after a successful save
- Migration: v0 saves gain money + home_base fields; partial dicts get defaults
- Multiple SaveManager instances on different paths are fully independent
"""
import json
import pytest
from pathlib import Path

from src.save.save_manager import SaveManager, SAVE_VERSION


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def save_path(tmp_path: Path) -> Path:
    """A temporary path for save.json that does not yet exist."""
    return tmp_path / "saves" / "save.json"


@pytest.fixture()
def manager(save_path: Path) -> SaveManager:
    return SaveManager(save_path=save_path)


def _state(money: int = 1500) -> dict:
    """Build a minimal but complete save state dict."""
    return {
        "version": SAVE_VERSION,
        "player": {"level": 3, "xp": 450, "money": money},
        "inventory": [],
        "skill_tree": {"unlocked_nodes": ["speed_1"]},
        "home_base": {"armory": 1, "med_bay": 0, "storage": 2, "comms": 0},
    }


# ---------------------------------------------------------------------------
# _new_game() schema
# ---------------------------------------------------------------------------

class TestNewGame:
    def test_money_is_zero(self, manager: SaveManager):
        assert manager._new_game()["player"]["money"] == 0

    def test_version_equals_current_save_version(self, manager: SaveManager):
        assert manager._new_game()["version"] == SAVE_VERSION

    def test_player_level_starts_at_one(self, manager: SaveManager):
        assert manager._new_game()["player"]["level"] == 1

    def test_player_xp_starts_at_zero(self, manager: SaveManager):
        assert manager._new_game()["player"]["xp"] == 0

    def test_inventory_is_empty_list(self, manager: SaveManager):
        assert manager._new_game()["inventory"] == []

    def test_skill_tree_has_empty_unlocked_nodes(self, manager: SaveManager):
        ng = manager._new_game()
        assert ng["skill_tree"]["unlocked_nodes"] == []

    def test_all_four_home_base_facilities_present(self, manager: SaveManager):
        hb = manager._new_game()["home_base"]
        for facility in ("armory", "med_bay", "storage", "comms"):
            assert facility in hb

    def test_all_home_base_facilities_start_at_zero(self, manager: SaveManager):
        hb = manager._new_game()["home_base"]
        for facility in ("armory", "med_bay", "storage", "comms"):
            assert hb[facility] == 0

    def test_has_all_top_level_keys(self, manager: SaveManager):
        ng = manager._new_game()
        for key in ("version", "player", "inventory", "skill_tree", "home_base"):
            assert key in ng


# ---------------------------------------------------------------------------
# load() — missing file
# ---------------------------------------------------------------------------

class TestLoadMissingFile:
    def test_returns_dict_without_raising(self, manager: SaveManager):
        data = manager.load()
        assert isinstance(data, dict)

    def test_missing_file_returns_new_game_money_zero(self, manager: SaveManager):
        assert manager.load()["player"]["money"] == 0

    def test_missing_file_returns_new_game_version(self, manager: SaveManager):
        assert manager.load()["version"] == SAVE_VERSION

    def test_missing_file_has_all_required_keys(self, manager: SaveManager):
        data = manager.load()
        for key in ("version", "player", "inventory", "skill_tree", "home_base"):
            assert key in data


# ---------------------------------------------------------------------------
# load() — corrupt or malformed file
# ---------------------------------------------------------------------------

class TestLoadCorruptFile:
    def test_corrupt_json_returns_new_game_without_raising(
        self, save_path: Path, manager: SaveManager
    ):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text("{ this is definitely not valid json }", encoding="utf-8")
        data = manager.load()
        assert data["player"]["money"] == 0

    def test_empty_file_returns_new_game(
        self, save_path: Path, manager: SaveManager
    ):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text("", encoding="utf-8")
        data = manager.load()
        assert data["player"]["money"] == 0

    def test_truncated_json_returns_new_game(
        self, save_path: Path, manager: SaveManager
    ):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text('{"version": 1, "player": {', encoding="utf-8")
        data = manager.load()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# save() + load() round-trip
# ---------------------------------------------------------------------------

class TestSaveLoadRoundTrip:
    def test_save_creates_the_file(self, save_path: Path, manager: SaveManager):
        manager.save(_state())
        assert save_path.exists()

    def test_round_trip_preserves_money(self, save_path: Path, manager: SaveManager):
        manager.save(_state(money=3200))
        assert manager.load()["player"]["money"] == 3200

    def test_round_trip_preserves_zero_money(self, save_path: Path, manager: SaveManager):
        manager.save(_state(money=0))
        assert manager.load()["player"]["money"] == 0

    def test_round_trip_preserves_large_money(self, save_path: Path, manager: SaveManager):
        manager.save(_state(money=999_999))
        assert manager.load()["player"]["money"] == 999_999

    def test_round_trip_preserves_player_level(self, save_path: Path, manager: SaveManager):
        manager.save(_state())
        assert manager.load()["player"]["level"] == 3

    def test_round_trip_preserves_home_base_levels(self, save_path: Path, manager: SaveManager):
        state = _state()
        state["home_base"]["armory"] = 3
        state["home_base"]["storage"] = 5
        manager.save(state)
        loaded = manager.load()
        assert loaded["home_base"]["armory"] == 3
        assert loaded["home_base"]["storage"] == 5

    def test_saved_file_is_valid_json(self, save_path: Path, manager: SaveManager):
        manager.save(_state())
        raw = save_path.read_text(encoding="utf-8")
        parsed = json.loads(raw)  # must not raise
        assert isinstance(parsed, dict)

    def test_no_tmp_file_left_after_successful_save(
        self, save_path: Path, manager: SaveManager
    ):
        manager.save(_state())
        assert not save_path.with_suffix(".tmp").exists()

    def test_multiple_saves_last_write_wins(self, save_path: Path, manager: SaveManager):
        manager.save(_state(money=100))
        manager.save(_state(money=9999))
        assert manager.load()["player"]["money"] == 9999

    def test_save_creates_parent_directories(self, tmp_path: Path):
        """save() must create missing parent directories automatically."""
        deep_path = tmp_path / "a" / "b" / "c" / "save.json"
        m = SaveManager(save_path=deep_path)
        m.save(_state())
        assert deep_path.exists()

    def test_round_trip_preserves_skill_tree_unlocked_nodes(
        self, save_path: Path, manager: SaveManager
    ):
        state = _state()
        state["skill_tree"]["unlocked_nodes"] = ["speed_1", "armor_2"]
        manager.save(state)
        assert manager.load()["skill_tree"]["unlocked_nodes"] == ["speed_1", "armor_2"]


# ---------------------------------------------------------------------------
# Migration: v0 → v1
# ---------------------------------------------------------------------------

class TestMigration:
    def _write_raw(self, save_path: Path, data: dict) -> None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(data), encoding="utf-8")

    def test_v0_save_gets_money_field_defaulted_to_zero(
        self, save_path: Path, manager: SaveManager
    ):
        self._write_raw(save_path, {
            "version": 0,
            "player": {"level": 2, "xp": 100},
            "inventory": [],
        })
        data = manager.load()
        assert data["player"]["money"] == 0

    def test_v0_save_gets_home_base_with_all_facilities(
        self, save_path: Path, manager: SaveManager
    ):
        self._write_raw(save_path, {
            "version": 0,
            "player": {"level": 1, "xp": 0},
            "inventory": [],
        })
        data = manager.load()
        for facility in ("armory", "med_bay", "storage", "comms"):
            assert facility in data["home_base"]
            assert data["home_base"][facility] == 0

    def test_v0_save_version_bumped_to_1_after_migration(
        self, save_path: Path, manager: SaveManager
    ):
        self._write_raw(save_path, {
            "version": 0,
            "player": {"level": 1, "xp": 0},
            "inventory": [],
        })
        assert manager.load()["version"] == 1

    def test_partial_player_dict_gets_missing_keys_filled(
        self, save_path: Path, manager: SaveManager
    ):
        """Player dict missing xp gets xp filled with the default (0)."""
        self._write_raw(save_path, {
            "version": 1,
            "player": {"level": 5, "money": 2000},  # xp missing
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        })
        data = manager.load()
        assert "xp" in data["player"]

    def test_partial_home_base_gets_missing_facilities_filled(
        self, save_path: Path, manager: SaveManager
    ):
        """Home base dict missing comms/storage gets them filled with 0."""
        self._write_raw(save_path, {
            "version": 1,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 2, "med_bay": 1},  # storage + comms missing
        })
        data = manager.load()
        assert "storage" in data["home_base"]
        assert "comms" in data["home_base"]

    def test_complete_v1_save_is_returned_unchanged(
        self, save_path: Path, manager: SaveManager
    ):
        original = _state(money=5000)
        self._write_raw(save_path, original)
        data = manager.load()
        assert data["player"]["money"] == 5000
        assert data["player"]["level"] == 3


# ---------------------------------------------------------------------------
# Multiple independent managers / paths
# ---------------------------------------------------------------------------

class TestCustomSavePath:
    def test_custom_path_saves_and_loads(self, tmp_path: Path):
        path = tmp_path / "custom" / "mysave.json"
        m = SaveManager(save_path=path)
        m.save(_state(money=777))
        assert m.load()["player"]["money"] == 777

    def test_two_managers_on_different_paths_are_independent(self, tmp_path: Path):
        path_a = tmp_path / "a.json"
        path_b = tmp_path / "b.json"
        m_a = SaveManager(save_path=path_a)
        m_b = SaveManager(save_path=path_b)
        m_a.save(_state(money=100))
        m_b.save(_state(money=200))
        assert m_a.load()["player"]["money"] == 100
        assert m_b.load()["player"]["money"] == 200

    def test_string_path_is_accepted(self, tmp_path: Path):
        path = str(tmp_path / "str_save.json")
        m = SaveManager(save_path=path)
        m.save(_state(money=42))
        assert m.load()["player"]["money"] == 42
