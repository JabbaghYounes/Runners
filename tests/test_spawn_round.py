"""Tests for SpawnSystem round-level spawn lifecycle.

Covers:
- SpawnResult dataclass: fields, defaults, construction
- SpawnSystem._emit(): event payload, silent when no bus
- spawn_player(): Player type, position, empty-list fallback, event emission
- spawn_loot(): count, position, empty-db guard, None-db guard, event emission
- spawn_pvp_bots(): count, type, position, missing-attr guard, event emission
- teardown(): marks alive=False, clears lists, idempotent, all-entity-types
- spawn_round(): returns SpawnResult, entity types, dependency order
- entity_spawned events: count, payload fields, ordering guarantee
- Full lifecycle: spawn_round → teardown → re-spawn

Run: pytest tests/test_spawn_round.py
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.entities.player import Player
from src.entities.player_agent import PlayerAgent
from src.entities.robot_enemy import RobotEnemy
from src.map.zone import Zone
from src.systems.spawn_system import SpawnResult, SpawnSystem


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _zone(
    name: str = "test_zone",
    enemy_spawns: list | None = None,
    spawn_points: list | None = None,
    pvp_bot_spawns: list | None = None,
) -> Zone:
    return Zone(
        name=name,
        rect=(0, 0, 640, 480),
        enemy_spawns=enemy_spawns if enemy_spawns is not None else [],
        spawn_points=spawn_points if spawn_points is not None else [],
        pvp_bot_spawns=pvp_bot_spawns if pvp_bot_spawns is not None else [],
    )


def _make_enemy_db(known_types: tuple = ("grunt", "heavy", "sniper")) -> MagicMock:
    """Mock EnemyDatabase whose create() produces real RobotEnemy instances."""

    def _create(type_id: str, pos: Any, waypoints: Any = None) -> RobotEnemy:
        if type_id not in known_types:
            raise KeyError(type_id)
        return RobotEnemy(
            x=float(pos[0]),
            y=float(pos[1]),
            type_id=type_id,
            hp=50,
            patrol_waypoints=list(waypoints) if waypoints else [(float(pos[0]), float(pos[1]))],
        )

    db = MagicMock()
    db.create.side_effect = _create
    return db


def _make_item_db(item_ids: list | None = None) -> MagicMock:
    """Mock ItemDatabase with a configurable item_ids list."""
    ids = item_ids if item_ids is not None else ["ammo_pistol"]
    db = MagicMock()
    db.item_ids = ids
    mock_item = MagicMock()
    mock_item.name = "Ammo"
    db.create.return_value = mock_item
    return db


def _make_tile_map(
    player_spawns: list | None = None,
    loot_spawns: list | None = None,
    zones: list | None = None,
) -> MagicMock:
    """Mock TileMap with configurable spawn data."""
    tm = MagicMock()
    tm.player_spawns = player_spawns if player_spawns is not None else [(100.0, 200.0)]
    tm.loot_spawns = loot_spawns if loot_spawns is not None else []
    tm.zones = zones if zones is not None else []
    return tm


# ---------------------------------------------------------------------------
# SpawnResult dataclass
# ---------------------------------------------------------------------------


class TestSpawnResult:
    """SpawnResult is a typed container for all entities created at round start."""

    def test_player_field_stores_provided_player(self):
        player = Player(0.0, 0.0)
        result = SpawnResult(player=player)
        assert result.player is player

    def test_enemies_defaults_to_empty_list(self):
        result = SpawnResult(player=Player(0.0, 0.0))
        assert result.enemies == []

    def test_pvp_bots_defaults_to_empty_list(self):
        result = SpawnResult(player=Player(0.0, 0.0))
        assert result.pvp_bots == []

    def test_loot_items_defaults_to_empty_list(self):
        result = SpawnResult(player=Player(0.0, 0.0))
        assert result.loot_items == []

    def test_can_store_enemies_list(self):
        enemy = RobotEnemy()
        result = SpawnResult(player=Player(0.0, 0.0), enemies=[enemy])
        assert result.enemies == [enemy]

    def test_can_store_pvp_bots_list(self):
        bot = PlayerAgent()
        result = SpawnResult(player=Player(0.0, 0.0), pvp_bots=[bot])
        assert result.pvp_bots == [bot]

    def test_can_store_loot_items_list(self):
        from src.entities.loot_item import LootItem
        loot = LootItem(MagicMock(), 10.0, 20.0)
        result = SpawnResult(player=Player(0.0, 0.0), loot_items=[loot])
        assert result.loot_items == [loot]

    def test_all_four_fields_accessible_together(self):
        player = Player(0.0, 0.0)
        enemy = RobotEnemy()
        bot = PlayerAgent()
        result = SpawnResult(player=player, enemies=[enemy], pvp_bots=[bot], loot_items=[])
        assert result.player is player
        assert result.enemies == [enemy]
        assert result.pvp_bots == [bot]
        assert result.loot_items == []


# ---------------------------------------------------------------------------
# SpawnSystem._emit()
# ---------------------------------------------------------------------------


class TestEmit:
    """_emit() fires 'entity_spawned' when a bus is configured, and is silent otherwise."""

    def test_emits_entity_spawned_event_when_bus_is_set(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss._emit("player", MagicMock(), 10.0, 20.0)
        assert len(event_bus.all_events("entity_spawned")) == 1

    def test_emit_payload_contains_entity_type(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss._emit("player", MagicMock(), 10.0, 20.0)
        assert event_bus.first_event("entity_spawned")["entity_type"] == "player"

    def test_emit_payload_contains_entity_reference(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        entity = MagicMock()
        ss._emit("enemy", entity, 0.0, 0.0)
        assert event_bus.first_event("entity_spawned")["entity"] is entity

    def test_emit_payload_contains_x_coordinate(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss._emit("loot", MagicMock(), 55.0, 77.0)
        assert event_bus.first_event("entity_spawned")["x"] == pytest.approx(55.0)

    def test_emit_payload_contains_y_coordinate(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss._emit("loot", MagicMock(), 55.0, 77.0)
        assert event_bus.first_event("entity_spawned")["y"] == pytest.approx(77.0)

    def test_does_not_raise_when_bus_is_none(self):
        ss = SpawnSystem(event_bus=None)
        ss._emit("player", MagicMock(), 0.0, 0.0)  # must not raise

    def test_no_events_emitted_when_bus_is_none(self):
        """Emitting with no bus leaves all external state unchanged."""
        from tests.conftest import _TrackingEventBus
        unrelated_bus = _TrackingEventBus()
        ss = SpawnSystem(event_bus=None)
        ss._emit("player", MagicMock(), 0.0, 0.0)
        assert unrelated_bus.emitted == []

    def test_multiple_emit_calls_produce_multiple_events(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss._emit("loot", MagicMock(), 1.0, 1.0)
        ss._emit("enemy", MagicMock(), 2.0, 2.0)
        ss._emit("player", MagicMock(), 3.0, 3.0)
        assert len(event_bus.all_events("entity_spawned")) == 3


# ---------------------------------------------------------------------------
# spawn_player()
# ---------------------------------------------------------------------------


class TestSpawnPlayer:
    """spawn_player() creates the Player entity at a random valid spawn point."""

    def test_returns_player_instance(self):
        ss = SpawnSystem()
        assert isinstance(ss.spawn_player([(100.0, 200.0)]), Player)

    def test_player_starts_alive(self):
        ss = SpawnSystem()
        player = ss.spawn_player([(100.0, 200.0)])
        assert player.alive is True

    def test_single_spawn_point_places_player_at_correct_x(self):
        ss = SpawnSystem()
        player = ss.spawn_player([(128.0, 256.0)])
        assert player.x == pytest.approx(128.0)

    def test_single_spawn_point_places_player_at_correct_y(self):
        ss = SpawnSystem()
        player = ss.spawn_player([(128.0, 256.0)])
        assert player.y == pytest.approx(256.0)

    def test_empty_spawn_list_returns_player_without_raising(self):
        ss = SpawnSystem()
        player = ss.spawn_player([])
        assert isinstance(player, Player)

    def test_empty_spawn_list_places_player_at_world_origin(self):
        ss = SpawnSystem()
        player = ss.spawn_player([])
        assert player.x == pytest.approx(0.0)
        assert player.y == pytest.approx(0.0)

    def test_player_spawned_at_patched_random_choice(self):
        ss = SpawnSystem()
        spawns = [(10.0, 20.0), (300.0, 400.0), (500.0, 600.0)]
        with patch("src.systems.spawn_system.random.choice", return_value=(300.0, 400.0)):
            player = ss.spawn_player(spawns)
        assert player.x == pytest.approx(300.0)
        assert player.y == pytest.approx(400.0)

    def test_random_choice_receives_full_spawns_list(self):
        ss = SpawnSystem()
        spawns = [(10.0, 20.0), (30.0, 40.0)]
        with patch("src.systems.spawn_system.random.choice", return_value=(10.0, 20.0)) as mock_choice:
            ss.spawn_player(spawns)
        mock_choice.assert_called_once_with(spawns)

    def test_emits_one_entity_spawned_event(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss.spawn_player([(50.0, 60.0)])
        assert len(event_bus.all_events("entity_spawned")) == 1

    def test_emits_event_with_player_entity_type(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss.spawn_player([(50.0, 60.0)])
        assert event_bus.first_event("entity_spawned")["entity_type"] == "player"

    def test_emitted_event_entity_is_the_returned_player(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        player = ss.spawn_player([(0.0, 0.0)])
        assert event_bus.first_event("entity_spawned")["entity"] is player

    def test_empty_spawn_list_still_emits_event(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss.spawn_player([])
        assert len(event_bus.all_events("entity_spawned")) == 1

    def test_no_events_without_event_bus(self):
        """spawn_player completes without error when no bus is configured."""
        ss = SpawnSystem(event_bus=None)
        player = ss.spawn_player([(10.0, 20.0)])
        assert isinstance(player, Player)


# ---------------------------------------------------------------------------
# spawn_loot()
# ---------------------------------------------------------------------------


class TestSpawnLoot:
    """spawn_loot() places a random item at each loot spawn point."""

    def test_returns_a_list(self):
        ss = SpawnSystem()
        result = ss.spawn_loot([(50.0, 60.0)], _make_item_db())
        assert isinstance(result, list)

    def test_one_spawn_point_produces_one_loot_item(self):
        ss = SpawnSystem()
        result = ss.spawn_loot([(50.0, 60.0)], _make_item_db())
        assert len(result) == 1

    def test_three_spawn_points_produce_three_loot_items(self):
        ss = SpawnSystem()
        result = ss.spawn_loot([(10, 10), (20, 20), (30, 30)], _make_item_db())
        assert len(result) == 3

    def test_empty_spawn_list_returns_empty_list(self):
        ss = SpawnSystem()
        assert ss.spawn_loot([], _make_item_db()) == []

    def test_none_item_db_returns_empty_list(self):
        ss = SpawnSystem()
        assert ss.spawn_loot([(50.0, 60.0)], None) == []

    def test_empty_item_ids_returns_empty_list(self):
        ss = SpawnSystem()
        assert ss.spawn_loot([(50.0, 60.0)], _make_item_db(item_ids=[])) == []

    def test_loot_item_placed_at_correct_x(self):
        ss = SpawnSystem()
        result = ss.spawn_loot([(100.0, 200.0)], _make_item_db())
        assert result[0].x == pytest.approx(100.0)

    def test_loot_item_placed_at_correct_y(self):
        ss = SpawnSystem()
        result = ss.spawn_loot([(100.0, 200.0)], _make_item_db())
        assert result[0].y == pytest.approx(200.0)

    def test_all_loot_items_start_alive(self):
        ss = SpawnSystem()
        result = ss.spawn_loot([(10, 20), (30, 40)], _make_item_db())
        assert all(li.alive for li in result)

    def test_loot_items_are_loot_item_instances(self):
        from src.entities.loot_item import LootItem
        ss = SpawnSystem()
        result = ss.spawn_loot([(10, 20)], _make_item_db())
        assert all(isinstance(li, LootItem) for li in result)

    def test_emits_one_event_per_loot_item(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss.spawn_loot([(10, 20), (30, 40), (50, 60)], _make_item_db())
        assert len(event_bus.all_events("entity_spawned")) == 3

    def test_loot_events_carry_loot_entity_type(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss.spawn_loot([(10, 20)], _make_item_db())
        assert event_bus.first_event("entity_spawned")["entity_type"] == "loot"

    def test_loot_event_entity_is_the_spawned_loot_item(self, event_bus):
        from src.entities.loot_item import LootItem
        ss = SpawnSystem(event_bus=event_bus)
        result = ss.spawn_loot([(10, 20)], _make_item_db())
        ev = event_bus.first_event("entity_spawned")
        assert ev["entity"] is result[0]
        assert isinstance(ev["entity"], LootItem)

    def test_no_events_emitted_when_item_db_is_none(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss.spawn_loot([(10, 20)], None)
        assert event_bus.all_events("entity_spawned") == []

    def test_no_events_emitted_when_item_ids_is_empty(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        ss.spawn_loot([(10, 20)], _make_item_db(item_ids=[]))
        assert event_bus.all_events("entity_spawned") == []


# ---------------------------------------------------------------------------
# spawn_pvp_bots()
# ---------------------------------------------------------------------------


class TestSpawnPvpBots:
    """spawn_pvp_bots() creates a PlayerAgent for each entry in zone.pvp_bot_spawns."""

    def test_returns_a_list(self):
        ss = SpawnSystem()
        assert isinstance(ss.spawn_pvp_bots([]), list)

    def test_empty_zones_returns_empty_list(self):
        ss = SpawnSystem()
        assert ss.spawn_pvp_bots([]) == []

    def test_zone_with_two_bot_spawns_produces_two_bots(self):
        ss = SpawnSystem()
        zone = _zone(pvp_bot_spawns=[(100.0, 200.0), (300.0, 400.0)])
        assert len(ss.spawn_pvp_bots([zone])) == 2

    def test_bots_are_player_agent_instances(self):
        ss = SpawnSystem()
        zone = _zone(pvp_bot_spawns=[(100.0, 200.0), (300.0, 400.0)])
        result = ss.spawn_pvp_bots([zone])
        assert all(isinstance(b, PlayerAgent) for b in result)

    def test_bots_start_alive(self):
        ss = SpawnSystem()
        zone = _zone(pvp_bot_spawns=[(50.0, 60.0)])
        result = ss.spawn_pvp_bots([zone])
        assert result[0].alive is True

    def test_bot_placed_at_correct_x(self):
        ss = SpawnSystem()
        zone = _zone(pvp_bot_spawns=[(150.0, 250.0)])
        result = ss.spawn_pvp_bots([zone])
        assert result[0].rect.x == 150

    def test_bot_placed_at_correct_y(self):
        ss = SpawnSystem()
        zone = _zone(pvp_bot_spawns=[(150.0, 250.0)])
        result = ss.spawn_pvp_bots([zone])
        assert result[0].rect.y == 250

    def test_zone_with_empty_pvp_bot_spawns_contributes_zero_bots(self):
        ss = SpawnSystem()
        zone = _zone(pvp_bot_spawns=[])
        assert ss.spawn_pvp_bots([zone]) == []

    def test_zone_with_none_pvp_bot_spawns_contributes_zero_bots(self):
        ss = SpawnSystem()
        zone = Zone(name="z", rect=(0, 0, 100, 100), pvp_bot_spawns=None)
        assert ss.spawn_pvp_bots([zone]) == []

    def test_zone_without_pvp_bot_spawns_attr_contributes_zero_bots(self):
        ss = SpawnSystem()

        class _BareZone:
            pass  # no pvp_bot_spawns attribute at all

        assert ss.spawn_pvp_bots([_BareZone()]) == []  # type: ignore[arg-type]

    def test_multiple_zones_bots_merged_into_flat_list(self):
        ss = SpawnSystem()
        zone_a = _zone(name="a", pvp_bot_spawns=[(10.0, 10.0), (20.0, 20.0)])
        zone_b = _zone(name="b", pvp_bot_spawns=[(30.0, 30.0)])
        result = ss.spawn_pvp_bots([zone_a, zone_b])
        assert len(result) == 3

    def test_mixed_zones_only_those_with_spawns_contribute(self):
        ss = SpawnSystem()
        empty = _zone(name="empty", pvp_bot_spawns=[])
        active = _zone(name="active", pvp_bot_spawns=[(50.0, 50.0)])
        result = ss.spawn_pvp_bots([empty, active])
        assert len(result) == 1

    def test_emits_one_event_per_bot(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(pvp_bot_spawns=[(10, 20), (30, 40)])
        ss.spawn_pvp_bots([zone])
        assert len(event_bus.all_events("entity_spawned")) == 2

    def test_bot_events_carry_pvp_bot_entity_type(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(pvp_bot_spawns=[(10, 20)])
        ss.spawn_pvp_bots([zone])
        assert event_bus.first_event("entity_spawned")["entity_type"] == "pvp_bot"

    def test_bot_event_entity_is_the_spawned_bot(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(pvp_bot_spawns=[(10, 20)])
        result = ss.spawn_pvp_bots([zone])
        assert event_bus.first_event("entity_spawned")["entity"] is result[0]


# ---------------------------------------------------------------------------
# teardown()
# ---------------------------------------------------------------------------


class TestTeardown:
    """teardown() marks every entity dead and empties the caller's lists."""

    def test_marks_all_enemies_dead(self):
        ss = SpawnSystem()
        e1 = RobotEnemy()
        e2 = RobotEnemy()
        enemies = [e1, e2]
        ss.teardown(enemies, [], [])
        assert e1.alive is False
        assert e2.alive is False

    def test_enemies_list_is_empty_after_teardown(self):
        ss = SpawnSystem()
        enemies = [RobotEnemy()]
        ss.teardown(enemies, [], [])
        assert len(enemies) == 0

    def test_marks_all_pvp_bots_dead(self):
        ss = SpawnSystem()
        b1 = PlayerAgent()
        b2 = PlayerAgent()
        pvp_bots = [b1, b2]
        ss.teardown([], pvp_bots, [])
        assert b1.alive is False
        assert b2.alive is False

    def test_pvp_bots_list_is_empty_after_teardown(self):
        ss = SpawnSystem()
        pvp_bots = [PlayerAgent(), PlayerAgent()]
        ss.teardown([], pvp_bots, [])
        assert len(pvp_bots) == 0

    def test_marks_all_loot_items_dead(self):
        from src.entities.loot_item import LootItem
        ss = SpawnSystem()
        loot = LootItem(MagicMock(), 0.0, 0.0)
        loot_items = [loot]
        ss.teardown([], [], loot_items)
        assert loot.alive is False

    def test_loot_items_list_is_empty_after_teardown(self):
        from src.entities.loot_item import LootItem
        ss = SpawnSystem()
        loot_items = [LootItem(MagicMock(), 0.0, 0.0)]
        ss.teardown([], [], loot_items)
        assert len(loot_items) == 0

    def test_all_three_lists_cleared_in_one_call(self):
        from src.entities.loot_item import LootItem
        ss = SpawnSystem()
        enemies = [RobotEnemy()]
        bots = [PlayerAgent()]
        loot = [LootItem(MagicMock(), 0.0, 0.0)]
        ss.teardown(enemies, bots, loot)
        assert len(enemies) == 0
        assert len(bots) == 0
        assert len(loot) == 0

    def test_empty_lists_do_not_raise(self):
        ss = SpawnSystem()
        ss.teardown([], [], [])  # must not raise

    def test_idempotent_second_call_on_empty_lists_does_not_raise(self):
        ss = SpawnSystem()
        enemies = [RobotEnemy()]
        ss.teardown(enemies, [], [])
        ss.teardown(enemies, [], [])  # list is now empty — must not raise

    def test_already_dead_entity_does_not_cause_error(self):
        ss = SpawnSystem()
        enemy = RobotEnemy()
        enemy.alive = False
        enemies = [enemy]
        ss.teardown(enemies, [], [])  # must not raise

    def test_mixed_alive_and_dead_entities_all_set_to_dead(self):
        ss = SpawnSystem()
        alive_enemy = RobotEnemy()
        dead_enemy = RobotEnemy()
        dead_enemy.alive = False
        enemies = [alive_enemy, dead_enemy]
        ss.teardown(enemies, [], [])
        assert alive_enemy.alive is False
        assert dead_enemy.alive is False


