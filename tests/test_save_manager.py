"""Unit + integration tests for SaveManager — load, save, migration, atomic write."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.save.save_manager import SaveManager, SAVE_VERSION
from src.progression.home_base import HomeBase
from src.progression.currency import Currency
from src.progression.xp_system import XPSystem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def save_path(tmp_path) -> Path:
    """Return a non-existent save path inside a temp directory."""
    return tmp_path / "saves" / "save.json"


@pytest.fixture
def manager(save_path) -> SaveManager:
    return SaveManager(save_path)


@pytest.fixture
def hb(tmp_path) -> HomeBase:
    """HomeBase loaded from the real data file."""
    return HomeBase("data/home_base.json")


@pytest.fixture
def currency() -> Currency:
    return Currency(balance=750)


@pytest.fixture
def xp() -> XPSystem:
    s = XPSystem()
    s.award(500)
    return s


# ---------------------------------------------------------------------------
# TestLoadBehavior
# ---------------------------------------------------------------------------

class TestLoadBehavior:
    def test_missing_file_returns_new_game_state(self, manager):
        state = manager.load()
        # Must have all top-level keys
        assert "version" in state
        assert "player" in state
        assert "inventory" in state
        assert "home_base" in state
        assert "skill_tree" in state

    def test_missing_file_home_base_is_all_zero(self, manager):
        state = manager.load()
        assert state["home_base"]["armory"] == 0
        assert state["home_base"]["med_bay"] == 0
        assert state["home_base"]["storage"] == 0

    def test_missing_file_player_starts_at_level_1(self, manager):
        state = manager.load()
        assert state["player"]["level"] == 1

    def test_missing_file_player_money_is_zero(self, manager):
        state = manager.load()
        assert state["player"]["money"] == 0

    def test_corrupt_json_returns_new_game_state(self, save_path):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text("{ this is not valid JSON !!!")
        manager = SaveManager(save_path)
        state = manager.load()
        assert state["player"]["level"] == 1
        assert state["home_base"]["armory"] == 0

    def test_empty_file_returns_new_game_state(self, save_path):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text("")
        manager = SaveManager(save_path)
        state = manager.load()
        assert state["player"]["level"] == 1

    def test_new_game_version_is_current(self, manager):
        state = manager.load()
        assert state["version"] == SAVE_VERSION

    def test_new_game_inventory_is_empty_list(self, manager):
        state = manager.load()
        assert state["inventory"] == []

    def test_new_game_skill_tree_has_unlocked_nodes(self, manager):
        state = manager.load()
        assert "unlocked_nodes" in state["skill_tree"]


# ---------------------------------------------------------------------------
# TestSaveLoad — round-trip correctness
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_creates_file(self, manager, hb, currency, xp):
        manager.save(home_base=hb, currency=currency, xp_system=xp)
        assert manager._save_path.exists()

    def test_save_creates_parent_directory(self, tmp_path, hb, currency, xp):
        nested_path = tmp_path / "deep" / "nested" / "saves" / "save.json"
        m = SaveManager(nested_path)
        m.save(home_base=hb, currency=currency, xp_system=xp)
        assert nested_path.exists()

    def test_save_writes_valid_json(self, manager, hb, currency, xp):
        manager.save(home_base=hb, currency=currency, xp_system=xp)
        raw = manager._save_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_save_version_field_is_written(self, manager, hb, currency, xp):
        manager.save(home_base=hb, currency=currency, xp_system=xp)
        state = manager.load()
        assert state["version"] == SAVE_VERSION

    def test_roundtrip_home_base_levels(self, manager, tmp_path, currency, xp):
        hb = HomeBase("data/home_base.json")
        rich = Currency(10_000)
        hb.upgrade("armory", rich)
        hb.upgrade("armory", rich)
        hb.upgrade("med_bay", rich)

        manager.save(home_base=hb, currency=currency, xp_system=xp)
        loaded = manager.load()
        assert loaded["home_base"]["armory"] == 2
        assert loaded["home_base"]["med_bay"] == 1
        assert loaded["home_base"]["storage"] == 0

    def test_roundtrip_currency_balance(self, manager, hb, xp):
        c = Currency(balance=1234)
        manager.save(home_base=hb, currency=c, xp_system=xp)
        loaded = manager.load()
        assert loaded["player"]["money"] == 1234

    def test_roundtrip_xp_and_level(self, manager, hb, currency):
        xp_sys = XPSystem()
        xp_sys.award(1400)  # should reach level 6
        manager.save(home_base=hb, currency=currency, xp_system=xp_sys)
        loaded = manager.load()
        assert loaded["player"]["xp"] == 1400
        assert loaded["player"]["level"] == xp_sys.level

    def test_save_without_inventory_stores_empty_list(self, manager, hb, currency, xp):
        manager.save(home_base=hb, currency=currency, xp_system=xp, inventory=None)
        loaded = manager.load()
        assert loaded["inventory"] == []

    def test_save_with_inventory_stores_items(self, manager, hb, currency, xp):
        from src.inventory.inventory import Inventory
        from src.inventory.item import Item
        inv = Inventory(capacity=5)
        inv.add_item(Item(item_id="pistol", name="Pistol", quantity=1))
        manager.save(home_base=hb, currency=currency, xp_system=xp, inventory=inv)
        loaded = manager.load()
        assert len(loaded["inventory"]) == 1
        assert loaded["inventory"][0]["item_id"] == "pistol"

    def test_overwrite_previous_save(self, manager, hb, xp):
        # First save
        c1 = Currency(balance=100)
        manager.save(home_base=hb, currency=c1, xp_system=xp)
        # Second save — overwrites
        c2 = Currency(balance=999)
        manager.save(home_base=hb, currency=c2, xp_system=xp)
        loaded = manager.load()
        assert loaded["player"]["money"] == 999


# ---------------------------------------------------------------------------
# TestAtomicWrite
# ---------------------------------------------------------------------------

class TestAtomicWrite:
    def test_no_tmp_file_remains_after_save(self, manager, hb, currency, xp):
        manager.save(home_base=hb, currency=currency, xp_system=xp)
        tmp = manager._save_path.with_suffix(".tmp")
        assert not tmp.exists()

    def test_save_file_has_correct_suffix(self, manager, hb, currency, xp):
        manager.save(home_base=hb, currency=currency, xp_system=xp)
        assert manager._save_path.suffix == ".json"


# ---------------------------------------------------------------------------
# TestMigrate — _migrate() fills in missing fields from old saves
# ---------------------------------------------------------------------------

class TestMigrate:
    def _write_raw(self, save_path: Path, data: dict) -> None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(data), encoding="utf-8")

    def test_migrate_adds_missing_home_base_key(self, save_path):
        """A save missing 'home_base' should get a default home_base block."""
        self._write_raw(save_path, {
            "version": 1,
            "player": {"level": 2, "xp": 200, "money": 50},
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            # 'home_base' deliberately omitted
        })
        manager = SaveManager(save_path)
        state = manager.load()
        assert "home_base" in state
        assert state["home_base"]["armory"] == 0
        assert state["home_base"]["med_bay"] == 0
        assert state["home_base"]["storage"] == 0

    def test_migrate_adds_missing_player_money(self, save_path):
        """A save where player dict lacks 'money' should get money=0."""
        self._write_raw(save_path, {
            "version": 1,
            "player": {"level": 3, "xp": 500},   # no 'money' key
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0},
        })
        manager = SaveManager(save_path)
        state = manager.load()
        assert state["player"]["money"] == 0

    def test_migrate_preserves_existing_player_data(self, save_path):
        self._write_raw(save_path, {
            "version": 1,
            "player": {"level": 5, "xp": 1400, "money": 3000},
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 3, "med_bay": 2, "storage": 1},
        })
        manager = SaveManager(save_path)
        state = manager.load()
        assert state["player"]["level"] == 5
        assert state["player"]["xp"] == 1400
        assert state["player"]["money"] == 3000

    def test_migrate_preserves_home_base_levels(self, save_path):
        self._write_raw(save_path, {
            "version": 1,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 4, "med_bay": 3, "storage": 5},
        })
        manager = SaveManager(save_path)
        state = manager.load()
        assert state["home_base"]["armory"] == 4
        assert state["home_base"]["med_bay"] == 3
        assert state["home_base"]["storage"] == 5

    def test_migrate_adds_missing_top_level_keys(self, save_path):
        """Old saves lacking top-level keys (e.g. skill_tree) get defaults."""
        self._write_raw(save_path, {
            "version": 1,
            "player": {"level": 1, "xp": 0, "money": 0},
            # 'inventory', 'skill_tree', 'home_base' missing
        })
        manager = SaveManager(save_path)
        state = manager.load()
        assert "inventory" in state
        assert "skill_tree" in state
        assert "home_base" in state
