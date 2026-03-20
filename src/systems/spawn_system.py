"""SpawnSystem -- instantiate robot enemies and PvP bots from map data.

Spawn order: loot → robot enemies → PvP bots → player.

Each successful entity creation emits ``"entity_spawned"`` on the EventBus
with payload ``(entity_type, entity, x, y)``.

Zone enemy configuration (unchanged)::

    [{"type": "grunt", "pos": [x, y]}, ...]

The top-level map JSON may carry a ``bot_spawns`` list::

    [{"pos": [x, y], "patrol_waypoints": [[x1,y1], ...], "difficulty": "medium"}, ...]

``spawn_points`` on the zone are reused as patrol waypoints so that robots
patrol the area they guard.
"""
from __future__ import annotations

import random
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.data.enemy_database import EnemyDatabase
    from src.entities.loot_item import LootItem
    from src.entities.player import Player
    from src.entities.player_agent import PlayerAgent
    from src.entities.robot_enemy import RobotEnemy
    from src.entities.player_agent import PlayerAgent
    from src.inventory.item_database import ItemDatabase
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
    # Player spawning
    # ------------------------------------------------------------------

    def spawn_player(
        self,
        spawn_points: "list[tuple[float, float]]",
    ) -> "Player":
        """Create the player entity at a randomly chosen spawn point.

        Parameters:
            spawn_points: List of ``(x, y)`` world positions. When empty,
                          the player is placed at the world origin (0, 0).

        Returns:
            A newly constructed :class:`Player` instance.
        """
        from src.entities.player import Player

        if spawn_points:
            sx, sy = random.choice(spawn_points)
        else:
            sx, sy = 0.0, 0.0

        player = Player(float(sx), float(sy), event_bus=self._event_bus)
        self._emit("player", player, float(sx), float(sy))
        return player

    # ------------------------------------------------------------------
    # Loot spawning
    # ------------------------------------------------------------------

    def spawn_loot(
        self,
        spawn_points: "list[tuple[float, float]]",
        item_db: "ItemDatabase | None",
    ) -> "list[LootItem]":
        """Place one loot item at each spawn point.

        Parameters:
            spawn_points: List of ``(x, y)`` world positions.
            item_db:      ItemDatabase used to pick and create items.
                          When ``None`` or empty, returns an empty list.

        Returns:
            List of :class:`LootItem` instances.
        """
        if item_db is None or not getattr(item_db, 'item_ids', None):
            return []

        from src.entities.loot_item import LootItem

        loot: List["LootItem"] = []
        for (lx, ly) in spawn_points:
            item_id = random.choice(item_db.item_ids)
            item = item_db.create(item_id)
            if item is None:
                continue
            loot_item = LootItem(item, float(lx), float(ly))
            loot.append(loot_item)
            self._emit("loot", loot_item, float(lx), float(ly))
        return loot

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

    def spawn_pvp_bots(
        self,
        zones: "List[Zone]",
    ) -> "List[PlayerAgent]":
        """Create a :class:`PlayerAgent` for every entry in each zone's
        ``pvp_bot_spawns`` list.

        Parameters:
            zones: Iterable of :class:`Zone` objects. Zones that lack the
                   ``pvp_bot_spawns`` attribute, or have it as ``None`` / empty,
                   contribute zero bots.

        Returns:
            Flat list of :class:`PlayerAgent` instances in zone order.
        """
        from src.entities.player_agent import PlayerAgent

        bots: List[PlayerAgent] = []
        for zone in zones:
            spawns = getattr(zone, "pvp_bot_spawns", None) or []
            for (bx, by) in spawns:
                try:
                    bot = PlayerAgent(x=float(bx), y=float(by))
                    bots.append(bot)
                    self._emit("pvp_bot", bot, float(bx), float(by))
                except Exception:
                    pass
        return bots

    def teardown(
        self,
        enemies: "List",
        pvp_bots: "List",
        loot_items: "List",
    ) -> None:
        """Mark every entity dead and clear all three lists in-place.

        Safe to call on already-empty lists or entities already dead.
        Idempotent: a second call on the now-empty lists is a no-op.
        """
        for entity in list(enemies):
            entity.alive = False
        enemies.clear()

        for entity in list(pvp_bots):
            entity.alive = False
        pvp_bots.clear()

        for entity in list(loot_items):
            entity.alive = False
        loot_items.clear()

    def spawn_round(
        self,
        tile_map: Any,
        enemy_db: "EnemyDatabase",
        item_db: "ItemDatabase",
    ) -> "SpawnResult":
        """Create all round entities from *tile_map* data.

        Spawn order: loot → robot enemies → PvP bots → player.

        Returns:
            :class:`SpawnResult` containing all created entities.
        """
        # Loot first (earliest in event order)
        loot_spawns = getattr(tile_map, "loot_spawns", []) or []
        loot_items = self.spawn_loot(loot_spawns, item_db)

        # Robot enemies from all zone enemy_spawns definitions
        zones = getattr(tile_map, "zones", []) or []
        enemies = self.spawn_all_zones(zones, enemy_db)

        # PvP bots from each zone's pvp_bot_spawns list
        pvp_bots = self.spawn_pvp_bots(zones)

        # Player last (must always be the final entity_spawned event)
        player_spawns = getattr(tile_map, "player_spawns", []) or []
        player = self.spawn_player(player_spawns)

        return SpawnResult(
            player=player,
            enemies=enemies,
            pvp_bots=pvp_bots,
            loot_items=loot_items,
        )

    def spawn_bots(
        self,
        map_data: dict,
        item_db: "ItemDatabase",
    ) -> List["PlayerAgent"]:
        """Instantiate PvP bots from the ``bot_spawns`` array in map data.

        Each entry may have:
            ``pos``              — [x, y] world-space spawn position (required)
            ``patrol_waypoints`` — [[x,y], …] patrol route (optional)
            ``difficulty``       — ``"easy"`` | ``"medium"`` | ``"hard"``

        Invalid or out-of-bounds entries are skipped with a warning.

        Returns:
            List of fully-equipped :class:`PlayerAgent` instances.
        """
        from src.entities.player_agent import PlayerAgent
        from src.entities.bot_loadout import BotLoadoutBuilder

        bot_spawns = map_data.get("bot_spawns", [])
        bots: List[PlayerAgent] = []

        for i, entry in enumerate(bot_spawns):
            # --- Validate required 'pos' key ---
            if "pos" not in entry:
                warnings.warn(
                    f"[SpawnSystem] bot_spawns[{i}] missing 'pos' key — skipped",
                    stacklevel=2,
                )
                continue

            pos = entry["pos"]
            try:
                bx, by = float(pos[0]), float(pos[1])
            except (TypeError, ValueError, IndexError):
                warnings.warn(
                    f"[SpawnSystem] bot_spawns[{i}] invalid pos {pos!r} — skipped",
                    stacklevel=2,
                )
                continue

            # --- Parse waypoints ---
            raw_wps = entry.get("patrol_waypoints", [])
            waypoints = []
            for wp in raw_wps:
                try:
                    waypoints.append((float(wp[0]), float(wp[1])))
                except (TypeError, ValueError, IndexError):
                    pass
            if not waypoints:
                waypoints = [(bx, by)]

            difficulty: str = entry.get("difficulty", "medium")

            # --- Build loadout ---
            try:
                loadout = BotLoadoutBuilder.random_loadout(item_db, difficulty)
            except Exception as exc:
                warnings.warn(
                    f"[SpawnSystem] bot_spawns[{i}] loadout error: {exc} — "
                    f"spawning with empty loadout",
                    stacklevel=2,
                )
                loadout = {"weapon": None, "armor": None}

            # --- Construct bot ---
            try:
                bot = PlayerAgent(
                    x=bx,
                    y=by,
                    patrol_waypoints=waypoints,
                    loadout=loadout,
                    difficulty=difficulty,
                )
                bots.append(bot)
            except Exception as exc:
                warnings.warn(
                    f"[SpawnSystem] bot_spawns[{i}] construction failed: {exc} — skipped",
                    stacklevel=2,
                )

        return bots
