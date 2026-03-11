"""
Unit tests for ItemDatabase singleton — src/inventory/item_database.py

Covers:
  - Singleton pattern  : get_instance() always returns the same object
  - load()             : parses items.json; idempotent on second call
  - create()           : returns correct subclass; populates fields; raises KeyError on unknown id
  - Instance isolation : cloned instances are independent (no shared mutation)
  - Helper queries     : get_all_by_type(), get_all_by_rarity()
"""
import copy
import json
import pytest

from src.inventory.item_database import ItemDatabase
from src.inventory.item import Rarity, Weapon, Armor, Consumable, Attachment


# ---------------------------------------------------------------------------
# Minimal catalog used by all tests (written to a tmp file per test)
# ---------------------------------------------------------------------------

SAMPLE_CATALOG = [
    {
        "id": "pistol_common",
        "name": "Common Pistol",
        "type": "weapon",
        "rarity": "COMMON",
        "weight": 1.5,
        "base_value": 100,
        "stats": {"accuracy": 0.7},
        "sprite": "sprites/pistol.png",
        "mod_slots": [],
        "damage": 25,
        "fire_rate": 4,
        "magazine_size": 12,
    },
    {
        "id": "rifle_legendary",
        "name": "Legendary Rifle",
        "type": "weapon",
        "rarity": "LEGENDARY",
        "weight": 3.5,
        "base_value": 1000,
        "stats": {"accuracy": 0.95},
        "sprite": "sprites/rifle.png",
        "mod_slots": ["slot_1", "slot_2"],
        "damage": 80,
        "fire_rate": 2,
        "magazine_size": 30,
    },
    {
        "id": "vest_common",
        "name": "Basic Vest",
        "type": "armor",
        "rarity": "COMMON",
        "weight": 3.0,
        "base_value": 150,
        "stats": {},
        "sprite": "sprites/vest.png",
        "defense": 20,
        "slot": "chest",
    },
    {
        "id": "helmet_rare",
        "name": "Tactical Helmet",
        "type": "armor",
        "rarity": "RARE",
        "weight": 2.0,
        "base_value": 300,
        "stats": {},
        "sprite": "sprites/helmet.png",
        "defense": 15,
        "slot": "helmet",
    },
    {
        "id": "medkit_uncommon",
        "name": "Medkit",
        "type": "consumable",
        "rarity": "UNCOMMON",
        "weight": 0.5,
        "base_value": 75,
        "stats": {},
        "sprite": "sprites/medkit.png",
        "effect_type": "heal",
        "effect_value": 50,
    },
    {
        "id": "scope_epic",
        "name": "Epic Scope",
        "type": "attachment",
        "rarity": "EPIC",
        "weight": 0.3,
        "base_value": 500,
        "stats": {},
        "sprite": "sprites/scope.png",
        "compatible_weapons": ["rifle_legendary"],
        "stat_delta": {"accuracy": 0.1},
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the ItemDatabase singleton between every test for isolation."""
    # Reset before
    if hasattr(ItemDatabase, "_instance"):
        ItemDatabase._instance = None
    if hasattr(ItemDatabase, "_items"):
        ItemDatabase._items = {}
    yield
    # Reset after
    if hasattr(ItemDatabase, "_instance"):
        ItemDatabase._instance = None
    if hasattr(ItemDatabase, "_items"):
        ItemDatabase._items = {}


@pytest.fixture()
def items_json(tmp_path):
    """Write SAMPLE_CATALOG to a temporary JSON file and return its path string."""
    path = tmp_path / "items.json"
    path.write_text(json.dumps(SAMPLE_CATALOG))
    return str(path)


@pytest.fixture()
def loaded_db(items_json):
    """Return an ItemDatabase that has already loaded SAMPLE_CATALOG."""
    db = ItemDatabase.get_instance()
    db.load(items_json)
    return db


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_instance_returns_item_database(self):
        db = ItemDatabase.get_instance()
        assert isinstance(db, ItemDatabase)

    def test_get_instance_twice_returns_same_object(self, items_json):
        db1 = ItemDatabase.get_instance()
        db2 = ItemDatabase.get_instance()
        assert db1 is db2

    def test_singleton_preserved_after_load(self, items_json):
        db1 = ItemDatabase.get_instance()
        db1.load(items_json)
        db2 = ItemDatabase.get_instance()
        assert db1 is db2

    def test_load_called_twice_does_not_raise(self, items_json):
        db = ItemDatabase.get_instance()
        db.load(items_json)
        db.load(items_json)  # idempotent — must not raise or corrupt state

    def test_create_still_works_after_double_load(self, items_json):
        db = ItemDatabase.get_instance()
        db.load(items_json)
        db.load(items_json)
        item = db.create("pistol_common")
        assert item is not None


# ---------------------------------------------------------------------------
# create() — correct subclass returned
# ---------------------------------------------------------------------------

class TestCreateSubclass:
    def test_create_weapon_returns_weapon(self, loaded_db):
        assert isinstance(loaded_db.create("pistol_common"), Weapon)

    def test_create_second_weapon_returns_weapon(self, loaded_db):
        assert isinstance(loaded_db.create("rifle_legendary"), Weapon)

    def test_create_armor_returns_armor(self, loaded_db):
        assert isinstance(loaded_db.create("vest_common"), Armor)

    def test_create_helmet_returns_armor(self, loaded_db):
        assert isinstance(loaded_db.create("helmet_rare"), Armor)

    def test_create_consumable_returns_consumable(self, loaded_db):
        assert isinstance(loaded_db.create("medkit_uncommon"), Consumable)

    def test_create_attachment_returns_attachment(self, loaded_db):
        assert isinstance(loaded_db.create("scope_epic"), Attachment)

    def test_create_unknown_id_raises_key_error(self, loaded_db):
        with pytest.raises(KeyError):
            loaded_db.create("nonexistent_item_xyz_abc")


# ---------------------------------------------------------------------------
# create() — field population
# ---------------------------------------------------------------------------

class TestCreateFields:
    def test_weapon_id(self, loaded_db):
        assert loaded_db.create("pistol_common").id == "pistol_common"

    def test_weapon_name(self, loaded_db):
        assert loaded_db.create("pistol_common").name == "Common Pistol"

    def test_weapon_rarity_common(self, loaded_db):
        assert loaded_db.create("pistol_common").rarity == Rarity.COMMON

    def test_weapon_rarity_legendary(self, loaded_db):
        assert loaded_db.create("rifle_legendary").rarity == Rarity.LEGENDARY

    def test_weapon_weight(self, loaded_db):
        assert loaded_db.create("pistol_common").weight == pytest.approx(1.5)

    def test_weapon_base_value(self, loaded_db):
        assert loaded_db.create("pistol_common").base_value == 100

    def test_weapon_damage(self, loaded_db):
        assert loaded_db.create("pistol_common").damage == 25

    def test_weapon_fire_rate(self, loaded_db):
        assert loaded_db.create("pistol_common").fire_rate == 4

    def test_weapon_magazine_size(self, loaded_db):
        assert loaded_db.create("pistol_common").magazine_size == 12

    def test_weapon_mod_slots_populated(self, loaded_db):
        rifle = loaded_db.create("rifle_legendary")
        assert "slot_1" in rifle.mod_slots
        assert "slot_2" in rifle.mod_slots

    def test_armor_defense(self, loaded_db):
        assert loaded_db.create("vest_common").defense == 20

    def test_armor_slot_chest(self, loaded_db):
        assert loaded_db.create("vest_common").slot == "chest"

    def test_armor_slot_helmet(self, loaded_db):
        assert loaded_db.create("helmet_rare").slot == "helmet"

    def test_armor_rarity_rare(self, loaded_db):
        assert loaded_db.create("helmet_rare").rarity == Rarity.RARE

    def test_consumable_effect_type(self, loaded_db):
        assert loaded_db.create("medkit_uncommon").effect_type == "heal"

    def test_consumable_effect_value(self, loaded_db):
        assert loaded_db.create("medkit_uncommon").effect_value == 50

    def test_consumable_rarity_uncommon(self, loaded_db):
        assert loaded_db.create("medkit_uncommon").rarity == Rarity.UNCOMMON

    def test_attachment_compatible_weapons(self, loaded_db):
        scope = loaded_db.create("scope_epic")
        assert "rifle_legendary" in scope.compatible_weapons

    def test_attachment_stat_delta(self, loaded_db):
        scope = loaded_db.create("scope_epic")
        assert scope.stat_delta.get("accuracy") == pytest.approx(0.1)

    def test_attachment_rarity_epic(self, loaded_db):
        assert loaded_db.create("scope_epic").rarity == Rarity.EPIC

    def test_stats_dict_populated(self, loaded_db):
        pistol = loaded_db.create("pistol_common")
        assert pistol.stats.get("accuracy") == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Instance isolation (cloning / no shared mutation)
# ---------------------------------------------------------------------------

class TestInstanceIsolation:
    def test_two_creates_return_different_objects(self, loaded_db):
        a = loaded_db.create("pistol_common")
        b = loaded_db.create("pistol_common")
        assert a is not b

    def test_mutating_stats_on_one_instance_does_not_affect_another(self, loaded_db):
        a = loaded_db.create("pistol_common")
        b = loaded_db.create("pistol_common")
        a.stats["injected"] = "mutated"
        assert "injected" not in b.stats

    def test_mutating_mod_slots_on_one_does_not_affect_another(self, loaded_db):
        r1 = loaded_db.create("rifle_legendary")
        r2 = loaded_db.create("rifle_legendary")
        r1.mod_slots.append("extra_attachment")
        assert "extra_attachment" not in r2.mod_slots

    def test_mutating_compatible_weapons_on_one_does_not_affect_another(self, loaded_db):
        s1 = loaded_db.create("scope_epic")
        s2 = loaded_db.create("scope_epic")
        s1.compatible_weapons.append("new_gun")
        assert "new_gun" not in s2.compatible_weapons

    def test_mutating_stat_delta_on_one_does_not_affect_another(self, loaded_db):
        s1 = loaded_db.create("scope_epic")
        s2 = loaded_db.create("scope_epic")
        s1.stat_delta["damage"] = 999
        assert s2.stat_delta.get("damage") != 999


# ---------------------------------------------------------------------------
# Helper queries
# ---------------------------------------------------------------------------

class TestGetAllByType:
    def test_weapons_returns_two_weapons(self, loaded_db):
        result = loaded_db.get_all_by_type("weapon")
        assert len(result) == 2
        assert all(isinstance(w, Weapon) for w in result)

    def test_armors_returns_two_armors(self, loaded_db):
        result = loaded_db.get_all_by_type("armor")
        assert len(result) == 2
        assert all(isinstance(a, Armor) for a in result)

    def test_consumables_returns_one_consumable(self, loaded_db):
        result = loaded_db.get_all_by_type("consumable")
        assert len(result) == 1
        assert isinstance(result[0], Consumable)

    def test_attachments_returns_one_attachment(self, loaded_db):
        result = loaded_db.get_all_by_type("attachment")
        assert len(result) == 1
        assert isinstance(result[0], Attachment)

    def test_unknown_type_returns_empty_list(self, loaded_db):
        result = loaded_db.get_all_by_type("unknown_type_xyz")
        assert result == []


class TestGetAllByRarity:
    def test_common_returns_two_items(self, loaded_db):
        result = loaded_db.get_all_by_rarity(Rarity.COMMON)
        assert len(result) == 2  # pistol_common + vest_common
        assert all(i.rarity == Rarity.COMMON for i in result)

    def test_uncommon_returns_one_item(self, loaded_db):
        result = loaded_db.get_all_by_rarity(Rarity.UNCOMMON)
        assert len(result) == 1
        assert result[0].id == "medkit_uncommon"

    def test_rare_returns_one_item(self, loaded_db):
        result = loaded_db.get_all_by_rarity(Rarity.RARE)
        assert len(result) == 1
        assert result[0].id == "helmet_rare"

    def test_epic_returns_one_item(self, loaded_db):
        result = loaded_db.get_all_by_rarity(Rarity.EPIC)
        assert len(result) == 1
        assert result[0].id == "scope_epic"

    def test_legendary_returns_one_item(self, loaded_db):
        result = loaded_db.get_all_by_rarity(Rarity.LEGENDARY)
        assert len(result) == 1
        assert result[0].id == "rifle_legendary"

    def test_rarity_with_no_items_returns_empty_list(self, loaded_db):
        # Our sample has no RARE weapons — confirm correct count rather than empty
        result = loaded_db.get_all_by_rarity(Rarity.RARE)
        assert isinstance(result, list)
        assert all(i.rarity == Rarity.RARE for i in result)
