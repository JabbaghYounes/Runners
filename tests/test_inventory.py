"""Unit tests for Inventory — slot management, capacity expansion, quick-slots."""
from __future__ import annotations

import pytest

from src.inventory.inventory import Inventory
from src.inventory.item import Consumable, Item, Weapon


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(item_id: str = "test_item", name: str = "Test Item") -> Item:
    return Item(item_id=item_id, name=name)


def _consumable(item_id: str = "medkit", heal_amount: int = 50) -> Consumable:
    return Consumable(item_id=item_id, name="Medkit", stats={"heal_amount": heal_amount})


# ---------------------------------------------------------------------------
# TestInventoryDefaults
# ---------------------------------------------------------------------------

class TestInventoryDefaults:
    def test_default_capacity_is_24(self):
        inv = Inventory()
        assert len(inv.slots) == 24

    def test_custom_capacity(self):
        inv = Inventory(capacity=10)
        assert len(inv.slots) == 10

    def test_all_slots_start_empty(self):
        inv = Inventory()
        assert all(s is None for s in inv.slots)

    def test_quick_slots_initialized_to_none(self):
        inv = Inventory()
        assert inv.quick_slots == [None, None, None, None]

    def test_quick_slots_has_four_entries(self):
        inv = Inventory()
        assert len(inv.quick_slots) == 4

    def test_zero_capacity_inventory(self):
        inv = Inventory(capacity=0)
        assert len(inv.slots) == 0


# ---------------------------------------------------------------------------
# TestAddItem
# ---------------------------------------------------------------------------

class TestAddItem:
    def test_add_item_returns_slot_index(self):
        inv = Inventory()
        idx = inv.add_item(_item())
        assert idx == 0

    def test_add_item_places_item_in_first_slot(self):
        inv = Inventory()
        item = _item()
        inv.add_item(item)
        assert inv.slots[0] is item

    def test_add_second_item_goes_to_next_slot(self):
        inv = Inventory()
        inv.add_item(_item("item_a", "A"))
        idx = inv.add_item(_item("item_b", "B"))
        assert idx == 1

    def test_add_item_to_full_inventory_returns_none(self):
        inv = Inventory(capacity=1)
        inv.add_item(_item())
        result = inv.add_item(_item("extra", "Extra"))
        assert result is None

    def test_add_item_fills_gaps(self):
        inv = Inventory(capacity=3)
        inv.add_item(_item("a", "A"))
        inv.add_item(_item("b", "B"))
        inv.add_item(_item("c", "C"))
        # Remove slot 1
        inv.remove_item(1)
        idx = inv.add_item(_item("d", "D"))
        assert idx == 1  # gap at slot 1 is re-used

    def test_item_at_matches_add_item_result(self):
        inv = Inventory()
        item = _item()
        idx = inv.add_item(item)
        assert inv.item_at(idx) is item


# ---------------------------------------------------------------------------
# TestRemoveItem
# ---------------------------------------------------------------------------

class TestRemoveItem:
    def test_remove_item_returns_item(self):
        inv = Inventory()
        item = _item()
        inv.add_item(item)
        removed = inv.remove_item(0)
        assert removed is item

    def test_remove_item_empties_slot(self):
        inv = Inventory()
        inv.add_item(_item())
        inv.remove_item(0)
        assert inv.item_at(0) is None

    def test_remove_from_empty_slot_returns_none(self):
        inv = Inventory()
        assert inv.remove_item(0) is None

    def test_remove_clears_quick_slot_link(self):
        inv = Inventory()
        inv.add_item(_item())          # slot 0
        inv.assign_quick_slot(0, 2)    # QS[2] → slot 0
        inv.remove_item(0)
        assert inv.quick_slots[2] is None

    def test_remove_does_not_clear_other_quick_slot_links(self):
        inv = Inventory()
        inv.add_item(_item("a", "A"))  # slot 0
        inv.add_item(_item("b", "B"))  # slot 1
        inv.assign_quick_slot(0, 0)   # QS[0] → slot 0
        inv.assign_quick_slot(1, 1)   # QS[1] → slot 1
        inv.remove_item(0)
        assert inv.quick_slots[1] == 1  # unaffected

    def test_remove_out_of_range_returns_none(self):
        inv = Inventory(capacity=5)
        assert inv.remove_item(-1) is None
        assert inv.remove_item(5) is None
        assert inv.remove_item(100) is None


# ---------------------------------------------------------------------------
# TestItemAt
# ---------------------------------------------------------------------------

class TestItemAt:
    def test_item_at_out_of_range_returns_none(self):
        inv = Inventory(capacity=5)
        assert inv.item_at(-1) is None
        assert inv.item_at(5) is None

    def test_item_at_returns_correct_item(self):
        inv = Inventory()
        item_a = _item("a", "A")
        item_b = _item("b", "B")
        inv.add_item(item_a)
        inv.add_item(item_b)
        assert inv.item_at(0) is item_a
        assert inv.item_at(1) is item_b

    def test_item_at_empty_slot_returns_none(self):
        inv = Inventory()
        assert inv.item_at(0) is None


