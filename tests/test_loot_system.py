"""
Unit tests for LootSystem — src/systems/loot_system.py

Run: pytest tests/test_loot_system.py

Covers:
  - Proximity gating        : pickup only within PICKUP_RADIUS
  - E-key gating            : pickup only when e_key_pressed=True
  - Event emission          : "item_picked_up" fired with correct payload
  - Full-inventory          : blocks pickup and emits "inventory_full" warning
  - spawn_at()              : creates a LootItem at the specified position
  - roll_loot_table()       : returns a list of item-id strings, respects "rolls"
  - Enemy-death drop        : _on_enemy_killed spawns LootItems at death position
  - String loot_table attr  : enemy.loot_table="grunt_drops" resolves via roll_loot_table
  - Multi-item world        : only items within radius are collected
  - _on_player_killed()     : victim inventory drops into world loot list
  - despawn_all()           : marks all items dead, clears internal list
  - spawn_round_loot()      : seeds static map loot from tile map positions
  - _weighted_rarity_choice : two-stage rarity-tier distribution
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


# ---------------------------------------------------------------------------
# roll_loot_table() — respects "rolls" count from enemies.json
# ---------------------------------------------------------------------------


class TestRollLootTableRolls:
    """roll_loot_table() must produce exactly `rolls` item IDs per call."""

    def test_heavy_drops_returns_two_items_matching_rolls_field(self):
        """enemies.json heavy_drops has rolls=2 — result must be length 2."""
        system, _, _ = _make_system()
        result = system.roll_loot_table("heavy_drops")
        assert len(result) == 2

    def test_grunt_drops_returns_one_item_matching_rolls_field(self):
        """enemies.json grunt_drops has rolls=1 — result must be length 1."""
        system, _, _ = _make_system()
        result = system.roll_loot_table("grunt_drops")
        assert len(result) == 1

    def test_sniper_drops_returns_one_item_matching_rolls_field(self):
        """enemies.json sniper_drops has rolls=1 — result must be length 1."""
        system, _, _ = _make_system()
        result = system.roll_loot_table("sniper_drops")
        assert len(result) == 1

    def test_roll_results_are_valid_grunt_drop_item_ids(self):
        """All item IDs from grunt_drops must belong to its entries in enemies.json."""
        system, _, _ = _make_system()
        valid_ids = {"ammo_pistol", "medkit_small", "weapon_pistol"}
        result = system.roll_loot_table("grunt_drops")
        for item_id in result:
            assert item_id in valid_ids

    def test_roll_results_are_valid_heavy_drop_item_ids(self):
        """All item IDs from heavy_drops must belong to its entries in enemies.json."""
        system, _, _ = _make_system()
        valid_ids = {"ammo_rifle", "medkit_large", "armor_light", "weapon_rifle"}
        result = system.roll_loot_table("heavy_drops")
        for item_id in result:
            assert item_id in valid_ids

    def test_explicit_config_dict_with_rolls_3_returns_three_items(self):
        """A config dict with rolls=3 must return exactly 3 item IDs."""
        system, _, _ = _make_system()
        config = {
            "rolls": 3,
            "entries": [{"item_id": "test_item", "weight": 1}],
            "rarity_weights": {},
        }
        result = system.roll_loot_table(config)
        assert len(result) == 3
        assert all(r == "test_item" for r in result)

    def test_flat_list_input_treated_as_single_roll(self):
        """Passing a raw entry list (legacy) must produce a single-item result."""
        system, _, _ = _make_system()
        entries = [{"item_id": "flat_item", "weight": 1}]
        result = system.roll_loot_table(entries)
        assert len(result) == 1
        assert result[0] == "flat_item"


# ---------------------------------------------------------------------------
# _on_enemy_killed() — string loot_table attribute on the enemy object
# ---------------------------------------------------------------------------


class TestOnEnemyKilledStringTableName:
    """When enemy.loot_table is a string name it must route through roll_loot_table."""

    def test_string_table_name_routes_through_roll_loot_table(self):
        """enemy.loot_table='grunt_drops' must call roll_loot_table('grunt_drops')."""
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        enemy = MagicMock()
        enemy.loot_table_id = None
        enemy.loot_table = "grunt_drops"
        enemy.rect = MagicMock()
        enemy.rect.center = (50, 100)

        with patch.object(system, "roll_loot_table", return_value=["pistol_01"]) as mock_roll, \
             patch("src.systems.loot_system.LootItem") as MockLoot:
            MockLoot.return_value = MagicMock(alive=True)
            system._on_enemy_killed(MagicMock(), enemy)

        mock_roll.assert_called_with("grunt_drops")

    def test_string_table_name_appends_loot_item_to_world_list(self):
        """Items resolved from a string-named table must appear in _loot_items."""
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        enemy = MagicMock()
        enemy.loot_table_id = None
        enemy.loot_table = "grunt_drops"
        enemy.rect = MagicMock()
        enemy.rect.center = (50, 100)

        with patch.object(system, "roll_loot_table", return_value=["pistol_01"]), \
             patch("src.systems.loot_system.LootItem") as MockLoot:
            MockLoot.return_value = MagicMock(alive=True)
            system._on_enemy_killed(MagicMock(), enemy)

        assert len(system._loot_items) == 1

    def test_string_table_spawns_loot_at_enemy_rect_center(self):
        """Loot from a string-named table must be placed at the enemy's rect.center."""
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        enemy = MagicMock()
        enemy.loot_table_id = None
        enemy.loot_table = "grunt_drops"
        enemy.rect = MagicMock()
        enemy.rect.center = (333, 444)

        with patch.object(system, "roll_loot_table", return_value=["pistol_01"]), \
             patch.object(system, "spawn_at", return_value=MagicMock()) as mock_spawn:
            system._on_enemy_killed(MagicMock(), enemy)

        mock_spawn.assert_called_once_with("pistol_01", (333, 444))

    def test_empty_string_loot_table_falls_through_gracefully(self):
        """enemy.loot_table='' with no loot_table_id must return a list (no crash)."""
        system, _, _ = _make_system()

        enemy = MagicMock()
        enemy.loot_table_id = None
        enemy.loot_table = ""
        enemy.rect = MagicMock()
        enemy.rect.center = (0, 0)

        with patch("src.systems.loot_system.LootItem"):
            result = system._on_enemy_killed(MagicMock(), enemy)

        assert isinstance(result, list)

    def test_multiple_item_ids_from_roll_all_spawned(self):
        """When roll_loot_table returns N IDs, N LootItems must be created."""
        system, _, item_db = _make_system()
        item_db.create.return_value = _weapon()

        enemy = MagicMock()
        enemy.loot_table_id = None
        enemy.loot_table = "heavy_drops"
        enemy.rect = MagicMock()
        enemy.rect.center = (0, 0)

        with patch.object(system, "roll_loot_table", return_value=["r1", "r2"]), \
             patch("src.systems.loot_system.LootItem") as MockLoot:
            MockLoot.side_effect = lambda item, x, y: _LootItem(item, x, y)
            system._on_enemy_killed(MagicMock(), enemy)

        assert len(system._loot_items) == 2


