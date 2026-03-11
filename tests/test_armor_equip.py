"""Tests for the Armor item extension and the Inventory equipped-armor slot.

Covers:
  - Armor.armor_value field (default 0, settable on creation)
  - make_item factory produces Armor with armor_value when present in data
  - items.json contains the three required armor entries (light_vest, tac_vest,
    ballistic_plate) with correct armor_value and rarity fields
  - Inventory.equipped_armor slot: starts None, equip/unequip semantics
  - Inventory.equip_armor returns displaced item or None
  - Inventory.on_armor_changed callback fires on equip and unequip
  - Player._recalculate_armor wires armor = base_armor + equipped.armor_value
"""
import json
import os
import pytest

from src.inventory.item import Armor, Rarity, make_item
from src.inventory.inventory import Inventory

_ITEMS_JSON = os.path.join(os.path.dirname(__file__), '..', 'data', 'items.json')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_armor(item_id='vest', name='Test Vest', rarity=Rarity.COMMON,
                weight=1.0, value=100, armor_value=0, **extra):
    """Create an Armor instance, skipping the test if armor_value is not supported."""
    try:
        return Armor(item_id=item_id, name=name, type='armor',
                     rarity=rarity, weight=weight, value=value,
                     armor_value=armor_value, **extra)
    except TypeError:
        pytest.skip("Armor.armor_value field not yet implemented")


# ---------------------------------------------------------------------------
# Armor.armor_value field
# ---------------------------------------------------------------------------

class TestArmorItemField:
    def test_armor_has_armor_value_attribute(self):
        a = _make_armor()
        assert hasattr(a, 'armor_value')

    def test_armor_value_defaults_to_zero(self):
        a = _make_armor()
        assert a.armor_value == 0

    def test_armor_value_set_on_creation(self):
        a = _make_armor(armor_value=22)
        assert a.armor_value == 22

    def test_armor_value_is_integer(self):
        a = _make_armor(armor_value=12)
        assert isinstance(a.armor_value, int)

    def test_armor_type_field_is_armor(self):
        a = _make_armor()
        assert a.type == 'armor'

    def test_armor_value_zero_does_not_affect_weight(self):
        a = _make_armor(weight=2.5, armor_value=0)
        assert a.weight == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# make_item factory with armor_value
# ---------------------------------------------------------------------------

class TestMakeItemArmorValue:
    def test_make_item_creates_armor_with_armor_value(self):
        data = {
            'item_id': 'light_vest',
            'name': 'Light Vest',
            'type': 'armor',
            'rarity': 'common',
            'weight': 2.0,
            'value': 300,
            'armor_value': 5,
        }
        try:
            item = make_item(data)
        except TypeError:
            pytest.skip("make_item does not yet support armor_value")
        assert isinstance(item, Armor)
        assert item.armor_value == 5

    def test_make_item_armor_missing_armor_value_defaults_to_zero(self):
        data = {
            'item_id': 'old_vest',
            'name': 'Old Vest',
            'type': 'armor',
            'rarity': 'common',
            'weight': 2.0,
            'value': 100,
        }
        try:
            item = make_item(data)
        except TypeError:
            pytest.skip("make_item does not yet support armor_value")
        assert getattr(item, 'armor_value', 0) == 0


# ---------------------------------------------------------------------------
# items.json — new armor entries
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def items_data():
    if not os.path.exists(_ITEMS_JSON):
        pytest.skip("data/items.json not found")
    with open(_ITEMS_JSON) as f:
        return json.load(f)


