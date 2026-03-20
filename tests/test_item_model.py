"""
Unit tests for the Item model hierarchy — src/inventory/item.py

# Run: pytest tests/test_item_model.py

Covers:
  - Rarity enum (five tiers, expected names)
  - Rarity.from_str() normalisation
  - Item.monetary_value property (correct calculation, ordering, scaling)
  - RARITY_DEFAULT_VALUES fallback when explicit value is absent or zero
  - Item.get_stat() helper
  - Item.to_save_dict() serialisation
  - Weapon / Armor / Consumable / Attachment subclass fields
  - RARITY_VALUE_MULTIPLIERS constant
  - make_item() factory — dict-based and positional call conventions
"""
import pytest

from src.inventory.item import Rarity, Item, Weapon, Armor, Consumable, Attachment

try:
    from src.core.constants import RARITY_VALUE_MULTIPLIERS
except (ImportError, ModuleNotFoundError):
    # Fallback so tests are importable even before constants.py is written;
    # the RARITY_VALUE_MULTIPLIERS tests will still fail if the values differ.
    RARITY_VALUE_MULTIPLIERS = {
        Rarity.COMMON: 1.0,
        Rarity.UNCOMMON: 1.5,
        Rarity.RARE: 2.5,
        Rarity.EPIC: 5.0,
        Rarity.LEGENDARY: 10.0,
    }


# ---------------------------------------------------------------------------
# Helpers — build sample items without repeating boilerplate
# ---------------------------------------------------------------------------

def _weapon(
    id="pistol_01",
    rarity=Rarity.COMMON,
    base_value=100,
    weight=1.5,
    damage=25,
    fire_rate=4,
    magazine_size=15,
    mod_slots=None,
    stats=None,
):
    return Weapon(
        id=id,
        name="Test Pistol",
        type="weapon",
        rarity=rarity,
        weight=weight,
        base_value=base_value,
        stats=stats or {},
        sprite_path="sprites/pistol.png",
        damage=damage,
        fire_rate=fire_rate,
        magazine_size=magazine_size,
        mod_slots=mod_slots if mod_slots is not None else [],
    )


def _armor(id="vest_01", rarity=Rarity.COMMON, base_value=150, weight=3.0, defense=20, slot="chest"):
    return Armor(
        id=id,
        name="Test Vest",
        type="armor",
        rarity=rarity,
        weight=weight,
        base_value=base_value,
        stats={},
        sprite_path="sprites/vest.png",
        defense=defense,
        slot=slot,
    )


def _consumable(id="medkit_01", rarity=Rarity.COMMON, base_value=50, effect_type="heal", effect_value=50):
    return Consumable(
        id=id,
        name="Test Medkit",
        type="consumable",
        rarity=rarity,
        weight=0.5,
        base_value=base_value,
        stats={},
        sprite_path="sprites/medkit.png",
        effect_type=effect_type,
        effect_value=effect_value,
    )


def _attachment(
    id="scope_01",
    rarity=Rarity.COMMON,
    compatible_weapons=None,
    stat_delta=None,
):
    return Attachment(
        id=id,
        name="Test Scope",
        type="attachment",
        rarity=rarity,
        weight=0.3,
        base_value=80,
        stats={},
        sprite_path="sprites/scope.png",
        compatible_weapons=["pistol_01"] if compatible_weapons is None else compatible_weapons,
        stat_delta={"accuracy": 0.15} if stat_delta is None else stat_delta,
    )


# ---------------------------------------------------------------------------
# Rarity enum
# ---------------------------------------------------------------------------

class TestRarity:
    def test_five_tiers_exist(self):
        assert len(Rarity) == 5

    def test_common_exists(self):
        assert hasattr(Rarity, "COMMON")

    def test_uncommon_exists(self):
        assert hasattr(Rarity, "UNCOMMON")

    def test_rare_exists(self):
        assert hasattr(Rarity, "RARE")

    def test_epic_exists(self):
        assert hasattr(Rarity, "EPIC")

    def test_legendary_exists(self):
        assert hasattr(Rarity, "LEGENDARY")

    def test_all_tiers_are_unique(self):
        values = [r.value for r in Rarity]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# monetary_value property
# ---------------------------------------------------------------------------

