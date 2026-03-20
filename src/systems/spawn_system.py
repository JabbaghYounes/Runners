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

import warnings
from typing import TYPE_CHECKING, List

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
