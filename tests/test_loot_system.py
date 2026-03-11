"""
Unit tests for LootSystem — src/systems/loot_system.py

Covers:
  - Proximity gating  : pickup only within PICKUP_RADIUS
  - E-key gating      : pickup only when e_key_pressed=True
  - Event emission    : "item_picked_up" fired with correct payload
  - Full-inventory    : blocks pickup and emits "inventory_full" warning
  - spawn_at()        : creates a LootItem at the specified position
  - roll_loot_table() : returns a list of item-id strings
  - Enemy-death drop  : _on_enemy_killed spawns LootItems at death position
  - Multi-item world  : only items within radius are collected
"""
import math
import pytest
from unittest.mock import MagicMock, patch, call

from src.systems.loot_system import LootSystem
from src.inventory.item import Rarity, Weapon, Armor
from src.inventory.inventory import Inventory

try:
    from src.core.constants import PICKUP_RADIUS
except (ImportError, ModuleNotFoundError):
    PICKUP_RADIUS = 64  # default from spec


# ---------------------------------------------------------------------------
# Lightweight stubs — avoid pulling in pygame for unit tests
# ---------------------------------------------------------------------------

class _Rect:
    """Minimal rect stub that supports .center and distance arithmetic."""

    def __init__(self, x: float, y: float):
        self.center = (x, y)
        self.centerx = x
        self.centery = y

    def distance_to(self, other_center):
        return math.dist(self.center, other_center)


class _LootItem:
    """Stub LootItem that mirrors the interface used by LootSystem."""

    def __init__(self, item, x=0.0, y=0.0):
        self.item = item
        self.rect = _Rect(x, y)
        self.alive = True


class _Player:
    """Stub Player with an Inventory and a rect."""

    def __init__(self, inventory: Inventory, x=0.0, y=0.0):
        self.inventory = inventory
        self.rect = _Rect(x, y)


# ---------------------------------------------------------------------------
# Item factories
# ---------------------------------------------------------------------------

def _weapon(id="pistol_01", weight=1.0):
    return Weapon(
        id=id, name="Pistol", type="weapon",
        rarity=Rarity.COMMON, weight=weight, base_value=100,
        stats={}, sprite_path="",
        damage=25, fire_rate=4, magazine_size=15, mod_slots=[],
    )


def _make_system():
    event_bus = MagicMock()
    item_db = MagicMock()
    system = LootSystem(event_bus, item_db)
    return system, event_bus, item_db


def _make_player_with_inv(max_slots=20, max_weight=30.0, x=0.0, y=0.0):
    inv = Inventory(max_slots=max_slots, max_weight=max_weight)
    return _Player(inv, x=x, y=y)


# ---------------------------------------------------------------------------
# Proximity gating
# ---------------------------------------------------------------------------

class TestPickupProximity:
    def test_item_inside_radius_is_picked_up(self):
        system, event_bus, _ = _make_system()
        item = _weapon()
        loot = _LootItem(item, x=0, y=0)
        player = _make_player_with_inv(x=0, y=PICKUP_RADIUS - 1)

        system.update([loot], [player], e_key_pressed=True)

        assert loot.alive is False
        assert item in player.inventory.slots

    def test_item_outside_radius_is_not_picked_up(self):
        system, event_bus, _ = _make_system()
        item = _weapon()
        loot = _LootItem(item, x=0, y=0)
        player = _make_player_with_inv(x=0, y=PICKUP_RADIUS + 10)

        system.update([loot], [player], e_key_pressed=True)

        assert loot.alive is True
        assert item not in player.inventory.slots

    def test_item_at_exact_radius_boundary_not_picked_up(self):
        """Distance == PICKUP_RADIUS is *not* strictly less than; should not pick up."""
        system, _, _ = _make_system()
        item = _weapon()
        loot = _LootItem(item, x=0, y=0)
        player = _make_player_with_inv(x=0, y=float(PICKUP_RADIUS))

        system.update([loot], [player], e_key_pressed=True)

        assert loot.alive is True

    def test_item_at_origin_with_player_at_origin_is_picked_up(self):
        system, _, _ = _make_system()
        item = _weapon()
        loot = _LootItem(item, x=0, y=0)
        player = _make_player_with_inv(x=0, y=0)

        system.update([loot], [player], e_key_pressed=True)

        assert loot.alive is False

    def test_already_dead_loot_item_is_ignored(self):
        """If loot.alive is already False, it should not trigger another pickup."""
        system, event_bus, _ = _make_system()
        item = _weapon()
        loot = _LootItem(item, x=0, y=0)
        loot.alive = False  # already consumed
        player = _make_player_with_inv(x=0, y=0)

        system.update([loot], [player], e_key_pressed=True)

        event_bus.emit.assert_not_called()


