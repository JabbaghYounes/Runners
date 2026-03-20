"""EnemyDatabase -- parse enemies.json and produce typed RobotEnemy instances."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from src.entities.robot_enemy import RobotEnemy

_DEFAULT_PATH = Path(__file__).parents[2] / "data" / "enemies.json"

# Default animation FPS per state when not specified in enemies.json
_DEFAULT_ANIM_FPS: dict[str, int] = {
    "patrol": 8,
    "aggro":  10,
    "attack": 12,
    "dead":   6,
}

# Magenta placeholder size returned by AssetManager on missing assets
_PLACEHOLDER_SIZE = (32, 32)


class EnemyDatabase:
    """Loads enemy configuration once at startup and acts as a factory.

    Parameters
    ----------
    path:
        Path to enemies.json.  Defaults to data/enemies.json.
    asset_manager:
        Optional AssetManager for sprite loading.  When provided,
        ``create()`` builds an ``AnimationController`` from the sprite
        sheet declared in the JSON and attaches it to the robot.
        When ``None``, ``robot.animation_controller`` is left as ``None``
        (coloured-rect fallback in ``render()``).
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

        # Build and attach animation controller when an asset manager is available
        if self._asset_manager is not None:
            self._build_animation_controller(robot, cfg)

        return robot

    # ------------------------------------------------------------------
    # Animation controller builder
    # ------------------------------------------------------------------

    def _build_animation_controller(self, robot: RobotEnemy, cfg: dict) -> None:
        """Slice the enemy sprite sheet and build an AnimationController.

        If the sprite sheet is missing (AssetManager returns a 32×32 magenta
        placeholder), single solid-colour fallback surfaces are used per state
        so the game runs without assets.  Out-of-range frame indices are
        clamped to valid bounds.
        """
        import pygame
        from src.entities.animation_controller import AnimationController

        frame_w: int = cfg.get("frame_width", 32)
        frame_h: int = cfg.get("frame_height", 48)
        sprite_sheet_path: str = cfg.get("sprite_sheet", "")

        sheet: pygame.Surface = self._asset_manager.load_image(sprite_sheet_path)  # type: ignore[attr-defined]

        # Detect the magenta placeholder returned by AssetManager on a miss
        is_placeholder: bool = sheet.get_size() == _PLACEHOLDER_SIZE

        # Per-state FPS from JSON (optional); fall back to hardcoded defaults
        anim_fps: dict[str, int] = {**_DEFAULT_ANIM_FPS, **cfg.get("anim_fps", {})}

        animations: dict = cfg.get("animations", {})

        # Ensure all four standard states exist even if JSON omits some
        for state in ("patrol", "aggro", "attack", "dead"):
            if state not in animations:
                animations[state] = [0]

        # Number of frames in the sheet (for index clamping)
        n_sheet_frames: int = max(1, sheet.get_width() // frame_w) if not is_placeholder else 1

        states_config: dict = {}
        for state_name, frame_indices in animations.items():
            fps = anim_fps.get(state_name, _DEFAULT_ANIM_FPS.get(state_name, 8))
            frames: list[pygame.Surface] = []

            if is_placeholder or not frame_indices:
                # Use a single solid-colour fallback surface
                surf = pygame.Surface((frame_w, frame_h))
                surf.fill((180, 60, 60))
                frames = [surf]
            else:
                for idx in frame_indices:
                    clamped = max(0, min(int(idx), n_sheet_frames - 1))
                    try:
                        frame = sheet.subsurface(clamped * frame_w, 0, frame_w, frame_h)
                        frames.append(frame)
                    except Exception:
                        # Dimension mismatch — fall back to solid colour
                        surf = pygame.Surface((frame_w, frame_h))
                        surf.fill((180, 60, 60))
                        frames.append(surf)

            # Guarantee at least one frame to prevent AnimationController errors
            if not frames:
                surf = pygame.Surface((frame_w, frame_h))
                surf.fill((180, 60, 60))
                frames = [surf]

            states_config[state_name] = {"frames": frames, "fps": fps}

        if states_config:
            robot.animation_controller = AnimationController(states_config)

    def get_loot_table(self, table_id: str) -> list:
        """Return loot entries for table_id, or empty list."""
        return list(self._loot_tables.get(table_id, {}).get("entries", []))

    def type_ids(self) -> list[str]:
        return list(self._types.keys())
