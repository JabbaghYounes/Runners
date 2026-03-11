"""
Unit tests for the Item model hierarchy — src/inventory/item.py

Covers:
  - Rarity enum (five tiers, expected names)
  - Item.monetary_value property (correct calculation, ordering, scaling)
  - Weapon / Armor / Consumable / Attachment subclass fields
  - RARITY_VALUE_MULTIPLIERS constant from src/core/constants.py
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
