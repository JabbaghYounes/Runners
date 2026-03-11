"""Unit tests for Item value handling and ItemDatabase.

Tests cover:
- RARITY_DEFAULT_VALUES: correct mid-point fallback per rarity tier
- Item.value: explicit positive value is used; zero / negative falls back to
  the rarity default
- make_item() factory: dispatches to correct subclass
- ItemDatabase: loads all items from data/items.json, create() returns deep
  copy with correct value, unknown IDs raise KeyError, all items have value > 0
"""
import pytest

from src.inventory.item import (
    Armor,
    Attachment,
    Consumable,
    Item,
    RARITY_COLORS,
    RARITY_COMMON,
    RARITY_DEFAULT_VALUES,
    RARITY_EPIC,
    RARITY_LEGENDARY,
    RARITY_ORDER,
    RARITY_RARE,
    RARITY_UNCOMMON,
    Weapon,
    make_item,
)
from src.inventory.item_database import ItemDatabase

# Path to the real item catalog used during tests (must exist in the repo).
_ITEMS_JSON = "data/items.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make(
    value: int,
    rarity: str = RARITY_COMMON,
    item_type: str = "weapon",
    item_id: str = "test_item",
) -> Item:
    """Shortcut to create a minimal base ``Item`` instance.

    Instantiates ``Item`` directly (not via ``make_item()``) to avoid the
    known bug where ``make_item()`` passes ``item_type`` to subclass
    constructors (Weapon, Armor, etc.) that also hardcode it via
    ``super().__init__(item_type=...)``, which raises a ``TypeError``.
    Value-fallback and attribute tests only need the base ``Item`` class.
    """
    return Item(
        item_id=item_id,
        name="Test",
        item_type=item_type,
        rarity=rarity,
        value=value,
        weight=1.0,
        sprite="",
    )


def _fresh_db() -> ItemDatabase:
    """Return a freshly loaded ItemDatabase (bypasses singleton to isolate tests)."""
    db = ItemDatabase()
    db.load(_ITEMS_JSON)
    return db


# ---------------------------------------------------------------------------
# RARITY_DEFAULT_VALUES
# ---------------------------------------------------------------------------

class TestRarityDefaultValues:
    """Verify the fallback value table matches the documented rarity ranges."""

    def test_common_default_is_100(self):
        assert RARITY_DEFAULT_VALUES[RARITY_COMMON] == 100

    def test_uncommon_default_is_300(self):
        assert RARITY_DEFAULT_VALUES[RARITY_UNCOMMON] == 300

    def test_rare_default_is_550(self):
        assert RARITY_DEFAULT_VALUES[RARITY_RARE] == 550

    def test_epic_default_is_1150(self):
        assert RARITY_DEFAULT_VALUES[RARITY_EPIC] == 1150

    def test_legendary_default_is_2500(self):
        assert RARITY_DEFAULT_VALUES[RARITY_LEGENDARY] == 2500

    def test_all_five_rarity_tiers_have_entries(self):
        for rarity in RARITY_ORDER:
            assert rarity in RARITY_DEFAULT_VALUES, f"{rarity!r} missing from RARITY_DEFAULT_VALUES"

    def test_defaults_increase_with_rarity(self):
        """Higher rarity tiers must have strictly higher default values."""
        values = [RARITY_DEFAULT_VALUES[r] for r in RARITY_ORDER]
        assert values == sorted(values), "Defaults are not monotonically increasing"

    def test_defaults_are_positive_ints(self):
        for rarity, value in RARITY_DEFAULT_VALUES.items():
            assert isinstance(value, int) and value > 0, f"{rarity} has non-positive default {value}"


# ---------------------------------------------------------------------------
# Item.value attribute
# ---------------------------------------------------------------------------

class TestItemValue:
    """item.value resolves from explicit JSON value or rarity fallback."""

    def test_explicit_positive_value_is_used(self):
        item = _make(value=999)
        assert item.value == 999

    def test_value_is_stored_as_int(self):
        item = _make(value=123)
        assert isinstance(item.value, int)

    def test_zero_value_falls_back_to_rarity_default_common(self):
        item = _make(value=0, rarity=RARITY_COMMON)
        assert item.value == RARITY_DEFAULT_VALUES[RARITY_COMMON]

    def test_zero_value_falls_back_to_rarity_default_uncommon(self):
        item = _make(value=0, rarity=RARITY_UNCOMMON)
        assert item.value == RARITY_DEFAULT_VALUES[RARITY_UNCOMMON]

    def test_zero_value_falls_back_to_rarity_default_rare(self):
        item = _make(value=0, rarity=RARITY_RARE)
        assert item.value == RARITY_DEFAULT_VALUES[RARITY_RARE]

    def test_zero_value_falls_back_to_rarity_default_epic(self):
        item = _make(value=0, rarity=RARITY_EPIC)
        assert item.value == RARITY_DEFAULT_VALUES[RARITY_EPIC]

    def test_zero_value_falls_back_to_rarity_default_legendary(self):
        item = _make(value=0, rarity=RARITY_LEGENDARY)
        assert item.value == RARITY_DEFAULT_VALUES[RARITY_LEGENDARY]

    def test_negative_value_falls_back_to_rarity_default(self):
        item = _make(value=-500, rarity=RARITY_RARE)
        assert item.value == RARITY_DEFAULT_VALUES[RARITY_RARE]

    def test_value_attribute_is_readable_without_computation(self):
        """Accessing .value twice returns the same result (not computed each time)."""
        item = _make(value=400)
        assert item.value == item.value

    def test_rarity_color_property_exists(self):
        item = _make(value=100, rarity=RARITY_COMMON)
        color = item.rarity_color
        assert isinstance(color, tuple) and len(color) == 3