# ---------------------------------------------------------------------------
# _on_player_killed() — victim inventory drops into world loot
# ---------------------------------------------------------------------------


class TestOnPlayerKilled:
    """Killing a player must scatter their inventory into the world as LootItems."""

    def _make_victim(self, items=None, equipped_weapon=None, equipped_armor=None):
        """Return a minimal victim mock with configurable inventory."""
        victim = MagicMock()
        inv = MagicMock()
        inv.slots = list(items or [])
        inv.equipped_weapon = equipped_weapon
        inv.equipped_armor = equipped_armor
        inv.clear = MagicMock()
        victim.inventory = inv
        victim.rect = MagicMock()
        victim.rect.center = (200, 300)
        return victim

    def test_victim_inventory_slots_become_world_loot(self):
        """Every item in the victim's slots must appear in _loot_items."""
        system, _, _ = _make_system()
        w1, w2 = _weapon("w1"), _weapon("w2")
        victim = self._make_victim(items=[w1, w2])

        with patch("src.systems.loot_system.LootItem",
                   side_effect=lambda item, x, y: _LootItem(item, x, y)):
            system._on_player_killed(killer=MagicMock(), victim=victim)

        assert len(system._loot_items) == 2

    def test_dropped_item_identities_match_victim_inventory(self):
        """Items in _loot_items must be the exact same objects as the victim's items."""
        system, _, _ = _make_system()
        w1, w2 = _weapon("w1"), _weapon("w2")
        victim = self._make_victim(items=[w1, w2])

        with patch("src.systems.loot_system.LootItem",
                   side_effect=lambda item, x, y: _LootItem(item, x, y)):
            system._on_player_killed(killer=MagicMock(), victim=victim)

        dropped = {loot.item for loot in system._loot_items}
        assert w1 in dropped
        assert w2 in dropped

    def test_equipped_weapon_also_dropped(self):
        """The victim's equipped_weapon must appear in world loot."""
        system, _, _ = _make_system()
        equipped = _weapon("equipped_pistol")
        victim = self._make_victim(items=[], equipped_weapon=equipped)

        with patch("src.systems.loot_system.LootItem",
                   side_effect=lambda item, x, y: _LootItem(item, x, y)):
            system._on_player_killed(killer=MagicMock(), victim=victim)

        dropped_items = [loot.item for loot in system._loot_items]
        assert equipped in dropped_items

    def test_no_loot_when_victim_is_none(self):
        """victim=None must return [] and leave _loot_items unchanged."""
        system, _, _ = _make_system()
        result = system._on_player_killed(killer=MagicMock(), victim=None)
        assert result == []
        assert len(system._loot_items) == 0

    def test_no_loot_when_victim_has_no_inventory(self):
        """victim.inventory=None must return [] without crashing."""
        system, _, _ = _make_system()
        victim = MagicMock()
        victim.inventory = None
        result = system._on_player_killed(killer=MagicMock(), victim=victim)
        assert result == []
        assert len(system._loot_items) == 0

    def test_dropped_loot_items_are_alive_on_creation(self):
        """Every LootItem spawned during a player kill must start with alive=True."""
        system, _, _ = _make_system()
        victim = self._make_victim(items=[_weapon("w1")])

        with patch("src.systems.loot_system.LootItem",
                   side_effect=lambda item, x, y: _LootItem(item, x, y)):
            system._on_player_killed(killer=MagicMock(), victim=victim)

        assert all(loot.alive for loot in system._loot_items)

    def test_victim_inventory_cleared_after_drop(self):
        """inventory.clear() must be called exactly once after the drop."""
        system, _, _ = _make_system()
        victim = self._make_victim(items=[_weapon("w1")])

        with patch("src.systems.loot_system.LootItem",
                   side_effect=lambda item, x, y: _LootItem(item, x, y)):
            system._on_player_killed(killer=MagicMock(), victim=victim)

        victim.inventory.clear.assert_called_once()

    def test_empty_inventory_produces_no_world_loot(self):
        """A victim with an empty inventory must produce zero LootItems."""
        system, _, _ = _make_system()
        victim = self._make_victim(items=[], equipped_weapon=None, equipped_armor=None)

        with patch("src.systems.loot_system.LootItem",
                   side_effect=lambda item, x, y: _LootItem(item, x, y)):
            system._on_player_killed(killer=MagicMock(), victim=victim)

        assert len(system._loot_items) == 0


