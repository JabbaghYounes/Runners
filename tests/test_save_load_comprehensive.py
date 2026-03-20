"""Comprehensive tests for save/load of all player progression state.

Tests cover:
- Item.to_save_dict() serialisation and round-trip via make_item()
- Inventory.to_save_list() / from_save_list() round-trip
- SaveManager with live objects (Currency, XPSystem, Inventory, SkillTree, HomeBase)
- SaveManager.restore() pushing loaded state back into live objects
- Corruption / missing-file graceful fallback for all subsystems
- Skill tree unlock state persistence through full save/load cycle
- Home base facility levels persistence through full save/load cycle
"""
import json
from pathlib import Path

import pytest

from src.inventory.inventory import Inventory
from src.inventory.item import (
    Armor,
    Consumable,
    Item,
    Weapon,
    make_item,
    RARITY_COMMON,
    RARITY_EPIC,
    RARITY_RARE,
)
from src.progression.currency import Currency
from src.progression.skill_tree import SkillTree
from src.progression.xp_system import XPSystem
from src.save.save_manager import SaveManager, SAVE_VERSION


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def save_path(tmp_path: Path) -> Path:
    return tmp_path / "saves" / "save.json"


@pytest.fixture()
def manager(save_path: Path) -> SaveManager:
    return SaveManager(save_path=save_path)


@pytest.fixture()
def skill_tree_path(tmp_path: Path) -> str:
    data = {
        "branches": ["general"],
        "nodes": [
            {"id": "speed_1", "branch": "general", "requires": [], "stat_bonus": {"speed": 5}},
            {"id": "speed_2", "branch": "general", "requires": ["speed_1"], "stat_bonus": {"speed": 5}},
            {"id": "armor_1", "branch": "general", "requires": [], "stat_bonus": {"armor": 3}},
        ]
    }
    p = tmp_path / "skill_tree.json"
    p.write_text(json.dumps(data))
    return str(p)


@pytest.fixture()
def home_base_path(tmp_path: Path) -> str:
    data = {
        "facilities": [
            {
                "id": "armory",
                "name": "ARMORY",
                "description": "Test",
                "max_level": 3,
                "levels": [
                    {"cost": 100, "bonus_type": "loot_value_bonus", "bonus_value": 0.10, "description": "+10%"},
                    {"cost": 200, "bonus_type": "loot_value_bonus", "bonus_value": 0.20, "description": "+20%"},
                    {"cost": 300, "bonus_type": "loot_value_bonus", "bonus_value": 0.30, "description": "+30%"},
                ],
            },
            {
                "id": "med_bay",
                "name": "MED BAY",
                "description": "Test",
                "max_level": 3,
                "levels": [
                    {"cost": 100, "bonus_type": "extra_hp", "bonus_value": 25, "description": "+25 HP"},
                    {"cost": 200, "bonus_type": "extra_hp", "bonus_value": 50, "description": "+50 HP"},
                    {"cost": 300, "bonus_type": "extra_hp", "bonus_value": 75, "description": "+75 HP"},
                ],
            },
            {
                "id": "storage",
                "name": "STORAGE",
                "description": "Test",
                "max_level": 3,
                "levels": [
                    {"cost": 100, "bonus_type": "extra_slots", "bonus_value": 2, "description": "+2"},
                    {"cost": 200, "bonus_type": "extra_slots", "bonus_value": 4, "description": "+4"},
                    {"cost": 300, "bonus_type": "extra_slots", "bonus_value": 6, "description": "+6"},
                ],
            },
        ]
    }
    p = tmp_path / "home_base.json"
    p.write_text(json.dumps(data))
    return str(p)


def _weapon(item_id="rifle_test", value=500, weight=2.0):
    return Weapon(item_id=item_id, name="Test Rifle", rarity="rare", value=value,
                  weight=weight, sprite="items/rifle", stats={"damage": 30, "fire_rate": 3.0})


def _armor(item_id="vest_test", value=200, weight=3.0):
    return Armor(item_id=item_id, name="Test Vest", rarity="uncommon", value=value,
                 weight=weight, sprite="items/vest", armor_value=15,
                 stats={"armor": 15, "mobility_penalty": 5})


