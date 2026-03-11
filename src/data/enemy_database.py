"""EnemyDatabase -- parse enemies.json and produce typed RobotEnemy instances."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from src.entities.robot_enemy import RobotEnemy

_DEFAULT_PATH = Path(__file__).parents[2] / "data" / "enemies.json"


class EnemyDatabase:
    """Loads enemy configuration once at startup and acts as a factory.

    Parameters
    ----------
    path:
        Path to enemies.json.  Defaults to data/enemies.json.
    asset_manager:
        Optional AssetManager for sprite loading.
    """

    def __init__(
        self,
        path: Optional["Path | str"] = None,
        asset_manager: object = None,
    ) -> None:
        self._types: dict = {}
        self._loot_tables: dict = {}
        self._asset_manager = asset_manager
        self._raw_data: dict = {}

        if path is not None:
            self._load_from_path(Path(path))

    def _load_from_path(self, resolved: Path) -> None:
        with open(resolved, encoding="utf-8") as fh:
            raw = json.load(fh)

        if isinstance(raw, dict):
            self._types = raw.get("enemies", raw)
            self._loot_tables = raw.get("loot_tables", {})
            self._raw_data = raw

    def load(self, path: str) -> None:
        """Legacy load method."""
        self._load_from_path(Path(path))

    def create(
        self,
        type_id: str,
        pos: "Tuple[float, float] | Sequence[float] | None" = None,
        waypoints: "Optional[Sequence[Tuple[float, float]]]" = None,
    ) -> RobotEnemy:
        """Create a RobotEnemy.

        Raises KeyError if type_id is not found.
        """
        if not type_id or type_id not in self._types:
            raise KeyError(f"Unknown enemy type: {type_id!r}")

        cfg = self._types[type_id]

        if pos is None:
            pos = (0.0, 0.0)

        loot_table_id: str = cfg.get("loot_table", "")
        if isinstance(loot_table_id, str):
            loot_entries: list = self._loot_tables.get(
                loot_table_id, {}
            ).get("entries", [])
        else:
            # loot_table is directly a list
            loot_entries = loot_table_id if isinstance(loot_table_id, list) else []

        patrol: list
        if waypoints:
            patrol = [(float(wp[0]), float(wp[1])) for wp in waypoints]
        else:
            patrol = [(float(pos[0]), float(pos[1]))]

        robot = RobotEnemy(
            x=float(pos[0]),
            y=float(pos[1]),
            width=cfg.get("frame_width", 32),
            height=cfg.get("frame_height", 48),
            hp=cfg.get("hp", 60),
            patrol_speed=float(cfg.get("patrol_speed", 40)),
            move_speed=float(cfg.get("move_speed", 80)),
            aggro_range=float(cfg.get("aggro_range", 200)),
            attack_range=float(cfg.get("attack_range", 40)),
            attack_damage=int(cfg.get("attack_damage", cfg.get("damage", 10))),
            attack_cooldown=float(cfg.get("attack_cooldown", 1.2)),
            xp_reward=int(cfg.get("xp_reward", 25)),
            loot_table=list(loot_entries),
            type_id=type_id,
            patrol_waypoints=patrol,
        )

        return robot

    def get_loot_table(self, table_id: str) -> list:
        """Return loot entries for table_id, or empty list."""
        return list(self._loot_tables.get(table_id, {}).get("entries", []))

    def type_ids(self) -> list[str]:
        return list(self._types.keys())
