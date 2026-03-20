"""Extra unit tests for the consumable subsystem — fills gaps not in test_consumables.py.

Covers:
- BuffSystem.get_modifiers()  — direct stat-query API
- BuffSystem.get_active_buff_names()  — legacy alias
- Player.set_buff_system()  — post-construction dependency injection
- Consumable.use() with unknown consumable_type  — graceful no-op
- Inventory.drop()  — item removal by reference
- Inventory.get_items()  — all present items
- Inventory.get_consumables()  — filtered + capped list
- Inventory.expand_capacity()  — dynamic slot growth

Run: pytest tests/test_consumables_extra.py
"""
from __future__ import annotations

import pytest

from src.core.event_bus import event_bus
from src.entities.player import Player
from src.inventory.inventory import Inventory
from src.inventory.item import Consumable
from src.systems.buff_system import ActiveBuff, BuffSystem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_event_bus():
    """Isolate event bus subscriptions between tests."""
    event_bus.clear()
    yield
    event_bus.clear()


@pytest.fixture
def buff_system() -> BuffSystem:
    return BuffSystem()


@pytest.fixture
def player(buff_system: BuffSystem) -> Player:
    return Player(max_health=100, buff_system=buff_system)


@pytest.fixture
def player_no_bs() -> Player:
    """Player without a BuffSystem — apply_buff writes directly to active_buffs."""
    return Player(max_health=100)


@pytest.fixture
def inventory() -> Inventory:
    return Inventory()


@pytest.fixture
def medkit_small() -> Consumable:
    return Consumable(
        id="medkit_small",
        name="Small Medkit",
        rarity="common",
        sprite_key="medkit_small",
        value=50,
        consumable_type="heal",
        heal_amount=30,
    )


@pytest.fixture
def medkit_large() -> Consumable:
    return Consumable(
        id="medkit_large",
        name="Large Medkit",
        rarity="uncommon",
        sprite_key="medkit_large",
        value=120,
        consumable_type="heal",
        heal_amount=80,
    )


# ---------------------------------------------------------------------------
# BuffSystem.get_modifiers()
# ---------------------------------------------------------------------------


class TestBuffSystemGetModifiers:
    """Direct tests for BuffSystem.get_modifiers(entity, stat_name) → float."""

    def test_returns_zero_when_player_has_no_buffs(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        assert buff_system.get_modifiers(player, "speed") == pytest.approx(0.0)

    def test_returns_buff_value_for_matching_stat(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("speed", value=30.0, duration=15.0, time_remaining=15.0))
        assert buff_system.get_modifiers(player, "speed") == pytest.approx(30.0)

    def test_sums_multiple_buffs_of_same_stat(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("speed", 20.0, 15.0, 15.0))
        player.apply_buff(ActiveBuff("speed", 10.0, 10.0, 10.0))
        assert buff_system.get_modifiers(player, "speed") == pytest.approx(30.0)

    def test_ignores_buffs_for_a_different_stat(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("damage", 25.0, 12.0, 12.0))
        assert buff_system.get_modifiers(player, "speed") == pytest.approx(0.0)

    def test_returns_zero_after_all_buffs_expire(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 3.0, 3.0))
        buff_system.update(3.0)
        assert buff_system.get_modifiers(player, "speed") == pytest.approx(0.0)

    def test_unknown_stat_returns_zero_when_no_matching_buffs(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 15.0, 15.0))
        assert buff_system.get_modifiers(player, "luck") == pytest.approx(0.0)

    def test_only_expired_buff_contributes_zero(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        """One expired + one live buff: only live value is returned."""
        player.apply_buff(ActiveBuff("speed", 30.0, 2.0, 2.0))   # Expires at t=2
        player.apply_buff(ActiveBuff("speed", 10.0, 15.0, 15.0))  # Stays alive
        buff_system.update(2.0)
        assert buff_system.get_modifiers(player, "speed") == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# BuffSystem.get_active_buff_names()
# ---------------------------------------------------------------------------


class TestBuffSystemGetActiveBuffNames:
    """Legacy alias: returns a flat list of all buff_type strings across entities."""

    def test_returns_empty_list_when_no_entities_registered(
        self, buff_system: BuffSystem
    ) -> None:
        assert buff_system.get_active_buff_names() == []

    def test_returns_buff_type_for_one_active_buff(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 15.0, 15.0))
        names = buff_system.get_active_buff_names()
        assert "speed" in names

    def test_returns_all_buff_types_on_single_entity(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 15.0, 15.0))
        player.apply_buff(ActiveBuff("damage", 25.0, 12.0, 12.0))
        names = buff_system.get_active_buff_names()
        assert "speed" in names
        assert "damage" in names

    def test_excludes_expired_buff_types(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 2.0, 2.0))
        buff_system.update(2.0)
        assert buff_system.get_active_buff_names() == []

    def test_spans_multiple_entities(self, buff_system: BuffSystem) -> None:
        """Names from all registered entities are included."""
        p1 = Player(max_health=100, buff_system=buff_system)
        p2 = Player(max_health=100, buff_system=buff_system)
        p1.apply_buff(ActiveBuff("speed", 30.0, 15.0, 15.0))
        p2.apply_buff(ActiveBuff("damage", 25.0, 12.0, 12.0))
        names = buff_system.get_active_buff_names()
        assert "speed" in names
        assert "damage" in names


