"""EnemyDatabase — parse ``data/enemies.json`` and produce typed RobotEnemy instances.

Usage::

    db = EnemyDatabase()
    grunt = db.create("grunt", pos=(100, 200), waypoints=[(100, 200), (300, 200)])
    table = db.get_loot_table("grunt_drops")
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

from src.entities.robot_enemy import RobotEnemy

if TYPE_CHECKING:
    pass

# Default location relative to the project root.
_DEFAULT_PATH = Path(__file__).parents[2] / "data" / "enemies.json"


class EnemyDatabase:
    """Loads enemy configuration once at startup and acts as a factory.

    Parameters
    ----------
    path:
        Path to ``enemies.json``.  Defaults to ``data/enemies.json`` relative
        to the project root.
    asset_manager:
        Optional :class:`~src.core.asset_manager.AssetManager` used to load
        sprite sheets.  When *None*, sprite loading is skipped.
    """

    def __init__(
        self,
        path: Optional[Path | str] = None,
        asset_manager: object = None,
    ) -> None:
        resolved = Path(path) if path is not None else _DEFAULT_PATH

        with open(resolved, encoding="utf-8") as fh:
            raw = json.load(fh)

        self._types: dict = raw.get("enemies", {})
        self._loot_tables: dict = raw.get("loot_tables", {})
        self._asset_manager = asset_manager

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    def create(
        self,
        type_id: str,
        pos: Tuple[float, float] | Sequence[float],
        waypoints: Optional[Sequence[Tuple[float, float]]] = None,
    ) -> RobotEnemy:
        """Instantiate a :class:`~src.entities.robot_enemy.RobotEnemy`.

        Parameters
        ----------
        type_id:
            Key from ``enemies.json`` (e.g. ``"grunt"``).
        pos:
            ``(x, y)`` spawn position in world pixels.
        waypoints:
            Ordered patrol waypoints.  Defaults to a single point at *pos*.

        Raises
        ------
        KeyError
            If *type_id* is not defined in the loaded config.
        """
        cfg = self._types[type_id]  # KeyError propagated intentionally

        loot_table_id: str = cfg.get("loot_table", "")
        loot_entries: List[dict] = self._loot_tables.get(
            loot_table_id, {}
        ).get("entries", [])

        patrol: List[Tuple[float, float]]
        if waypoints:
            patrol = [(float(wp[0]), float(wp[1])) for wp in waypoints]
        else:
            patrol = [(float(pos[0]), float(pos[1]))]

        robot = RobotEnemy(
            x=float(pos[0]),
            y=float(pos[1]),
            width=cfg.get("frame_width", 32),
            height=cfg.get("frame_height", 48),
            hp=cfg["hp"],
            patrol_speed=float(cfg.get("patrol_speed", 40)),
            move_speed=float(cfg.get("move_speed", 80)),
            aggro_range=float(cfg.get("aggro_range", 200)),
            attack_range=float(cfg.get("attack_range", 40)),
            attack_damage=int(cfg.get("attack_damage", 10)),
            attack_cooldown=float(cfg.get("attack_cooldown", 1.2)),
            xp_reward=int(cfg.get("xp_reward", 25)),
            loot_table=list(loot_entries),
            type_id=type_id,
            patrol_waypoints=patrol,
        )

        # Attempt sprite load — non-fatal if asset manager is absent or returns None.
        if self._asset_manager is not None:
            sprite_path: Optional[str] = cfg.get("sprite_sheet")
            if sprite_path:
                try:
                    surface = self._asset_manager.load_image(sprite_path)
                    if surface is not None:
                        robot._sprite_sheet = surface
                except Exception:
                    pass

        return robot

    # ------------------------------------------------------------------
    # Loot table access
    # ------------------------------------------------------------------

    def get_loot_table(self, table_id: str) -> List[dict]:
        """Return the list of ``{"item_id", "weight"}`` entries for *table_id*.

        Returns an empty list if the table is not found.
        """
        return list(self._loot_tables.get(table_id, {}).get("entries", []))

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def type_ids(self) -> List[str]:
        """Return all defined enemy type identifiers."""
        return list(self._types.keys())