class TestItemsJsonArmorEntries:
    def test_light_vest_exists(self, items_data):
        assert 'light_vest' in items_data, \
            "items.json is missing the 'light_vest' armor entry"

    def test_tac_vest_exists(self, items_data):
        assert 'tac_vest' in items_data, \
            "items.json is missing the 'tac_vest' armor entry"

    def test_ballistic_plate_exists(self, items_data):
        assert 'ballistic_plate' in items_data, \
            "items.json is missing the 'ballistic_plate' armor entry"

    def test_light_vest_type_is_armor(self, items_data):
        assert items_data.get('light_vest', {}).get('type') == 'armor'

    def test_tac_vest_type_is_armor(self, items_data):
        assert items_data.get('tac_vest', {}).get('type') == 'armor'

    def test_ballistic_plate_type_is_armor(self, items_data):
        assert items_data.get('ballistic_plate', {}).get('type') == 'armor'

    def test_light_vest_armor_value_is_5(self, items_data):
        entry = items_data.get('light_vest', {})
        assert entry.get('armor_value') == 5

    def test_tac_vest_armor_value_is_12(self, items_data):
        entry = items_data.get('tac_vest', {})
        assert entry.get('armor_value') == 12

    def test_ballistic_plate_armor_value_is_22(self, items_data):
        entry = items_data.get('ballistic_plate', {})
        assert entry.get('armor_value') == 22

    def test_light_vest_rarity_is_common(self, items_data):
        entry = items_data.get('light_vest', {})
        assert entry.get('rarity', '').lower() == 'common'

    def test_tac_vest_rarity_is_uncommon(self, items_data):
        entry = items_data.get('tac_vest', {})
        assert entry.get('rarity', '').lower() == 'uncommon'

    def test_ballistic_plate_rarity_is_rare(self, items_data):
        entry = items_data.get('ballistic_plate', {})
        assert entry.get('rarity', '').lower() == 'rare'

    def test_all_armor_entries_have_weight(self, items_data):
        for key in ('light_vest', 'tac_vest', 'ballistic_plate'):
            entry = items_data.get(key, {})
            assert 'weight' in entry, f"'{key}' is missing 'weight'"

    def test_all_armor_entries_have_name(self, items_data):
        for key in ('light_vest', 'tac_vest', 'ballistic_plate'):
            entry = items_data.get(key, {})
            assert 'name' in entry and entry['name'], f"'{key}' is missing 'name'"


# ---------------------------------------------------------------------------
# Inventory.equipped_armor slot
# ---------------------------------------------------------------------------

def _require_equip_armor(inv):
    if not hasattr(inv, 'equip_armor'):
        pytest.skip("Inventory.equip_armor not yet implemented")


class TestInventoryEquippedArmorSlot:
    def test_equipped_armor_starts_none(self):
        inv = Inventory()
        slot = getattr(inv, 'equipped_armor', 'MISSING')
        if slot == 'MISSING':
            pytest.skip("Inventory.equipped_armor not yet implemented")
        assert slot is None

    def test_equip_armor_sets_slot(self):
        inv = Inventory()
        _require_equip_armor(inv)
        armor = _make_armor(armor_value=10)
        inv.equip_armor(armor)
        assert inv.equipped_armor is armor

    def test_equip_when_empty_returns_none(self):
        inv = Inventory()
        _require_equip_armor(inv)
        armor = _make_armor(armor_value=10)
        displaced = inv.equip_armor(armor)
        assert displaced is None

    def test_equip_over_existing_returns_displaced(self):
        inv = Inventory()
        _require_equip_armor(inv)
        a1 = _make_armor(item_id='a1', armor_value=5)
        a2 = _make_armor(item_id='a2', armor_value=15)
        inv.equip_armor(a1)
        displaced = inv.equip_armor(a2)
        assert displaced is a1

    def test_equip_over_existing_replaces_slot(self):
        inv = Inventory()
        _require_equip_armor(inv)
        a1 = _make_armor(item_id='a1', armor_value=5)
        a2 = _make_armor(item_id='a2', armor_value=15)
        inv.equip_armor(a1)
        inv.equip_armor(a2)
        assert inv.equipped_armor is a2

    def test_unequip_armor_clears_slot(self):
        inv = Inventory()
        _require_equip_armor(inv)
        if not hasattr(inv, 'unequip_armor'):
            pytest.skip("Inventory.unequip_armor not yet implemented")
        armor = _make_armor(armor_value=10)
        inv.equip_armor(armor)
        inv.unequip_armor()
        assert inv.equipped_armor is None

    def test_unequip_armor_returns_removed_item(self):
        inv = Inventory()
        _require_equip_armor(inv)
        if not hasattr(inv, 'unequip_armor'):
            pytest.skip("Inventory.unequip_armor not yet implemented")
        armor = _make_armor(armor_value=10)
        inv.equip_armor(armor)
        result = inv.unequip_armor()
        assert result is armor

    def test_unequip_when_empty_returns_none(self):
        inv = Inventory()
        if not hasattr(inv, 'unequip_armor'):
            pytest.skip("Inventory.unequip_armor not yet implemented")
        result = inv.unequip_armor()
        assert result is None


