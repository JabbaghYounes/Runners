"""
Unit tests for Inventory — src/inventory/inventory.py

Covers:
  - add()  : slot-cap enforcement, weight-cap enforcement, return value
  - remove(): slot freed to None, return value, non-existent item
  - drop()  : returns item, removes from slots, raises on non-existent
  - equip() : weapon, armor; type guard; item-not-in-inventory guard
  - unequip(): clears ref, item stays in slots, bad category raises
  - Properties: is_full, total_weight, used_slots, equipped_weapon, equipped_armor
"""
import pytest

from src.inventory.inventory import Inventory
from src.inventory.item import Rarity, Weapon, Armor, Consumable, Attachment


# ---------------------------------------------------------------------------
# Item factories
# ---------------------------------------------------------------------------

def _weapon(id="pistol_01", weight=1.5, rarity=Rarity.COMMON, damage=25):
    return Weapon(
        id=id, name="Test Pistol", type="weapon",
        rarity=rarity, weight=weight, base_value=100,
        stats={}, sprite_path="",
        damage=damage, fire_rate=4, magazine_size=15, mod_slots=[],
    )


def _armor(id="vest_01", weight=3.0, slot="chest"):
    return Armor(
        id=id, name="Test Vest", type="armor",
        rarity=Rarity.COMMON, weight=weight, base_value=150,
        stats={}, sprite_path="",
        defense=20, slot=slot,
    )


def _consumable(id="medkit_01", weight=0.5):
    return Consumable(
        id=id, name="Test Medkit", type="consumable",
        rarity=Rarity.COMMON, weight=weight, base_value=50,
        stats={}, sprite_path="",
        effect_type="heal", effect_value=50,
    )


def _attachment(id="scope_01", weight=0.3):
    return Attachment(
        id=id, name="Test Scope", type="attachment",
        rarity=Rarity.COMMON, weight=weight, base_value=80,
        stats={}, sprite_path="",
        compatible_weapons=["pistol_01"],
        stat_delta={"accuracy": 0.15},
    )


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------