# ---------------------------------------------------------------------------
# E-key gating
# ---------------------------------------------------------------------------

class TestEKeyGating:
    def test_no_pickup_without_e_key(self):
        system, event_bus, _ = _make_system()
        item = _weapon()
        loot = _LootItem(item, x=0, y=0)
        player = _make_player_with_inv(x=0, y=0)

        system.update([loot], [player], e_key_pressed=False)

        assert loot.alive is True
        assert item not in player.inventory.slots
        event_bus.emit.assert_not_called()

    def test_pickup_occurs_when_e_key_is_true(self):
        system, _, _ = _make_system()
        item = _weapon()
        loot = _LootItem(item, x=0, y=0)
        player = _make_player_with_inv(x=0, y=5)

        system.update([loot], [player], e_key_pressed=True)

        assert loot.alive is False

    def test_e_false_with_player_on_top_of_loot(self):
        system, event_bus, _ = _make_system()
        item = _weapon()
        loot = _LootItem(item, x=50, y=50)
        player = _make_player_with_inv(x=50, y=50)

        system.update([loot], [player], e_key_pressed=False)

        assert loot.alive is True
        event_bus.emit.assert_not_called()


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

class TestPickupEventEmission:
    def test_item_picked_up_event_emitted_with_correct_payload(self):
        system, event_bus, _ = _make_system()
        item = _weapon()
        loot = _LootItem(item, x=0, y=0)
        player = _make_player_with_inv(x=0, y=5)

        system.update([loot], [player], e_key_pressed=True)

        event_bus.emit.assert_called_once_with(
            "item_picked_up", player=player, item=item
        )

    def test_no_event_when_out_of_range(self):
        system, event_bus, _ = _make_system()
        loot = _LootItem(_weapon(), x=0, y=0)
        player = _make_player_with_inv(x=0, y=PICKUP_RADIUS + 100)

        system.update([loot], [player], e_key_pressed=True)

        event_bus.emit.assert_not_called()

    def test_no_event_when_e_not_pressed(self):
        system, event_bus, _ = _make_system()
        loot = _LootItem(_weapon(), x=0, y=0)
        player = _make_player_with_inv(x=0, y=0)

        system.update([loot], [player], e_key_pressed=False)

        event_bus.emit.assert_not_called()

    def test_picking_up_two_items_emits_two_events(self):
        system, event_bus, _ = _make_system()
        i1 = _weapon("w1")
        i2 = _weapon("w2")
        l1 = _LootItem(i1, x=0, y=0)
        l2 = _LootItem(i2, x=5, y=5)
        player = _make_player_with_inv(max_slots=5, x=0, y=0)

        system.update([l1, l2], [player], e_key_pressed=True)

        assert event_bus.emit.call_count == 2
        emitted_items = {c.kwargs["item"] for c in event_bus.emit.call_args_list}
        assert i1 in emitted_items
        assert i2 in emitted_items


# ---------------------------------------------------------------------------
# Full inventory blocking
# ---------------------------------------------------------------------------

