"""SpawnSystem -- instantiate all entities at round start.

Spawn order: loot → robot enemies → PvP bots → player.

Each successful entity creation emits ``"entity_spawned"`` on the EventBus
with payload ``(entity_type, entity, x, y)``.

Zone enemy configuration (unchanged)::

    [{"type": "grunt", "pos": [x, y]}, ...]

``spawn_points`` on the zone are reused as patrol waypoints so that robots
patrol the area they guard.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.data.enemy_database import EnemyDatabase
    from src.entities.loot_item import LootItem
    from src.entities.player import Player
    from src.entities.player_agent import PlayerAgent
    from src.entities.robot_enemy import RobotEnemy
    from src.inventory.item_database import ItemDatabase
    from src.map.tile_map import TileMap
    from src.map.zone import Zone


@dataclass
class SpawnResult:
    """Container returned by :meth:`SpawnSystem.spawn_round`.

    Attributes:
        player:     The player entity placed at its spawn point.
        enemies:    All robot enemies created across all zones.
        pvp_bots:   All PvP-bot agents created across all zones.
        loot_items: All loot entities placed at map loot spawn points.
    """

    player: "Player"
    enemies: List["RobotEnemy"] = field(default_factory=list)
    pvp_bots: List["PlayerAgent"] = field(default_factory=list)
    loot_items: List["LootItem"] = field(default_factory=list)


class SpawnSystem:
    """Creates and tears down all entities for a round.

    Parameters:
        event_bus: Optional EventBus; when provided an ``"entity_spawned"``
                   event is emitted for every successfully created entity.
    """

    def __init__(self, event_bus: "EventBus | None" = None) -> None:
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, entity_type: str, entity: Any, x: float, y: float) -> None:
        """Emit ``"entity_spawned"`` if an event bus is configured."""
        if self._event_bus is not None:
            self._event_bus.emit(
                "entity_spawned",
                entity_type=entity_type,
                entity=entity,
                x=x,
                y=y,
            )

    # ------------------------------------------------------------------
    # Robot enemy spawning
    # ------------------------------------------------------------------

    def spawn_zone_enemies(
        self,
        zone: "Zone",
        enemy_db: "EnemyDatabase",
    ) -> List["RobotEnemy"]:
        """Create RobotEnemy instances for a single zone's enemy_spawns list."""
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
                self._emit("enemy", robot, float(pos[0]), float(pos[1]))
            except KeyError:
                # Unknown type_id -- skip without crashing.
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
        """Aggregate robot enemies from every zone into a flat list."""
        all_enemies: List["RobotEnemy"] = []
        for zone in zones:
            all_enemies.extend(self.spawn_zone_enemies(zone, enemy_db))
        return all_enemies

    # ------------------------------------------------------------------
    # Player spawning
    # ------------------------------------------------------------------

    def spawn_player(self, player_spawns: List[tuple]) -> "Player":
        """Instantiate the Player at a randomly chosen valid spawn point.

        If *player_spawns* is empty the player is placed at world origin
        ``(0, 0)`` so the method always returns a usable entity.
        """
        from src.entities.player import Player

        if not player_spawns:
            player = Player(0.0, 0.0)
            self._emit("player", player, 0.0, 0.0)
            return player

        sx, sy = random.choice(player_spawns)
        sx, sy = float(sx), float(sy)
        player = Player(sx, sy)
        self._emit("player", player, sx, sy)
        return player

    # ------------------------------------------------------------------
    # Loot spawning
    # ------------------------------------------------------------------

    def spawn_loot(
        self,
        loot_spawns: List[tuple],
        item_db: "ItemDatabase | None",
    ) -> List["LootItem"]:
        """Place a random loot item at each loot spawn point.

        Returns an empty list when *item_db* is ``None`` or contains no items.
        Any individual spawn that raises an exception is silently skipped.
        """
        from src.entities.loot_item import LootItem

        if item_db is None:
            return []
        item_ids = getattr(item_db, "item_ids", [])
        if not item_ids:
            return []

        loot_items: List["LootItem"] = []
        for lx, ly in loot_spawns:
            lx, ly = float(lx), float(ly)
            try:
                item_id = random.choice(item_ids)
                item = item_db.create(item_id)
                if item is not None:
                    loot_item = LootItem(item, lx, ly)
                    loot_items.append(loot_item)
                    self._emit("loot", loot_item, lx, ly)
            except Exception:
                pass

        return loot_items

    # ------------------------------------------------------------------
    # PvP bot spawning
    # ------------------------------------------------------------------

    def spawn_pvp_bots(self, zones: List["Zone"]) -> List["PlayerAgent"]:
        """Create a PlayerAgent for each entry in zone.pvp_bot_spawns.

        Zones without a ``pvp_bot_spawns`` attribute, or with an empty list,
        contribute zero bots.  Individual creation failures are silently skipped.
        """
        from src.entities.player_agent import PlayerAgent

        bots: List["PlayerAgent"] = []
        for zone in zones:
            bot_spawns = getattr(zone, "pvp_bot_spawns", None) or []
            for bx, by in bot_spawns:
                bx, by = float(bx), float(by)
                try:
                    bot = PlayerAgent(x=bx, y=by)
                    bots.append(bot)
                    self._emit("pvp_bot", bot, bx, by)
                except Exception:
                    pass

        return bots

    # ------------------------------------------------------------------
    # Round-level orchestration
    # ------------------------------------------------------------------

    def spawn_round(
        self,
        tile_map: "TileMap",
        enemy_db: "EnemyDatabase",
        item_db: "ItemDatabase",
    ) -> SpawnResult:
        """Spawn all entities in dependency order and return a :class:`SpawnResult`.

        Order: **loot → robot enemies → PvP bots → player**.
        """
        loot_spawns = getattr(tile_map, "loot_spawns", [])
        zones = getattr(tile_map, "zones", [])
        player_spawns = getattr(tile_map, "player_spawns", [])

        # 1. Loot — world hazards first
        loot_items = self.spawn_loot(loot_spawns, item_db)

        # 2. Robot enemies
        enemies = self.spawn_all_zones(zones, enemy_db)

        # 3. PvP bots
        pvp_bots = self.spawn_pvp_bots(zones)

        # 4. Player — placed last so all hazards already exist
        player = self.spawn_player(player_spawns)

        return SpawnResult(
            player=player,
            enemies=enemies,
            pvp_bots=pvp_bots,
            loot_items=loot_items,
        )

    # ------------------------------------------------------------------
    # Round teardown
    # ------------------------------------------------------------------

    def teardown(
        self,
        enemies: List[Any],
        pvp_bots: List[Any],
        loot_items: List[Any],
    ) -> None:
        """Mark every spawned entity dead and empty the caller's lists.

        Idempotent: calling on already-empty lists or already-dead entities
        is safe and produces no side effects.
        """
        for entity in enemies:
            entity.alive = False
        for entity in pvp_bots:
            entity.alive = False
        for entity in loot_items:
            entity.alive = False
        enemies.clear()
        pvp_bots.clear()
        loot_items.clear()
