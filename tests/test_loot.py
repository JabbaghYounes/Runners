"""Unit and integration tests for LootItem and LootSystem.

Covers:
- LootItem initialisation, centre calculation, distance helpers
- in_pickup_range() boundary conditions (at-radius, inside, outside)
- pickup() marks item dead and returns wrapped Item
- LootSystem.spawn_loot() with default and custom loot tables
- spawn_loot() silently swallows unknown item IDs
- LootSystem.update() happy-path pickup: item transferred to inventory,
  item_picked_up event emitted, LootItem removed from world list
- update() guard rails: e_key not pressed, player out of range,
  player with no inventory, already-dead loot items
- enemy_killed EventBus handler spawns loot at the enemy's position
- teardown() unsubscribes from enemy_killed
- _weighted_choice() static method boundary conditions

All tests are pure Python and do NOT require Pygame or a display.
"""

from __future__ import annotations

import sys
import types

import pytest


# ---------------------------------------------------------------------------
# Minimal Pygame stub (matches the one in test_consumables.py)
# ---------------------------------------------------------------------------


def _install_pygame_stub() -> None:
    if "pygame" in sys.modules:
        return

    pg = types.ModuleType("pygame")
    pg.K_1 = 49  # type: ignore[attr-defined]
    pg.K_2 = 50  # type: ignore[attr-defined]
    pg.K_e = 101  # type: ignore[attr-defined]
    pg.KEYDOWN = 2  # type: ignore[attr-defined]

    font_mod = types.ModuleType("pygame.font")
    font_mod.SysFont = lambda *a, **kw: None  # type: ignore[attr-defined]
    pg.font = font_mod  # type: ignore[attr-defined]

    draw_mod = types.ModuleType("pygame.draw")
    draw_mod.rect = lambda *a, **kw: None  # type: ignore[attr-defined]
    pg.draw = draw_mod  # type: ignore[attr-defined]

    pg.Rect = lambda *a, **kw: None  # type: ignore[attr-defined]

    sys.modules["pygame"] = pg
    sys.modules["pygame.font"] = font_mod
    sys.modules["pygame.draw"] = draw_mod


_install_pygame_stub()

# ---------------------------------------------------------------------------
# src imports — safe after the stub is in place
# ---------------------------------------------------------------------------

from src.core.event_bus import event_bus                       # noqa: E402
from src.entities.loot_item import LootItem, PICKUP_RADIUS     # noqa: E402
from src.entities.player import Player                         # noqa: E402
from src.inventory.inventory import Inventory                  # noqa: E402
from src.inventory.item import Consumable                      # noqa: E402
from src.systems.buff_system import BuffSystem                 # noqa: E402
from src.systems.loot_system import LootSystem                 # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Wipe all subscriptions before and after every test."""
    event_bus.clear()
    yield
    event_bus.clear()


@pytest.fixture
def buff_system() -> BuffSystem:
    return BuffSystem()


@pytest.fixture
def player(buff_system: BuffSystem) -> Player:
    """Player at the origin with an attached inventory and buff system."""
    inv = Inventory()
    return Player(x=0.0, y=0.0, max_health=100, buff_system=buff_system, inventory=inv)


@pytest.fixture
def medkit() -> Consumable:
    """A small healing consumable for use as test loot."""
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
def loot_system():
    """LootSystem with automatic teardown so it doesn't leak subscriptions."""
    ls = LootSystem()
    yield ls
    ls.teardown()


# ---------------------------------------------------------------------------
# Helper: a minimal stand-in for a killed enemy entity
# ---------------------------------------------------------------------------


class _FakeEnemy:
    def __init__(self, x: float = 0.0, y: float = 0.0, loot_table=None) -> None:
        self.x = x
        self.y = y
        self.loot_table = loot_table


# ---------------------------------------------------------------------------
# LootItem — initialisation
# ---------------------------------------------------------------------------