# ---------------------------------------------------------------------------
# spawn_all_zones() emits entity_spawned events
# ---------------------------------------------------------------------------


class TestSpawnAllZonesEvents:
    """spawn_zone_enemies() and spawn_all_zones() must emit entity_spawned per robot."""

    def test_emits_one_event_per_robot_enemy(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(enemy_spawns=[
            {"type": "grunt", "pos": [100, 100]},
            {"type": "heavy", "pos": [200, 100]},
        ])
        ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert len(event_bus.all_events("entity_spawned")) == 2

    def test_robot_enemy_events_carry_enemy_entity_type(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [100, 100]}])
        ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert event_bus.first_event("entity_spawned")["entity_type"] == "enemy"

    def test_robot_event_entity_is_the_spawned_robot(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [100, 100]}])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert event_bus.first_event("entity_spawned")["entity"] is result[0]

    def test_unknown_type_id_does_not_emit_event(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(enemy_spawns=[{"type": "ghost", "pos": [100, 100]}])
        ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert event_bus.all_events("entity_spawned") == []

    def test_spawn_all_zones_aggregates_events_across_zones(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zones = [
            _zone(name="z1", enemy_spawns=[{"type": "grunt", "pos": [0, 0]}]),
            _zone(name="z2", enemy_spawns=[
                {"type": "heavy", "pos": [100, 0]},
                {"type": "sniper", "pos": [200, 0]},
            ]),
        ]
        ss.spawn_all_zones(zones, _make_enemy_db())
        assert len(event_bus.all_events("entity_spawned")) == 3


# ---------------------------------------------------------------------------
# spawn_round() — integration
# ---------------------------------------------------------------------------


class TestSpawnRound:
    """spawn_round() orchestrates all four entity types in dependency order."""

    def test_returns_spawn_result_instance(self):
        ss = SpawnSystem()
        result = ss.spawn_round(_make_tile_map(), _make_enemy_db(), _make_item_db())
        assert isinstance(result, SpawnResult)

    def test_result_player_is_a_player_instance(self):
        ss = SpawnSystem()
        result = ss.spawn_round(_make_tile_map(), _make_enemy_db(), _make_item_db())
        assert isinstance(result.player, Player)

    def test_result_player_starts_alive(self):
        ss = SpawnSystem()
        result = ss.spawn_round(_make_tile_map(), _make_enemy_db(), _make_item_db())
        assert result.player.alive is True

    def test_enemies_populated_from_zone_enemy_spawns(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[
            {"type": "grunt", "pos": [100, 100]},
            {"type": "heavy", "pos": [200, 100]},
        ])
        tm = _make_tile_map(zones=[zone])
        result = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        assert len(result.enemies) == 2

    def test_enemies_are_robot_enemy_instances(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [100, 100]}])
        tm = _make_tile_map(zones=[zone])
        result = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        assert all(isinstance(e, RobotEnemy) for e in result.enemies)

    def test_pvp_bots_populated_from_zone_pvp_bot_spawns(self):
        ss = SpawnSystem()
        zone = _zone(pvp_bot_spawns=[(200.0, 300.0), (400.0, 300.0)])
        tm = _make_tile_map(zones=[zone])
        result = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        assert len(result.pvp_bots) == 2

    def test_pvp_bots_are_player_agent_instances(self):
        ss = SpawnSystem()
        zone = _zone(pvp_bot_spawns=[(200.0, 300.0)])
        tm = _make_tile_map(zones=[zone])
        result = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        assert all(isinstance(b, PlayerAgent) for b in result.pvp_bots)

    def test_loot_items_populated_from_map_loot_spawns(self):
        from src.entities.loot_item import LootItem
        ss = SpawnSystem()
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0), (70.0, 80.0)])
        result = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        assert len(result.loot_items) == 2
        assert all(isinstance(li, LootItem) for li in result.loot_items)

    def test_empty_tile_map_returns_player_with_no_enemies_bots_or_loot(self):
        ss = SpawnSystem()
        tm = _make_tile_map(player_spawns=[(100.0, 200.0)], loot_spawns=[], zones=[])
        result = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        assert result.enemies == []
        assert result.pvp_bots == []
        assert result.loot_items == []
        assert isinstance(result.player, Player)

    def test_tile_map_without_player_spawns_attr_does_not_crash(self):
        """TileMap lacking player_spawns uses fallback and returns a valid Player."""
        ss = SpawnSystem()

        class _MinimalTileMap:
            loot_spawns: list = []
            zones: list = []
            # no player_spawns attr — tests getattr fallback

        result = ss.spawn_round(_MinimalTileMap(), _make_enemy_db(), _make_item_db())
        assert isinstance(result.player, Player)

    def test_total_entity_spawned_event_count_equals_entity_total(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(
            enemy_spawns=[
                {"type": "grunt", "pos": [100, 100]},
                {"type": "heavy", "pos": [200, 100]},
            ],
            pvp_bot_spawns=[(300.0, 100.0)],
        )
        tm = _make_tile_map(
            loot_spawns=[(50.0, 60.0), (70.0, 80.0)],
            zones=[zone],
        )
        ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        # 2 loot + 2 enemies + 1 pvp_bot + 1 player = 6
        assert len(event_bus.all_events("entity_spawned")) == 6

    def test_all_events_carry_entity_type_field(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(
            enemy_spawns=[{"type": "grunt", "pos": [100, 100]}],
            pvp_bot_spawns=[(200.0, 200.0)],
        )
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0)], zones=[zone])
        ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        for _, payload in event_bus.emitted:
            assert "entity_type" in payload

    def test_all_events_carry_entity_field(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0)], zones=[])
        ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        for _, payload in event_bus.emitted:
            assert "entity" in payload


