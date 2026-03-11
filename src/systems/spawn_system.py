"""SpawnSystem — instantiate robot enemies from zone configuration.

Usage (inside ``GameScene.__init__``)::

    spawn = SpawnSystem()
    self.enemies = spawn.spawn_all_zones(self._zones, enemy_db)

Each :class:`~src.map.zone.Zone` may carry an ``enemy_spawns`` list::

    [{"type": "grunt", "pos": [x, y]}, ...]

``spawn_points`` on the zone are reused as patrol waypoints so that robots
patrol the area they guard.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.data.enemy_database import EnemyDatabase
    from src.entities.robot_enemy import RobotEnemy
    from src.map.zone import Zone


class SpawnSystem:
    """Creates :class:`~src.entities.robot_enemy.RobotEnemy` instances from
    zone spawn configuration.

    This class is stateless; a single instance can be reused across rounds.
    """

    def spawn_zone_enemies(
        self,
        zone: "Zone",
        enemy_db: "EnemyDatabase",
    ) -> List["RobotEnemy"]:
        """Spawn all enemies defined in *zone*.

        Parameters
        ----------
        zone:
            A :class:`~src.map.zone.Zone` with an ``enemy_spawns`` attribute.
        enemy_db:
            Factory used to produce configured robot instances.

        Returns
        -------
        list[RobotEnemy]
            All successfully created robots.  Entries with unknown type IDs
            are silently skipped.
        """
        enemies: List["RobotEnemy"] = []
        enemy_spawns: list = getattr(zone, "enemy_spawns", [])

        # Use zone's spawn_points as patrol waypoints; fall back to individual
        # robot spawn positions when the zone has no generic spawn points.
        zone_waypoints = list(getattr(zone, "spawn_points", []))

        for entry in enemy_spawns:
            type_id: str = entry.get("type", "")
            pos = entry.get("pos", [0, 0])

            # Fall back to just the spawn position when no zone waypoints exist.
            waypoints = zone_waypoints if zone_waypoints else [(float(pos[0]), float(pos[1]))]

            try:
                robot = enemy_db.create(type_id, pos, waypoints)
                enemies.append(robot)
            except KeyError:
                # Unknown type_id — skip without crashing.
                pass
            except Exception:
                # Defensive: any other config error should not abort the round.
                pass

        return enemies

    def spawn_all_zones(
        self,
        zones: List["Zone"],
        enemy_db: "EnemyDatabase",
    ) -> List["RobotEnemy"]:
        """Convenience method — spawn enemies for every zone and merge results.

        Parameters
        ----------
        zones:
            All zones in the current map.
        enemy_db:
            Shared :class:`~src.data.enemy_database.EnemyDatabase` instance.

        Returns
        -------
        list[RobotEnemy]
            Flat list of all robots from all zones.
        """
        all_enemies: List["RobotEnemy"] = []
        for zone in zones:
            all_enemies.extend(self.spawn_zone_enemies(zone, enemy_db))
        return all_enemies