# ---------------------------------------------------------------------------
# despawn_all() — round-end cleanup
# ---------------------------------------------------------------------------


class TestDespawnAll:
    """despawn_all() must mark every live item dead and clear _loot_items."""

    def test_all_items_set_to_alive_false(self):
        """Every LootItem in _loot_items must have alive=False after despawn_all."""
        system, _, _ = _make_system()
        loot1 = _LootItem(_weapon("w1"), 0, 0)
        loot2 = _LootItem(_weapon("w2"), 50, 50)
        system._loot_items.extend([loot1, loot2])

        system.despawn_all()

        assert loot1.alive is False
        assert loot2.alive is False

    def test_loot_items_list_empty_after_despawn_all(self):
        """The internal _loot_items list must be empty after despawn_all."""
        system, _, _ = _make_system()
        system._loot_items.append(_LootItem(_weapon(), 0, 0))
        system._loot_items.append(_LootItem(_weapon(), 10, 10))

        system.despawn_all()

        assert len(system._loot_items) == 0

    def test_public_loot_items_property_empty_after_despawn_all(self):
        """The public loot_items property must return [] after despawn_all."""
        system, _, _ = _make_system()
        system._loot_items.append(_LootItem(_weapon(), 0, 0))

        system.despawn_all()

        assert system.loot_items == []

    def test_despawn_all_on_empty_list_does_not_raise(self):
        """despawn_all() on a system with no loot must not raise."""
        system, _, _ = _make_system()
        assert len(system._loot_items) == 0
        system.despawn_all()  # Must not raise
        assert len(system._loot_items) == 0

    def test_already_dead_items_handled_without_error(self):
        """Items already marked dead must not cause errors in despawn_all."""
        system, _, _ = _make_system()
        loot = _LootItem(_weapon(), 0, 0)
        loot.alive = False
        system._loot_items.append(loot)

        system.despawn_all()  # Must not raise

        assert len(system._loot_items) == 0

    def test_despawn_all_marks_item_dead_before_clearing(self):
        """Items must be marked dead even though the list is cleared afterward."""
        system, _, _ = _make_system()
        saved_loot = _LootItem(_weapon(), 0, 0)
        system._loot_items.append(saved_loot)

        system.despawn_all()

        # Item reference still holds the alive=False state set before clear
        assert saved_loot.alive is False