# ---------------------------------------------------------------------------
# TestQuickSlots
# ---------------------------------------------------------------------------

class TestQuickSlots:
    def test_assign_quick_slot_links_to_inventory_slot(self):
        inv = Inventory()
        item = _item()
        inv.add_item(item)
        inv.assign_quick_slot(0, 1)
        assert inv.quick_slot_item(1) is item

    def test_assign_quick_slot_out_of_range_is_noop(self):
        inv = Inventory()
        inv.add_item(_item())
        inv.assign_quick_slot(0, -1)  # no-op
        inv.assign_quick_slot(0, 4)   # no-op
        # quick_slots unchanged
        assert inv.quick_slots == [None, None, None, None]

    def test_quick_slot_item_returns_none_when_unassigned(self):
        inv = Inventory()
        assert inv.quick_slot_item(0) is None

    def test_quick_slot_item_out_of_range_returns_none(self):
        inv = Inventory()
        assert inv.quick_slot_item(-1) is None
        assert inv.quick_slot_item(4) is None

    def test_quick_slot_item_returns_none_when_slot_empty(self):
        inv = Inventory()
        inv.assign_quick_slot(0, 0)  # QS[0] → slot 0, but slot 0 is empty
        assert inv.quick_slot_item(0) is None


# ---------------------------------------------------------------------------
# TestExpandCapacity
# ---------------------------------------------------------------------------

class TestExpandCapacity:
    def test_expand_capacity_increases_slot_count(self):
        inv = Inventory(capacity=10)
        inv.expand_capacity(5)
        assert len(inv.slots) == 15

    def test_expand_capacity_new_slots_are_none(self):
        inv = Inventory(capacity=2)
        inv.expand_capacity(3)
        # The three appended slots should all be empty
        assert all(s is None for s in inv.slots[2:])

    def test_expand_capacity_zero_is_noop(self):
        inv = Inventory(capacity=10)
        inv.expand_capacity(0)
        assert len(inv.slots) == 10

    def test_expand_capacity_negative_is_noop(self):
        inv = Inventory(capacity=10)
        inv.expand_capacity(-5)
        assert len(inv.slots) == 10

    def test_expand_capacity_large_value(self):
        inv = Inventory(capacity=24)
        inv.expand_capacity(100)
        assert len(inv.slots) == 124

    def test_expand_capacity_preserves_existing_items(self):
        inv = Inventory(capacity=3)
        item = _item()
        inv.add_item(item)
        inv.expand_capacity(5)
        assert inv.item_at(0) is item

    def test_expand_capacity_allows_adding_items_to_new_slots(self):
        inv = Inventory(capacity=1)
        inv.add_item(_item("a", "A"))   # fills slot 0
        inv.expand_capacity(2)
        idx = inv.add_item(_item("b", "B"))
        assert idx == 1  # new slot 1 is available

    def test_expand_capacity_multiple_calls_are_cumulative(self):
        inv = Inventory(capacity=10)
        inv.expand_capacity(5)
        inv.expand_capacity(5)
        assert len(inv.slots) == 20

    def test_expand_capacity_updates_internal_capacity(self):
        """_capacity counter tracks the expanded size."""
        inv = Inventory(capacity=10)
        inv.expand_capacity(4)
        assert inv._capacity == 14


# ---------------------------------------------------------------------------
# TestSlotsProperty
# ---------------------------------------------------------------------------

class TestSlotsProperty:
    def test_slots_is_a_list(self):
        inv = Inventory()
        assert isinstance(inv.slots, list)

    def test_slots_returns_copy_not_reference(self):
        inv = Inventory()
        snap = inv.slots
        snap[0] = _item()  # mutate the snapshot
        # The internal list should be unchanged
        assert inv.item_at(0) is None

    def test_slots_length_equals_capacity(self):
        inv = Inventory(capacity=8)
        assert len(inv.slots) == 8


# ---------------------------------------------------------------------------
# TestToSaveList
# ---------------------------------------------------------------------------

class TestToSaveList:
    def test_empty_inventory_saves_empty_list(self):
        inv = Inventory()
        assert inv.to_save_list() == []

    def test_single_item_is_serialised(self):
        inv = Inventory()
        item = Item(item_id="pistol", name="Pistol", quantity=1)
        inv.add_item(item)
        result = inv.to_save_list()
        assert len(result) == 1
        assert result[0]["item_id"] == "pistol"
        assert result[0]["quantity"] == 1

    def test_only_non_none_slots_are_serialised(self):
        inv = Inventory(capacity=5)
        inv.add_item(_item("a", "A"))
        # 4 slots remain empty → only 1 item in save list
        result = inv.to_save_list()
        assert len(result) == 1

    def test_multiple_items_all_serialised(self):
        inv = Inventory(capacity=3)
        inv.add_item(Item(item_id="a", name="A", quantity=1))
        inv.add_item(Item(item_id="b", name="B", quantity=3))
        inv.add_item(Item(item_id="c", name="C", quantity=2))
        result = inv.to_save_list()
        assert len(result) == 3
        ids = {r["item_id"] for r in result}
        assert ids == {"a", "b", "c"}