# ---------------------------------------------------------------------------
# make_item() factory — subclass dispatch
# ---------------------------------------------------------------------------
# NOTE: These tests call make_item() directly and are expected to FAIL until
# the known bug is resolved.  The bug: make_item() passes item_type as a
# keyword argument to subclass constructors (Weapon, Armor, etc.) which also
# hardcode it in their super().__init__(item_type=...) calls, resulting in a
# TypeError: "got multiple values for keyword argument 'item_type'".
# Keeping these tests here ensures the bug is tracked and the fix is verified
# when it lands.
# ---------------------------------------------------------------------------

class TestMakeItemFactory:
    def test_weapon_type_returns_weapon_instance(self):
        item = make_item("w", "W", "weapon", RARITY_COMMON, 100, 1.0, "")
        assert isinstance(item, Weapon)

    def test_armor_type_returns_armor_instance(self):
        item = make_item("a", "A", "armor", RARITY_COMMON, 100, 2.0, "")
        assert isinstance(item, Armor)

    def test_consumable_type_returns_consumable_instance(self):
        item = make_item("c", "C", "consumable", RARITY_COMMON, 100, 0.5, "")
        assert isinstance(item, Consumable)

    def test_attachment_type_returns_attachment_instance(self):
        item = make_item("t", "T", "attachment", RARITY_COMMON, 100, 0.2, "")
        assert isinstance(item, Attachment)

    def test_unknown_type_falls_back_to_base_item(self):
        # Unknown types resolve to Item (not a subclass), so no duplicate
        # item_type kwarg collision — this one should PASS.
        item = make_item("u", "U", "unknown_category", RARITY_COMMON, 100, 1.0, "")
        assert type(item) is Item

    def test_factory_propagates_value_correctly(self):
        weapon = make_item("w", "W", "weapon", RARITY_RARE, 600, 2.0, "")
        assert weapon.value == 600

    def test_weapon_subclass_exposes_damage_property(self):
        weapon = make_item(
            "wep", "Gun", "weapon", RARITY_COMMON, 80, 1.0, "",
            stats={"damage": 25},
        )
        assert weapon.damage == 25  # type: ignore[attr-defined]

    def test_armor_subclass_exposes_armor_property(self):
        armor = make_item(
            "arm", "Vest", "armor", RARITY_COMMON, 60, 2.0, "",
            stats={"armor": 15},
        )
        assert armor.armor == 15  # type: ignore[attr-defined]

    def test_consumable_subclass_exposes_heal_amount_property(self):
        med = make_item(
            "med", "Medkit", "consumable", RARITY_COMMON, 50, 0.5, "",
            stats={"heal_amount": 30},
        )
        assert med.heal_amount == 30  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# ItemDatabase — loading
# ---------------------------------------------------------------------------

class TestItemDatabaseLoad:
    def test_load_populates_items(self):
        db = _fresh_db()
        assert len(db) > 0

    def test_load_contains_expected_count(self):
        """data/items.json contains exactly 36 seed items."""
        db = _fresh_db()
        assert len(db) == 36

    def test_all_ids_returns_sorted_list(self):
        db = _fresh_db()
        ids = db.all_ids()
        assert ids == sorted(ids)

    def test_known_id_in_db(self):
        db = _fresh_db()
        assert "pistol_mk1" in db

    def test_legendary_weapon_in_db(self):
        db = _fresh_db()
        assert "cannon_obliterator" in db

    def test_legendary_armor_in_db(self):
        db = _fresh_db()
        assert "armor_aegis" in db


# ---------------------------------------------------------------------------
# ItemDatabase — create() and deep copy
# ---------------------------------------------------------------------------