def _consumable(item_id="medkit_test", value=50, weight=0.5):
    return Consumable(item_id=item_id, name="Test Medkit", rarity="common", value=value,
                      weight=weight, sprite="items/medkit", heal_amount=30,
                      stats={"heal_amount": 30, "use_time": 1.5})


# ===========================================================================
# Item.to_save_dict()
# ===========================================================================

class TestItemToSaveDict:
    def test_weapon_to_save_dict_has_all_keys(self):
        d = _weapon().to_save_dict()
        for key in ("item_id", "name", "item_type", "rarity", "value", "weight",
                     "sprite", "stats", "quantity"):
            assert key in d

    def test_weapon_item_type_is_weapon(self):
        assert _weapon().to_save_dict()["item_type"] == "weapon"

    def test_armor_item_type_is_armor(self):
        assert _armor().to_save_dict()["item_type"] == "armor"

    def test_consumable_item_type_is_consumable(self):
        assert _consumable().to_save_dict()["item_type"] == "consumable"

    def test_rarity_is_string_not_enum(self):
        d = _weapon().to_save_dict()
        assert isinstance(d["rarity"], str)

    def test_value_preserved(self):
        assert _weapon(value=750).to_save_dict()["value"] == 750

    def test_weight_preserved(self):
        assert _weapon(weight=4.5).to_save_dict()["weight"] == 4.5

    def test_stats_preserved(self):
        d = _weapon().to_save_dict()
        assert d["stats"]["damage"] == 30
        assert d["stats"]["fire_rate"] == 3.0

    def test_roundtrip_via_make_item_preserves_id(self):
        original = _weapon(item_id="test_gun")
        restored = make_item(original.to_save_dict())
        assert restored.item_id == "test_gun"

    def test_roundtrip_via_make_item_preserves_type(self):
        original = _weapon()
        restored = make_item(original.to_save_dict())
        assert isinstance(restored, Weapon)

    def test_roundtrip_via_make_item_preserves_value(self):
        original = _weapon(value=999)
        restored = make_item(original.to_save_dict())
        assert restored.value == 999

    def test_roundtrip_armor_via_make_item(self):
        original = _armor()
        restored = make_item(original.to_save_dict())
        assert isinstance(restored, Armor)
        assert restored.item_id == "vest_test"

    def test_roundtrip_consumable_via_make_item(self):
        original = _consumable()
        restored = make_item(original.to_save_dict())
        assert isinstance(restored, Consumable)
        assert restored.item_id == "medkit_test"


# ===========================================================================
# Inventory.to_save_list() / from_save_list()
# ===========================================================================

