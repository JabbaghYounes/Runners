"""Tests for the armor-equip feature — complementing test_armor_equip.py.

Covers gaps not already addressed by that file:

  Unit (≈60 %):
    - Armor.armor_rating as the canonical feature-plan property name
    - equip_armor() raises TypeError for non-Armor arguments
    - Inventory.clear() resets equipped_armor slot
    - Inventory.to_save_list() appends equipped-armor sentinel entry
    - Inventory.from_save_list() restores equipped armor and fires callback
    - EventBus events: armor_equipped / armor_unequipped
    - Player.take_damage() no longer self-applies armor (new contract)
    - Player.get_effective_armor() returns float(self.armor)

  Integration (≈30 %):
    - Player.__init__ wires on_armor_changed to _recalculate_armor
    - Full equip → player.armor update chain via callback
    - CombatSystem armor pipeline: effective = max(1, raw − armor)
    - Inventory save/load round-trip preserves equipped armor item
    - InventoryScreen click handlers call equip/unequip correctly

  E2E (≈10 %):
    - Player equips armor → CombatSystem hit → damage is reduced
    - Equip → save → load → player.armor still active → combat reduced
    - Swap armor → CombatSystem uses new piece's rating

# Run: pytest tests/test_armor_feature.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pygame
import pytest

from src.inventory.item import (
    Armor, Attachment, Consumable, Item, Rarity, Weapon, make_item,
)
from src.inventory.inventory import Inventory
from src.entities.player import Player
from src.systems.combat import CombatSystem
from src.entities.projectile import Projectile


# ---------------------------------------------------------------------------
# Shared item factories
# ---------------------------------------------------------------------------

def _armor(item_id: str = "vest", armor_rating: int = 10,
           rarity: Rarity = Rarity.COMMON, weight: float = 2.0) -> Armor:
    return Armor(item_id=item_id, name="Test Vest",
                 rarity=rarity, weight=weight, value=200,
                 armor_value=armor_rating)


def _weapon_item() -> Weapon:
    return Weapon(item_id="pistol", name="Pistol",
                  rarity=Rarity.COMMON, weight=1.5, value=100)


def _consumable_item() -> Consumable:
    return Consumable(item_id="medkit", name="Medkit",
                      rarity=Rarity.COMMON, weight=0.5, value=50,
                      consumable_type="heal", heal_amount=50)


def _plain_item() -> Item:
    return Item(item_id="junk", name="Junk",
                item_type="loot", rarity=Rarity.COMMON, weight=0.1, value=10)


def _player() -> Player:
    return Player(x=0, y=0)


def _overlapping_proj(target, damage: int = 30, owner=None) -> Projectile:
    """Return a live Projectile whose rect overlaps target.rect."""
    return Projectile(target.rect.x, target.rect.y, vx=0, vy=0,
                      damage=damage, owner=owner)


def _hp(player: Player) -> int:
    return getattr(player, "current_health", player.health)


# ---------------------------------------------------------------------------
# EventBus capture helper
# ---------------------------------------------------------------------------

class _CapturedEvents:
    """Subscribe to global event_bus for one or more events; unsubscribe on exit."""

    def __init__(self, *event_names: str) -> None:
        self._names = event_names
        self.received: dict[str, list[dict]] = {n: [] for n in event_names}
        self._handlers: dict[str, object] = {}

    def _make_handler(self, name: str):
        received = self.received[name]

        def _h(**kwargs):
            received.append(kwargs)
        return _h

    def __enter__(self) -> "_CapturedEvents":
        from src.core.event_bus import event_bus
        for name in self._names:
            h = self._make_handler(name)
            self._handlers[name] = h
            event_bus.subscribe(name, h)
        return self

    def __exit__(self, *_) -> None:
        from src.core.event_bus import event_bus
        for name, h in self._handlers.items():
            event_bus.unsubscribe(name, h)

    def count(self, name: str) -> int:
        return len(self.received[name])

    def first(self, name: str) -> dict:
        return self.received[name][0]


# ============================================================================
# UNIT TESTS  (~60 %)
# ============================================================================

# ---------------------------------------------------------------------------
# Armor.armor_rating property
# ---------------------------------------------------------------------------

class TestArmorRatingProperty:
    """armor_rating is the canonical name referenced throughout the feature plan
    and consumed by Player._recalculate_armor().  It must be identical to
    armor_value."""

    def test_armor_rating_equals_armor_value(self):
        a = _armor(armor_rating=15)
        assert a.armor_rating == a.armor_value

    def test_armor_rating_defaults_to_zero(self):
        a = Armor(item_id="x", name="X", rarity="common", weight=1.0, value=50)
        assert a.armor_rating == 0

    def test_armor_rating_is_int(self):
        a = _armor(armor_rating=22)
        assert isinstance(a.armor_rating, int)

    def test_armor_rating_reflects_value_set_on_construction(self):
        a = _armor(armor_rating=12)
        assert a.armor_rating == 12

    def test_armor_rating_falls_back_to_stats_dict_when_no_constructor_value(self):
        """When armor_value is not given, the rating can live in stats."""
        a = Armor(item_id="x", name="X", rarity="common", weight=1.0,
                  value=50, stats={"armor": 8})
        assert a.armor_rating == 8

    def test_higher_rating_is_strictly_greater(self):
        light = _armor(armor_rating=5)
        tac = _armor(armor_rating=12)
        ballistic = _armor(armor_rating=22)
        assert ballistic.armor_rating > tac.armor_rating > light.armor_rating

    def test_zero_armor_rating_is_valid(self):
        a = _armor(armor_rating=0)
        assert a.armor_rating == 0


# ---------------------------------------------------------------------------
# equip_armor() type-guard
# ---------------------------------------------------------------------------

class TestEquipArmorTypeGuard:
    """equip_armor() must raise TypeError for anything that is not an Armor."""

    def test_raises_for_weapon(self):
        inv = Inventory()
        with pytest.raises(TypeError):
            inv.equip_armor(_weapon_item())

    def test_raises_for_consumable(self):
        inv = Inventory()
        with pytest.raises(TypeError):
            inv.equip_armor(_consumable_item())

    def test_raises_for_plain_item(self):
        inv = Inventory()
        with pytest.raises(TypeError):
            inv.equip_armor(_plain_item())

    def test_raises_for_non_item_object(self):
        inv = Inventory()
        with pytest.raises(TypeError):
            inv.equip_armor(object())  # type: ignore[arg-type]

    def test_does_not_raise_for_armor_instance(self):
        inv = Inventory()
        inv.equip_armor(_armor())  # must not raise

    def test_slot_unchanged_after_failed_equip(self):
        """A TypeError during equip must not corrupt the equipped_armor slot."""
        inv = Inventory()
        existing = _armor(item_id="existing", armor_rating=10)
        inv.equip_armor(existing)
        with pytest.raises(TypeError):
            inv.equip_armor(_weapon_item())
        assert inv.equipped_armor is existing


# ---------------------------------------------------------------------------
# Inventory.clear() resets equipped_armor
# ---------------------------------------------------------------------------

class TestInventoryClearResetsArmorSlot:

    def test_clear_sets_equipped_armor_to_none(self):
        inv = Inventory()
        inv.equip_armor(_armor())
        inv.clear()
        assert inv.equipped_armor is None

    def test_clear_resets_slot_even_after_multiple_equips(self):
        inv = Inventory()
        inv.equip_armor(_armor(item_id="a1"))
        inv.equip_armor(_armor(item_id="a2"))
        inv.clear()
        assert inv.equipped_armor is None

    def test_clear_also_empties_main_grid(self):
        inv = Inventory()
        inv.add_item(_weapon_item())
        inv.equip_armor(_armor())
        inv.clear()
        assert len(inv.get_items()) == 0
        assert inv.equipped_armor is None


# ---------------------------------------------------------------------------
# Inventory.to_save_list() — equipped-armor sentinel
# ---------------------------------------------------------------------------

class TestInventoryToSaveList:

    def test_empty_inventory_produces_no_sentinel(self):
        inv = Inventory()
        sentinels = [e for e in inv.to_save_list()
                     if e.get("_slot") == "equipped_armor"]
        assert len(sentinels) == 0

    def test_equipped_armor_produces_exactly_one_sentinel(self):
        inv = Inventory()
        inv.equip_armor(_armor(armor_rating=10))
        sentinels = [e for e in inv.to_save_list()
                     if e.get("_slot") == "equipped_armor"]
        assert len(sentinels) == 1

    def test_sentinel_slot_key_is_equipped_armor(self):
        inv = Inventory()
        inv.equip_armor(_armor())
        sentinel = next(e for e in inv.to_save_list()
                        if e.get("_slot") == "equipped_armor")
        assert sentinel["_slot"] == "equipped_armor"

    def test_sentinel_contains_item_id(self):
        inv = Inventory()
        inv.equip_armor(_armor(item_id="tac_vest_01", armor_rating=12))
        sentinel = next(e for e in inv.to_save_list()
                        if e.get("_slot") == "equipped_armor")
        assert sentinel.get("item_id") == "tac_vest_01"

    def test_sentinel_contains_item_type_armor(self):
        inv = Inventory()
        inv.equip_armor(_armor())
        sentinel = next(e for e in inv.to_save_list()
                        if e.get("_slot") == "equipped_armor")
        assert sentinel.get("item_type") == "armor"

    def test_regular_grid_items_appear_in_list(self):
        inv = Inventory()
        inv.add_item(_weapon_item())
        inv.equip_armor(_armor())
        non_sentinels = [e for e in inv.to_save_list()
                         if e.get("_slot") != "equipped_armor"]
        assert len(non_sentinels) == 1

    def test_equipped_armor_not_double_counted_in_grid(self):
        """equip_armor() does not place items in the main grid;
        to_save_list() must not count the equipped piece twice."""
        inv = Inventory()
        inv.equip_armor(_armor(item_id="double_check"))
        matching = [e for e in inv.to_save_list()
                    if e.get("item_id") == "double_check"]
        assert len(matching) == 1

    def test_unequip_removes_sentinel_from_list(self):
        inv = Inventory()
        inv.equip_armor(_armor())
        inv.unequip_armor()
        sentinels = [e for e in inv.to_save_list()
                     if e.get("_slot") == "equipped_armor"]
        assert len(sentinels) == 0

    def test_sentinel_is_appended_after_regular_items(self):
        """Sentinel must come at the end so loaders can separate it easily."""
        inv = Inventory()
        inv.add_item(_weapon_item())
        inv.equip_armor(_armor())
        result = inv.to_save_list()
        sentinel_idx = next(i for i, e in enumerate(result)
                            if e.get("_slot") == "equipped_armor")
        non_sentinel_count = sum(1 for e in result
                                 if e.get("_slot") != "equipped_armor")
        assert sentinel_idx == non_sentinel_count


# ---------------------------------------------------------------------------
# Inventory.from_save_list() — restores equipped armor
# ---------------------------------------------------------------------------

class TestInventoryFromSaveList:

    def test_restores_equipped_armor_from_sentinel(self):
        inv = Inventory()
        inv.equip_armor(_armor(item_id="light_vest_save"))
        fresh = Inventory()
        fresh.from_save_list(inv.to_save_list())
        assert fresh.equipped_armor is not None
        assert fresh.equipped_armor.item_id == "light_vest_save"

    def test_restored_equipped_armor_is_armor_instance(self):
        inv = Inventory()
        inv.equip_armor(_armor())
        fresh = Inventory()
        fresh.from_save_list(inv.to_save_list())
        assert isinstance(fresh.equipped_armor, Armor)

    def test_equipped_armor_not_also_in_main_grid_after_restore(self):
        inv = Inventory()
        inv.equip_armor(_armor(item_id="armor_only_id"))
        fresh = Inventory()
        fresh.from_save_list(inv.to_save_list())
        grid_matches = [i for i in fresh.get_items()
                        if getattr(i, "item_id", "") == "armor_only_id"]
        assert len(grid_matches) == 0

    def test_fires_on_armor_changed_when_restoring_equipped(self):
        inv = Inventory()
        inv.equip_armor(_armor())
        calls: list[int] = []
        fresh = Inventory()
        fresh.on_armor_changed = lambda: calls.append(1)
        fresh.from_save_list(inv.to_save_list())
        assert len(calls) == 1

    def test_regular_items_restored_to_grid(self):
        inv = Inventory()
        inv.add_item(_weapon_item())
        inv.add_item(_consumable_item())
        fresh = Inventory()
        fresh.from_save_list(inv.to_save_list())
        assert len(fresh.get_items()) == 2

    def test_no_equipped_armor_in_save_leaves_slot_none(self):
        inv = Inventory()
        inv.add_item(_weapon_item())
        fresh = Inventory()
        fresh.from_save_list(inv.to_save_list())
        assert fresh.equipped_armor is None

    def test_clears_existing_equipped_armor_before_loading(self):
        fresh = Inventory()
        fresh.equip_armor(_armor(item_id="old_armor"))
        fresh.from_save_list([])  # load empty save
        assert fresh.equipped_armor is None

    def test_empty_list_clears_main_grid_too(self):
        inv = Inventory()
        inv.add_item(_weapon_item())
        inv.from_save_list([])
        assert len(inv.get_items()) == 0

    def test_corrupt_entry_is_skipped_without_raising(self):
        corrupt = [{"_slot": "equipped_armor", "item_type": "armor",
                    "item_id": None, "name": None, "rarity": "???",
                    "value": "not_an_int", "weight": "bad"}]
        fresh = Inventory()
        fresh.from_save_list(corrupt)  # must not raise
        # corrupt entry should be skipped; slot stays None
        assert fresh.equipped_armor is None

    def test_both_grid_and_equipped_armor_restored_together(self):
        inv = Inventory()
        inv.add_item(_weapon_item())
        inv.equip_armor(_armor(item_id="vest_combo"))
        fresh = Inventory()
        fresh.from_save_list(inv.to_save_list())
        assert len(fresh.get_items()) == 1
        assert fresh.equipped_armor is not None
        assert fresh.equipped_armor.item_id == "vest_combo"


# ---------------------------------------------------------------------------
# EventBus events from equip_armor / unequip_armor
# ---------------------------------------------------------------------------

class TestArmorEquipEvents:

    def test_equip_armor_emits_armor_equipped(self):
        inv = Inventory()
        with _CapturedEvents("armor_equipped") as cap:
            inv.equip_armor(_armor())
        assert cap.count("armor_equipped") == 1

    def test_armor_equipped_event_carries_item_in_payload(self):
        inv = Inventory()
        armor = _armor(item_id="event_vest")
        with _CapturedEvents("armor_equipped") as cap:
            inv.equip_armor(armor)
        assert cap.first("armor_equipped").get("item") is armor

    def test_unequip_armor_emits_armor_unequipped(self):
        inv = Inventory()
        inv.equip_armor(_armor())
        with _CapturedEvents("armor_unequipped") as cap:
            inv.unequip_armor()
        assert cap.count("armor_unequipped") == 1

    def test_armor_unequipped_event_carries_item_in_payload(self):
        inv = Inventory()
        armor = _armor(item_id="event_vest2")
        inv.equip_armor(armor)
        with _CapturedEvents("armor_unequipped") as cap:
            inv.unequip_armor()
        assert cap.first("armor_unequipped").get("item") is armor

    def test_unequip_when_empty_does_not_emit_armor_unequipped(self):
        inv = Inventory()
        with _CapturedEvents("armor_unequipped") as cap:
            inv.unequip_armor()
        assert cap.count("armor_unequipped") == 0

    def test_equip_over_existing_emits_armor_equipped_exactly_once(self):
        """Swapping emits exactly one armor_equipped event per call."""
        inv = Inventory()
        inv.equip_armor(_armor(item_id="a1"))
        with _CapturedEvents("armor_equipped") as cap:
            inv.equip_armor(_armor(item_id="a2"))
        assert cap.count("armor_equipped") == 1

    def test_equip_over_existing_does_not_emit_armor_unequipped(self):
        """Displacement is not the same as an explicit unequip."""
        inv = Inventory()
        inv.equip_armor(_armor(item_id="a1"))
        with _CapturedEvents("armor_unequipped") as cap:
            inv.equip_armor(_armor(item_id="a2"))
        assert cap.count("armor_unequipped") == 0


# ---------------------------------------------------------------------------
# Player.take_damage() no longer self-applies armor
# ---------------------------------------------------------------------------

class TestPlayerTakeDamageNoSelfArmorReduction:
    """After the Phase-1 refactor, Player.take_damage(n) applies exactly n HP
    of damage.  Armor reduction is CombatSystem's responsibility, not Player's."""

    @pytest.fixture(autouse=True)
    def _p(self):
        self.p = _player()

    def test_full_amount_applied_when_armor_is_nonzero(self):
        self.p.armor = 20
        hp_before = _hp(self.p)
        self.p.take_damage(30)
        assert hp_before - _hp(self.p) == 30   # NOT 10

    def test_full_amount_applied_when_armor_exceeds_damage(self):
        """Old behaviour: max(0, 10−50) = 0 damage.
        New behaviour: exactly 10 HP lost."""
        self.p.armor = 50
        hp_before = _hp(self.p)
        self.p.take_damage(10)
        assert hp_before - _hp(self.p) == 10

    def test_zero_armor_still_applies_full_amount(self):
        self.p.armor = 0
        hp_before = _hp(self.p)
        self.p.take_damage(15)
        assert hp_before - _hp(self.p) == 15

    def test_return_value_equals_amount_passed(self):
        self.p.armor = 20
        result = self.p.take_damage(30)
        assert result == 30

    def test_health_cannot_drop_below_zero(self):
        self.p.armor = 0
        self.p.take_damage(99999)
        assert _hp(self.p) == 0


# ---------------------------------------------------------------------------
# Player.get_effective_armor()
# ---------------------------------------------------------------------------

class TestPlayerGetEffectiveArmor:

    @pytest.fixture(autouse=True)
    def _p(self):
        self.p = _player()

    def test_returns_float(self):
        assert isinstance(self.p.get_effective_armor(), float)

    def test_returns_zero_float_when_armor_is_zero(self):
        self.p.armor = 0
        assert self.p.get_effective_armor() == 0.0

    def test_returns_float_of_current_armor(self):
        self.p.armor = 15
        assert self.p.get_effective_armor() == 15.0

    def test_reflects_armor_after_direct_set(self):
        self.p.armor = 22
        assert self.p.get_effective_armor() == pytest.approx(22.0)

    def test_method_is_callable(self):
        assert callable(getattr(self.p, "get_effective_armor", None))

    def test_high_armor_returns_high_float(self):
        self.p.armor = 100
        assert self.p.get_effective_armor() == 100.0


# ============================================================================
# INTEGRATION TESTS  (~30 %)
# ============================================================================

# ---------------------------------------------------------------------------
# Player.__init__ wires on_armor_changed
# ---------------------------------------------------------------------------

class TestPlayerInventoryCallbackWiring:

    def test_inventory_callback_is_set_on_player_init(self):
        p = _player()
        assert p.inventory.on_armor_changed is not None

    def test_callback_points_to_player_recalculate_armor(self):
        p = _player()
        assert p.inventory.on_armor_changed == p._recalculate_armor

    def test_equip_armor_via_inventory_updates_player_armor(self):
        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(armor_rating=10))
        assert p.armor == 10

    def test_unequip_armor_restores_base_armor(self):
        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(armor_rating=10))
        p.inventory.unequip_armor()
        assert p.armor == 0

    def test_swap_armor_updates_to_new_piece_rating(self):
        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(item_id="a1", armor_rating=5))
        p.inventory.equip_armor(_armor(item_id="a2", armor_rating=20))
        assert p.armor == 20

    def test_base_armor_added_to_equipped_rating(self):
        p = _player()
        p.base_armor = 5
        p._recalculate_armor()   # sync from base (no item equipped yet)
        p.inventory.equip_armor(_armor(armor_rating=10))
        assert p.armor == 15   # 5 base + 10 equipped

    def test_get_effective_armor_reflects_equipped_item_rating(self):
        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(armor_rating=12))
        assert p.get_effective_armor() == pytest.approx(12.0)

    def test_player_armor_zero_after_unequip_with_zero_base(self):
        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(armor_rating=8))
        p.inventory.unequip_armor()
        assert p.get_effective_armor() == 0.0


# ---------------------------------------------------------------------------
# CombatSystem armor pipeline
# ---------------------------------------------------------------------------

class TestCombatSystemArmorPipeline:

    @pytest.fixture(autouse=True)
    def _cs(self):
        self.cs = CombatSystem()

    def test_armor_20_raw_30_deals_10_effective(self):
        """effective = max(1, 30 − 20) = 10"""
        p = _player()
        p.armor = 20
        hp_before = _hp(p)
        self.cs.update([_overlapping_proj(p, damage=30)], [p], dt=0.016)
        assert hp_before - _hp(p) == 10

    def test_armor_exceeds_raw_deals_minimum_one(self):
        """effective = max(1, 20 − 50) = 1"""
        p = _player()
        p.armor = 50
        hp_before = _hp(p)
        self.cs.update([_overlapping_proj(p, damage=20)], [p], dt=0.016)
        assert hp_before - _hp(p) == 1

    def test_zero_armor_takes_full_raw_damage(self):
        p = _player()
        p.armor = 0
        hp_before = _hp(p)
        self.cs.update([_overlapping_proj(p, damage=25)], [p], dt=0.016)
        assert hp_before - _hp(p) == 25

    def test_equip_armor_then_combat_hit_reduces_damage(self):
        """End-to-end: equip armor → CombatSystem hit → effective < raw."""
        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(armor_rating=15))
        assert p.armor == 15
        hp_before = _hp(p)
        self.cs.update([_overlapping_proj(p, damage=25)], [p], dt=0.016)
        # effective = max(1, 25 − 15) = 10
        assert hp_before - _hp(p) == 10

    def test_unequip_armor_restores_full_raw_damage(self):
        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(armor_rating=15))
        p.inventory.unequip_armor()
        assert p.armor == 0
        hp_before = _hp(p)
        self.cs.update([_overlapping_proj(p, damage=25)], [p], dt=0.016)
        assert hp_before - _hp(p) == 25

    def test_higher_armor_means_less_damage(self):
        p_low = _player()
        p_high = _player()
        p_low.armor = 5
        p_high.armor = 20
        hp_low_before = _hp(p_low)
        hp_high_before = _hp(p_high)
        self.cs.update([_overlapping_proj(p_low, damage=30)], [p_low], dt=0.016)
        self.cs.update([_overlapping_proj(p_high, damage=30)], [p_high], dt=0.016)
        loss_low = hp_low_before - _hp(p_low)
        loss_high = hp_high_before - _hp(p_high)
        assert loss_low > loss_high


# ---------------------------------------------------------------------------
# Inventory save / load round-trip
# ---------------------------------------------------------------------------

class TestInventorySaveLoadRoundTrip:

    def test_equipped_armor_item_id_survives_round_trip(self):
        inv = Inventory()
        inv.equip_armor(_armor(item_id="tac_vest_rt"))
        fresh = Inventory()
        fresh.from_save_list(inv.to_save_list())
        assert fresh.equipped_armor is not None
        assert fresh.equipped_armor.item_id == "tac_vest_rt"

    def test_no_equipped_armor_round_trip_leaves_slot_none(self):
        inv = Inventory()
        inv.add_item(_weapon_item())
        fresh = Inventory()
        fresh.from_save_list(inv.to_save_list())
        assert fresh.equipped_armor is None

    def test_grid_items_and_equipped_armor_both_survive(self):
        inv = Inventory()
        inv.add_item(_weapon_item())
        inv.add_item(_consumable_item())
        inv.equip_armor(_armor(item_id="combo_vest"))
        fresh = Inventory()
        fresh.from_save_list(inv.to_save_list())
        assert len(fresh.get_items()) == 2
        assert fresh.equipped_armor is not None

    @pytest.mark.xfail(
        strict=False,
        reason="Bug: Armor.to_save_dict() does not persist armor_value; "
               "make_item() reconstructs Armor with armor_rating=0 after load. "
               "Fix: override to_save_dict() in Armor to include 'armor_value'.",
    )
    def test_player_armor_correct_after_inventory_round_trip(self):
        """Restoring inventory into a wired Player updates player.armor."""
        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(item_id="wired_vest", armor_rating=10))
        saved = p.inventory.to_save_list()

        p2 = _player()
        p2.base_armor = 0
        p2.inventory.from_save_list(saved)
        assert p2.armor == 10

    @pytest.mark.xfail(
        strict=False,
        reason="Bug: Armor.to_save_dict() does not persist armor_value; "
               "make_item() reconstructs Armor with armor_rating=0 after load. "
               "Fix: override to_save_dict() in Armor to include 'armor_value'.",
    )
    def test_save_manager_full_round_trip_with_equipped_armor(self):
        """SaveManager.save() → load() → restore() path persists equipped armor."""
        from src.save.save_manager import SaveManager

        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(item_id="sm_vest", armor_rating=8))

        with tempfile.TemporaryDirectory() as tmp:
            sm = SaveManager(save_path=Path(tmp) / "test_save.json")
            sm.save(inventory=p.inventory)

            p2 = _player()
            p2.base_armor = 0
            sm.restore(inventory=p2.inventory)

        assert p2.inventory.equipped_armor is not None
        assert p2.inventory.equipped_armor.item_id == "sm_vest"
        assert p2.armor == 8


# ---------------------------------------------------------------------------
# InventoryScreen click handling
# ---------------------------------------------------------------------------

class TestInventoryScreenClickHandling:

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.ui.inventory_screen import InventoryScreen
        self.inv = Inventory()
        self.screen = InventoryScreen(inventory=self.inv)

    def _click(self, pos: tuple[int, int]) -> None:
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos}
        )
        self.screen.handle_events([event])

    def _slot_center(self, idx: int) -> tuple[int, int]:
        return self.screen._slot_rect(idx).center

    def _armor_slot_center(self) -> tuple[int, int]:
        return self.screen._armor_slot_rect().center

    # -- Clicking an armor item in the main grid --

    def test_click_armor_in_grid_equips_it(self):
        armor = _armor(item_id="click_vest")
        slot = self.inv.add_item(armor)
        self._click(self._slot_center(slot))
        assert self.inv.equipped_armor is armor

    def test_click_armor_in_grid_removes_it_from_grid(self):
        armor = _armor()
        slot = self.inv.add_item(armor)
        self._click(self._slot_center(slot))
        assert self.inv.item_at(slot) is None

    def test_click_non_armor_item_leaves_slot_unchanged(self):
        weapon = _weapon_item()
        slot = self.inv.add_item(weapon)
        self._click(self._slot_center(slot))
        assert self.inv.equipped_armor is None
        assert self.inv.item_at(slot) is weapon

    def test_click_empty_grid_slot_does_nothing(self):
        self._click(self._slot_center(0))
        assert self.inv.equipped_armor is None

    # -- Clicking the dedicated armor slot --

    def test_click_armor_slot_when_occupied_unequips(self):
        self.inv.equip_armor(_armor())
        self._click(self._armor_slot_center())
        assert self.inv.equipped_armor is None

    def test_click_armor_slot_returns_item_to_grid(self):
        armor = _armor()
        self.inv.equip_armor(armor)
        self._click(self._armor_slot_center())
        assert armor in self.inv.get_items()

    def test_click_armor_slot_when_empty_does_not_raise(self):
        self._click(self._armor_slot_center())  # must not raise

    # -- Displacement on re-equip --

    def test_equip_over_occupied_slot_displaced_item_returns_to_grid(self):
        a1 = _armor(item_id="displaced", armor_rating=5)
        a2 = _armor(item_id="new_piece", armor_rating=15)
        self.inv.equip_armor(a1)      # directly into armor slot
        slot = self.inv.add_item(a2)  # a2 in grid
        self._click(self._slot_center(slot))
        assert self.inv.equipped_armor is a2
        assert a1 in self.inv.get_items()

    def test_equip_over_occupied_slot_displaces_correct_item(self):
        a1 = _armor(item_id="a1_displaced")
        a2 = _armor(item_id="a2_new")
        self.inv.equip_armor(a1)
        slot = self.inv.add_item(a2)
        self._click(self._slot_center(slot))
        grid_ids = [i.item_id for i in self.inv.get_items()]
        assert "a1_displaced" in grid_ids

    def test_inventory_full_event_when_grid_full_on_unequip(self):
        """When the grid is full, unequipping can't return the item; event is emitted."""
        # Fill all capacity slots with zero-weight items
        for i in range(self.inv.capacity):
            self.inv.add_item(_armor(item_id=f"filler_{i}", weight=0.0))
        overflow = _armor(item_id="overflow_armor")
        self.inv.equip_armor(overflow)   # goes to armor slot only, not grid

        with _CapturedEvents("inventory_full") as cap:
            self._click(self._armor_slot_center())
        assert cap.count("inventory_full") >= 1