# ---------------------------------------------------------------------------
# Player.set_buff_system() — post-construction dependency injection
# ---------------------------------------------------------------------------


class TestPlayerSetBuffSystem:
    """Calling set_buff_system() after construction must re-route apply_buff()."""

    def test_subsequent_apply_buff_is_tracked_by_new_system(
        self, player_no_bs: Player
    ) -> None:
        bs = BuffSystem()
        player_no_bs.set_buff_system(bs)
        player_no_bs.apply_buff(ActiveBuff("speed", 30.0, 15.0, 15.0))
        assert "speed" in bs.get_active_buff_names()

    def test_buff_also_appears_in_player_active_buffs(
        self, player_no_bs: Player
    ) -> None:
        bs = BuffSystem()
        player_no_bs.set_buff_system(bs)
        buff = ActiveBuff("damage", 25.0, 12.0, 12.0)
        player_no_bs.apply_buff(buff)
        assert buff in player_no_bs.active_buffs

    def test_buff_applied_event_emitted_after_set_buff_system(
        self, player_no_bs: Player
    ) -> None:
        received: list[dict] = []
        event_bus.subscribe("buff_applied", received.append)
        bs = BuffSystem()
        player_no_bs.set_buff_system(bs)
        player_no_bs.apply_buff(ActiveBuff("speed", 30.0, 15.0, 15.0))
        assert len(received) == 1

    def test_buff_ticks_and_expires_after_set_buff_system(
        self, player_no_bs: Player
    ) -> None:
        bs = BuffSystem()
        player_no_bs.set_buff_system(bs)
        buff = ActiveBuff("speed", 30.0, 5.0, 5.0)
        player_no_bs.apply_buff(buff)
        bs.update(5.0)
        assert buff not in player_no_bs.active_buffs

    def test_replace_existing_buff_system_with_new_one(
        self, player: Player
    ) -> None:
        """set_buff_system replaces the one passed at construction time."""
        new_bs = BuffSystem()
        player.set_buff_system(new_bs)
        player.apply_buff(ActiveBuff("damage", 25.0, 12.0, 12.0))
        assert "damage" in new_bs.get_active_buff_names()


# ---------------------------------------------------------------------------
# Consumable.use() with unknown consumable_type
# ---------------------------------------------------------------------------


class TestConsumableUnknownType:
    """An unrecognised consumable_type must be a silent no-op."""

    def _mystery(self) -> Consumable:
        return Consumable(
            id="mystery",
            name="Mystery",
            rarity="common",
            sprite_key="mystery",
            value=100,
            consumable_type="teleport",  # Not "heal" or "buff"
        )

    def test_unknown_type_does_not_modify_health(
        self, player_no_bs: Player
    ) -> None:
        hp_before = player_no_bs.health
        self._mystery().use(player_no_bs)
        assert player_no_bs.health == hp_before

    def test_unknown_type_does_not_add_active_buffs(
        self, player_no_bs: Player
    ) -> None:
        self._mystery().use(player_no_bs)
        assert player_no_bs.active_buffs == []

    def test_unknown_type_does_not_raise(self, player_no_bs: Player) -> None:
        self._mystery().use(player_no_bs)  # Must not raise


# ---------------------------------------------------------------------------
# Inventory.drop()
# ---------------------------------------------------------------------------