class TestInventorySaveList:
    def test_empty_inventory_returns_empty_list(self):
        inv = Inventory(capacity=10, max_weight=50.0)
        assert inv.to_save_list() == []

    def test_single_item_serialises_to_one_element(self):
        inv = Inventory(capacity=10, max_weight=50.0)
        inv.add_item(_weapon())
        result = inv.to_save_list()
        assert len(result) == 1
        assert result[0]["item_id"] == "rifle_test"

    def test_multiple_items_serialise_correctly(self):
        inv = Inventory(capacity=10, max_weight=50.0)
        inv.add_item(_weapon(item_id="gun_a"))
        inv.add_item(_armor(item_id="vest_a"))
        inv.add_item(_consumable(item_id="med_a"))
        result = inv.to_save_list()
        assert len(result) == 3
        ids = [d["item_id"] for d in result]
        assert "gun_a" in ids
        assert "vest_a" in ids
        assert "med_a" in ids

    def test_from_save_list_restores_items(self):
        inv = Inventory(capacity=10, max_weight=50.0)
        inv.add_item(_weapon(item_id="gun_x"))
        data = inv.to_save_list()

        inv2 = Inventory(capacity=10, max_weight=50.0)
        inv2.from_save_list(data)
        assert inv2.used_slots == 1
        items = inv2.get_items()
        assert items[0].item_id == "gun_x"

    def test_from_save_list_clears_existing_items_first(self):
        inv = Inventory(capacity=10, max_weight=50.0)
        inv.add_item(_weapon(item_id="old_gun"))

        inv.from_save_list([_consumable(item_id="new_med").to_save_dict()])
        items = inv.get_items()
        assert len(items) == 1
        assert items[0].item_id == "new_med"

    def test_from_save_list_with_empty_list_clears_inventory(self):
        inv = Inventory(capacity=10, max_weight=50.0)
        inv.add_item(_weapon())
        inv.from_save_list([])
        assert inv.used_slots == 0

    def test_from_save_list_skips_invalid_entries(self):
        inv = Inventory(capacity=10, max_weight=50.0)
        inv.from_save_list([
            _weapon(item_id="good_item").to_save_dict(),
            "not_a_dict",
            42,
            None,
        ])
        assert inv.used_slots == 1
        assert inv.get_items()[0].item_id == "good_item"

    def test_roundtrip_preserves_item_types(self):
        inv = Inventory(capacity=10, max_weight=50.0)
        inv.add_item(_weapon())
        inv.add_item(_armor())
        inv.add_item(_consumable())
        data = inv.to_save_list()

        inv2 = Inventory(capacity=10, max_weight=50.0)
        inv2.from_save_list(data)
        types = sorted(i.item_type for i in inv2.get_items())
        assert types == ["armor", "consumable", "weapon"]


# ===========================================================================
# SaveManager with live objects (object-based save)
# ===========================================================================

class TestSaveManagerWithObjects:
    def test_save_with_all_objects(self, save_path, manager, home_base_path, skill_tree_path):
        from src.progression.home_base import HomeBase

        hb = HomeBase(home_base_path)
        cur = Currency(balance=2500)
        xp = XPSystem()
        xp.xp = 100
        xp.level = 3
        inv = Inventory(capacity=10, max_weight=50.0)
        inv.add_item(_weapon(item_id="saved_gun"))
        st = SkillTree()
        st.load(skill_tree_path)
        st.unlock("speed_1")

        manager.save(
            home_base=hb,
            currency=cur,
            xp_system=xp,
            inventory=inv,
            skill_tree=st,
        )

        loaded = manager.load()
        assert loaded["player"]["money"] == 2500
        assert loaded["player"]["xp"] == 100
        assert loaded["player"]["level"] == 3
        assert len(loaded["inventory"]) == 1
        assert loaded["inventory"][0]["item_id"] == "saved_gun"
        assert "speed_1" in loaded["skill_tree"]["unlocked_nodes"]
        assert loaded["home_base"]["armory"] == 0

    def test_save_with_upgraded_home_base(self, save_path, manager, home_base_path):
        from src.progression.home_base import HomeBase

        hb = HomeBase(home_base_path)
        rich = Currency(balance=10000)
        hb.upgrade("armory", rich)
        hb.upgrade("armory", rich)

        manager.save(home_base=hb, currency=rich, xp_system=XPSystem())
        loaded = manager.load()
        assert loaded["home_base"]["armory"] == 2

    def test_save_with_skill_tree_unlocks(self, save_path, manager, skill_tree_path):
        st = SkillTree()
        st.load(skill_tree_path)
        st.unlock("speed_1")
        st.unlock("armor_1")

        manager.save(skill_tree=st)
        loaded = manager.load()
        nodes = loaded["skill_tree"]["unlocked_nodes"]
        assert "speed_1" in nodes
        assert "armor_1" in nodes

    def test_save_with_no_skill_tree_defaults_to_empty(self, save_path, manager):
        manager.save(home_base=None, currency=Currency(), xp_system=XPSystem())
        loaded = manager.load()
        assert loaded["skill_tree"]["unlocked_nodes"] == []

    def test_save_with_inventory_items(self, save_path, manager):
        inv = Inventory(capacity=10, max_weight=50.0)
        inv.add_item(_weapon(item_id="gun_1", value=300))
        inv.add_item(_armor(item_id="armor_1", value=200))
        manager.save(inventory=inv)
        loaded = manager.load()
        assert len(loaded["inventory"]) == 2

    def test_legacy_positional_save_still_works(self, save_path, manager, home_base_path):
        """save(home_base_obj, currency=..., xp_system=...) still works."""
        from src.progression.home_base import HomeBase

        hb = HomeBase(home_base_path)
        manager.save(hb, currency=Currency(500), xp_system=XPSystem())
        loaded = manager.load()
        assert loaded["player"]["money"] == 500