class TestLootItemInit:
    def test_item_reference_is_stored(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 10.0, 20.0)
        assert loot.item is medkit

    def test_position_is_stored(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 100.0, 200.0)
        assert loot.x == 100.0
        assert loot.y == 200.0

    def test_not_picked_up_on_creation(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        assert loot.picked_up is False

    def test_alive_on_creation(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        assert loot.alive is True

    def test_center_is_midpoint_of_24x24_sprite(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 100.0, 200.0)
        cx, cy = loot.center
        assert cx == pytest.approx(100.0 + 24 / 2)
        assert cy == pytest.approx(200.0 + 24 / 2)


# ---------------------------------------------------------------------------
# LootItem — distance and pickup range
# ---------------------------------------------------------------------------


class TestLootItemPickupRange:
    def test_distance_to_own_center_is_zero(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        cx, cy = loot.center
        assert loot.distance_to(cx, cy) == pytest.approx(0.0)

    def test_distance_to_3_4_5_triple(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        cx, cy = loot.center
        assert loot.distance_to(cx + 3.0, cy + 4.0) == pytest.approx(5.0)

    def test_in_pickup_range_at_own_center(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        cx, cy = loot.center
        assert loot.in_pickup_range(cx, cy) is True

    def test_in_pickup_range_inside_radius(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        cx, cy = loot.center
        assert loot.in_pickup_range(cx + PICKUP_RADIUS - 1, cy) is True

    def test_in_pickup_range_at_exact_radius_boundary(
        self, medkit: Consumable
    ) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        cx, cy = loot.center
        # Exactly at the boundary — spec says <= so this is True
        assert loot.in_pickup_range(cx + PICKUP_RADIUS, cy) is True

    def test_out_of_pickup_range_just_beyond_radius(
        self, medkit: Consumable
    ) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        cx, cy = loot.center
        assert loot.in_pickup_range(cx + PICKUP_RADIUS + 1, cy) is False

    def test_out_of_pickup_range_far_away(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        assert loot.in_pickup_range(10_000.0, 10_000.0) is False


# ---------------------------------------------------------------------------
# LootItem — pickup()
# ---------------------------------------------------------------------------


class TestLootItemPickup:
    def test_pickup_returns_wrapped_item(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        result = loot.pickup()
        assert result is medkit

    def test_pickup_marks_picked_up_true(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        loot.pickup()
        assert loot.picked_up is True

    def test_pickup_sets_alive_false(self, medkit: Consumable) -> None:
        loot = LootItem(medkit, 0.0, 0.0)
        loot.pickup()
        assert loot.alive is False


# ---------------------------------------------------------------------------
# LootSystem — spawn_loot()
# ---------------------------------------------------------------------------


class TestLootSystemSpawn:
    def test_spawn_loot_adds_one_loot_item(
        self, loot_system: LootSystem
    ) -> None:
        assert len(loot_system.loot_items) == 0
        loot_system.spawn_loot(50.0, 50.0)
        assert len(loot_system.loot_items) == 1

    def test_spawn_loot_places_item_at_given_coordinates(
        self, loot_system: LootSystem
    ) -> None:
        loot_system.spawn_loot(123.0, 456.0)
        loot = loot_system.loot_items[0]
        assert loot.x == 123.0
        assert loot.y == 456.0

    def test_spawn_loot_with_custom_single_item_table(
        self, loot_system: LootSystem
    ) -> None:
        table = [{"item_id": "medkit_small", "weight": 1}]
        loot_system.spawn_loot(0.0, 0.0, loot_table=table)
        assert len(loot_system.loot_items) == 1
        assert loot_system.loot_items[0].item.id == "medkit_small"

    def test_spawn_loot_unknown_item_id_silently_skipped(
        self, loot_system: LootSystem
    ) -> None:
        table = [{"item_id": "totally_fake_item_xyz_9999", "weight": 1}]
        loot_system.spawn_loot(0.0, 0.0, loot_table=table)  # Must not raise
        assert len(loot_system.loot_items) == 0

    def test_spawn_loot_empty_table_spawns_nothing(
        self, loot_system: LootSystem
    ) -> None:
        loot_system.spawn_loot(0.0, 0.0, loot_table=[])
        assert len(loot_system.loot_items) == 0

    def test_spawn_loot_all_default_item_ids_are_valid(
        self, loot_system: LootSystem
    ) -> None:
        """Every item in the default table must resolve without KeyError."""
        from src.systems.loot_system import _DEFAULT_LOOT_TABLE
        from src.inventory.item_database import item_database

        for entry in _DEFAULT_LOOT_TABLE:
            item = item_database.create(entry["item_id"])  # Must not raise
            assert item.id == entry["item_id"]


# ---------------------------------------------------------------------------
# LootSystem — update() pickup interactions
# ---------------------------------------------------------------------------


class TestLootSystemUpdate:
    def _place_loot_at_player(
        self, loot_system: LootSystem, player: Player, item: Consumable
    ) -> LootItem:
        """Add a LootItem directly at the player's position."""
        loot = LootItem(item, player.x, player.y)
        loot_system._loot_items.append(loot)
        return loot

    # --- happy path ---

    def test_pickup_transfers_item_to_player_inventory(
        self, loot_system: LootSystem, player: Player, medkit: Consumable
    ) -> None:
        self._place_loot_at_player(loot_system, player, medkit)
        loot_system.update(player, e_key_pressed=True)
        assert player.inventory.item_at(0) is medkit  # type: ignore[union-attr]

    def test_pickup_emits_item_picked_up_event(
        self, loot_system: LootSystem, player: Player, medkit: Consumable
    ) -> None:
        received: list[dict] = []
        event_bus.subscribe("item_picked_up", received.append)
        self._place_loot_at_player(loot_system, player, medkit)
        loot_system.update(player, e_key_pressed=True)
        assert len(received) == 1
        assert received[0]["item"] is medkit
        assert received[0]["player"] is player

    def test_pickup_removes_loot_item_from_world_list(
        self, loot_system: LootSystem, player: Player, medkit: Consumable
    ) -> None:
        loot = self._place_loot_at_player(loot_system, player, medkit)
        loot_system.update(player, e_key_pressed=True)
        assert loot not in loot_system.loot_items

    def test_pickup_marks_loot_item_as_picked_up(
        self, loot_system: LootSystem, player: Player, medkit: Consumable
    ) -> None:
        loot = self._place_loot_at_player(loot_system, player, medkit)
        loot_system.update(player, e_key_pressed=True)
        assert loot.picked_up is True

    # --- guard rails ---

    def test_no_pickup_when_e_key_not_pressed(
        self, loot_system: LootSystem, player: Player, medkit: Consumable
    ) -> None:
        loot = self._place_loot_at_player(loot_system, player, medkit)
        loot_system.update(player, e_key_pressed=False)
        assert loot in loot_system.loot_items
        assert not loot.picked_up

    def test_no_pickup_when_player_out_of_range(
        self, loot_system: LootSystem, player: Player, medkit: Consumable
    ) -> None:
        # Place loot far from the player
        loot = LootItem(medkit, player.x + 10_000.0, player.y + 10_000.0)
        loot_system._loot_items.append(loot)
        loot_system.update(player, e_key_pressed=True)
        assert loot in loot_system.loot_items
        assert not loot.picked_up

    def test_dead_loot_items_cleaned_up_on_update(
        self, loot_system: LootSystem, player: Player, medkit: Consumable
    ) -> None:
        loot = LootItem(medkit, 9_999.0, 9_999.0)
        loot.alive = False  # Pre-killed, e.g. by a previous frame
        loot_system._loot_items.append(loot)
        loot_system.update(player, e_key_pressed=False)
        assert loot not in loot_system.loot_items

    def test_no_crash_when_player_has_no_inventory(
        self, loot_system: LootSystem, player: Player, medkit: Consumable
    ) -> None:
        player.inventory = None
        self._place_loot_at_player(loot_system, player, medkit)
        loot_system.update(player, e_key_pressed=True)  # Must not raise

    def test_multiple_nearby_loot_items_all_picked_up(
        self, loot_system: LootSystem, player: Player
    ) -> None:
        items = [
            Consumable(
                id="medkit_small",
                name=f"Medkit {i}",
                rarity="common",
                sprite_key="medkit_small",
                value=50,
                consumable_type="heal",
                heal_amount=30,
            )
            for i in range(3)
        ]
        for item in items:
            self._place_loot_at_player(loot_system, player, item)
        loot_system.update(player, e_key_pressed=True)
        assert len(loot_system.loot_items) == 0
        # All three should be in the player's inventory
        inv_items = [player.inventory.item_at(i) for i in range(3)]  # type: ignore[union-attr]
        for item in items:
            assert item in inv_items


# ---------------------------------------------------------------------------
# LootSystem — enemy_killed EventBus handler
# ---------------------------------------------------------------------------


class TestLootSystemEnemyKilled:
    def test_enemy_killed_spawns_loot_in_world(
        self, loot_system: LootSystem
    ) -> None:
        event_bus.emit("enemy_killed", {"enemy": _FakeEnemy(x=0.0, y=0.0)})
        assert len(loot_system.loot_items) == 1

    def test_enemy_killed_spawns_loot_at_enemy_position(
        self, loot_system: LootSystem
    ) -> None:
        table = [{"item_id": "medkit_small", "weight": 1}]
        event_bus.emit(
            "enemy_killed",
            {"enemy": _FakeEnemy(x=300.0, y=400.0, loot_table=table)},
        )
        loot = loot_system.loot_items[0]
        assert loot.x == 300.0
        assert loot.y == 400.0

    def test_enemy_killed_uses_enemy_custom_loot_table(
        self, loot_system: LootSystem
    ) -> None:
        table = [{"item_id": "medkit_large", "weight": 1}]
        event_bus.emit(
            "enemy_killed",
            {"enemy": _FakeEnemy(x=0.0, y=0.0, loot_table=table)},
        )
        assert loot_system.loot_items[0].item.id == "medkit_large"

    def test_enemy_killed_without_enemy_key_spawns_nothing(
        self, loot_system: LootSystem
    ) -> None:
        event_bus.emit("enemy_killed", {})
        assert len(loot_system.loot_items) == 0

    def test_teardown_unsubscribes_from_enemy_killed(self) -> None:
        ls = LootSystem()
        ls.teardown()
        event_bus.emit("enemy_killed", {"enemy": _FakeEnemy()})
        assert len(ls.loot_items) == 0

    def test_teardown_does_not_affect_other_loot_systems(self) -> None:
        ls_a = LootSystem()
        ls_b = LootSystem()
        ls_a.teardown()
        event_bus.emit("enemy_killed", {"enemy": _FakeEnemy()})
        # ls_b is still subscribed; ls_a is not
        assert len(ls_b.loot_items) == 1
        assert len(ls_a.loot_items) == 0
        ls_b.teardown()


# ---------------------------------------------------------------------------
# LootSystem._weighted_choice() (static helper)
# ---------------------------------------------------------------------------


class TestWeightedChoice:
    def test_empty_table_returns_none(self) -> None:
        assert LootSystem._weighted_choice([]) is None

    def test_single_entry_always_returned(self) -> None:
        table = [{"item_id": "only_item", "weight": 100}]
        for _ in range(10):
            assert LootSystem._weighted_choice(table) == "only_item"

    def test_result_is_from_table(self) -> None:
        table = [
            {"item_id": "a", "weight": 1},
            {"item_id": "b", "weight": 1},
            {"item_id": "c", "weight": 1},
        ]
        valid_ids = {"a", "b", "c"}
        for _ in range(20):
            assert LootSystem._weighted_choice(table) in valid_ids

    def test_weight_zero_entry_can_coexist(self) -> None:
        """An item with weight 0 should never be selected when another exists."""
        table = [
            {"item_id": "never", "weight": 0},
            {"item_id": "always", "weight": 100},
        ]
        for _ in range(20):
            assert LootSystem._weighted_choice(table) == "always"
