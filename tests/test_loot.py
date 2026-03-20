"""Unit and integration tests for LootItem and LootSystem.

Run: pytest tests/test_loot.py

Covers:
- LootItem initialisation, centre calculation, distance helpers
- in_pickup_range() boundary conditions (at-radius, inside, outside)
- pickup() marks item dead and returns wrapped Item
- LootItem.render() draws rarity-colored outer border and dark inner fill
- LootSystem.spawn_loot() with default and custom loot tables
- spawn_loot() silently swallows unknown item IDs
- LootSystem.update() happy-path pickup: item transferred to inventory,
  item_picked_up event emitted, LootItem removed from world list
- update() guard rails: e_key not pressed, player out of range,
  player with no inventory, already-dead loot items
- enemy_killed EventBus handler spawns loot at the enemy's position
- teardown() unsubscribes from enemy_killed
- _weighted_choice() static method boundary conditions
- Item rarity values and monetary value scaling
- LAYER_LOOT render-layer Z-order constant

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


# ---------------------------------------------------------------------------
# LootItem — render() rarity-colored border
# ---------------------------------------------------------------------------


class TestLootItemRender:
    """LootItem.render() must draw a rarity-colored outer border and dark inner fill."""

    def test_outer_rect_uses_item_rarity_color(self, medkit: Consumable) -> None:
        """The first pygame.draw.rect call must use item.rarity_color as the color."""
        from unittest.mock import MagicMock, patch

        loot = LootItem(medkit, 0.0, 0.0)
        screen = MagicMock()
        captured: list = []

        with patch("pygame.draw.rect", side_effect=lambda *a, **kw: captured.append(a)):
            loot.render(screen, (0, 0))

        assert len(captured) >= 1
        # pygame.draw.rect(surface, color, rect) → color is index 1
        outer_color = captured[0][1]
        assert outer_color == medkit.rarity_color

    def test_inner_rect_uses_dark_fill_color(self, medkit: Consumable) -> None:
        """The second pygame.draw.rect call must use (30, 30, 40) for the inner fill."""
        from unittest.mock import MagicMock, patch

        loot = LootItem(medkit, 0.0, 0.0)
        screen = MagicMock()
        captured: list = []

        with patch("pygame.draw.rect", side_effect=lambda *a, **kw: captured.append(a)):
            loot.render(screen, (0, 0))

        assert len(captured) >= 2
        inner_color = captured[1][1]
        assert inner_color == (30, 30, 40)

    def test_exactly_two_rects_drawn_per_alive_item(self, medkit: Consumable) -> None:
        """render() must call pygame.draw.rect exactly twice: border + fill."""
        from unittest.mock import MagicMock, patch

        loot = LootItem(medkit, 0.0, 0.0)
        screen = MagicMock()
        captured: list = []

        with patch("pygame.draw.rect", side_effect=lambda *a, **kw: captured.append(a)):
            loot.render(screen, (0, 0))

        assert len(captured) == 2

    def test_render_skipped_entirely_when_not_alive(self, medkit: Consumable) -> None:
        """A dead LootItem (alive=False) must not call pygame.draw.rect at all."""
        from unittest.mock import MagicMock, patch

        loot = LootItem(medkit, 0.0, 0.0)
        loot.alive = False
        screen = MagicMock()
        captured: list = []

        with patch("pygame.draw.rect", side_effect=lambda *a, **kw: captured.append(a)):
            loot.render(screen, (0, 0))

        assert len(captured) == 0

    def test_camera_offset_shifts_render_position(self, medkit: Consumable) -> None:
        """Screen x-coord must equal world_x minus camera_offset_x."""
        from unittest.mock import MagicMock, patch

        loot = LootItem(medkit, 200.0, 300.0)
        screen = MagicMock()
        captured: list = []

        with patch("pygame.draw.rect", side_effect=lambda *a, **kw: captured.append(a)):
            loot.render(screen, (50, 100))

        # sx = int(200) - 50 = 150
        outer_rect = captured[0][2]
        assert outer_rect[0] == 150

    def test_rarity_color_differs_between_common_and_epic(self) -> None:
        """A common item and an epic item must produce visually distinct borders."""
        epic_item = Consumable(
            id="rare_stim",
            name="Epic Stim",
            rarity="epic",
            sprite_key="stim",
            value=500,
            consumable_type="buff",
        )
        common_item = Consumable(
            id="medkit_small",
            name="Small Medkit",
            rarity="common",
            sprite_key="medkit_small",
            value=50,
            consumable_type="heal",
        )
        assert epic_item.rarity_color != common_item.rarity_color

    def test_border_outer_rect_covers_full_sprite_size(self, medkit: Consumable) -> None:
        """Outer rect width and height must equal _SPRITE_SIZE (24 px)."""
        from unittest.mock import MagicMock, patch
        from src.entities.loot_item import _SPRITE_SIZE

        loot = LootItem(medkit, 0.0, 0.0)
        screen = MagicMock()
        captured: list = []

        with patch("pygame.draw.rect", side_effect=lambda *a, **kw: captured.append(a)):
            loot.render(screen, (0, 0))

        outer_rect = captured[0][2]
        assert outer_rect[2] == _SPRITE_SIZE
        assert outer_rect[3] == _SPRITE_SIZE

    def test_inner_rect_inset_from_outer_border(self, medkit: Consumable) -> None:
        """Inner rect must be 2 px inset on each side compared to the outer rect."""
        from unittest.mock import MagicMock, patch

        loot = LootItem(medkit, 0.0, 0.0)
        screen = MagicMock()
        captured: list = []

        with patch("pygame.draw.rect", side_effect=lambda *a, **kw: captured.append(a)):
            loot.render(screen, (0, 0))

        outer = captured[0][2]
        inner = captured[1][2]
        # Inner rect is 2 px inset: x+2, y+2, w-4, h-4
        assert inner[0] == outer[0] + 2
        assert inner[2] == outer[2] - 4
        assert inner[3] == outer[3] - 4


# ---------------------------------------------------------------------------
# Item rarity — monetary value and color properties
# ---------------------------------------------------------------------------


class TestRarityValues:
    """Item.value and monetary_value must reflect the rarity tier hierarchy."""

    def test_common_default_value_less_than_epic(self) -> None:
        """RARITY_DEFAULT_VALUES: common < uncommon < rare < epic."""
        from src.inventory.item import RARITY_DEFAULT_VALUES
        assert RARITY_DEFAULT_VALUES["common"] < RARITY_DEFAULT_VALUES["epic"]

    def test_all_rarity_tiers_have_positive_default_value(self) -> None:
        """Every tier in RARITY_DEFAULT_VALUES must have a value > 0."""
        from src.inventory.item import RARITY_DEFAULT_VALUES
        for tier, val in RARITY_DEFAULT_VALUES.items():
            assert val > 0, f"Rarity '{tier}' has non-positive default value {val}"

    def test_rarity_order_has_strictly_increasing_values(self) -> None:
        """Default values must increase monotonically along RARITY_ORDER."""
        from src.inventory.item import RARITY_DEFAULT_VALUES, RARITY_ORDER
        known = [r for r in RARITY_ORDER if r in RARITY_DEFAULT_VALUES]
        values = [RARITY_DEFAULT_VALUES[r] for r in known]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1], (
                f"Value at '{known[i]}' ({values[i]}) not < '{known[i+1]}' ({values[i+1]})"
            )

    def test_item_with_zero_value_falls_back_to_rarity_default(self) -> None:
        """An item with value=0 must use RARITY_DEFAULT_VALUES for its tier."""
        from src.inventory.item import RARITY_DEFAULT_VALUES
        item = Consumable(
            id="test_common",
            name="Test Common",
            rarity="common",
            sprite_key="test",
            value=0,
            consumable_type="heal",
        )
        assert item.value == RARITY_DEFAULT_VALUES["common"]

    def test_monetary_value_scales_with_rarity_multiplier(self) -> None:
        """monetary_value must equal base_value * RARITY_VALUE_MULTIPLIERS[rarity]."""
        import pytest
        from src.inventory.item import RARITY_VALUE_MULTIPLIERS
        item = Consumable(
            id="test_rare",
            name="Test Rare",
            rarity="rare",
            sprite_key="test",
            value=0,
            consumable_type="heal",
        )
        expected = item.base_value * RARITY_VALUE_MULTIPLIERS["rare"]
        assert item.monetary_value == pytest.approx(expected)

    def test_rarity_colors_are_distinct_for_all_tiers(self) -> None:
        """Each rarity tier must have a unique color — no two tiers share a color."""
        from src.inventory.item import RARITY_COLORS
        colors = list(RARITY_COLORS.values())
        assert len(colors) == len(set(colors)), "Duplicate rarity colors detected"


# ---------------------------------------------------------------------------
# Render layer constant
# ---------------------------------------------------------------------------


class TestLootLayerConstant:
    """LAYER_LOOT must sit between tiles and enemies in the Z-order stack."""

    def test_layer_loot_is_1(self) -> None:
        """LAYER_LOOT == 1 per the spec render-layer table."""
        from src.constants import LAYER_LOOT
        assert LAYER_LOOT == 1

    def test_layer_loot_above_tiles(self) -> None:
        """Loot must render on top of the tile layer."""
        from src.constants import LAYER_LOOT, LAYER_TILES
        assert LAYER_LOOT > LAYER_TILES

    def test_layer_loot_below_enemies(self) -> None:
        """Loot must render beneath enemies so enemies occlude dropped items."""
        from src.constants import LAYER_LOOT, LAYER_ENEMIES
        assert LAYER_LOOT < LAYER_ENEMIES

    def test_layer_loot_below_player(self) -> None:
        """Loot must render beneath the player layer."""
        from src.constants import LAYER_LOOT, LAYER_PLAYER
        assert LAYER_LOOT < LAYER_PLAYER