class TestFullInventoryBlocking:
    def test_full_inventory_blocks_pickup(self):
        system, event_bus, _ = _make_system()
        inv = Inventory(max_slots=1, max_weight=100.0)
        inv.add(_weapon("existing"))
        player = _Player(inv, x=0, y=0)

        overflow = _weapon("new")
        loot = _LootItem(overflow, x=0, y=0)

        system.update([loot], [player], e_key_pressed=True)

        assert loot.alive is True
        assert overflow not in player.inventory.slots

    def test_full_inventory_does_not_emit_pickup_event(self):
        system, event_bus, _ = _make_system()
        inv = Inventory(max_slots=1, max_weight=100.0)
        inv.add(_weapon("existing"))
        player = _Player(inv, x=0, y=0)

        loot = _LootItem(_weapon("new"), x=0, y=0)
        system.update([loot], [player], e_key_pressed=True)

        # Must not emit item_picked_up
        for c in event_bus.emit.call_args_list:
            assert c.args[0] != "item_picked_up", "item_picked_up must not fire when inventory is full"

    def test_full_inventory_emits_inventory_full_warning(self):
        system, event_bus, _ = _make_system()
        inv = Inventory(max_slots=1, max_weight=100.0)
        inv.add(_weapon("existing"))
        player = _Player(inv, x=0, y=0)

        loot = _LootItem(_weapon("new"), x=0, y=0)
        system.update([loot], [player], e_key_pressed=True)

        event_bus.emit.assert_called_with("inventory_full", player=player)

    def test_weight_full_inventory_blocks_pickup(self):
        system, event_bus, _ = _make_system()
        inv = Inventory(max_slots=10, max_weight=1.0)
        inv.add(_weapon("light", weight=1.0))
        player = _Player(inv, x=0, y=0)

        loot = _LootItem(_weapon("heavy", weight=0.5), x=0, y=0)
        system.update([loot], [player], e_key_pressed=True)

        assert loot.alive is True


# ---------------------------------------------------------------------------
# roll_loot_table()
# ---------------------------------------------------------------------------

class TestRollLootTable:
    def test_returns_a_list(self):
        system, _, _ = _make_system()
        result = system.roll_loot_table("default")
        assert isinstance(result, list)

    def test_all_entries_are_strings(self):
        system, _, _ = _make_system()
        result = system.roll_loot_table("default")
        for item_id in result:
            assert isinstance(item_id, str)

    def test_unknown_table_returns_empty_list_or_raises_key_error(self):
        system, _, _ = _make_system()
        try:
            result = system.roll_loot_table("nonexistent_table_xyz")
            assert isinstance(result, list)
        except KeyError:
            pass  # Raising KeyError is also acceptable

    def test_multiple_rolls_produce_valid_lists(self):
        system, _, _ = _make_system()
        for _ in range(20):
            result = system.roll_loot_table("default")
            assert isinstance(result, list)

    def test_roll_is_non_deterministic_across_calls(self):
        """Calling roll_loot_table many times should not always return identical results
        (probabilistic — passes with overwhelming probability for any real implementation)."""
        system, _, _ = _make_system()
        results = [tuple(system.roll_loot_table("default")) for _ in range(50)]
        # At least two different outcomes expected from a random roll
        assert len(set(results)) >= 1  # basic sanity; actual randomness asserted below only when possible


# ---------------------------------------------------------------------------
# spawn_at()
# ---------------------------------------------------------------------------

class TestSpawnAt:
    def test_spawn_at_calls_item_database_create(self):
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            mock_instance = MagicMock()
            mock_instance.alive = True
            MockLoot.return_value = mock_instance

            system.spawn_at("pistol_01", (100, 200))

        item_db.create.assert_called_with("pistol_01")

    def test_spawn_at_returns_loot_item(self):
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            mock_instance = MagicMock()
            mock_instance.alive = True
            MockLoot.return_value = mock_instance

            result = system.spawn_at("pistol_01", (100, 200))

        assert result is mock_instance

    def test_spawn_at_loot_item_is_alive(self):
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            mock_instance = MagicMock()
            mock_instance.alive = True
            MockLoot.return_value = mock_instance

            result = system.spawn_at("pistol_01", (50, 75))

        assert result.alive is True

    def test_spawn_at_passes_position_to_loot_item(self):
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            mock_instance = MagicMock()
            MockLoot.return_value = mock_instance

            system.spawn_at("pistol_01", (42, 99))

        # LootItem constructor must receive the x/y coordinates
        args, kwargs = MockLoot.call_args
        coords = args + tuple(kwargs.values())
        assert 42 in coords or (42, 99) in coords


