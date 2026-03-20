"""Tests for loading weapon attachment data from the data files.

Validates:
  - data/attachments.json exists, is valid JSON, and has well-formed entries
  - Each attachment entry carries required fields: id, type, slot_type, stat_delta
  - ItemDatabase.load_additional() merges entries from attachments.json without
    clearing the existing weapon/armor/consumable catalog
  - After merging, Attachment items are accessible via ItemDatabase.create()
  - The loaded Attachment instances have correct slot_type and stat_delta
  - ItemDatabase gracefully handles a missing attachments.json (no crash)
  - data/items.json weapon entries have mod_slots defined
  - data/enemies.json loot tables include at least one attachment item_id

# Run: pytest tests/test_attachment_database_loading.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.inventory.item_database import ItemDatabase
from src.inventory.item import Attachment, Weapon


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_item_database_singleton():
    """Ensure each test gets a clean ItemDatabase singleton."""
    ItemDatabase._instance = None
    yield
    ItemDatabase._instance = None


@pytest.fixture()
def db_weapons_only(tmp_path: Path) -> ItemDatabase:
    """ItemDatabase loaded from a minimal weapons-only catalog."""
    catalog = [
        {
            "id": "rifle_test",
            "name": "Test Rifle",
            "type": "weapon",
            "rarity": "COMMON",
            "weight": 3.0,
            "base_value": 200,
            "stats": {"range": 450, "reload_time": 2.0},
            "sprite": "",
            "mod_slots": ["scope", "barrel", "grip"],
            "damage": 30,
            "fire_rate": 4.0,
            "magazine_size": 20,
        },
    ]
    path = tmp_path / "items.json"
    path.write_text(json.dumps(catalog))
    db = ItemDatabase.get_instance()
    db.load(str(path))
    return db


@pytest.fixture()
def tmp_attachments_json(tmp_path: Path) -> Path:
    """A minimal attachments.json with one entry per supported slot type."""
    entries = [
        {
            "id": "tmp_scope",
            "name": "Tmp Scope",
            "type": "attachment",
            "slot_type": "scope",
            "rarity": "common",
            "value": 100,
            "weight": 0.3,
            "sprite": "",
            "stat_delta": {"accuracy": 15, "damage": 5},
            "compatible_weapons": [],
            "stats": {},
        },
        {
            "id": "tmp_barrel",
            "name": "Tmp Barrel",
            "type": "attachment",
            "slot_type": "barrel",
            "rarity": "uncommon",
            "value": 200,
            "weight": 0.4,
            "sprite": "",
            "stat_delta": {"damage": -3, "fire_rate": 0.5},
            "compatible_weapons": ["rifle_test"],
            "stats": {},
        },
        {
            "id": "tmp_grip",
            "name": "Tmp Grip",
            "type": "attachment",
            "slot_type": "grip",
            "rarity": "rare",
            "value": 400,
            "weight": 0.2,
            "sprite": "",
            "stat_delta": {"fire_rate": 1.0},
            "compatible_weapons": [],
            "stats": {},
        },
    ]
    path = tmp_path / "attachments.json"
    path.write_text(json.dumps(entries))
    return path


# ---------------------------------------------------------------------------
# data/attachments.json schema validation
# ---------------------------------------------------------------------------


class TestAttachmentsJsonSchema:
    """The canonical data/attachments.json must exist and be well-formed."""

    DATA_PATH = Path("data") / "attachments.json"

    def test_attachments_json_exists(self):
        assert self.DATA_PATH.exists(), (
            "data/attachments.json is missing — create it with attachment definitions"
        )

    def test_attachments_json_is_valid_json(self):
        content = self.DATA_PATH.read_text(encoding="utf-8")
        data = json.loads(content)  # raises if invalid JSON
        assert isinstance(data, list), "data/attachments.json must be a JSON array"

    def test_every_entry_has_required_id(self):
        data = json.loads(self.DATA_PATH.read_text(encoding="utf-8"))
        for entry in data:
            assert "id" in entry, f"Missing 'id' in entry: {entry}"

    def test_every_entry_has_type_attachment(self):
        data = json.loads(self.DATA_PATH.read_text(encoding="utf-8"))
        for entry in data:
            assert entry.get("type") == "attachment", (
                f"Entry {entry.get('id')} has type={entry.get('type')!r}, expected 'attachment'"
            )

    def test_every_entry_has_slot_type(self):
        data = json.loads(self.DATA_PATH.read_text(encoding="utf-8"))
        for entry in data:
            assert "slot_type" in entry and entry["slot_type"], (
                f"Entry {entry.get('id')!r} is missing a non-empty 'slot_type'"
            )

    def test_every_entry_has_stat_delta(self):
        data = json.loads(self.DATA_PATH.read_text(encoding="utf-8"))
        for entry in data:
            assert "stat_delta" in entry and isinstance(entry["stat_delta"], dict), (
                f"Entry {entry.get('id')!r} is missing a 'stat_delta' dict"
            )

    def test_slot_types_are_from_valid_set(self):
        valid_slots = {"scope", "barrel", "grip", "magazine", "stock"}
        data = json.loads(self.DATA_PATH.read_text(encoding="utf-8"))
        for entry in data:
            slot = entry.get("slot_type", "")
            assert slot in valid_slots, (
                f"Entry {entry.get('id')!r} has unknown slot_type={slot!r}. "
                f"Valid values: {valid_slots}"
            )

    def test_stat_delta_values_are_numeric(self):
        data = json.loads(self.DATA_PATH.read_text(encoding="utf-8"))
        for entry in data:
            for key, val in entry.get("stat_delta", {}).items():
                assert isinstance(val, (int, float)), (
                    f"Entry {entry.get('id')!r}: stat_delta[{key!r}] = {val!r} "
                    "must be a number"
                )

    def test_compatible_weapons_is_a_list(self):
        data = json.loads(self.DATA_PATH.read_text(encoding="utf-8"))
        for entry in data:
            cw = entry.get("compatible_weapons", [])
            assert isinstance(cw, list), (
                f"Entry {entry.get('id')!r}: compatible_weapons must be a list"
            )


# ---------------------------------------------------------------------------
# data/items.json weapon mod_slots
# ---------------------------------------------------------------------------


class TestWeaponModSlotsInItemsJson:
    """Every weapon entry in data/items.json must declare its mod_slots."""

    DATA_PATH = Path("data") / "items.json"

    def test_weapon_entries_have_mod_slots_field(self):
        raw = json.loads(self.DATA_PATH.read_text(encoding="utf-8"))
        # items.json may be a list or a dict
        if isinstance(raw, list):
            entries = raw
        elif isinstance(raw, dict) and "items" in raw:
            entries = raw["items"]
        else:
            entries = list(raw.values())

        weapons = [e for e in entries if e.get("type") == "weapon"]
        assert len(weapons) > 0, "No weapon entries found in data/items.json"
        for w in weapons:
            assert "mod_slots" in w, (
                f"Weapon {w.get('id')!r} in items.json is missing 'mod_slots'"
            )

    def test_mod_slots_values_are_valid_slot_types(self):
        valid = {"scope", "barrel", "grip", "magazine", "stock"}
        raw = json.loads(self.DATA_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            entries = raw
        elif isinstance(raw, dict) and "items" in raw:
            entries = raw["items"]
        else:
            entries = list(raw.values())

        for e in entries:
            if e.get("type") != "weapon":
                continue
            for slot in e.get("mod_slots", []):
                assert slot in valid, (
                    f"Weapon {e.get('id')!r} has invalid slot_type {slot!r}"
                )


# ---------------------------------------------------------------------------
# ItemDatabase.load_additional() merges attachments.json
# ---------------------------------------------------------------------------


class TestItemDatabaseLoadAdditional:
    """ItemDatabase must expose a load_additional() method that merges a second
    catalog file (e.g. attachments.json) into the existing item catalog without
    overwriting weapons/armor/consumables already loaded from items.json.
    """

    def test_load_additional_method_exists(self):
        db = ItemDatabase.get_instance()
        assert hasattr(db, "load_additional"), (
            "ItemDatabase must have a load_additional() method for loading "
            "data/attachments.json"
        )

    def test_load_additional_makes_attachments_available(
        self, db_weapons_only: ItemDatabase, tmp_attachments_json: Path
    ):
        db_weapons_only.load_additional(str(tmp_attachments_json))
        scope = db_weapons_only.create("tmp_scope")
        assert isinstance(scope, Attachment)

    def test_load_additional_preserves_existing_weapons(
        self, db_weapons_only: ItemDatabase, tmp_attachments_json: Path
    ):
        """Weapons loaded by load() must still be accessible after load_additional()."""
        db_weapons_only.load_additional(str(tmp_attachments_json))
        rifle = db_weapons_only.create("rifle_test")
        assert isinstance(rifle, Weapon)

    def test_attachment_from_load_additional_has_correct_slot_type(
        self, db_weapons_only: ItemDatabase, tmp_attachments_json: Path
    ):
        db_weapons_only.load_additional(str(tmp_attachments_json))
        barrel = db_weapons_only.create("tmp_barrel")
        assert barrel.slot_type == "barrel"

    def test_attachment_from_load_additional_has_correct_stat_delta(
        self, db_weapons_only: ItemDatabase, tmp_attachments_json: Path
    ):
        db_weapons_only.load_additional(str(tmp_attachments_json))
        scope = db_weapons_only.create("tmp_scope")
        assert scope.stat_delta.get("accuracy") == pytest.approx(15)
        assert scope.stat_delta.get("damage") == pytest.approx(5)

    def test_attachment_from_load_additional_has_correct_compatible_weapons(
        self, db_weapons_only: ItemDatabase, tmp_attachments_json: Path
    ):
        db_weapons_only.load_additional(str(tmp_attachments_json))
        barrel = db_weapons_only.create("tmp_barrel")
        assert "rifle_test" in barrel.compatible_weapons

    def test_load_additional_catalog_size_grows(
        self, db_weapons_only: ItemDatabase, tmp_attachments_json: Path
    ):
        count_before = len(db_weapons_only)
        db_weapons_only.load_additional(str(tmp_attachments_json))
        count_after = len(db_weapons_only)
        assert count_after == count_before + 3  # three attachment entries in tmp fixture

    def test_create_returns_deep_copy_not_shared_instance(
        self, db_weapons_only: ItemDatabase, tmp_attachments_json: Path
    ):
        """Each create() call must return an independent copy."""
        db_weapons_only.load_additional(str(tmp_attachments_json))
        a1 = db_weapons_only.create("tmp_scope")
        a2 = db_weapons_only.create("tmp_scope")
        assert a1 is not a2


# ---------------------------------------------------------------------------
# ItemDatabase graceful fallback when attachments.json is missing
# ---------------------------------------------------------------------------


class TestItemDatabaseMissingAttachmentFile:
    """load_additional() must not raise when the file doesn't exist; it should
    log a warning and leave the catalog intact.
    """

    def test_load_additional_missing_file_does_not_raise(
        self, db_weapons_only: ItemDatabase, tmp_path: Path
    ):
        nonexistent = tmp_path / "nonexistent_attachments.json"
        # Must not raise FileNotFoundError or any other exception
        try:
            db_weapons_only.load_additional(str(nonexistent))
        except FileNotFoundError:
            pytest.fail(
                "load_additional() raised FileNotFoundError on a missing file "
                "instead of silently continuing"
            )

    def test_load_additional_missing_file_preserves_existing_items(
        self, db_weapons_only: ItemDatabase, tmp_path: Path
    ):
        nonexistent = tmp_path / "nonexistent_attachments.json"
        count_before = len(db_weapons_only)
        try:
            db_weapons_only.load_additional(str(nonexistent))
        except Exception:
            pass  # we just care about catalog integrity
        assert len(db_weapons_only) == count_before


# ---------------------------------------------------------------------------
# data/attachments.json loads end-to-end via ItemDatabase
# ---------------------------------------------------------------------------


class TestAttachmentsJsonIntegration:
    """Integration: load data/attachments.json into a real ItemDatabase and
    verify Attachment instances are usable for equipping onto Weapon items.
    """

    @pytest.fixture()
    def db_with_attachments(self) -> ItemDatabase:
        """Real ItemDatabase loaded from the actual project data files."""
        db = ItemDatabase.get_instance()
        db.load("data/items.json")
        db.load_additional("data/attachments.json")
        return db

    def test_all_canonical_attachment_ids_are_accessible(
        self, db_with_attachments: ItemDatabase
    ):
        canonical_ids = [
            "barrel_extended",
            "barrel_compensator",
            "grip_angled",
            "grip_combat",
            "magazine_extended_sm",
            "magazine_extended_lg",
            "stock_folding",
            "stock_precision",
            "scope_acog",
        ]
        for aid in canonical_ids:
            item = db_with_attachments.create(aid)
            assert isinstance(item, Attachment), (
                f"Expected Attachment for id={aid!r}, got {type(item).__name__}"
            )

    def test_scope_acog_has_correct_slot_type(
        self, db_with_attachments: ItemDatabase
    ):
        scope = db_with_attachments.create("scope_acog")
        assert scope.slot_type == "scope"

    def test_barrel_extended_stat_delta_increases_damage(
        self, db_with_attachments: ItemDatabase
    ):
        barrel = db_with_attachments.create("barrel_extended")
        assert barrel.stat_delta.get("damage", 0) > 0

    def test_attachment_can_be_equipped_to_weapon_with_matching_slot(
        self, db_with_attachments: ItemDatabase
    ):
        rifle = db_with_attachments.create("rifle_vantage")
        assert isinstance(rifle, Weapon)
        scope = db_with_attachments.create("scope_acog")
        assert scope.slot_type in rifle.mod_slots
        assert rifle.attach(scope) is True

    def test_effective_stat_reflects_attachment_after_equip(
        self, db_with_attachments: ItemDatabase
    ):
        rifle = db_with_attachments.create("rifle_vantage")
        barrel = db_with_attachments.create("barrel_extended")
        base_dmg = rifle.effective_stat("damage")
        rifle.attach(barrel)
        boosted_dmg = rifle.effective_stat("damage")
        delta = barrel.stat_delta.get("damage", 0)
        assert boosted_dmg == pytest.approx(base_dmg + delta)


# ---------------------------------------------------------------------------
# data/enemies.json loot tables contain attachment IDs
# ---------------------------------------------------------------------------


class TestEnemyLootTablesHaveAttachments:
    """After the feature is implemented, at least one loot table in
    data/enemies.json must include an attachment item_id entry so that
    players can find attachments as loot drops.
    """

    ENEMIES_PATH = Path("data") / "enemies.json"

    def _all_loot_entry_ids(self) -> set[str]:
        data = json.loads(self.ENEMIES_PATH.read_text(encoding="utf-8"))
        ids: set[str] = set()
        for _table_name, table in data.get("loot_tables", {}).items():
            for entry in table.get("entries", []):
                ids.add(entry.get("item_id", ""))
        return ids

    def _attachment_ids_in_data(self) -> set[str]:
        att_path = Path("data") / "attachments.json"
        data = json.loads(att_path.read_text(encoding="utf-8"))
        return {entry["id"] for entry in data}

    def test_at_least_one_attachment_in_loot_tables(self):
        """At least one loot entry must reference a known attachment ID."""
        loot_ids = self._all_loot_entry_ids()
        attachment_ids = self._attachment_ids_in_data()
        overlap = loot_ids & attachment_ids
        assert overlap, (
            "No attachment IDs found in any loot table in data/enemies.json. "
            f"Known attachment IDs: {sorted(attachment_ids)}. "
            f"Current loot entry IDs: {sorted(loot_ids)}"
        )

    def test_grunt_drops_contains_an_attachment(self):
        """The grunt_drops table is the most common source, so it must have at
        least one attachment entry for players to find attachments early.
        """
        data = json.loads(self.ENEMIES_PATH.read_text(encoding="utf-8"))
        grunt_entries = {
            e["item_id"]
            for e in data.get("loot_tables", {})
            .get("grunt_drops", {})
            .get("entries", [])
        }
        attachment_ids = self._attachment_ids_in_data()
        assert grunt_entries & attachment_ids, (
            "grunt_drops loot table contains no attachment items. "
            "Add at least one attachment (e.g. grip_angled) with a low weight."
        )