# ============================================================================
# END-TO-END TESTS  (~10 %)
# ============================================================================

class TestArmorEquipEndToEnd:
    """Complete user-flow tests: loot pickup → equip → combat → verify."""

    @pytest.fixture(autouse=True)
    def _cs(self):
        self.cs = CombatSystem()

    def test_equip_from_inventory_then_hit_reduces_damage(self):
        """Primary happy path: add armor to inventory, equip, take a hit."""
        p = _player()
        p.base_armor = 0
        vest = _armor(item_id="tac_vest", armor_rating=15)

        # Simulate loot pickup: item lands in grid
        p.inventory.add_item(vest)
        # Simulate InventoryScreen equip: remove from grid, call equip_armor
        p.inventory.remove_item(0)
        p.inventory.equip_armor(vest)

        assert p.armor == 15

        hp_before = _hp(p)
        self.cs.update([_overlapping_proj(p, damage=25)], [p], dt=0.016)
        # effective = max(1, 25 − 15) = 10
        assert hp_before - _hp(p) == 10

    @pytest.mark.xfail(
        strict=False,
        reason="Bug: Armor.to_save_dict() does not persist armor_value; "
               "after save/load armor_rating is 0 so full damage is taken. "
               "Fix: override to_save_dict() in Armor to include 'armor_value'.",
    )
    def test_equip_save_load_combat_still_reduces_damage(self):
        """Equip armor → serialize → deserialize → combat hit is still reduced."""
        from src.save.save_manager import SaveManager

        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(item_id="e2e_vest", armor_rating=12))

        with tempfile.TemporaryDirectory() as tmp:
            sm = SaveManager(save_path=Path(tmp) / "e2e_save.json")
            sm.save(inventory=p.inventory)

            p2 = _player()
            p2.base_armor = 0
            sm.restore(inventory=p2.inventory)

        assert p2.armor == 12
        hp_before = _hp(p2)
        self.cs.update([_overlapping_proj(p2, damage=22)], [p2], dt=0.016)
        # effective = max(1, 22 − 12) = 10
        assert hp_before - _hp(p2) == 10

    def test_swap_armor_combat_uses_new_rating(self):
        """Swap armor mid-session; next combat hit uses the new piece's rating."""
        p = _player()
        p.base_armor = 0
        p.inventory.equip_armor(_armor(item_id="light", armor_rating=5))
        p.inventory.equip_armor(_armor(item_id="heavy", armor_rating=12))
        assert p.armor == 12

        hp_before = _hp(p)
        self.cs.update([_overlapping_proj(p, damage=20)], [p], dt=0.016)
        # effective = max(1, 20 − 12) = 8
        assert hp_before - _hp(p) == 8

    def test_no_armor_takes_full_damage_end_to_end(self):
        """Baseline: player with no equipped armor takes full raw damage."""
        p = _player()
        p.base_armor = 0
        assert p.armor == 0

        hp_before = _hp(p)
        self.cs.update([_overlapping_proj(p, damage=20)], [p], dt=0.016)
        assert hp_before - _hp(p) == 20