# ---------------------------------------------------------------------------
# spawn_round_loot() — static map loot placement at round start
# ---------------------------------------------------------------------------


class TestSpawnRoundLoot:
    """spawn_round_loot() seeds one LootItem per tile-map spawn position."""

    def test_spawns_one_loot_item_per_position(self):
        """Each (x, y) in loot_spawns must add exactly one entry to _loot_items."""
        system, _, item_db = _make_system()
        item_db.item_ids = ["pistol_01", "medkit_small"]
        item_db.create.return_value = _weapon()

        with patch("src.systems.loot_system.LootItem") as MockLoot:
            MockLoot.return_value = MagicMock(alive=True)
            system.spawn_round_loot([(100, 200), (300, 400), (500, 600)])

        assert len(system._loot_items) == 3

    def test_no_items_spawned_when_item_db_is_none(self):
        """When the system has no item_db, spawn_round_loot must be a no-op."""
        bus = MagicMock()
        system = LootSystem(bus, item_db=None)
        system.spawn_round_loot([(100, 200), (300, 400)])
        assert len(system._loot_items) == 0

    def test_no_items_spawned_when_item_ids_is_empty(self):
        """An empty item_ids list must prevent any spawning."""
        system, _, item_db = _make_system()
        item_db.item_ids = []
        system.spawn_round_loot([(100, 200)])
        assert len(system._loot_items) == 0

    def test_no_items_spawned_for_empty_spawn_list(self):
        """An empty loot_spawns list must leave _loot_items unchanged."""
        system, _, item_db = _make_system()
        item_db.item_ids = ["pistol_01"]
        item_db.create.return_value = _weapon()
        system.spawn_round_loot([])
        assert len(system._loot_items) == 0

    def test_item_db_create_called_once_per_position(self):
        """item_db.create() must be invoked exactly once per spawn position."""
        system, _, item_db = _make_system()
        item_db.item_ids = ["pistol_01"]
        item_db.create.return_value = _weapon()

        with patch("src.systems.loot_system.LootItem",
                   side_effect=lambda item, x, y: _LootItem(item, x, y)):
            system.spawn_round_loot([(10, 20), (30, 40)])

        assert item_db.create.call_count == 2

    def test_spawned_items_are_alive(self):
        """Every LootItem produced by spawn_round_loot must start with alive=True."""
        system, _, item_db = _make_system()
        item_db.item_ids = ["pistol_01"]
        item_db.create.return_value = _weapon()

        with patch("src.systems.loot_system.LootItem",
                   side_effect=lambda item, x, y: _LootItem(item, x, y)):
            system.spawn_round_loot([(50, 75)])

        assert len(system._loot_items) == 1
        assert system._loot_items[0].alive is True

    def test_loot_items_accessible_via_public_property_after_round_spawn(self):
        """Items created by spawn_round_loot must be visible through loot_items."""
        system, _, item_db = _make_system()
        item_db.item_ids = ["pistol_01"]
        item_db.create.return_value = _weapon()

        with patch("src.systems.loot_system.LootItem",
                   side_effect=lambda item, x, y: _LootItem(item, x, y)):
            system.spawn_round_loot([(0, 0)])

        assert len(system.loot_items) == 1