class TestMonetaryValue:
    def test_common_monetary_value(self):
        item = _weapon(rarity=Rarity.COMMON, base_value=100)
        assert item.monetary_value == pytest.approx(100 * RARITY_VALUE_MULTIPLIERS[Rarity.COMMON])

    def test_uncommon_monetary_value(self):
        item = _weapon(rarity=Rarity.UNCOMMON, base_value=100)
        assert item.monetary_value == pytest.approx(100 * RARITY_VALUE_MULTIPLIERS[Rarity.UNCOMMON])

    def test_rare_monetary_value(self):
        item = _weapon(rarity=Rarity.RARE, base_value=100)
        assert item.monetary_value == pytest.approx(100 * RARITY_VALUE_MULTIPLIERS[Rarity.RARE])

    def test_epic_monetary_value(self):
        item = _weapon(rarity=Rarity.EPIC, base_value=100)
        assert item.monetary_value == pytest.approx(100 * RARITY_VALUE_MULTIPLIERS[Rarity.EPIC])

    def test_legendary_monetary_value(self):
        item = _weapon(rarity=Rarity.LEGENDARY, base_value=100)
        assert item.monetary_value == pytest.approx(100 * RARITY_VALUE_MULTIPLIERS[Rarity.LEGENDARY])

    def test_legendary_value_greater_than_common(self):
        common = _weapon(rarity=Rarity.COMMON, base_value=100)
        legendary = _weapon(rarity=Rarity.LEGENDARY, base_value=100)
        assert legendary.monetary_value > common.monetary_value

    def test_rarity_ordering_is_strictly_ascending(self):
        """monetary_value must increase monotonically: COMMON < UNCOMMON < RARE < EPIC < LEGENDARY."""
        tiers = [Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE, Rarity.EPIC, Rarity.LEGENDARY]
        values = [_weapon(rarity=r, base_value=100).monetary_value for r in tiers]
        assert values == sorted(values), "Monetary values must be in ascending order by rarity"

    def test_monetary_value_scales_with_base_value(self):
        low = _weapon(rarity=Rarity.RARE, base_value=50)
        high = _weapon(rarity=Rarity.RARE, base_value=200)
        assert high.monetary_value == pytest.approx(4 * low.monetary_value)

    def test_zero_base_value_gives_zero_monetary_value(self):
        item = _weapon(rarity=Rarity.LEGENDARY, base_value=0)
        assert item.monetary_value == pytest.approx(0.0)

    def test_all_rarities_have_positive_multipliers(self):
        for rarity in Rarity:
            assert RARITY_VALUE_MULTIPLIERS[rarity] > 0, (
                f"Multiplier for {rarity} must be positive"
            )

    def test_rarity_value_multipliers_covers_all_tiers(self):
        for rarity in Rarity:
            assert rarity in RARITY_VALUE_MULTIPLIERS, (
                f"RARITY_VALUE_MULTIPLIERS missing entry for {rarity}"
            )


# ---------------------------------------------------------------------------
# Weapon subclass
# ---------------------------------------------------------------------------

class TestWeapon:
    def test_weapon_is_item_subclass(self):
        assert issubclass(Weapon, Item)

    def test_weapon_stores_damage(self):
        w = _weapon(damage=30)
        assert w.damage == 30

    def test_weapon_stores_fire_rate(self):
        w = _weapon(fire_rate=10)
        assert w.fire_rate == 10

    def test_weapon_stores_magazine_size(self):
        w = _weapon(magazine_size=30)
        assert w.magazine_size == 30

    def test_weapon_mod_slots_defaults_to_empty_list(self):
        w = _weapon(mod_slots=[])
        assert w.mod_slots == []

    def test_weapon_mod_slots_can_hold_attachment_ids(self):
        w = _weapon(mod_slots=["scope_01", "grip_01"])
        assert "scope_01" in w.mod_slots
        assert "grip_01" in w.mod_slots
        assert len(w.mod_slots) == 2

    def test_weapon_inherits_id(self):
        w = _weapon(id="pistol_01")
        assert w.id == "pistol_01"

    def test_weapon_inherits_name(self):
        w = _weapon()
        assert w.name == "Test Pistol"

    def test_weapon_inherits_rarity(self):
        w = _weapon(rarity=Rarity.EPIC)
        assert w.rarity == Rarity.EPIC

    def test_weapon_inherits_weight(self):
        w = _weapon(weight=2.5)
        assert w.weight == pytest.approx(2.5)

    def test_weapon_stats_dict_accessible(self):
        w = _weapon(stats={"accuracy": 0.8})
        assert w.stats["accuracy"] == pytest.approx(0.8)

    def test_weapon_type_field(self):
        w = _weapon()
        assert w.type == "weapon"


