"""
Unit tests for Inventory — src/inventory/inventory.py

# Run: pytest tests/test_inventory.py

Covers:
  - add()          : slot-cap enforcement, weight-cap enforcement, return value
  - add_item()     : returns slot index on success, None on failure
  - remove()       : slot freed to None, return value, non-existent item
  - remove_item()  : by slot index; clears linked quick-slot
  - drop()         : returns item, removes from slots, raises on non-existent
  - equip()        : weapon, armor; type guard; item-not-in-inventory guard
  - unequip()      : clears ref, item stays in slots, bad category raises
  - Properties     : is_full, total_weight, used_slots, equipped_weapon, equipped_armor
  - Quick-slots    : assign_quick_slot, quick_slot_item
  - use_consumable : heals player, removes item, returns False on non-consumable
  - clear()        : removes all items and quick-slot refs
  - expand_capacity: grows slot count
  - get_items()    : non-None items
  - get_consumables: consumables only
  - Serialisation  : to_save_list / from_save_list round-trip
  - Collections    : __len__, __iter__, __contains__
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


# ---------------------------------------------------------------------------
# add_item() — returns slot index
# ---------------------------------------------------------------------------

class TestAddItem:
    def test_add_item_returns_integer_slot_index(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        idx = inv.add_item(_weapon())
        assert isinstance(idx, int)

    def test_add_item_first_item_lands_in_slot_0(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        idx = inv.add_item(_weapon())
        assert idx == 0

    def test_add_item_second_item_lands_in_slot_1(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add_item(_weapon("w1"))
        idx = inv.add_item(_weapon("w2"))
        assert idx == 1

    def test_add_item_returns_none_when_slots_full(self):
        inv = Inventory(max_slots=1, max_weight=100.0)
        inv.add_item(_weapon("w1"))
        idx = inv.add_item(_weapon("w2"))
        assert idx is None

    def test_add_item_returns_none_when_weight_exceeded(self):
        inv = Inventory(max_slots=10, max_weight=1.0)
        inv.add_item(_weapon("w1", weight=1.0))
        idx = inv.add_item(_weapon("w2", weight=0.5))
        assert idx is None

    def test_item_at_returned_index_is_the_added_item(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        idx = inv.add_item(item)
        assert inv.item_at(idx) is item


# ---------------------------------------------------------------------------
# remove_item() — by slot index
# ---------------------------------------------------------------------------

class TestRemoveItem:
    def test_remove_item_returns_the_item(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        idx = inv.add_item(item)
        returned = inv.remove_item(idx)
        assert returned is item

    def test_remove_item_clears_the_slot(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        idx = inv.add_item(item)
        inv.remove_item(idx)
        assert inv.item_at(idx) is None

    def test_remove_item_by_out_of_range_index_returns_none(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.remove_item(99) is None

    def test_remove_item_clears_linked_quick_slot(self):
        """When an inventory slot that is assigned to a quick-slot is removed,
        the quick-slot reference must also be cleared."""
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _consumable()
        idx = inv.add_item(item)
        inv.assign_quick_slot(idx, 0)       # quick-slot 0 → inv slot idx
        inv.remove_item(idx)
        assert inv.quick_slots[0] is None

    def test_remove_item_does_not_affect_other_slots(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w1 = _weapon("w1")
        w2 = _weapon("w2")
        inv.add_item(w1)
        idx2 = inv.add_item(w2)
        inv.remove_item(0)
        assert inv.item_at(idx2) is w2


# ---------------------------------------------------------------------------
# Quick-slot management: assign_quick_slot / quick_slot_item
# ---------------------------------------------------------------------------

class TestQuickSlots:
    def test_quick_slot_item_returns_none_when_unassigned(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.quick_slot_item(0) is None

    def test_quick_slot_item_returns_item_after_assignment(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _consumable()
        inv.add_item(item)
        inv.assign_quick_slot(0, 0)
        assert inv.quick_slot_item(0) is item

    def test_assign_quick_slot_out_of_range_does_nothing(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add_item(_consumable())
        inv.assign_quick_slot(0, 99)        # qs_idx 99 is invalid
        assert all(qs is None for qs in inv.quick_slots)

    def test_four_independent_quick_slots(self):
        inv = Inventory(max_slots=24, max_weight=30.0)
        items = [_consumable(f"c{i}", weight=0.2) for i in range(4)]
        for item in items:
            inv.add_item(item)
        for qs in range(4):
            inv.assign_quick_slot(qs, qs)
        for qs in range(4):
            assert inv.quick_slot_item(qs) is items[qs]

    def test_reassigning_quick_slot_replaces_previous_assignment(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        c1 = _consumable("c1")
        c2 = _consumable("c2")
        inv.add_item(c1)   # slot 0
        inv.add_item(c2)   # slot 1
        inv.assign_quick_slot(0, 0)
        inv.assign_quick_slot(1, 0)    # reassign quick-slot 0 to slot 1
        assert inv.quick_slot_item(0) is c2

    def test_quick_slot_item_out_of_range_returns_none(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.quick_slot_item(-1) is None
        assert inv.quick_slot_item(4) is None


# ---------------------------------------------------------------------------
# use_consumable()
# ---------------------------------------------------------------------------

class TestUseConsumable:
    """Consumable use integrates with a stub Player that exposes heal()."""

    class _StubPlayer:
        def __init__(self):
            self.health = 50
            self.max_health = 100

        def heal(self, amount: int) -> int:
            gained = min(amount, self.max_health - self.health)
            self.health += gained
            return gained

    def test_use_consumable_returns_true_on_success(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        from src.inventory.item import Consumable as C
        c = C(id="kit", name="Kit", rarity="common", weight=0.5, base_value=50,
              consumable_type="heal", heal_amount=30, stats={}, sprite_path="")
        inv.add_item(c)
        inv.assign_quick_slot(0, 0)
        assert inv.use_consumable(0, self._StubPlayer()) is True

    def test_use_consumable_heals_player(self):
        from src.inventory.item import Consumable as C
        inv = Inventory(max_slots=5, max_weight=30.0)
        c = C(id="kit", name="Kit", rarity="common", weight=0.5, base_value=50,
              consumable_type="heal", heal_amount=30, stats={}, sprite_path="")
        inv.add_item(c)
        inv.assign_quick_slot(0, 0)
        player = self._StubPlayer()
        inv.use_consumable(0, player)
        assert player.health == 80

    def test_use_consumable_removes_item_after_use(self):
        from src.inventory.item import Consumable as C
        inv = Inventory(max_slots=5, max_weight=30.0)
        c = C(id="kit", name="Kit", rarity="common", weight=0.5, base_value=50,
              consumable_type="heal", heal_amount=30, stats={}, sprite_path="")
        inv.add_item(c)
        inv.assign_quick_slot(0, 0)
        inv.use_consumable(0, self._StubPlayer())
        assert c not in inv.slots

    def test_use_consumable_returns_false_when_quick_slot_empty(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.use_consumable(0, self._StubPlayer()) is False

    def test_use_consumable_returns_false_for_non_consumable_item(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        inv.add_item(w)
        inv.assign_quick_slot(0, 0)
        assert inv.use_consumable(0, self._StubPlayer()) is False


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------

class TestClear:
    def test_clear_removes_all_items(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon("w1"))
        inv.add(_weapon("w2"))
        inv.clear()
        assert inv.used_slots == 0

    def test_clear_resets_quick_slots(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add_item(_consumable())
        inv.assign_quick_slot(0, 0)
        inv.clear()
        assert all(qs is None for qs in inv.quick_slots)

    def test_clear_resets_equipped_weapon(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        inv.add(w)
        inv.equip(w)
        inv.clear()
        assert inv.equipped_weapon is None

    def test_clear_resets_equipped_armor(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        a = _armor()
        inv.add(a)
        inv.equip(a)
        inv.clear()
        assert inv.equipped_armor is None

    def test_clear_allows_re_adding_items(self):
        inv = Inventory(max_slots=2, max_weight=100.0)
        inv.add(_weapon("w1"))
        inv.add(_weapon("w2"))
        inv.clear()
        assert inv.add(_weapon("w3")) is True
        assert inv.add(_weapon("w4")) is True


# ---------------------------------------------------------------------------
# expand_capacity()
# ---------------------------------------------------------------------------

class TestExpandCapacity:
    def test_expand_capacity_increases_capacity(self):
        inv = Inventory(max_slots=24, max_weight=100.0)
        inv.expand_capacity(4)
        assert inv.capacity == 28

    def test_expanded_slots_can_hold_items(self):
        inv = Inventory(max_slots=2, max_weight=100.0)
        inv.add(_weapon("w1"))
        inv.add(_weapon("w2"))
        inv.expand_capacity(2)
        assert inv.add(_weapon("w3")) is True

    def test_expand_by_zero_does_not_change_capacity(self):
        inv = Inventory(max_slots=24, max_weight=100.0)
        inv.expand_capacity(0)
        assert inv.capacity == 24

    def test_expand_preserves_existing_items(self):
        inv = Inventory(max_slots=3, max_weight=100.0)
        w = _weapon()
        inv.add(w)
        inv.expand_capacity(5)
        assert w in inv.slots


# ---------------------------------------------------------------------------
# get_items() and get_consumables()
# ---------------------------------------------------------------------------

class TestGetItems:
    def test_get_items_returns_empty_list_when_inventory_empty(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.get_items() == []

    def test_get_items_returns_all_added_items(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        a = _armor()
        inv.add(w)
        inv.add(a)
        items = inv.get_items()
        assert w in items
        assert a in items

    def test_get_items_excludes_none_slots(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon())
        items = inv.get_items()
        assert None not in items

    def test_get_consumables_returns_only_consumables(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        c = _consumable()
        inv.add(w)
        inv.add(c)
        consumables = inv.get_consumables()
        assert c in consumables
        assert w not in consumables

    def test_get_consumables_returns_empty_list_when_none_present(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon())
        assert inv.get_consumables() == []


# ---------------------------------------------------------------------------
# Serialisation: to_save_list / from_save_list
# ---------------------------------------------------------------------------

class TestSerialisation:
    def test_to_save_list_returns_list_of_dicts(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon())
        result = inv.to_save_list()
        assert isinstance(result, list)
        assert all(isinstance(d, dict) for d in result)

    def test_to_save_list_empty_inventory_returns_empty_list(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert inv.to_save_list() == []

    def test_to_save_list_includes_item_id(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon(id="my_pistol"))
        saved = inv.to_save_list()
        assert saved[0]["item_id"] == "my_pistol"

    def test_to_save_list_includes_item_type(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon())
        saved = inv.to_save_list()
        assert saved[0]["item_type"] == "weapon"

    def test_from_save_list_restores_correct_number_of_items(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon("w1"))
        inv.add(_armor("a1"))
        saved = inv.to_save_list()

        inv2 = Inventory(max_slots=5, max_weight=30.0)
        inv2.from_save_list(saved)
        assert inv2.used_slots == 2

    def test_from_save_list_restores_item_id(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon(id="pistol_01"))
        saved = inv.to_save_list()

        inv2 = Inventory(max_slots=5, max_weight=30.0)
        inv2.from_save_list(saved)
        ids = [item.item_id for item in inv2.get_items()]
        assert "pistol_01" in ids

    def test_from_save_list_clears_existing_items_first(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon("old"))
        inv.from_save_list([])      # empty list → should clear all
        assert inv.used_slots == 0

    def test_round_trip_preserves_item_count(self):
        inv = Inventory(max_slots=24, max_weight=50.0)
        for i in range(5):
            inv.add(_weapon(f"w{i}", weight=0.5))
        saved = inv.to_save_list()

        inv2 = Inventory(max_slots=24, max_weight=50.0)
        inv2.from_save_list(saved)
        assert inv2.used_slots == 5


# ---------------------------------------------------------------------------
# Collection protocols: __len__, __iter__, __contains__
# ---------------------------------------------------------------------------

class TestCollectionProtocols:
    def test_len_of_empty_inventory_is_zero(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert len(inv) == 0

    def test_len_increases_with_added_items(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        inv.add(_weapon("w1"))
        inv.add(_armor("a1"))
        assert len(inv) == 2

    def test_len_decreases_after_remove(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        item = _weapon()
        inv.add(item)
        inv.remove(item)
        assert len(inv) == 0

    def test_iter_yields_only_non_none_items(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        inv.add(w)
        items = list(inv)
        assert w in items
        assert None not in items

    def test_iter_empty_inventory_yields_nothing(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        assert list(inv) == []

    def test_contains_returns_true_for_added_item(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        inv.add(w)
        assert w in inv

    def test_contains_returns_false_for_absent_item(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        assert w not in inv

    def test_contains_returns_false_after_remove(self):
        inv = Inventory(max_slots=5, max_weight=30.0)
        w = _weapon()
        inv.add(w)
        inv.remove(w)
        assert w not in inv