class TestAdd:
    def test_add_returns_true_on_success(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.add(_weapon()) is True

    def test_added_item_appears_in_slots(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        inv.add(item)
        assert item in inv.slots

    def test_add_two_items_both_present(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        a = _armor()
        inv.add(w)
        inv.add(a)
        assert w in inv.slots
        assert a in inv.slots

    def test_add_returns_false_when_slot_cap_reached(self):
        inv = Inventory(max_slots=2, max_weight=100.0)
        inv.add(_weapon("w1"))
        inv.add(_weapon("w2"))
        assert inv.add(_weapon("w3")) is False

    def test_add_does_not_insert_item_when_slots_full(self):
        inv = Inventory(max_slots=1, max_weight=100.0)
        existing = _weapon("w1")
        overflow = _weapon("w2")
        inv.add(existing)
        inv.add(overflow)
        assert overflow not in inv.slots

    def test_add_returns_false_when_weight_cap_exceeded(self):
        inv = Inventory(max_slots=10, max_weight=2.0)
        inv.add(_weapon("w1", weight=1.5))
        assert inv.add(_weapon("w2", weight=1.5)) is False

    def test_add_does_not_insert_item_when_over_weight(self):
        inv = Inventory(max_slots=10, max_weight=2.0)
        heavy = _weapon("heavy", weight=1.5)
        overflow = _weapon("overflow", weight=1.5)
        inv.add(heavy)
        inv.add(overflow)
        assert overflow not in inv.slots

    def test_add_at_exact_weight_limit_succeeds(self):
        inv = Inventory(max_slots=10, max_weight=3.0)
        assert inv.add(_weapon("w1", weight=1.5)) is True
        assert inv.add(_weapon("w2", weight=1.5)) is True

    def test_add_one_unit_over_weight_limit_fails(self):
        inv = Inventory(max_slots=10, max_weight=3.0)
        inv.add(_weapon("w1", weight=1.5))
        inv.add(_weapon("w2", weight=1.5))
        assert inv.add(_weapon("w3", weight=0.1)) is False

    def test_add_different_item_types(self):
        inv = Inventory(max_slots=10, max_weight=30.0)
        assert inv.add(_weapon()) is True
        assert inv.add(_armor()) is True
        assert inv.add(_consumable()) is True
        assert inv.add(_attachment()) is True


# ---------------------------------------------------------------------------
# remove()
# ---------------------------------------------------------------------------

class TestRemove:
    def test_remove_returns_true(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        inv.add(item)
        assert inv.remove(item) is True

    def test_removed_item_not_in_slots(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        inv.add(item)
        inv.remove(item)
        assert item not in inv.slots

    def test_remove_leaves_other_items_intact(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w1 = _weapon("w1")
        w2 = _weapon("w2")
        inv.add(w1)
        inv.add(w2)
        inv.remove(w1)
        assert w2 in inv.slots

    def test_remove_nonexistent_item_returns_false(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.remove(_weapon()) is False

    def test_slot_becomes_reusable_after_remove(self):
        """After removing an item from a full inventory the freed slot can accept a new item."""
        inv = Inventory(max_slots=2, max_weight=100.0)
        w1, w2, w3 = _weapon("w1"), _weapon("w2"), _weapon("w3")
        inv.add(w1)
        inv.add(w2)
        inv.remove(w1)
        assert inv.add(w3) is True

    def test_remove_twice_returns_false_second_time(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        inv.add(item)
        inv.remove(item)
        assert inv.remove(item) is False


# ---------------------------------------------------------------------------
# drop()
# ---------------------------------------------------------------------------

class TestDrop:
    def test_drop_returns_the_item(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        inv.add(item)
        returned = inv.drop(item)
        assert returned is item

    def test_drop_removes_item_from_slots(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        inv.add(item)
        inv.drop(item)
        assert item not in inv.slots

    def test_drop_nonexistent_item_raises(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        with pytest.raises((ValueError, KeyError)):
            inv.drop(_weapon())

    def test_drop_frees_slot_for_new_item(self):
        inv = Inventory(max_slots=1, max_weight=100.0)
        w1 = _weapon("w1")
        w2 = _weapon("w2")
        inv.add(w1)
        inv.drop(w1)
        assert inv.add(w2) is True


# ---------------------------------------------------------------------------
# is_full property
# ---------------------------------------------------------------------------

class TestIsFull:
    def test_not_full_when_empty(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.is_full is False

    def test_not_full_when_partially_filled(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon())
        assert inv.is_full is False

    def test_full_when_all_slots_occupied(self):
        inv = Inventory(max_slots=2, max_weight=100.0)
        inv.add(_weapon("w1"))
        inv.add(_weapon("w2"))
        assert inv.is_full is True

    def test_full_when_weight_cap_reached(self):
        inv = Inventory(max_slots=10, max_weight=1.5)
        inv.add(_weapon(weight=1.5))
        assert inv.is_full is True

    def test_not_full_after_remove(self):
        inv = Inventory(max_slots=1, max_weight=100.0)
        item = _weapon()
        inv.add(item)
        inv.remove(item)
        assert inv.is_full is False

    def test_not_full_after_drop(self):
        inv = Inventory(max_slots=1, max_weight=100.0)
        item = _weapon()
        inv.add(item)
        inv.drop(item)
        assert inv.is_full is False


# ---------------------------------------------------------------------------
# total_weight property
# ---------------------------------------------------------------------------

class TestTotalWeight:
    def test_empty_inventory_weight_is_zero(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.total_weight == pytest.approx(0.0)

    def test_single_item_weight(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon(weight=1.5))
        assert inv.total_weight == pytest.approx(1.5)

    def test_weight_accumulates_across_items(self):
        inv = Inventory(max_slots=10, max_weight=30.0)
        inv.add(_weapon(weight=1.5))
        inv.add(_armor(weight=3.0))
        assert inv.total_weight == pytest.approx(4.5)

    def test_weight_decreases_on_remove(self):
        inv = Inventory(max_slots=10, max_weight=30.0)
        item = _weapon(weight=2.0)
        inv.add(item)
        inv.remove(item)
        assert inv.total_weight == pytest.approx(0.0)

    def test_weight_decreases_on_drop(self):
        inv = Inventory(max_slots=10, max_weight=30.0)
        item = _weapon(weight=2.0)
        inv.add(item)
        inv.drop(item)
        assert inv.total_weight == pytest.approx(0.0)

    def test_weight_sums_multiple_removes(self):
        inv = Inventory(max_slots=10, max_weight=30.0)
        w1 = _weapon("w1", weight=1.0)
        w2 = _weapon("w2", weight=2.0)
        w3 = _weapon("w3", weight=3.0)
        inv.add(w1)
        inv.add(w2)
        inv.add(w3)
        inv.remove(w2)
        assert inv.total_weight == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# used_slots property
# ---------------------------------------------------------------------------

class TestUsedSlots:
    def test_starts_at_zero(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.used_slots == 0

    def test_increments_after_add(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon())
        assert inv.used_slots == 1

    def test_multiple_increments(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon("w1"))
        inv.add(_weapon("w2"))
        assert inv.used_slots == 2

    def test_decrements_after_remove(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        inv.add(item)
        inv.remove(item)
        assert inv.used_slots == 0

    def test_decrements_after_drop(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        inv.add(item)
        inv.drop(item)
        assert inv.used_slots == 0

    def test_does_not_increment_on_failed_add(self):
        inv = Inventory(max_slots=1, max_weight=100.0)
        inv.add(_weapon("w1"))
        inv.add(_weapon("w2"))  # should fail silently
        assert inv.used_slots == 1


# ---------------------------------------------------------------------------
# equip()
# ---------------------------------------------------------------------------

class TestEquip:
    def test_equip_weapon_sets_equipped_weapon(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        inv.add(w)
        inv.equip(w)
        assert inv.equipped_weapon is w

    def test_equip_armor_sets_equipped_armor(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        a = _armor()
        inv.add(a)
        inv.equip(a)
        assert inv.equipped_armor is a

    def test_equip_consumable_raises_type_error(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        c = _consumable()
        inv.add(c)
        with pytest.raises((TypeError, ValueError)):
            inv.equip(c)

    def test_equip_attachment_raises_type_error(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        a = _attachment()
        inv.add(a)
        with pytest.raises((TypeError, ValueError)):
            inv.equip(a)

    def test_equip_item_not_in_inventory_raises(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()  # never added
        with pytest.raises((ValueError, KeyError)):
            inv.equip(w)

    def test_equip_second_weapon_replaces_first(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w1 = _weapon("w1")
        w2 = _weapon("w2")
        inv.add(w1)
        inv.add(w2)
        inv.equip(w1)
        inv.equip(w2)
        assert inv.equipped_weapon is w2

    def test_equip_chest_armor(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        a = _armor(slot="chest")
        inv.add(a)
        inv.equip(a)
        assert inv.equipped_armor is a

    def test_equip_helmet_armor(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        a = _armor(slot="helmet")
        inv.add(a)
        inv.equip(a)
        assert inv.equipped_armor is a

    def test_equip_weapon_does_not_modify_equipped_armor(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        a = _armor()
        w = _weapon()
        inv.add(a)
        inv.add(w)
        inv.equip(a)
        inv.equip(w)
        assert inv.equipped_armor is a  # armor unchanged


# ---------------------------------------------------------------------------
# unequip()
# ---------------------------------------------------------------------------

class TestUnequip:
    def test_unequip_weapon_clears_equipped_weapon(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        inv.add(w)
        inv.equip(w)
        inv.unequip("weapon")
        assert inv.equipped_weapon is None

    def test_unequip_armor_clears_equipped_armor(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        a = _armor()
        inv.add(a)
        inv.equip(a)
        inv.unequip("armor")
        assert inv.equipped_armor is None

    def test_unequip_keeps_item_in_slots(self):
        """Unequipping must NOT remove the item from the inventory."""
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        inv.add(w)
        inv.equip(w)
        inv.unequip("weapon")
        assert w in inv.slots

    def test_unequip_unknown_category_raises(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        with pytest.raises((ValueError, KeyError)):
            inv.unequip("invalid_category")

    def test_unequip_already_empty_does_not_raise(self):
        """Calling unequip when nothing is equipped should not raise."""
        inv = Inventory(max_slots=5, max_weight=30.0)
        try:
            inv.unequip("weapon")
        except (ValueError, KeyError):
            pytest.fail("unequip on empty slot should not raise")

    def test_unequip_weapon_leaves_armor_intact(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        a = _armor()
        w = _weapon()
        inv.add(a)
        inv.add(w)
        inv.equip(a)
        inv.equip(w)
        inv.unequip("weapon")
        assert inv.equipped_armor is a


# ---------------------------------------------------------------------------
# Default equipped state
# ---------------------------------------------------------------------------

class TestDefaultEquippedState:
    def test_equipped_weapon_is_none_by_default(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.equipped_weapon is None

    def test_equipped_armor_is_none_by_default(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.equipped_armor is None