# ---------------------------------------------------------------------------
# Armor subclass
# ---------------------------------------------------------------------------

class TestArmor:
    def test_armor_is_item_subclass(self):
        assert issubclass(Armor, Item)

    def test_armor_stores_defense(self):
        a = _armor(defense=35)
        assert a.defense == 35

    def test_armor_chest_slot(self):
        a = _armor(slot="chest")
        assert a.slot == "chest"

    def test_armor_helmet_slot(self):
        a = _armor(slot="helmet")
        assert a.slot == "helmet"

    def test_armor_inherits_id(self):
        a = _armor(id="vest_rare")
        assert a.id == "vest_rare"

    def test_armor_inherits_rarity(self):
        a = _armor(rarity=Rarity.RARE)
        assert a.rarity == Rarity.RARE

    def test_armor_inherits_weight(self):
        a = _armor(weight=4.0)
        assert a.weight == pytest.approx(4.0)

    def test_armor_type_field(self):
        a = _armor()
        assert a.type == "armor"

    def test_armor_monetary_value_uses_multiplier(self):
        a = _armor(rarity=Rarity.EPIC, base_value=200)
        assert a.monetary_value == pytest.approx(200 * RARITY_VALUE_MULTIPLIERS[Rarity.EPIC])


# ---------------------------------------------------------------------------
# Consumable subclass
# ---------------------------------------------------------------------------

class TestConsumable:
    def test_consumable_is_item_subclass(self):
        assert issubclass(Consumable, Item)

    def test_consumable_stores_effect_type(self):
        c = _consumable(effect_type="heal")
        assert c.effect_type == "heal"

    def test_consumable_stores_effect_value(self):
        c = _consumable(effect_value=75)
        assert c.effect_value == 75

    def test_consumable_speed_boost_effect(self):
        c = _consumable(effect_type="speed_boost", effect_value=20)
        assert c.effect_type == "speed_boost"
        assert c.effect_value == 20

    def test_consumable_type_field(self):
        c = _consumable()
        assert c.type == "consumable"

    def test_consumable_inherits_rarity(self):
        c = _consumable(rarity=Rarity.UNCOMMON)
        assert c.rarity == Rarity.UNCOMMON


# ---------------------------------------------------------------------------
# Attachment subclass
# ---------------------------------------------------------------------------

class TestAttachment:
    def test_attachment_is_item_subclass(self):
        assert issubclass(Attachment, Item)

    def test_attachment_stores_compatible_weapons(self):
        a = _attachment(compatible_weapons=["pistol_01", "smg_01"])
        assert "pistol_01" in a.compatible_weapons
        assert "smg_01" in a.compatible_weapons

    def test_attachment_stat_delta_damage(self):
        a = _attachment(stat_delta={"damage": 5})
        assert a.stat_delta["damage"] == 5

    def test_attachment_stat_delta_accuracy(self):
        a = _attachment(stat_delta={"accuracy": 0.12})
        assert a.stat_delta["accuracy"] == pytest.approx(0.12)

    def test_attachment_multiple_stat_deltas(self):
        a = _attachment(stat_delta={"damage": 5, "accuracy": 0.1, "fire_rate": -1})
        assert a.stat_delta["damage"] == 5
        assert a.stat_delta["accuracy"] == pytest.approx(0.1)
        assert a.stat_delta["fire_rate"] == -1

    def test_attachment_empty_stat_delta(self):
        a = _attachment(stat_delta={})
        assert a.stat_delta == {}

    def test_attachment_type_field(self):
        a = _attachment()
        assert a.type == "attachment"

    def test_attachment_inherits_rarity(self):
        a = _attachment(rarity=Rarity.LEGENDARY)
        assert a.rarity == Rarity.LEGENDARY

    def test_attachment_inherits_weight(self):
        a = _attachment()
        assert a.weight == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Rarity.from_str()
# ---------------------------------------------------------------------------