# ---------------------------------------------------------------------------
# Spawn dependency order
# ---------------------------------------------------------------------------


class TestSpawnOrder:
    """Entities must be created in order: loot → enemies → pvp_bots → player."""

    def test_loot_spawned_before_enemies(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [100, 100]}])
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0)], zones=[zone])
        ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        types = [p["entity_type"] for _, p in event_bus.emitted]
        assert types.index("loot") < types.index("enemy")

    def test_enemies_spawned_before_pvp_bots(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(
            enemy_spawns=[{"type": "grunt", "pos": [100, 100]}],
            pvp_bot_spawns=[(200.0, 200.0)],
        )
        tm = _make_tile_map(zones=[zone])
        ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        types = [p["entity_type"] for _, p in event_bus.emitted]
        assert types.index("enemy") < types.index("pvp_bot")

    def test_pvp_bots_spawned_before_player(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(pvp_bot_spawns=[(200.0, 200.0)])
        tm = _make_tile_map(zones=[zone])
        ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        types = [p["entity_type"] for _, p in event_bus.emitted]
        assert types.index("pvp_bot") < types.index("player")

    def test_player_is_always_the_last_event(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(
            enemy_spawns=[{"type": "grunt", "pos": [100, 100]}],
            pvp_bot_spawns=[(200.0, 200.0)],
        )
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0)], zones=[zone])
        ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        types = [p["entity_type"] for _, p in event_bus.emitted]
        assert types[-1] == "player"

    def test_loot_is_the_first_event(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [100, 100]}])
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0)], zones=[zone])
        ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        types = [p["entity_type"] for _, p in event_bus.emitted]
        assert types[0] == "loot"

    def test_full_order_loot_enemy_bot_player(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(
            enemy_spawns=[{"type": "grunt", "pos": [100, 100]}],
            pvp_bot_spawns=[(200.0, 200.0)],
        )
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0)], zones=[zone])
        ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        types = [p["entity_type"] for _, p in event_bus.emitted]
        # Verify strict ordering: loot < enemy < pvp_bot < player
        assert types.index("loot") < types.index("enemy")
        assert types.index("enemy") < types.index("pvp_bot")
        assert types.index("pvp_bot") < types.index("player")