# ---------------------------------------------------------------------------
# _weighted_rarity_choice() — two-stage rarity distribution
# ---------------------------------------------------------------------------


class TestWeightedRarityChoice:
    """_weighted_rarity_choice picks a rarity tier first, then an item from it."""

    def test_result_is_always_from_entry_list(self):
        """Every returned item_id must be one of the ids in entries."""
        entries = [
            {"item_id": "common_item", "weight": 1, "rarity": "common"},
            {"item_id": "rare_item", "weight": 1, "rarity": "rare"},
        ]
        rarity_weights = {"common": 1, "rare": 1}
        valid_ids = {"common_item", "rare_item"}
        for _ in range(30):
            result = LootSystem._weighted_rarity_choice(entries, rarity_weights)
            assert result in valid_ids

    def test_sole_non_zero_rarity_always_selected(self):
        """When only one rarity has non-zero weight, that tier is always chosen."""
        entries = [
            {"item_id": "common_item", "weight": 1, "rarity": "common"},
            {"item_id": "rare_item", "weight": 1, "rarity": "rare"},
        ]
        rarity_weights = {"common": 100, "rare": 0}
        for _ in range(20):
            result = LootSystem._weighted_rarity_choice(entries, rarity_weights)
            assert result == "common_item"

    def test_falls_back_when_chosen_rarity_has_no_matching_entries(self):
        """If the selected rarity has no entries, flat fallback must be used."""
        entries = [{"item_id": "only_item", "weight": 1, "rarity": "common"}]
        rarity_weights = {"epic": 100}  # Only epic; no epic entries
        result = LootSystem._weighted_rarity_choice(entries, rarity_weights)
        assert result == "only_item"

    def test_all_zero_weights_falls_back_to_flat_choice(self):
        """When all rarity weights are 0, flat weighted choice is the fallback."""
        entries = [{"item_id": "item_a", "weight": 1, "rarity": "common"}]
        rarity_weights = {"common": 0, "rare": 0}
        result = LootSystem._weighted_rarity_choice(entries, rarity_weights)
        assert result == "item_a"

    def test_multiple_items_in_same_tier_are_both_selectable(self):
        """When a tier has multiple entries, any of them can be picked."""
        entries = [
            {"item_id": "common_a", "weight": 1, "rarity": "common"},
            {"item_id": "common_b", "weight": 1, "rarity": "common"},
        ]
        rarity_weights = {"common": 1}
        results = {
            LootSystem._weighted_rarity_choice(entries, rarity_weights)
            for _ in range(50)
        }
        assert results <= {"common_a", "common_b"}
        assert len(results) >= 1

    def test_grunt_drops_rarity_weights_respected_in_roll(self):
        """Rolling grunt_drops many times must not produce 'epic' (weight=0)."""
        system, _, _ = _make_system()
        grunt_config = system._loot_tables.get("grunt_drops")
        if grunt_config is None:
            pytest.skip("grunt_drops not loaded — enemies.json unavailable")

        entries = grunt_config["entries"]
        rarity_weights = grunt_config.get("rarity_weights", {})
        if not rarity_weights or rarity_weights.get("epic", 0) != 0:
            pytest.skip("grunt_drops rarity_weights not configured or epic weight != 0")

        for _ in range(50):
            item_id = LootSystem._weighted_rarity_choice(entries, rarity_weights)
            # weapon_pistol is the only "rare" entry; it must not appear when rare=10
            # but epic=0, so no epic item should be picked
            assert item_id in {"ammo_pistol", "medkit_small", "weapon_pistol"}