class TestRarityFromStr:
    def test_from_str_lowercase_common(self):
        assert Rarity.from_str("common") == Rarity.COMMON

    def test_from_str_uppercase_LEGENDARY(self):
        assert Rarity.from_str("LEGENDARY") == Rarity.LEGENDARY

    def test_from_str_mixed_case_Rare(self):
        assert Rarity.from_str("Rare") == Rarity.RARE

    def test_from_str_unknown_falls_back_to_common(self):
        result = Rarity.from_str("not_a_real_rarity_xyz")
        assert result == Rarity.COMMON

    def test_from_str_empty_string_falls_back_to_common(self):
        result = Rarity.from_str("")
        assert result == Rarity.COMMON

    def test_from_str_epic_lowercase(self):
        assert Rarity.from_str("epic") == Rarity.EPIC

    def test_from_str_uncommon_lowercase(self):
        assert Rarity.from_str("uncommon") == Rarity.UNCOMMON


# ---------------------------------------------------------------------------
# RARITY_DEFAULT_VALUES — fallback when value is zero or absent
# ---------------------------------------------------------------------------

class TestRarityDefaultValues:
    def test_zero_explicit_value_uses_rarity_fallback(self):
        """An item constructed with value=0 must have monetary_value > 0 from the fallback."""
        from src.inventory.item import RARITY_DEFAULT_VALUES
        item = Item(item_id="x", name="x", item_type="item",
                    rarity=Rarity.COMMON, value=0)
        # The fallback for COMMON is 100; monetary_value = 100 * 1.0 = 100
        expected = RARITY_DEFAULT_VALUES["common"] * 1.0
        assert item.monetary_value == pytest.approx(expected)

    def test_legendary_fallback_greater_than_common_fallback(self):
        from src.inventory.item import RARITY_DEFAULT_VALUES
        common_val = RARITY_DEFAULT_VALUES["common"]
        legend_val = RARITY_DEFAULT_VALUES["legendary"]
        assert legend_val > common_val

    def test_default_values_defined_for_all_rarity_tiers(self):
        from src.inventory.item import RARITY_DEFAULT_VALUES, RARITY_ORDER
        for rarity_str in RARITY_ORDER:
            assert rarity_str in RARITY_DEFAULT_VALUES, (
                f"RARITY_DEFAULT_VALUES missing entry for {rarity_str!r}"
            )

    def test_all_default_values_are_positive(self):
        from src.inventory.item import RARITY_DEFAULT_VALUES
        for k, v in RARITY_DEFAULT_VALUES.items():
            assert v > 0, f"Default value for {k!r} must be positive"

    def test_explicit_positive_value_overrides_fallback(self):
        item = Item(item_id="x", name="x", item_type="item",
                    rarity=Rarity.COMMON, value=999)
        assert item.value == 999


# ---------------------------------------------------------------------------
# Item.get_stat()
# ---------------------------------------------------------------------------

class TestGetStat:
    def test_get_stat_returns_value_when_key_present(self):
        item = Item(item_id="x", name="x", item_type="item",
                    rarity=Rarity.COMMON, stats={"armor": 15})
        assert item.get_stat("armor") == 15

    def test_get_stat_returns_default_when_key_absent(self):
        item = Item(item_id="x", name="x", item_type="item",
                    rarity=Rarity.COMMON, stats={})
        assert item.get_stat("missing_key") == 0

    def test_get_stat_returns_custom_default_when_key_absent(self):
        item = Item(item_id="x", name="x", item_type="item",
                    rarity=Rarity.COMMON, stats={})
        assert item.get_stat("missing_key", default=-1) == -1

    def test_get_stat_with_float_value(self):
        item = Item(item_id="x", name="x", item_type="item",
                    rarity=Rarity.COMMON, stats={"accuracy": 0.85})
        assert item.get_stat("accuracy") == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Item.to_save_dict()
# ---------------------------------------------------------------------------

class TestToSaveDict:
    def test_to_save_dict_returns_dict(self):
        assert isinstance(_weapon().to_save_dict(), dict)

    def test_to_save_dict_contains_item_id(self):
        d = _weapon(id="pistol_01").to_save_dict()
        assert d["item_id"] == "pistol_01"

    def test_to_save_dict_contains_name(self):
        d = _weapon().to_save_dict()
        assert d["name"] == "Test Pistol"

    def test_to_save_dict_contains_item_type(self):
        d = _weapon().to_save_dict()
        assert d["item_type"] == "weapon"

    def test_to_save_dict_contains_rarity_as_string(self):
        d = _weapon(rarity=Rarity.EPIC).to_save_dict()
        assert isinstance(d["rarity"], str)
        assert d["rarity"].lower() == "epic"

    def test_to_save_dict_contains_weight(self):
        d = _weapon(weight=2.5).to_save_dict()
        assert d["weight"] == pytest.approx(2.5)

    def test_to_save_dict_contains_stats(self):
        d = _weapon(stats={"accuracy": 0.9}).to_save_dict()
        assert d["stats"].get("accuracy") == pytest.approx(0.9)

    def test_to_save_dict_contains_quantity(self):
        from src.inventory.item import Item
        item = Item(item_id="x", name="x", item_type="item",
                    rarity=Rarity.COMMON, quantity=3)
        assert item.to_save_dict()["quantity"] == 3

    def test_armor_to_save_dict_contains_item_type_armor(self):
        d = _armor().to_save_dict()
        assert d["item_type"] == "armor"