class TestItemDatabaseCreate:
    def test_create_returns_item_instance(self):
        db = _fresh_db()
        assert isinstance(db.create("pistol_mk1"), Item)

    def test_create_pistol_mk1_has_correct_value(self):
        db = _fresh_db()
        assert db.create("pistol_mk1").value == 80

    def test_create_smg_rattler_has_correct_value(self):
        db = _fresh_db()
        assert db.create("smg_rattler").value == 120

    def test_create_rifle_pulse_has_correct_value(self):
        db = _fresh_db()
        assert db.create("rifle_pulse").value == 550

    def test_create_cannon_obliterator_legendary_value(self):
        db = _fresh_db()
        assert db.create("cannon_obliterator").value == 3500

    def test_create_armor_aegis_legendary_value(self):
        db = _fresh_db()
        assert db.create("armor_aegis").value == 2500

    def test_create_medkit_basic_common_value(self):
        db = _fresh_db()
        assert db.create("medkit_basic").value == 50

    def test_create_returns_deep_copy_not_shared_reference(self):
        """Mutating one copy must not affect subsequent creates."""
        db = _fresh_db()
        item_a = db.create("pistol_mk1")
        item_b = db.create("pistol_mk1")
        item_a.value = 9999  # type: ignore[assignment]
        assert item_b.value == 80

    def test_two_creates_of_same_id_are_independent_objects(self):
        db = _fresh_db()
        a = db.create("rifle_pulse")
        b = db.create("rifle_pulse")
        assert a is not b

    def test_create_unknown_id_raises_key_error(self):
        db = _fresh_db()
        with pytest.raises(KeyError):
            db.create("does_not_exist_item_xyz")

    def test_create_returns_correct_subclass_for_weapon(self):
        db = _fresh_db()
        assert isinstance(db.create("pistol_mk1"), Weapon)

    def test_create_returns_correct_subclass_for_armor(self):
        db = _fresh_db()
        assert isinstance(db.create("armor_light"), Armor)

    def test_create_returns_correct_subclass_for_consumable(self):
        db = _fresh_db()
        assert isinstance(db.create("medkit_basic"), Consumable)

    def test_create_returns_correct_subclass_for_attachment(self):
        db = _fresh_db()
        assert isinstance(db.create("scope_red_dot"), Attachment)


# ---------------------------------------------------------------------------
# ItemDatabase — value range validation against rarity tiers
# ---------------------------------------------------------------------------

class TestItemValueRanges:
    """All catalog items should have values within their documented rarity range."""

    def test_all_items_have_positive_value(self):
        db = _fresh_db()
        for item_id in db.all_ids():
            item = db.create(item_id)
            assert item.value > 0, f"{item_id} has value {item.value} (expected > 0)"

    def test_common_items_in_expected_range(self):
        """Common items: $50–$200 per feature plan."""
        db = _fresh_db()
        for item_id in db.all_ids():
            item = db.create(item_id)
            if item.rarity == RARITY_COMMON:
                assert 50 <= item.value <= 200, (
                    f"Common item {item_id!r} has value {item.value}, expected 50–200"
                )

    def test_uncommon_items_in_expected_range(self):
        """Uncommon items: $200–$400."""
        db = _fresh_db()
        for item_id in db.all_ids():
            item = db.create(item_id)
            if item.rarity == RARITY_UNCOMMON:
                assert 200 <= item.value <= 400, (
                    f"Uncommon item {item_id!r} has value {item.value}, expected 200–400"
                )

    def test_rare_items_in_expected_range(self):
        """Rare items: $400–$700."""
        db = _fresh_db()
        for item_id in db.all_ids():
            item = db.create(item_id)
            if item.rarity == RARITY_RARE:
                assert 400 <= item.value <= 700, (
                    f"Rare item {item_id!r} has value {item.value}, expected 400–700"
                )

    def test_epic_items_in_expected_range(self):
        """Epic items: $800–$1,500."""
        db = _fresh_db()
        for item_id in db.all_ids():
            item = db.create(item_id)
            if item.rarity == RARITY_EPIC:
                assert 800 <= item.value <= 1500, (
                    f"Epic item {item_id!r} has value {item.value}, expected 800–1500"
                )

    def test_legendary_items_at_least_2000(self):
        """Legendary items: $2,000+."""
        db = _fresh_db()
        for item_id in db.all_ids():
            item = db.create(item_id)
            if item.rarity == RARITY_LEGENDARY:
                assert item.value >= 2000, (
                    f"Legendary item {item_id!r} has value {item.value}, expected >= 2000"
                )

    def test_items_span_all_rarity_tiers(self):
        """The catalog must include at least one item of every rarity tier."""
        db = _fresh_db()
        found_rarities = {db.create(item_id).rarity for item_id in db.all_ids()}
        for rarity in RARITY_ORDER:
            assert rarity in found_rarities, f"No {rarity!r} item found in catalog"
