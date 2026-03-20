"""Tests for save/load persistence of weapon attachments.

Validates:
  - weapon_to_save_dict() produces a complete, JSON-safe representation that
    includes equipped attachment data
  - weapon_from_save_dict() correctly restores Attachment instances from the
    persisted dict, both with and without an item_factory
  - Effective stats are preserved through a full weapon_to_save_dict /
    weapon_from_save_dict / re-equip round-trip
  - SaveManager.save() persists weapon attachment data when writing inventory
  - SaveManager.load() / restore() rebuilds a weapon with its attachments
    intact so effective stats are correct after reload

# Run: pytest tests/test_attachment_save_load.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.inventory.item import Attachment, Rarity, Weapon, make_item
from src.inventory.inventory import Inventory
from src.inventory.weapon_attachments import (
    attach_to_weapon,
    weapon_from_save_dict,
    weapon_to_save_dict,
)
from src.save.save_manager import SaveManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weapon(
    wid: str = "rifle_01",
    mod_slots: list[str] | None = None,
    damage: int = 30,
    fire_rate: float = 4.0,
    magazine_size: int = 20,
) -> Weapon:
    return Weapon(
        id=wid,
        name="Test Rifle",
        rarity=Rarity.COMMON,
        weight=3.0,
        base_value=200,
        stats={"range": 450, "reload_time": 2.0, "accuracy": 70},
        sprite_path="",
        damage=damage,
        fire_rate=fire_rate,
        magazine_size=magazine_size,
        mod_slots=mod_slots if mod_slots is not None else ["scope", "barrel", "grip"],
    )


def _attachment(
    aid: str = "scope_01",
    slot_type: str = "scope",
    stat_delta: dict | None = None,
    compatible_weapons: list[str] | None = None,
    rarity: Rarity = Rarity.UNCOMMON,
) -> Attachment:
    return Attachment(
        id=aid,
        name="Test Scope",
        rarity=rarity,
        weight=0.3,
        base_value=80,
        stats={},
        sprite_path="",
        slot_type=slot_type,
        compatible_weapons=compatible_weapons or [],
        stat_delta=stat_delta or {"accuracy": 10},
    )


# ---------------------------------------------------------------------------
# weapon_to_save_dict() — structure and completeness
# ---------------------------------------------------------------------------


class TestWeaponToSaveDict:
    """weapon_to_save_dict() must produce a complete, JSON-serialisable structure."""

    def test_produces_dict_with_item_id(self):
        w = _weapon(wid="rifle_01")
        data = weapon_to_save_dict(w)
        assert data["item_id"] == "rifle_01"

    def test_produces_dict_with_mod_slots(self):
        w = _weapon(mod_slots=["scope", "barrel"])
        data = weapon_to_save_dict(w)
        assert data["mod_slots"] == ["scope", "barrel"]

    def test_attachments_key_is_empty_dict_when_no_mods_equipped(self):
        w = _weapon()
        data = weapon_to_save_dict(w)
        assert data["attachments"] == {}

    def test_equipped_attachment_appears_in_attachments_dict(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(aid="scope_01", slot_type="scope", stat_delta={"accuracy": 15})
        w.attach(att)
        data = weapon_to_save_dict(w)
        assert "scope" in data["attachments"]

    def test_attachment_entry_has_item_id(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(aid="scope_acog", slot_type="scope")
        w.attach(att)
        data = weapon_to_save_dict(w)
        assert data["attachments"]["scope"]["item_id"] == "scope_acog"

    def test_attachment_entry_has_stat_delta(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"accuracy": 15, "damage": 5})
        w.attach(att)
        data = weapon_to_save_dict(w)
        delta = data["attachments"]["scope"]["stat_delta"]
        assert delta["accuracy"] == pytest.approx(15)
        assert delta["damage"] == pytest.approx(5)

    def test_attachment_entry_has_slot_type(self):
        w = _weapon(mod_slots=["barrel"])
        att = _attachment(slot_type="barrel", stat_delta={"damage": 4})
        w.attach(att)
        data = weapon_to_save_dict(w)
        assert data["attachments"]["barrel"]["slot_type"] == "barrel"

    def test_multiple_attachments_all_serialised(self):
        w = _weapon(mod_slots=["scope", "barrel", "grip"])
        w.attach(_attachment(aid="s", slot_type="scope", stat_delta={"accuracy": 10}))
        w.attach(_attachment(aid="b", slot_type="barrel", stat_delta={"damage": -3}))
        w.attach(_attachment(aid="g", slot_type="grip", stat_delta={"fire_rate": 0.5}))
        data = weapon_to_save_dict(w)
        assert len(data["attachments"]) == 3

    def test_save_dict_is_json_serialisable(self):
        w = _weapon(mod_slots=["scope"])
        w.attach(_attachment(slot_type="scope", stat_delta={"accuracy": 15}))
        data = weapon_to_save_dict(w)
        serialised = json.dumps(data)
        assert isinstance(serialised, str)


# ---------------------------------------------------------------------------
# weapon_from_save_dict() — restoring attachments
# ---------------------------------------------------------------------------


class TestWeaponFromSaveDict:
    """weapon_from_save_dict() must restore the correct Attachment instances."""

    def test_empty_attachments_returns_empty_dict(self):
        data: dict[str, Any] = {
            "item_id": "rifle_01",
            "mod_slots": ["scope"],
            "attachments": {},
        }
        restored = weapon_from_save_dict(data)
        assert restored == {}

    def test_restores_single_attachment_instance(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(aid="scope_01", slot_type="scope", stat_delta={"accuracy": 15})
        w.attach(att)
        data = weapon_to_save_dict(w)
        restored = weapon_from_save_dict(data)
        assert "scope" in restored
        assert isinstance(restored["scope"], Attachment)

    def test_restored_attachment_has_correct_slot_type(self):
        w = _weapon(mod_slots=["barrel"])
        att = _attachment(slot_type="barrel", stat_delta={"damage": 4})
        w.attach(att)
        data = weapon_to_save_dict(w)
        restored = weapon_from_save_dict(data)
        assert restored["barrel"].slot_type == "barrel"

    def test_restored_attachment_preserves_stat_delta(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(
            slot_type="scope",
            stat_delta={"accuracy": 20, "damage": 8, "range": 50},
        )
        w.attach(att)
        data = weapon_to_save_dict(w)
        restored = weapon_from_save_dict(data)
        delta = restored["scope"].stat_delta
        assert delta.get("accuracy") == pytest.approx(20)
        assert delta.get("damage") == pytest.approx(8)
        assert delta.get("range") == pytest.approx(50)

    def test_round_trip_preserves_all_slot_attachments(self):
        w = _weapon(mod_slots=["scope", "barrel", "grip"])
        w.attach(_attachment(aid="s", slot_type="scope", stat_delta={"accuracy": 10}))
        w.attach(_attachment(aid="b", slot_type="barrel", stat_delta={"damage": -5}))
        w.attach(_attachment(aid="g", slot_type="grip", stat_delta={"fire_rate": 0.8}))
        data = weapon_to_save_dict(w)
        restored = weapon_from_save_dict(data)
        assert set(restored.keys()) == {"scope", "barrel", "grip"}

    def test_uses_item_factory_when_provided(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(
            aid="scope_premium", slot_type="scope", stat_delta={"accuracy": 25}
        )
        w.attach(att)
        data = weapon_to_save_dict(w)

        factory_calls: list[str] = []

        def factory(item_id: str) -> Attachment:
            factory_calls.append(item_id)
            return _attachment(aid=item_id, slot_type="scope", stat_delta={"accuracy": 25})

        restored = weapon_from_save_dict(data, item_factory=factory)
        assert "scope_premium" in factory_calls
        assert "scope" in restored

    def test_falls_back_to_inline_data_when_factory_fails(self):
        """If the factory raises, weapon_from_save_dict must fall back to inline data."""
        w = _weapon(mod_slots=["barrel"])
        att = _attachment(slot_type="barrel", stat_delta={"damage": 3})
        w.attach(att)
        data = weapon_to_save_dict(w)

        def failing_factory(item_id: str):
            raise KeyError(f"Unknown: {item_id}")

        restored = weapon_from_save_dict(data, item_factory=failing_factory)
        assert "barrel" in restored  # falls back to inline

    def test_re_equipping_restored_attachments_applies_effective_stat(self):
        """After restoring attachments from save data, equipping them onto a
        fresh weapon object must produce the correct effective_stat result.
        """
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        data = weapon_to_save_dict(w)

        fresh_weapon = _weapon(damage=30, mod_slots=["scope"])
        restored_atts = weapon_from_save_dict(data)
        for slot, restored_att in restored_atts.items():
            fresh_weapon.attach(restored_att, slot_type=slot)

        assert fresh_weapon.effective_stat("damage") == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# SaveManager integration — attached weapons survive save/load cycle
# ---------------------------------------------------------------------------


class TestSaveManagerWeaponAttachments:
    """SaveManager.save() + SaveManager.load() must preserve weapon attachment
    data so that effective stats are correct after reloading a save file.

    These tests will fail until SaveManager._build_state_dict() (or
    Inventory.to_save_list()) is updated to use weapon_to_save_dict() for
    Weapon items that have attachments.
    """

    @pytest.fixture()
    def save_path(self, tmp_path: Path) -> Path:
        return tmp_path / "saves" / "save.json"

    @pytest.fixture()
    def manager(self, save_path: Path) -> SaveManager:
        return SaveManager(save_path=save_path)

    def test_saved_state_contains_weapon_with_attachments_key(
        self, manager: SaveManager, save_path: Path
    ):
        """The raw save JSON for a weapon item must contain an 'attachments' key."""
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"accuracy": 15})
        w.attach(att)

        state = {
            "version": 1,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [weapon_to_save_dict(w)],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        }
        manager.save(state)

        raw = json.loads(save_path.read_text(encoding="utf-8"))
        weapon_entries = [
            e for e in raw.get("inventory", []) if e.get("item_id") == "rifle_01"
        ]
        assert weapon_entries, "Weapon entry not found in saved inventory"
        assert "attachments" in weapon_entries[0], (
            "Saved weapon entry is missing 'attachments' key — "
            "use weapon_to_save_dict() when serialising equipped weapons"
        )

    def test_attachment_stat_delta_survives_save_and_load(
        self, manager: SaveManager, save_path: Path
    ):
        """stat_delta of equipped attachments must be intact after load()."""
        w = _weapon(mod_slots=["barrel"])
        att = _attachment(slot_type="barrel", stat_delta={"damage": 7})
        w.attach(att)

        state = {
            "version": 1,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [weapon_to_save_dict(w)],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        }
        manager.save(state)
        loaded = manager.load()

        weapon_entry = next(
            (e for e in loaded.get("inventory", []) if e.get("item_id") == "rifle_01"),
            None,
        )
        assert weapon_entry is not None, "Weapon entry not found after load"
        barrel_att = weapon_entry.get("attachments", {}).get("barrel", {})
        assert barrel_att.get("stat_delta", {}).get("damage") == pytest.approx(7)

    def test_missing_save_file_returns_new_game_state_without_crash(
        self, tmp_path: Path
    ):
        """SaveManager must silently fall back to new-game state when the save
        file is missing — this is unchanged behaviour but must still work with
        the attachment feature enabled.
        """
        sm = SaveManager(save_path=tmp_path / "nonexistent.json")
        state = sm.load()
        assert "inventory" in state
        assert isinstance(state["inventory"], list)

    def test_corrupt_attachment_data_does_not_prevent_loading(
        self, manager: SaveManager
    ):
        """Corrupt/missing attachment data in the save file must not crash
        load() — the weapon loads with no attachments rather than raising.
        """
        corrupt_state = {
            "version": 1,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [
                {
                    "item_id": "rifle_01",
                    "item_type": "weapon",
                    "name": "Test Rifle",
                    "rarity": "common",
                    "value": 200,
                    "weight": 3.0,
                    "sprite": "",
                    "stats": {},
                    "quantity": 1,
                    "attachments": "NOT_A_DICT",  # intentionally corrupt
                }
            ],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        }
        manager.save(corrupt_state)
        # Must not raise
        loaded = manager.load()
        assert isinstance(loaded, dict)

    def test_inventory_restore_preserves_attachment_effective_stats(
        self, manager: SaveManager, save_path: Path
    ):
        """After a save/restore cycle through SaveManager.restore(), the weapon
        in the restored inventory must have its attachment effective stats intact.

        This test requires SaveManager to rebuild Weapon objects with
        weapon_from_save_dict() during restore().
        """
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 12})
        w.attach(att)

        # Manually build the save state using the proper serialiser
        state = {
            "version": 1,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [weapon_to_save_dict(w)],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        }
        manager.save(state)

        inv = Inventory(max_slots=10, max_weight=50.0)
        manager.restore(inventory=inv)

        weapons = [item for item in inv if isinstance(item, Weapon)]
        assert weapons, "No Weapon found in restored inventory"
        restored_weapon = weapons[0]

        # After restoring, the effective damage must include the attachment bonus
        assert restored_weapon.effective_stat("damage") == pytest.approx(42.0)