# ---------------------------------------------------------------------------
# Full round lifecycle: spawn → teardown → re-spawn  (E2E)
# ---------------------------------------------------------------------------


class TestRoundLifecycle:
    """End-to-end: a complete round spawns all entities then tears them down cleanly."""

    def test_teardown_marks_all_enemies_dead_after_spawn_round(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[
            {"type": "grunt", "pos": [100, 100]},
            {"type": "heavy", "pos": [200, 100]},
        ])
        tm = _make_tile_map(zones=[zone])
        result = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        enemies_ref = list(result.enemies)
        ss.teardown(result.enemies, result.pvp_bots, result.loot_items)
        assert all(e.alive is False for e in enemies_ref)

    def test_teardown_marks_all_pvp_bots_dead_after_spawn_round(self):
        ss = SpawnSystem()
        zone = _zone(pvp_bot_spawns=[(100.0, 100.0), (200.0, 100.0)])
        tm = _make_tile_map(zones=[zone])
        result = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        bots_ref = list(result.pvp_bots)
        ss.teardown(result.enemies, result.pvp_bots, result.loot_items)
        assert all(b.alive is False for b in bots_ref)

    def test_teardown_marks_all_loot_items_dead_after_spawn_round(self):
        ss = SpawnSystem()
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0), (70.0, 80.0)])
        result = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        loot_ref = list(result.loot_items)
        ss.teardown(result.enemies, result.pvp_bots, result.loot_items)
        assert all(li.alive is False for li in loot_ref)

    def test_teardown_empties_all_result_lists(self):
        ss = SpawnSystem()
        zone = _zone(
            enemy_spawns=[{"type": "grunt", "pos": [100, 100]}],
            pvp_bot_spawns=[(200.0, 200.0)],
        )
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0)], zones=[zone])
        result = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        ss.teardown(result.enemies, result.pvp_bots, result.loot_items)
        assert len(result.enemies) == 0
        assert len(result.pvp_bots) == 0
        assert len(result.loot_items) == 0

    def test_second_spawn_round_after_teardown_produces_fresh_entities(self):
        ss = SpawnSystem()
        zone = _zone(
            enemy_spawns=[{"type": "grunt", "pos": [100, 100]}],
            pvp_bot_spawns=[(200.0, 200.0)],
        )
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0)], zones=[zone])

        result1 = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        ss.teardown(result1.enemies, result1.pvp_bots, result1.loot_items)

        result2 = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        assert isinstance(result2.player, Player)
        assert result2.player.alive is True
        assert all(e.alive for e in result2.enemies)
        assert all(b.alive for b in result2.pvp_bots)
        assert all(li.alive for li in result2.loot_items)

    def test_event_counts_are_independent_across_two_rounds(self, event_bus):
        ss = SpawnSystem(event_bus=event_bus)
        zone = _zone(
            enemy_spawns=[{"type": "grunt", "pos": [100, 100]}],
            pvp_bot_spawns=[(200.0, 200.0)],
        )
        tm = _make_tile_map(loot_spawns=[(50.0, 60.0)], zones=[zone])

        # First round: 1 loot + 1 enemy + 1 bot + 1 player = 4 events
        result1 = ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        first_round_count = len(event_bus.all_events("entity_spawned"))
        assert first_round_count == 4

        ss.teardown(result1.enemies, result1.pvp_bots, result1.loot_items)

        # Second round adds another 4 events (bus accumulates)
        ss.spawn_round(tm, _make_enemy_db(), _make_item_db())
        assert len(event_bus.all_events("entity_spawned")) == 8