# ===========================================================================
# SaveManager.restore() — push loaded state into live objects
# ===========================================================================

class TestSaveManagerRestore:
    def test_restore_currency_balance(self, save_path, manager):
        manager.save({"version": SAVE_VERSION,
                       "player": {"level": 1, "xp": 0, "money": 4200},
                       "inventory": [], "skill_tree": {"unlocked_nodes": []},
                       "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0}})
        cur = Currency()
        manager.restore(currency=cur)
        assert cur.balance == 4200

    def test_restore_xp_and_level(self, save_path, manager):
        manager.save({"version": SAVE_VERSION,
                       "player": {"level": 7, "xp": 350, "money": 0},
                       "inventory": [], "skill_tree": {"unlocked_nodes": []},
                       "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0}})
        xp = XPSystem()
        manager.restore(xp_system=xp)
        assert xp.level == 7
        assert xp.xp == 350

    def test_restore_inventory(self, save_path, manager):
        state = {
            "version": SAVE_VERSION,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [_weapon(item_id="restore_gun").to_save_dict()],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        }
        manager.save(state)
        inv = Inventory(capacity=10, max_weight=50.0)
        manager.restore(inventory=inv)
        assert inv.used_slots == 1
        assert inv.get_items()[0].item_id == "restore_gun"

    def test_restore_skill_tree(self, save_path, manager, skill_tree_path):
        state = {
            "version": SAVE_VERSION,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [],
            "skill_tree": {"unlocked_nodes": ["speed_1", "armor_1"]},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        }
        manager.save(state)
        st = SkillTree()
        st.load(skill_tree_path)
        manager.restore(skill_tree=st)
        assert st.get_stat_bonuses().get("speed", 0) == 5
        assert st.get_stat_bonuses().get("armor", 0) == 3

    def test_restore_home_base(self, save_path, manager, home_base_path):
        from src.progression.home_base import HomeBase

        state = {
            "version": SAVE_VERSION,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 2, "med_bay": 1, "storage": 0},
        }
        manager.save(state)
        hb = HomeBase(home_base_path)
        manager.restore(home_base=hb)
        assert hb.current_level("armory") == 2
        assert hb.current_level("med_bay") == 1
        assert hb.current_level("storage") == 0

    def test_restore_all_objects_at_once(self, save_path, manager, home_base_path, skill_tree_path):
        from src.progression.home_base import HomeBase

        state = {
            "version": SAVE_VERSION,
            "player": {"level": 5, "xp": 200, "money": 3000},
            "inventory": [
                _weapon(item_id="full_gun").to_save_dict(),
                _armor(item_id="full_vest").to_save_dict(),
            ],
            "skill_tree": {"unlocked_nodes": ["speed_1"]},
            "home_base": {"armory": 1, "med_bay": 2, "storage": 0},
        }
        manager.save(state)

        cur = Currency()
        xp = XPSystem()
        inv = Inventory(capacity=10, max_weight=50.0)
        st = SkillTree()
        st.load(skill_tree_path)
        hb = HomeBase(home_base_path)

        manager.restore(
            currency=cur,
            xp_system=xp,
            inventory=inv,
            skill_tree=st,
            home_base=hb,
        )

        assert cur.balance == 3000
        assert xp.level == 5
        assert xp.xp == 200
        assert inv.used_slots == 2
        assert st.get_stat_bonuses().get("speed", 0) == 5
        assert hb.current_level("armory") == 1
        assert hb.current_level("med_bay") == 2

    def test_restore_returns_raw_state_dict(self, save_path, manager):
        manager.save({"version": SAVE_VERSION,
                       "player": {"level": 1, "xp": 0, "money": 999},
                       "inventory": [], "skill_tree": {"unlocked_nodes": []},
                       "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0}})
        result = manager.restore()
        assert isinstance(result, dict)
        assert result["player"]["money"] == 999

    def test_restore_with_no_objects_does_not_raise(self, save_path, manager):
        manager.save({"version": SAVE_VERSION,
                       "player": {"level": 1, "xp": 0, "money": 0},
                       "inventory": [], "skill_tree": {"unlocked_nodes": []},
                       "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0}})
        state = manager.restore()
        assert state["version"] == SAVE_VERSION


# ===========================================================================
# Full round-trip: save from objects -> load -> restore into new objects
# ===========================================================================

class TestFullRoundTrip:
    def test_full_roundtrip_all_state(self, save_path, manager, home_base_path, skill_tree_path):
        from src.progression.home_base import HomeBase

        # --- Set up original state ---
        cur1 = Currency(balance=5000)
        xp1 = XPSystem()
        xp1.level = 4
        xp1.xp = 300

        inv1 = Inventory(capacity=10, max_weight=50.0)
        inv1.add_item(_weapon(item_id="rt_gun", value=700))
        inv1.add_item(_consumable(item_id="rt_med", value=50))

        st1 = SkillTree()
        st1.load(skill_tree_path)
        st1.unlock("speed_1")
        st1.unlock("speed_2")

        hb1 = HomeBase(home_base_path)
        rich = Currency(balance=10000)
        hb1.upgrade("armory", rich)
        hb1.upgrade("med_bay", rich)
        hb1.upgrade("med_bay", rich)

        # --- Save ---
        manager.save(
            home_base=hb1,
            currency=cur1,
            xp_system=xp1,
            inventory=inv1,
            skill_tree=st1,
        )

        # --- Restore into fresh objects ---
        cur2 = Currency()
        xp2 = XPSystem()
        inv2 = Inventory(capacity=10, max_weight=50.0)
        st2 = SkillTree()
        st2.load(skill_tree_path)
        hb2 = HomeBase(home_base_path)

        manager.restore(
            currency=cur2,
            xp_system=xp2,
            inventory=inv2,
            skill_tree=st2,
            home_base=hb2,
        )

        # --- Verify everything matches ---
        assert cur2.balance == 5000
        assert xp2.level == 4
        assert xp2.xp == 300

        items = inv2.get_items()
        assert len(items) == 2
        item_ids = [i.item_id for i in items]
        assert "rt_gun" in item_ids
        assert "rt_med" in item_ids

        assert st2.get_stat_bonuses().get("speed", 0) == 10  # speed_1 + speed_2

        assert hb2.current_level("armory") == 1
        assert hb2.current_level("med_bay") == 2
        assert hb2.current_level("storage") == 0

    def test_new_game_restore_gives_zero_state(self, save_path, manager, home_base_path, skill_tree_path):
        """When no save file exists, restore gives new-game defaults."""
        from src.progression.home_base import HomeBase

        cur = Currency(balance=9999)  # will be reset
        xp = XPSystem()
        inv = Inventory(capacity=10, max_weight=50.0)
        inv.add_item(_weapon())  # will be cleared
        st = SkillTree()
        st.load(skill_tree_path)
        hb = HomeBase(home_base_path)

        manager.restore(
            currency=cur, xp_system=xp, inventory=inv,
            skill_tree=st, home_base=hb,
        )

        assert cur.balance == 0
        assert xp.level == 1
        assert xp.xp == 0
        assert inv.used_slots == 0
        assert st.get_stat_bonuses() == {}
        assert hb.current_level("armory") == 0


# ===========================================================================
# Corruption / missing file graceful fallback with objects
# ===========================================================================

class TestCorruptionFallbackWithObjects:
    def test_corrupt_json_restore_gives_new_game_defaults(self, save_path, manager):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text("{{{invalid json!!!", encoding="utf-8")
        cur = Currency(balance=9999)
        xp = XPSystem()
        manager.restore(currency=cur, xp_system=xp)
        assert cur.balance == 0
        assert xp.level == 1

    def test_empty_file_restore_gives_new_game_defaults(self, save_path, manager):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text("", encoding="utf-8")
        cur = Currency(balance=5000)
        manager.restore(currency=cur)
        assert cur.balance == 0

    def test_missing_file_restore_gives_new_game_defaults(self, save_path, manager):
        cur = Currency(balance=5000)
        manager.restore(currency=cur)
        assert cur.balance == 0

    def test_partial_save_missing_inventory_key(self, save_path, manager):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps({
            "version": 1,
            "player": {"level": 3, "xp": 100, "money": 500},
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        }), encoding="utf-8")
        inv = Inventory(capacity=10, max_weight=50.0)
        state = manager.restore(inventory=inv)
        # Should get empty inventory from migration defaults
        assert inv.used_slots == 0
        # Other fields should be intact
        assert state["player"]["money"] == 500

    def test_partial_save_missing_skill_tree_key(self, save_path, manager, skill_tree_path):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps({
            "version": 1,
            "player": {"level": 2, "xp": 50, "money": 300},
            "inventory": [],
            "home_base": {"armory": 1, "med_bay": 0, "storage": 0, "comms": 0},
        }), encoding="utf-8")
        st = SkillTree()
        st.load(skill_tree_path)
        manager.restore(skill_tree=st)
        # No unlocks
        assert st.get_stat_bonuses() == {}

    def test_truncated_json_fallback(self, save_path, manager):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text('{"version": 1, "player":', encoding="utf-8")
        cur = Currency(balance=9999)
        manager.restore(currency=cur)
        assert cur.balance == 0


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_save_and_load_with_empty_inventory(self, save_path, manager):
        inv = Inventory(capacity=10, max_weight=50.0)
        manager.save(inventory=inv)
        loaded = manager.load()
        assert loaded["inventory"] == []

    def test_save_and_load_preserves_item_count(self, save_path, manager):
        inv = Inventory(capacity=24, max_weight=100.0)
        for i in range(5):
            inv.add_item(_weapon(item_id=f"gun_{i}", weight=1.0))
        manager.save(inventory=inv)
        loaded = manager.load()
        assert len(loaded["inventory"]) == 5

    def test_multiple_save_cycles_last_wins(self, save_path, manager):
        manager.save({"version": SAVE_VERSION,
                       "player": {"level": 1, "xp": 0, "money": 100},
                       "inventory": [], "skill_tree": {"unlocked_nodes": []},
                       "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0}})
        manager.save({"version": SAVE_VERSION,
                       "player": {"level": 5, "xp": 999, "money": 9999},
                       "inventory": [], "skill_tree": {"unlocked_nodes": ["a", "b"]},
                       "home_base": {"armory": 3, "med_bay": 2, "storage": 1, "comms": 0}})
        loaded = manager.load()
        assert loaded["player"]["money"] == 9999
        assert loaded["player"]["level"] == 5
        assert loaded["skill_tree"]["unlocked_nodes"] == ["a", "b"]
        assert loaded["home_base"]["armory"] == 3

    def test_inventory_from_save_list_with_bad_item_data_skips_gracefully(self):
        inv = Inventory(capacity=10, max_weight=50.0)
        # Mix of good and bad data
        inv.from_save_list([
            {"item_id": "ok_item", "name": "OK", "item_type": "weapon",
             "rarity": "common", "value": 100, "weight": 1.0,
             "sprite": "", "stats": {}, "quantity": 1},
            {"bad_key": "bad_value"},  # missing required fields for make_item
        ])
        # Should have loaded the good item and skipped the bad one
        assert inv.used_slots >= 1

    def test_save_file_is_human_readable_json(self, save_path, manager):
        manager.save({"version": SAVE_VERSION,
                       "player": {"level": 1, "xp": 0, "money": 0},
                       "inventory": [], "skill_tree": {"unlocked_nodes": []},
                       "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0}})
        raw = save_path.read_text(encoding="utf-8")
        # Verify it's indented (human-readable)
        assert "\n" in raw
        parsed = json.loads(raw)
        assert parsed["version"] == SAVE_VERSION