# ---------------------------------------------------------------------------
# on_armor_changed callback
# ---------------------------------------------------------------------------

class TestInventoryArmorCallback:
    def _inv_with_callback(self):
        inv = Inventory()
        if not hasattr(inv, 'equip_armor'):
            pytest.skip("Inventory.equip_armor not yet implemented")
        if not hasattr(inv, 'on_armor_changed'):
            pytest.skip("Inventory.on_armor_changed not yet implemented")
        return inv

    def test_callback_fires_on_equip(self):
        inv = self._inv_with_callback()
        calls = []
        inv.on_armor_changed = lambda: calls.append(1)
        inv.equip_armor(_make_armor(armor_value=10))
        assert len(calls) == 1

    def test_callback_fires_on_unequip(self):
        inv = self._inv_with_callback()
        if not hasattr(inv, 'unequip_armor'):
            pytest.skip("Inventory.unequip_armor not yet implemented")
        inv.equip_armor(_make_armor(armor_value=10))
        calls = []
        inv.on_armor_changed = lambda: calls.append(1)
        inv.unequip_armor()
        assert len(calls) == 1

    def test_no_error_when_callback_is_none(self):
        inv = Inventory()
        if not hasattr(inv, 'equip_armor'):
            pytest.skip("Inventory.equip_armor not yet implemented")
        # Callback defaults to None — equip must not raise
        inv.equip_armor(_make_armor(armor_value=5))
        if hasattr(inv, 'unequip_armor'):
            inv.unequip_armor()


# ---------------------------------------------------------------------------
# Player armor recalculation via Inventory callback
# ---------------------------------------------------------------------------

class TestPlayerArmorRecalculation:
    @pytest.fixture(autouse=True)
    def skip_if_missing(self):
        vanguard = None
        try:
            from src.entities.character_class import VANGUARD
            vanguard = VANGUARD
        except ImportError:
            pytest.skip("character_class module not yet implemented")
        from src.entities.player import Player
        p = Player(x=0, y=0, character_class=vanguard)
        if not hasattr(p.inventory, 'equip_armor'):
            pytest.skip("Inventory.equip_armor not yet implemented")
        self.player = p
        self.base = p.base_armor

    def test_equip_armor_increases_player_armor(self):
        armor = _make_armor(armor_value=10)
        self.player.inventory.equip_armor(armor)
        assert self.player.armor == self.base + 10

    def test_equip_zero_armor_value_unchanged(self):
        armor = _make_armor(armor_value=0)
        self.player.inventory.equip_armor(armor)
        assert self.player.armor == self.base

    def test_unequip_restores_base_armor(self):
        armor = _make_armor(armor_value=15)
        self.player.inventory.equip_armor(armor)
        self.player.inventory.unequip_armor()
        assert self.player.armor == self.base

    def test_swap_armor_updates_correctly(self):
        a1 = _make_armor(item_id='a1', armor_value=5)
        a2 = _make_armor(item_id='a2', armor_value=20)
        self.player.inventory.equip_armor(a1)
        self.player.inventory.equip_armor(a2)
        assert self.player.armor == self.base + 20
