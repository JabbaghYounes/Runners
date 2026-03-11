"""
Tests for SpawnSystem and EnemyDatabase
========================================

SpawnSystem tests verify:
  - correct enemy counts per zone
  - correct types and positions
  - patrol waypoint assignment (zone spawn_points vs. fallback)
  - graceful handling of unknown type IDs
  - spawn_all_zones aggregation across multiple zones

EnemyDatabase tests verify:
  - loading and parsing enemies.json
  - create() factory produces correctly-configured RobotEnemy instances
  - KeyError on unknown type IDs
  - get_loot_table() returns the expected entries
  - type_ids() enumerates all defined types
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.entities.robot_enemy import AIState, RobotEnemy
from src.map.zone import Zone
from src.systems.spawn_system import SpawnSystem


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _zone(
    name: str = "test_zone",
    enemy_spawns: list | None = None,
    spawn_points: list | None = None,
) -> Zone:
    return Zone(
        name=name,
        rect=(0, 0, 640, 480),
        enemy_spawns=enemy_spawns if enemy_spawns is not None else [],
        spawn_points=spawn_points if spawn_points is not None else [],
    )


def _make_enemy_db(known_types: tuple = ("grunt", "heavy", "sniper")) -> MagicMock:
    """Mock EnemyDatabase whose ``create()`` produces real RobotEnemy objects."""

    def _create(type_id: str, pos, waypoints=None) -> RobotEnemy:
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


# ===========================================================================
# SpawnSystem.spawn_zone_enemies — counts
# ===========================================================================

class TestSpawnZoneEnemiesCount:

    def test_empty_enemy_spawns_returns_empty_list(self):
        ss = SpawnSystem()
        result = ss.spawn_zone_enemies(_zone(enemy_spawns=[]), _make_enemy_db())
        assert result == []

    def test_single_entry_returns_one_robot(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [100, 200]}])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert len(result) == 1

    def test_three_entries_return_three_robots(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[
            {"type": "grunt",  "pos": [100, 100]},
            {"type": "heavy",  "pos": [200, 100]},
            {"type": "sniper", "pos": [300, 100]},
        ])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert len(result) == 3

    def test_duplicate_type_ids_each_produce_a_robot(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[
            {"type": "grunt", "pos": [100, 0]},
            {"type": "grunt", "pos": [200, 0]},
        ])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert len(result) == 2

    def test_unknown_type_id_is_silently_skipped(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[
            {"type": "grunt",   "pos": [100, 100]},
            {"type": "phantom", "pos": [200, 100]},  # unknown
        ])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert len(result) == 1

    def test_all_unknown_type_ids_returns_empty(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[{"type": "ghost", "pos": [0, 0]}])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert result == []

    def test_mix_of_valid_and_unknown_types(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[
            {"type": "grunt",   "pos": [0, 0]},
            {"type": "???",     "pos": [0, 0]},
            {"type": "sniper",  "pos": [0, 0]},
            {"type": "missing", "pos": [0, 0]},
        ])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert len(result) == 2


# ===========================================================================
# SpawnSystem.spawn_zone_enemies — types and positions
# ===========================================================================

class TestSpawnZoneEnemiesDetails:

    def test_spawned_robot_has_correct_type_id(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[{"type": "heavy", "pos": [50, 75]}])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert result[0].type_id == "heavy"

    def test_spawned_robots_have_correct_types_in_order(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[
            {"type": "grunt",  "pos": [0, 0]},
            {"type": "sniper", "pos": [0, 0]},
        ])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert result[0].type_id == "grunt"
        assert result[1].type_id == "sniper"

    def test_spawned_robot_placed_at_correct_x(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [123, 456]}])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert result[0].x == pytest.approx(123.0)

    def test_spawned_robot_placed_at_correct_y(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [123, 456]}])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert result[0].y == pytest.approx(456.0)

    def test_spawned_robots_are_robot_enemy_instances(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[
            {"type": "grunt",  "pos": [0, 0]},
            {"type": "sniper", "pos": [0, 0]},
        ])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert all(isinstance(r, RobotEnemy) for r in result)

    def test_spawned_robots_start_alive(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [0, 0]}])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert result[0].alive is True

    def test_spawned_robots_start_in_patrol_state(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [0, 0]}])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert result[0].state == AIState.PATROL

    def test_returns_plain_list(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[{"type": "grunt", "pos": [0, 0]}])
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert isinstance(result, list)


# ===========================================================================
# SpawnSystem.spawn_zone_enemies — patrol waypoints
# ===========================================================================

class TestSpawnZoneEnemiesWaypoints:

    def test_zone_spawn_points_passed_as_waypoints_to_create(self):
        """SpawnSystem must forward zone.spawn_points to EnemyDatabase.create()."""
        ss = SpawnSystem()
        wps = [(10, 20), (30, 40), (50, 60)]
        zone = _zone(
            enemy_spawns=[{"type": "grunt", "pos": [10, 20]}],
            spawn_points=wps,
        )
        db = MagicMock()
        db.create.return_value = RobotEnemy(x=10.0, y=20.0, hp=50)
        ss.spawn_zone_enemies(zone, db)
        # Third positional arg to create() must be the zone's spawn_points.
        passed_waypoints = db.create.call_args[0][2]
        assert list(passed_waypoints) == wps

    def test_zone_waypoints_stored_on_robot(self):
        ss = SpawnSystem()
        wps = [(10, 20), (30, 40)]
        zone = _zone(
            enemy_spawns=[{"type": "grunt", "pos": [10, 20]}],
            spawn_points=wps,
        )
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert result[0].patrol_waypoints == [(10, 20), (30, 40)]

    def test_falls_back_to_spawn_position_when_no_zone_waypoints(self):
        ss = SpawnSystem()
        zone = _zone(
            enemy_spawns=[{"type": "grunt", "pos": [77, 88]}],
            spawn_points=[],
        )
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        assert result[0].patrol_waypoints == [(77.0, 88.0)]

    def test_each_robot_in_zone_receives_same_zone_waypoints(self):
        ss = SpawnSystem()
        wps = [(0, 0), (100, 0)]
        zone = _zone(
            enemy_spawns=[
                {"type": "grunt",  "pos": [0, 0]},
                {"type": "sniper", "pos": [100, 0]},
            ],
            spawn_points=wps,
        )
        result = ss.spawn_zone_enemies(zone, _make_enemy_db())
        for robot in result:
            assert robot.patrol_waypoints == wps

    def test_zone_without_spawn_points_attr_falls_back_gracefully(self):
        """Zone-like objects without spawn_points must not raise."""
        ss = SpawnSystem()

        class _BareZone:
            enemy_spawns = [{"type": "grunt", "pos": [50, 50]}]
            # no spawn_points attribute

        result = ss.spawn_zone_enemies(_BareZone(), _make_enemy_db())  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0].patrol_waypoints == [(50.0, 50.0)]


# ===========================================================================
# SpawnSystem.spawn_all_zones
# ===========================================================================

class TestSpawnAllZones:

    def test_empty_zones_list_returns_empty(self):
        ss = SpawnSystem()
        assert ss.spawn_all_zones([], _make_enemy_db()) == []

    def test_single_zone_aggregated(self):
        ss = SpawnSystem()
        zone = _zone(enemy_spawns=[
            {"type": "grunt", "pos": [100, 100]},
            {"type": "heavy", "pos": [200, 100]},
        ])
        result = ss.spawn_all_zones([zone], _make_enemy_db())
        assert len(result) == 2

    def test_multiple_zones_merged_into_flat_list(self):
        ss = SpawnSystem()
        zone_a = _zone(name="a", enemy_spawns=[{"type": "grunt", "pos": [0, 0]}])
        zone_b = _zone(name="b", enemy_spawns=[
            {"type": "heavy",  "pos": [100, 0]},
            {"type": "sniper", "pos": [200, 0]},
        ])
        result = ss.spawn_all_zones([zone_a, zone_b], _make_enemy_db())
        assert len(result) == 3

    def test_zone_with_no_enemy_spawns_contributes_nothing(self):
        ss = SpawnSystem()
        empty = _zone(name="empty", enemy_spawns=[])
        active = _zone(name="active", enemy_spawns=[{"type": "grunt", "pos": [50, 50]}])
        result = ss.spawn_all_zones([empty, active], _make_enemy_db())
        assert len(result) == 1

    def test_result_is_a_flat_list_of_robot_enemy_instances(self):
        ss = SpawnSystem()
        zones = [
            _zone(name="z1", enemy_spawns=[{"type": "grunt",  "pos": [0, 0]}]),
            _zone(name="z2", enemy_spawns=[{"type": "sniper", "pos": [0, 0]}]),
        ]
        result = ss.spawn_all_zones(zones, _make_enemy_db())
        assert isinstance(result, list)
        assert all(isinstance(r, RobotEnemy) for r in result)

    def test_all_zones_empty_returns_empty(self):
        ss = SpawnSystem()
        zones = [_zone(name=f"z{i}", enemy_spawns=[]) for i in range(5)]
        assert ss.spawn_all_zones(zones, _make_enemy_db()) == []

    def test_many_zones_correct_total_count(self):
        ss = SpawnSystem()
        zones = [
            _zone(name=f"zone_{i}", enemy_spawns=[{"type": "grunt", "pos": [i * 100, 0]}])
            for i in range(5)
        ]
        result = ss.spawn_all_zones(zones, _make_enemy_db())
        assert len(result) == 5


# ===========================================================================
# EnemyDatabase integration (uses real data/enemies.json)
# ===========================================================================

_ENEMIES_JSON = Path(__file__).resolve().parents[1] / "data" / "enemies.json"


@pytest.mark.skipif(
    not _ENEMIES_JSON.exists(),
    reason="data/enemies.json not found — skipping EnemyDatabase tests",
)
class TestEnemyDatabase:

    @pytest.fixture(autouse=True)
    def db(self):
        from src.data.enemy_database import EnemyDatabase
        return EnemyDatabase(path=_ENEMIES_JSON)

    # --- type_ids ---

    def test_type_ids_contains_grunt(self, db):
        assert "grunt" in db.type_ids()

    def test_type_ids_contains_heavy(self, db):
        assert "heavy" in db.type_ids()

    def test_type_ids_contains_sniper(self, db):
        assert "sniper" in db.type_ids()

    # --- create() happy path ---

    def test_create_grunt_returns_robot_enemy(self, db):
        robot = db.create("grunt", (100.0, 200.0))
        assert isinstance(robot, RobotEnemy)

    def test_create_sets_correct_position(self, db):
        robot = db.create("grunt", (150.0, 250.0))
        assert robot.x == pytest.approx(150.0)
        assert robot.y == pytest.approx(250.0)

    def test_create_grunt_hp(self, db):
        robot = db.create("grunt", (0, 0))
        assert robot.hp == 50
        assert robot.max_hp == 50

    def test_create_heavy_hp(self, db):
        robot = db.create("heavy", (0, 0))
        assert robot.hp == 150

    def test_create_sniper_hp(self, db):
        robot = db.create("sniper", (0, 0))
        assert robot.hp == 30

    def test_create_grunt_aggro_range(self, db):
        robot = db.create("grunt", (0, 0))
        assert robot.aggro_range == pytest.approx(200.0)

    def test_create_sniper_has_long_aggro_range(self, db):
        robot = db.create("sniper", (0, 0))
        assert robot.aggro_range > robot.hp  # sniper range (350) > hp (30)

    def test_create_sets_type_id(self, db):
        for type_id in ("grunt", "heavy", "sniper"):
            assert db.create(type_id, (0, 0)).type_id == type_id

    def test_create_with_waypoints_stores_them(self, db):
        wps = [(0.0, 0.0), (100.0, 0.0)]
        robot = db.create("grunt", (0.0, 0.0), waypoints=wps)
        assert robot.patrol_waypoints == wps

    def test_create_without_waypoints_defaults_to_spawn_pos(self, db):
        robot = db.create("grunt", (77.0, 88.0))
        assert robot.patrol_waypoints == [(77.0, 88.0)]

    def test_create_starts_robot_alive(self, db):
        assert db.create("grunt", (0, 0)).alive is True

    def test_create_starts_in_patrol_state(self, db):
        assert db.create("grunt", (0, 0)).state == AIState.PATROL

    def test_create_grunt_attack_damage(self, db):
        robot = db.create("grunt", (0, 0))
        assert robot.attack_damage == 10

    def test_create_sniper_attack_damage(self, db):
        robot = db.create("sniper", (0, 0))
        assert robot.attack_damage == 35

    def test_create_grunt_xp_reward(self, db):
        robot = db.create("grunt", (0, 0))
        assert robot.xp_reward == 25

    def test_create_grunt_loot_table_is_populated(self, db):
        robot = db.create("grunt", (0, 0))
        assert isinstance(robot.loot_table, list)
        assert len(robot.loot_table) > 0

    def test_create_loot_table_entries_have_item_id(self, db):
        robot = db.create("grunt", (0, 0))
        for entry in robot.loot_table:
            assert "item_id" in entry

    def test_create_loot_table_entries_have_weight(self, db):
        robot = db.create("grunt", (0, 0))
        for entry in robot.loot_table:
            assert "weight" in entry

    # --- create() error path ---

    def test_create_unknown_type_id_raises_key_error(self, db):
        with pytest.raises(KeyError):
            db.create("unknown_bot", (0, 0))

    def test_create_empty_type_id_raises_key_error(self, db):
        with pytest.raises(KeyError):
            db.create("", (0, 0))

    # --- get_loot_table() ---

    def test_get_loot_table_grunt_drops_not_empty(self, db):
        entries = db.get_loot_table("grunt_drops")
        assert len(entries) > 0

    def test_get_loot_table_unknown_returns_empty(self, db):
        assert db.get_loot_table("nonexistent_table") == []

    def test_get_loot_table_returns_list_of_dicts(self, db):
        entries = db.get_loot_table("grunt_drops")
        assert isinstance(entries, list)
        assert all(isinstance(e, dict) for e in entries)

    def test_get_loot_table_grunt_contains_ammo_pistol(self, db):
        items = {e["item_id"] for e in db.get_loot_table("grunt_drops")}
        assert "ammo_pistol" in items

    def test_get_loot_table_heavy_drops_not_empty(self, db):
        assert len(db.get_loot_table("heavy_drops")) > 0

    def test_get_loot_table_sniper_drops_not_empty(self, db):
        assert len(db.get_loot_table("sniper_drops")) > 0