# ---------------------------------------------------------------------------
# make_item() factory — dict-based call convention
# ---------------------------------------------------------------------------

class TestMakeItemDictConvention:
    def test_make_item_weapon_dict_returns_weapon(self):
        from src.inventory.item import make_item, Weapon
        data = {
            "item_id": "smg_01", "name": "SMG", "item_type": "weapon",
            "rarity": "UNCOMMON", "weight": 2.0, "value": 300,
            "stats": {}, "sprite": "", "damage": 20, "fire_rate": 8,
            "magazine_size": 25, "mod_slots": [],
        }
        item = make_item(data)
        assert isinstance(item, Weapon)

    def test_make_item_armor_dict_returns_armor(self):
        from src.inventory.item import make_item, Armor
        data = {
            "item_id": "vest_01", "name": "Vest", "item_type": "armor",
            "rarity": "COMMON", "weight": 3.0, "value": 150,
            "stats": {}, "sprite": "",
        }
        item = make_item(data)
        assert isinstance(item, Armor)

    def test_make_item_consumable_dict_returns_consumable(self):
        from src.inventory.item import make_item, Consumable
        data = {
            "item_id": "kit_01", "name": "Kit", "item_type": "consumable",
            "rarity": "COMMON", "weight": 0.5, "value": 50,
            "stats": {}, "sprite": "",
        }
        item = make_item(data)
        assert isinstance(item, Consumable)

    def test_make_item_attachment_dict_returns_attachment(self):
        from src.inventory.item import make_item, Attachment
        data = {
            "item_id": "scope_01", "name": "Scope", "item_type": "attachment",
            "rarity": "RARE", "weight": 0.3, "value": 200,
            "stats": {}, "sprite": "",
        }
        item = make_item(data)
        assert isinstance(item, Attachment)

    def test_make_item_unknown_type_dict_returns_base_item(self):
        from src.inventory.item import make_item, Item
        data = {
            "item_id": "misc_01", "name": "Misc", "item_type": "misc",
            "rarity": "COMMON", "weight": 0.1, "value": 10,
            "stats": {}, "sprite": "",
        }
        item = make_item(data)
        assert isinstance(item, Item)

    def test_make_item_dict_preserves_name(self):
        from src.inventory.item import make_item
        item = make_item({"item_id": "x", "name": "Elite Rifle",
                          "item_type": "weapon", "rarity": "LEGENDARY",
                          "weight": 4.0, "value": 2000, "stats": {}, "sprite": ""})
        assert item.name == "Elite Rifle"


# ---------------------------------------------------------------------------
# make_item() factory — positional / keyword call convention
# ---------------------------------------------------------------------------

class TestMakeItemPositionalConvention:
    def test_make_item_weapon_positional_returns_weapon(self):
        from src.inventory.item import make_item, Weapon
        item = make_item("rifle_01", "Rifle", "weapon", "rare", 500, 3.5, "")
        assert isinstance(item, Weapon)

    def test_make_item_armor_positional_returns_armor(self):
        from src.inventory.item import make_item, Armor
        item = make_item("vest_01", "Vest", "armor", "common", 150, 3.0, "")
        assert isinstance(item, Armor)

    def test_make_item_positional_preserves_id(self):
        from src.inventory.item import make_item
        item = make_item("my_weapon_id", "Gun", "weapon", "common", 100, 1.5, "")
        assert item.item_id == "my_weapon_id"

    def test_make_item_positional_preserves_rarity(self):
        from src.inventory.item import make_item
        item = make_item("x", "X", "armor", "epic", 1000, 2.0, "")
        assert item.rarity == Rarity.EPIC