class TestInventoryDrop:
    """drop(item) removes by object reference; raises ValueError if absent."""

    def test_drop_removes_item_from_its_slot(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        inventory.drop(medkit_small)
        assert inventory.item_at(slot) is None

    def test_drop_returns_the_item(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        inventory.add_item(medkit_small)
        result = inventory.drop(medkit_small)
        assert result is medkit_small

    def test_drop_raises_value_error_when_item_not_in_inventory(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        with pytest.raises(ValueError):
            inventory.drop(medkit_small)

    def test_drop_clears_linked_quick_slot(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        inventory.assign_quick_slot(slot, 0)
        inventory.drop(medkit_small)
        assert inventory.quick_slots[0] is None

    def test_drop_does_not_affect_other_occupied_slots(
        self,
        inventory: Inventory,
        medkit_small: Consumable,
        medkit_large: Consumable,
    ) -> None:
        inventory.add_item(medkit_small)   # slot 0
        inventory.add_item(medkit_large)   # slot 1
        inventory.drop(medkit_small)
        assert inventory.item_at(1) is medkit_large


# ---------------------------------------------------------------------------
# Inventory.get_items()
# ---------------------------------------------------------------------------


class TestInventoryGetItems:
    """get_items() returns a flat list of every non-None slot."""

    def test_returns_empty_list_when_inventory_is_empty(
        self, inventory: Inventory
    ) -> None:
        assert inventory.get_items() == []

    def test_returns_all_added_items(
        self,
        inventory: Inventory,
        medkit_small: Consumable,
        medkit_large: Consumable,
    ) -> None:
        inventory.add_item(medkit_small)
        inventory.add_item(medkit_large)
        items = inventory.get_items()
        assert medkit_small in items
        assert medkit_large in items

    def test_excludes_removed_items(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        inventory.remove_item(slot)
        assert inventory.get_items() == []

    def test_count_matches_used_slot_count(
        self,
        inventory: Inventory,
        medkit_small: Consumable,
        medkit_large: Consumable,
    ) -> None:
        inventory.add_item(medkit_small)
        inventory.add_item(medkit_large)
        assert len(inventory.get_items()) == 2

    def test_does_not_include_none_entries(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        """None placeholder slots must not appear in the returned list."""
        inventory.add_item(medkit_small)  # slot 0 filled, rest are None
        items = inventory.get_items()
        assert None not in items


# ---------------------------------------------------------------------------
# Inventory.get_consumables()
# ---------------------------------------------------------------------------


class TestInventoryGetConsumables:
    """get_consumables() returns consumable items, capped at 4."""

    def test_returns_empty_when_no_consumables(
        self, inventory: Inventory
    ) -> None:
        assert inventory.get_consumables() == []

    def test_returns_consumable_item(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        inventory.add_item(medkit_small)
        result = inventory.get_consumables()
        assert medkit_small in result

    def test_returns_at_most_four_consumables(self) -> None:
        """Even with 5 consumables in inventory, only 4 are returned."""
        inv = Inventory(capacity=10)
        for i in range(5):
            c = Consumable(
                id=f"c_{i}",
                name=f"Consumable {i}",
                rarity="common",
                sprite_key=f"c_{i}",
                value=10,
                consumable_type="heal",
                heal_amount=5,
            )
            inv.add_item(c)
        result = inv.get_consumables()
        assert len(result) <= 4


# ---------------------------------------------------------------------------
# Inventory.expand_capacity()
# ---------------------------------------------------------------------------


class TestInventoryExpandCapacity:
    """expand_capacity(n) grows the slot list by n."""

    def test_increases_capacity_by_given_amount(
        self, inventory: Inventory
    ) -> None:
        original = inventory.capacity
        inventory.expand_capacity(4)
        assert inventory.capacity == original + 4

    def test_new_slots_are_empty(self, inventory: Inventory) -> None:
        original_capacity = inventory.capacity
        inventory.expand_capacity(2)
        for i in range(original_capacity, inventory.capacity):
            assert inventory.item_at(i) is None

    def test_expand_zero_does_not_change_capacity(
        self, inventory: Inventory
    ) -> None:
        original = inventory.capacity
        inventory.expand_capacity(0)
        assert inventory.capacity == original

    def test_items_can_be_added_to_expanded_slots(
        self, medkit_small: Consumable
    ) -> None:
        """A previously-full inventory can accept new items after expansion."""
        inv = Inventory(capacity=1)
        inv.add_item(medkit_small)           # Fills the single slot
        assert inv.add_item(medkit_small) is None  # No room

        inv.expand_capacity(1)
        result = inv.add_item(medkit_small)  # Should succeed now
        assert result is not None

    def test_expanded_capacity_matches_attribute(
        self, inventory: Inventory
    ) -> None:
        inventory.expand_capacity(10)
        assert inventory.capacity == Inventory.MAX_SLOTS + 10