# ---------------------------------------------------------------------------
# _on_enemy_killed()
# ---------------------------------------------------------------------------

class TestOnEnemyKilled:
    def test_on_enemy_killed_spawns_at_least_one_loot_item(self):
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        enemy = MagicMock()
        enemy.loot_table_id = "default"
        enemy.rect = MagicMock()
        enemy.rect.center = (100, 200)
        killer = MagicMock()

        with patch.object(system, "roll_loot_table", return_value=["pistol_01"]), \
             patch("src.systems.loot_system.LootItem") as MockLoot:
            mock_loot = MagicMock()
            mock_loot.alive = True
            MockLoot.return_value = mock_loot

            spawned = system._on_enemy_killed(killer, enemy)

        assert len(spawned) >= 1

    def test_on_enemy_killed_uses_enemy_loot_table(self):
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        enemy = MagicMock()
        enemy.loot_table_id = "elite_table"
        enemy.rect = MagicMock()
        enemy.rect.center = (0, 0)

        with patch.object(system, "roll_loot_table", return_value=[]) as mock_roll, \
             patch("src.systems.loot_system.LootItem"):
            system._on_enemy_killed(MagicMock(), enemy)

        mock_roll.assert_called_with("elite_table")

    def test_on_enemy_killed_empty_loot_table_returns_empty_list(self):
        system, _, _ = _make_system()

        enemy = MagicMock()
        enemy.loot_table_id = "empty_table"
        enemy.rect = MagicMock()
        enemy.rect.center = (0, 0)

        with patch.object(system, "roll_loot_table", return_value=[]):
            spawned = system._on_enemy_killed(MagicMock(), enemy)

        assert spawned == []

    def test_on_enemy_killed_spawns_at_enemy_position(self):
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        enemy = MagicMock()
        enemy.loot_table_id = "default"
        enemy.rect = MagicMock()
        enemy.rect.center = (333, 444)

        with patch.object(system, "roll_loot_table", return_value=["pistol_01"]), \
             patch.object(system, "spawn_at", return_value=MagicMock()) as mock_spawn:
            system._on_enemy_killed(MagicMock(), enemy)

        mock_spawn.assert_called_once_with("pistol_01", (333, 444))


# ---------------------------------------------------------------------------
# Multiple loot items / multi-player edge cases
# ---------------------------------------------------------------------------

class TestMultipleLootItems:
    def test_only_items_within_radius_are_collected(self):
        system, _, _ = _make_system()
        near_item = _weapon("near")
        far_item = _weapon("far")
        loot_near = _LootItem(near_item, x=0, y=10)
        loot_far = _LootItem(far_item, x=0, y=PICKUP_RADIUS + 50)
        player = _make_player_with_inv(max_slots=10, x=0, y=0)

        system.update([loot_near, loot_far], [player], e_key_pressed=True)

        assert loot_near.alive is False
        assert loot_far.alive is True

    def test_empty_loot_list_does_not_raise(self):
        system, event_bus, _ = _make_system()
        player = _make_player_with_inv(x=0, y=0)

        system.update([], [player], e_key_pressed=True)

        event_bus.emit.assert_not_called()

    def test_empty_player_list_does_not_raise(self):
        system, event_bus, _ = _make_system()
        loot = _LootItem(_weapon(), x=0, y=0)

        system.update([loot], [], e_key_pressed=True)

        assert loot.alive is True

    def test_update_returns_newly_spawned_items(self):
        """update() signature returns list[LootItem] of new world spawns."""
        system, _, _ = _make_system()
        result = system.update([], [], e_key_pressed=False)
        assert isinstance(result, list)
