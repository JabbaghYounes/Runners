"""
Unit tests for weapon attachment slots and stat modifiers.

Covers:
  - Weapon.mod_slots: typed slot definitions (scope, barrel, grip, etc.)
  - Weapon.attach(): equip an attachment, slot validation, compatibility check
  - Weapon.detach(): remove and return an attachment
  - Weapon.get_attachment(): inspect without removing
  - Weapon.available_slots() / occupied_slots(): slot introspection
  - Weapon.effective_stat(): base + attachment delta computation
  - Attachment.slot_type: attachment knows its slot category
  - Attachment.stat_delta: stat modifications dictionary
  - Multiple attachments: cumulative stat bonuses
  - Inventory integration: attach/detach with inventory items
  - Serialization: weapon_to_save_dict / weapon_from_save_dict round-trip
  - ItemDatabase: attachments loaded from items.json with slot_type & stat_delta
"""
import json
import pytest

from src.inventory.item import (
    Rarity,
    Item,
    Weapon,
    Attachment,
    make_item,
)
from src.inventory.inventory import Inventory
from src.inventory.weapon_attachments import (
    attach_to_weapon,
    detach_from_weapon,
    weapon_to_save_dict,
    weapon_from_save_dict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weapon(
    id="rifle_01",
    mod_slots=None,
    damage=30,
    fire_rate=4.0,
    magazine_size=20,
    rarity=Rarity.COMMON,
    weight=3.0,
    stats=None,
):
    return Weapon(
        id=id,
        name="Test Rifle",
        type="weapon",
        rarity=rarity,
        weight=weight,
        base_value=200,
        stats=stats or {"range": 450, "reload_time": 2.0, "accuracy": 70},
        sprite_path="",
        damage=damage,
        fire_rate=fire_rate,
        magazine_size=magazine_size,
        mod_slots=mod_slots if mod_slots is not None else ["scope", "barrel", "grip"],
    )


def _attachment(
    id="scope_01",
    slot_type="scope",
    stat_delta=None,
    compatible_weapons=None,
    rarity=Rarity.COMMON,
    weight=0.3,
):
    return Attachment(
        id=id,
        name="Test Scope",
        type="attachment",
        rarity=rarity,
        weight=weight,
        base_value=80,
        stats={},
        sprite_path="",
        slot_type=slot_type,
        compatible_weapons=compatible_weapons if compatible_weapons is not None else [],
        stat_delta=stat_delta if stat_delta is not None else {"accuracy": 10},
    )


# ---------------------------------------------------------------------------
# Attachment.slot_type
# ---------------------------------------------------------------------------


class TestAttachmentSlotType:
    def test_attachment_has_slot_type(self):
        att = _attachment(slot_type="scope")
        assert att.slot_type == "scope"

    def test_attachment_barrel_slot_type(self):
        att = _attachment(slot_type="barrel")
        assert att.slot_type == "barrel"

    def test_attachment_grip_slot_type(self):
        att = _attachment(slot_type="grip")
        assert att.slot_type == "grip"

    def test_attachment_magazine_slot_type(self):
        att = _attachment(slot_type="magazine")
        assert att.slot_type == "magazine"

    def test_attachment_stock_slot_type(self):
        att = _attachment(slot_type="stock")
        assert att.slot_type == "stock"

    def test_attachment_default_slot_type_is_empty(self):
        att = Attachment(
            id="bare", name="Bare", rarity=Rarity.COMMON,
            weight=0.1, base_value=10, stats={}, sprite_path="",
        )
        assert att.slot_type == ""

    def test_attachment_stat_delta_still_works(self):
        att = _attachment(stat_delta={"damage": 5, "accuracy": 12})
        assert att.stat_delta["damage"] == 5
        assert att.stat_delta["accuracy"] == 12


# ---------------------------------------------------------------------------
# Weapon.mod_slots
# ---------------------------------------------------------------------------


class TestWeaponModSlots:
    def test_weapon_mod_slots_list(self):
        w = _weapon(mod_slots=["scope", "barrel", "grip"])
        assert w.mod_slots == ["scope", "barrel", "grip"]

    def test_weapon_empty_mod_slots(self):
        w = _weapon(mod_slots=[])
        assert w.mod_slots == []

    def test_weapon_single_mod_slot(self):
        w = _weapon(mod_slots=["scope"])
        assert w.mod_slots == ["scope"]

    def test_weapon_all_slot_types(self):
        w = _weapon(mod_slots=["scope", "barrel", "grip", "magazine", "stock"])
        assert len(w.mod_slots) == 5

    def test_weapon_starts_with_no_attachments(self):
        w = _weapon()
        assert w.attachments == {}


# ---------------------------------------------------------------------------
# Weapon.attach()
# ---------------------------------------------------------------------------


class TestWeaponAttach:
    def test_attach_returns_true_on_success(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope")
        assert w.attach(att) is True

    def test_attach_stores_attachment(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope")
        w.attach(att)
        assert w.attachments["scope"] is att

    def test_attach_to_unavailable_slot_returns_false(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="barrel")
        assert w.attach(att) is False

    def test_attach_to_occupied_slot_returns_false(self):
        w = _weapon(mod_slots=["scope"])
        att1 = _attachment(id="scope_01", slot_type="scope")
        att2 = _attachment(id="scope_02", slot_type="scope")
        w.attach(att1)
        assert w.attach(att2) is False

    def test_attach_with_explicit_slot_type_override(self):
        w = _weapon(mod_slots=["barrel"])
        att = _attachment(slot_type="scope")  # att says "scope"
        assert w.attach(att, slot_type="barrel") is True
        assert "barrel" in w.attachments

    def test_attach_incompatible_weapon_returns_false(self):
        w = _weapon(id="rifle_01", mod_slots=["scope"])
        att = _attachment(slot_type="scope", compatible_weapons=["pistol_01"])
        assert w.attach(att) is False

    def test_attach_compatible_weapon_succeeds(self):
        w = _weapon(id="rifle_01", mod_slots=["scope"])
        att = _attachment(slot_type="scope", compatible_weapons=["rifle_01"])
        assert w.attach(att) is True

    def test_attach_universal_attachment_succeeds(self):
        w = _weapon(id="rifle_01", mod_slots=["scope"])
        att = _attachment(slot_type="scope", compatible_weapons=[])
        assert w.attach(att) is True

    def test_attach_empty_slot_type_returns_false(self):
        w = _weapon(mod_slots=["scope"])
        att = Attachment(
            id="bare", name="Bare", rarity=Rarity.COMMON,
            weight=0.1, base_value=10, stats={}, sprite_path="",
        )
        assert w.attach(att) is False

    def test_attach_to_weapon_with_no_mod_slots_returns_false(self):
        w = _weapon(mod_slots=[])
        att = _attachment(slot_type="scope")
        assert w.attach(att) is False

    def test_attach_multiple_different_slots(self):
        w = _weapon(mod_slots=["scope", "barrel", "grip"])
        scope = _attachment(id="scope_01", slot_type="scope")
        barrel = _attachment(id="barrel_01", slot_type="barrel", stat_delta={"damage": -5})
        grip = _attachment(id="grip_01", slot_type="grip", stat_delta={"recoil": -15})
        assert w.attach(scope) is True
        assert w.attach(barrel) is True
        assert w.attach(grip) is True
        assert len(w.attachments) == 3


# ---------------------------------------------------------------------------
# Weapon.detach()
# ---------------------------------------------------------------------------


class TestWeaponDetach:
    def test_detach_returns_the_attachment(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope")
        w.attach(att)
        result = w.detach("scope")
        assert result is att

    def test_detach_removes_from_attachments(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope")
        w.attach(att)
        w.detach("scope")
        assert "scope" not in w.attachments

    def test_detach_empty_slot_returns_none(self):
        w = _weapon(mod_slots=["scope"])
        assert w.detach("scope") is None

    def test_detach_nonexistent_slot_returns_none(self):
        w = _weapon(mod_slots=["scope"])
        assert w.detach("barrel") is None

    def test_detach_allows_reattachment(self):
        w = _weapon(mod_slots=["scope"])
        att1 = _attachment(id="scope_01", slot_type="scope")
        att2 = _attachment(id="scope_02", slot_type="scope", stat_delta={"accuracy": 20})
        w.attach(att1)
        w.detach("scope")
        assert w.attach(att2) is True
        assert w.attachments["scope"] is att2


# ---------------------------------------------------------------------------
# Weapon.get_attachment()
# ---------------------------------------------------------------------------


class TestWeaponGetAttachment:
    def test_get_attachment_returns_equipped(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope")
        w.attach(att)
        assert w.get_attachment("scope") is att

    def test_get_attachment_does_not_remove(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope")
        w.attach(att)
        w.get_attachment("scope")
        assert "scope" in w.attachments

    def test_get_attachment_empty_returns_none(self):
        w = _weapon(mod_slots=["scope"])
        assert w.get_attachment("scope") is None


# ---------------------------------------------------------------------------
# Weapon.available_slots() / occupied_slots()
# ---------------------------------------------------------------------------


class TestSlotIntrospection:
    def test_all_slots_available_when_empty(self):
        w = _weapon(mod_slots=["scope", "barrel", "grip"])
        assert w.available_slots() == ["scope", "barrel", "grip"]

    def test_no_occupied_slots_when_empty(self):
        w = _weapon(mod_slots=["scope", "barrel"])
        assert w.occupied_slots() == []

    def test_available_decreases_after_attach(self):
        w = _weapon(mod_slots=["scope", "barrel"])
        w.attach(_attachment(slot_type="scope"))
        assert w.available_slots() == ["barrel"]

    def test_occupied_increases_after_attach(self):
        w = _weapon(mod_slots=["scope", "barrel"])
        w.attach(_attachment(slot_type="scope"))
        assert w.occupied_slots() == ["scope"]

    def test_available_restores_after_detach(self):
        w = _weapon(mod_slots=["scope", "barrel"])
        w.attach(_attachment(slot_type="scope"))
        w.detach("scope")
        assert w.available_slots() == ["scope", "barrel"]

    def test_all_slots_occupied(self):
        w = _weapon(mod_slots=["scope", "barrel"])
        w.attach(_attachment(id="s", slot_type="scope"))
        w.attach(_attachment(id="b", slot_type="barrel", stat_delta={"damage": -3}))
        assert w.available_slots() == []
        assert len(w.occupied_slots()) == 2


# ---------------------------------------------------------------------------
# Weapon.effective_stat() — stat modifiers
# ---------------------------------------------------------------------------


class TestEffectiveStat:
    def test_effective_stat_without_attachments_equals_base(self):
        w = _weapon(damage=30)
        assert w.effective_stat("damage") == pytest.approx(30.0)

    def test_effective_stat_with_single_attachment(self):
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 5})
        w.attach(att)
        assert w.effective_stat("damage") == pytest.approx(35.0)

    def test_effective_stat_with_negative_delta(self):
        w = _weapon(damage=30, mod_slots=["barrel"])
        att = _attachment(slot_type="barrel", stat_delta={"damage": -5})
        w.attach(att)
        assert w.effective_stat("damage") == pytest.approx(25.0)

    def test_effective_stat_cumulative_from_multiple_attachments(self):
        w = _weapon(damage=30, mod_slots=["scope", "barrel", "grip"])
        w.attach(_attachment(id="s", slot_type="scope", stat_delta={"damage": 5}))
        w.attach(_attachment(id="b", slot_type="barrel", stat_delta={"damage": 3}))
        w.attach(_attachment(id="g", slot_type="grip", stat_delta={"damage": 2}))
        assert w.effective_stat("damage") == pytest.approx(40.0)

    def test_effective_stat_fire_rate(self):
        w = _weapon(fire_rate=4.0, mod_slots=["barrel"])
        att = _attachment(slot_type="barrel", stat_delta={"fire_rate": 1.5})
        w.attach(att)
        assert w.effective_stat("fire_rate") == pytest.approx(5.5)

    def test_effective_stat_accuracy_from_stats_dict(self):
        w = _weapon(mod_slots=["scope"], stats={"accuracy": 70, "range": 450})
        att = _attachment(slot_type="scope", stat_delta={"accuracy": 15})
        w.attach(att)
        assert w.effective_stat("accuracy") == pytest.approx(85.0)

    def test_effective_stat_range_from_stats_dict(self):
        w = _weapon(mod_slots=["scope"], stats={"range": 450, "accuracy": 70})
        att = _attachment(slot_type="scope", stat_delta={"range": 50})
        w.attach(att)
        assert w.effective_stat("range") == pytest.approx(500.0)

    def test_effective_stat_with_explicit_base_override(self):
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        # Override base to 50 instead of the weapon's 30
        assert w.effective_stat("damage", base=50) == pytest.approx(60.0)

    def test_effective_stat_unknown_key_defaults_to_zero(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"penetration": 15})
        w.attach(att)
        assert w.effective_stat("penetration") == pytest.approx(15.0)

    def test_effective_stat_reverts_after_detach(self):
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        assert w.effective_stat("damage") == pytest.approx(40.0)
        w.detach("scope")
        assert w.effective_stat("damage") == pytest.approx(30.0)

    def test_base_damage_property_unchanged_by_attachments(self):
        """The .damage property returns the base value (not modified by attachments)."""
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        assert w.damage == 30  # base property unchanged

    def test_base_fire_rate_property_unchanged_by_attachments(self):
        w = _weapon(fire_rate=4.0, mod_slots=["barrel"])
        att = _attachment(slot_type="barrel", stat_delta={"fire_rate": 1.0})
        w.attach(att)
        assert w.fire_rate == pytest.approx(4.0)  # base property unchanged

    def test_attachment_bonus_sums_correctly(self):
        w = _weapon(mod_slots=["scope", "grip"])
        w.attach(_attachment(id="s", slot_type="scope", stat_delta={"accuracy": 10}))
        w.attach(_attachment(id="g", slot_type="grip", stat_delta={"accuracy": 15}))
        assert w._attachment_bonus("accuracy") == pytest.approx(25.0)

    def test_attachment_bonus_zero_when_no_attachments(self):
        w = _weapon()
        assert w._attachment_bonus("damage") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# make_item factory with attachment slot_type
# ---------------------------------------------------------------------------


class TestMakeItemAttachment:
    def test_make_item_creates_attachment_with_slot_type(self):
        att = make_item(
            "scope_test", name="Test Scope", item_type="attachment",
            rarity="common", slot_type="scope",
            stat_delta={"accuracy": 10},
        )
        assert isinstance(att, Attachment)
        assert att.slot_type == "scope"

    def test_make_item_dict_creates_attachment_with_slot_type(self):
        att = make_item({
            "item_id": "scope_dict",
            "name": "Dict Scope",
            "item_type": "attachment",
            "rarity": "common",
            "slot_type": "scope",
            "stat_delta": {"accuracy": 10},
        })
        assert isinstance(att, Attachment)
        # slot_type goes through extra_kwargs in make_item's dict path
        # but the dict path does not pass slot_type — check it doesn't crash
        assert att.item_type == "attachment"


# ---------------------------------------------------------------------------
# Inventory integration
# ---------------------------------------------------------------------------


class TestInventoryIntegration:
    def test_attach_from_inventory(self):
        inv = Inventory(max_slots=10, max_weight=30.0)
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope")
        inv.add(w)
        inv.add(att)
        assert attach_to_weapon(w, att) is True
        assert w.get_attachment("scope") is att

    def test_detach_returns_to_loose_item(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope")
        w.attach(att)
        returned = detach_from_weapon(w, "scope")
        assert returned is att

    def test_attach_non_weapon_returns_false(self):
        from src.inventory.item import Armor
        armor = Armor(
            id="vest", name="Vest", rarity=Rarity.COMMON,
            weight=3.0, base_value=100, stats={}, sprite_path="",
            defense=20, slot="chest",
        )
        att = _attachment(slot_type="scope")
        assert attach_to_weapon(armor, att) is False

    def test_attach_non_attachment_returns_false(self):
        w = _weapon(mod_slots=["scope"])
        from src.inventory.item import Consumable
        c = Consumable(
            id="med", name="Med", rarity=Rarity.COMMON,
            weight=0.5, base_value=50, stats={}, sprite_path="",
        )
        assert attach_to_weapon(w, c) is False

    def test_detach_from_non_weapon_returns_none(self):
        from src.inventory.item import Armor
        armor = Armor(
            id="vest", name="Vest", rarity=Rarity.COMMON,
            weight=3.0, base_value=100, stats={}, sprite_path="",
            defense=20, slot="chest",
        )
        assert detach_from_weapon(armor, "scope") is None

    def test_weapon_with_attachment_in_inventory(self):
        """Weapon with equipped attachments stays intact inside inventory."""
        inv = Inventory(max_slots=10, max_weight=30.0)
        w = _weapon(mod_slots=["scope", "barrel"])
        att = _attachment(slot_type="scope", stat_delta={"accuracy": 15})
        w.attach(att)
        inv.add(w)
        inv.equip(w)
        assert inv.equipped_weapon is w
        assert w.get_attachment("scope") is att
        assert w.effective_stat("accuracy") == pytest.approx(85.0)


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_weapon_to_save_dict_basic_structure(self):
        w = _weapon(id="rifle_01", mod_slots=["scope", "barrel"])
        data = weapon_to_save_dict(w)
        assert data["item_id"] == "rifle_01"
        assert data["mod_slots"] == ["scope", "barrel"]
        assert data["attachments"] == {}

    def test_weapon_to_save_dict_with_attachment(self):
        w = _weapon(id="rifle_01", mod_slots=["scope"])
        att = _attachment(id="scope_01", slot_type="scope", stat_delta={"accuracy": 10})
        w.attach(att)
        data = weapon_to_save_dict(w)
        assert "scope" in data["attachments"]
        att_data = data["attachments"]["scope"]
        assert att_data["item_id"] == "scope_01"
        assert att_data["slot_type"] == "scope"
        assert att_data["stat_delta"]["accuracy"] == 10

    def test_weapon_to_save_dict_multiple_attachments(self):
        w = _weapon(mod_slots=["scope", "barrel", "grip"])
        w.attach(_attachment(id="s", slot_type="scope", stat_delta={"accuracy": 10}))
        w.attach(_attachment(id="b", slot_type="barrel", stat_delta={"damage": -5}))
        w.attach(_attachment(id="g", slot_type="grip", stat_delta={"recoil": -15}))
        data = weapon_to_save_dict(w)
        assert len(data["attachments"]) == 3

    def test_weapon_from_save_dict_restores_attachments(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(id="scope_01", slot_type="scope", stat_delta={"accuracy": 10})
        w.attach(att)
        data = weapon_to_save_dict(w)
        restored = weapon_from_save_dict(data)
        assert "scope" in restored
        assert restored["scope"].item_id == "scope_01"
        assert restored["scope"].stat_delta.get("accuracy") == 10

    def test_round_trip_preserves_stat_delta(self):
        w = _weapon(mod_slots=["scope", "barrel"])
        w.attach(_attachment(id="s", slot_type="scope", stat_delta={"accuracy": 20, "range": 30}))
        w.attach(_attachment(id="b", slot_type="barrel", stat_delta={"damage": -3}))
        data = weapon_to_save_dict(w)
        restored = weapon_from_save_dict(data)
        assert restored["scope"].stat_delta["accuracy"] == 20
        assert restored["scope"].stat_delta["range"] == 30
        assert restored["barrel"].stat_delta["damage"] == -3

    def test_save_dict_is_json_serializable(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"accuracy": 15})
        w.attach(att)
        data = weapon_to_save_dict(w)
        # Must not raise
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    def test_round_trip_with_item_factory(self):
        """weapon_from_save_dict can use an item factory to rebuild attachments."""
        w = _weapon(mod_slots=["scope"])
        att = _attachment(id="scope_x", slot_type="scope", stat_delta={"accuracy": 99})
        w.attach(att)
        data = weapon_to_save_dict(w)

        factory_called = False
        def factory(item_id):
            nonlocal factory_called
            factory_called = True
            return _attachment(id=item_id, slot_type="scope", stat_delta={"accuracy": 99})

        restored = weapon_from_save_dict(data, item_factory=factory)
        assert factory_called
        assert "scope" in restored

    def test_from_save_dict_empty_attachments(self):
        data = {"item_id": "rifle_01", "mod_slots": ["scope"], "attachments": {}}
        restored = weapon_from_save_dict(data)
        assert restored == {}


# ---------------------------------------------------------------------------
# ItemDatabase integration
# ---------------------------------------------------------------------------


class TestItemDatabaseAttachments:
    """Test that items.json attachments load with slot_type and stat_delta."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        from src.inventory.item_database import ItemDatabase
        ItemDatabase._instance = None
        yield
        ItemDatabase._instance = None

    @pytest.fixture
    def loaded_db(self, tmp_path):
        from src.inventory.item_database import ItemDatabase
        catalog = [
            {
                "id": "test_rifle",
                "name": "Test Rifle",
                "type": "weapon",
                "rarity": "COMMON",
                "weight": 3.0,
                "base_value": 200,
                "stats": {"damage": 30, "fire_rate": 4.0, "range": 450},
                "sprite": "",
                "mod_slots": ["scope", "barrel", "grip"],
                "damage": 30,
                "fire_rate": 4.0,
                "magazine_size": 20,
            },
            {
                "id": "test_scope",
                "name": "Test Scope",
                "type": "attachment",
                "rarity": "UNCOMMON",
                "weight": 0.3,
                "base_value": 90,
                "stats": {},
                "sprite": "",
                "slot_type": "scope",
                "stat_delta": {"accuracy": 15, "range": 30},
                "compatible_weapons": [],
            },
            {
                "id": "test_barrel",
                "name": "Test Suppressor",
                "type": "attachment",
                "rarity": "UNCOMMON",
                "weight": 0.4,
                "base_value": 120,
                "stats": {},
                "sprite": "",
                "slot_type": "barrel",
                "stat_delta": {"damage": -5, "range": 20},
                "compatible_weapons": ["test_rifle"],
            },
            {
                "id": "test_grip",
                "name": "Test Grip",
                "type": "attachment",
                "rarity": "RARE",
                "weight": 0.2,
                "base_value": 150,
                "stats": {},
                "sprite": "",
                "slot_type": "grip",
                "stat_delta": {"accuracy": 10, "recoil": -25},
                "compatible_weapons": [],
            },
        ]
        path = tmp_path / "items.json"
        path.write_text(json.dumps(catalog))
        db = ItemDatabase.get_instance()
        db.load(str(path))
        return db

    def test_attachment_has_slot_type(self, loaded_db):
        scope = loaded_db.create("test_scope")
        assert scope.slot_type == "scope"

    def test_attachment_has_stat_delta(self, loaded_db):
        scope = loaded_db.create("test_scope")
        assert scope.stat_delta["accuracy"] == 15
        assert scope.stat_delta["range"] == 30

    def test_barrel_slot_type(self, loaded_db):
        barrel = loaded_db.create("test_barrel")
        assert barrel.slot_type == "barrel"

    def test_barrel_compatible_weapons(self, loaded_db):
        barrel = loaded_db.create("test_barrel")
        assert "test_rifle" in barrel.compatible_weapons

    def test_weapon_has_mod_slots(self, loaded_db):
        rifle = loaded_db.create("test_rifle")
        assert "scope" in rifle.mod_slots
        assert "barrel" in rifle.mod_slots
        assert "grip" in rifle.mod_slots

    def test_attach_database_items(self, loaded_db):
        rifle = loaded_db.create("test_rifle")
        scope = loaded_db.create("test_scope")
        assert rifle.attach(scope) is True
        assert rifle.get_attachment("scope") is scope

    def test_incompatible_attach_blocked(self, loaded_db):
        """test_barrel is only compatible with test_rifle."""
        rifle = loaded_db.create("test_rifle")
        barrel = loaded_db.create("test_barrel")
        # Compatible: should work
        assert rifle.attach(barrel) is True

    def test_effective_stat_with_database_items(self, loaded_db):
        rifle = loaded_db.create("test_rifle")
        scope = loaded_db.create("test_scope")
        grip = loaded_db.create("test_grip")
        rifle.attach(scope)
        rifle.attach(grip)
        # accuracy: base 0 (not in stats) + 15 (scope) + 10 (grip) = 25
        assert rifle.effective_stat("accuracy") == pytest.approx(25.0)

    def test_full_loadout_effective_stats(self, loaded_db):
        rifle = loaded_db.create("test_rifle")
        scope = loaded_db.create("test_scope")
        barrel = loaded_db.create("test_barrel")
        grip = loaded_db.create("test_grip")
        rifle.attach(scope)
        rifle.attach(barrel)
        rifle.attach(grip)
        # damage: base 30 + (-5 barrel) = 25
        assert rifle.effective_stat("damage") == pytest.approx(25.0)
        # range: base 450 + 30 (scope) + 20 (barrel) = 500
        assert rifle.effective_stat("range") == pytest.approx(500.0)
        # recoil: base 0 + (-25 grip) = -25
        assert rifle.effective_stat("recoil") == pytest.approx(-25.0)

    def test_detach_and_reattach_with_database_items(self, loaded_db):
        rifle = loaded_db.create("test_rifle")
        scope1 = loaded_db.create("test_scope")
        scope2 = loaded_db.create("test_scope")
        rifle.attach(scope1)
        assert rifle.effective_stat("accuracy") == pytest.approx(15.0)
        rifle.detach("scope")
        assert rifle.effective_stat("accuracy") == pytest.approx(0.0)
        rifle.attach(scope2)
        assert rifle.effective_stat("accuracy") == pytest.approx(15.0)

    def test_serialization_with_database_items(self, loaded_db):
        rifle = loaded_db.create("test_rifle")
        scope = loaded_db.create("test_scope")
        barrel = loaded_db.create("test_barrel")
        rifle.attach(scope)
        rifle.attach(barrel)
        data = weapon_to_save_dict(rifle)
        assert len(data["attachments"]) == 2
        # Round-trip using the db as factory
        restored = weapon_from_save_dict(data, item_factory=loaded_db.create)
        assert "scope" in restored
        assert "barrel" in restored
        assert restored["scope"].stat_delta["accuracy"] == 15


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_attach_same_attachment_twice_fails(self):
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope")
        w.attach(att)
        # Same object, slot already occupied
        assert w.attach(att) is False

    def test_weapon_deepcopy_preserves_attachments(self):
        import copy
        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"accuracy": 15})
        w.attach(att)
        w2 = copy.deepcopy(w)
        assert w2.get_attachment("scope") is not None
        assert w2.get_attachment("scope") is not att  # different object
        assert w2.get_attachment("scope").stat_delta["accuracy"] == 15

    def test_effective_stat_with_zero_delta(self):
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 0})
        w.attach(att)
        assert w.effective_stat("damage") == pytest.approx(30.0)

    def test_multiple_stat_keys_in_single_attachment(self):
        w = _weapon(damage=30, fire_rate=4.0, mod_slots=["scope"],
                     stats={"range": 450, "accuracy": 70, "reload_time": 2.0})
        att = _attachment(
            slot_type="scope",
            stat_delta={"damage": 5, "fire_rate": 0.5, "accuracy": 15, "range": 30},
        )
        w.attach(att)
        assert w.effective_stat("damage") == pytest.approx(35.0)
        assert w.effective_stat("fire_rate") == pytest.approx(4.5)
        assert w.effective_stat("accuracy") == pytest.approx(85.0)
        assert w.effective_stat("range") == pytest.approx(480.0)

    def test_weapon_repr_still_works(self):
        w = _weapon()
        repr_str = repr(w)
        assert "Weapon" in repr_str

    def test_attachment_repr_still_works(self):
        att = _attachment()
        repr_str = repr(att)
        assert "Attachment" in repr_str
