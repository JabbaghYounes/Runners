"""Enemy tier definitions and JSON loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class EnemyTier(Enum):
    SCOUT = "scout"
    ENFORCER = "enforcer"


@dataclass(frozen=True)
class EnemyTierConfig:
    """Immutable stat block for a single enemy tier.

    All values are loaded from ``data/enemies.json``.
    """

    tier: EnemyTier
    health: int
    speed: float
    damage: int
    detection_range: float
    attack_range: float
    fire_rate: float        # shots per second
    alert_delay: float      # seconds in DETECT before ATTACK
    idle_duration: float    # seconds in IDLE before PATROL
    loot_table_id: str
    xp_reward: int
    sprite_key: str


def load_enemy_tiers(path: str | Path = "data/enemies.json") -> dict[str, EnemyTierConfig]:
    """Load ``data/enemies.json`` and return a ``{tier_name: config}`` mapping."""
    with open(path, "r") as fh:
        data = json.load(fh)

    tiers: dict[str, EnemyTierConfig] = {}
    for name, stats in data["tiers"].items():
        tiers[name] = EnemyTierConfig(
            tier=EnemyTier(name),
            health=int(stats["health"]),
            speed=float(stats["speed"]),
            damage=int(stats["damage"]),
            detection_range=float(stats["detection_range"]),
            attack_range=float(stats["attack_range"]),
            fire_rate=float(stats["fire_rate"]),
            alert_delay=float(stats["alert_delay"]),
            idle_duration=float(stats["idle_duration"]),
            loot_table_id=str(stats["loot_table_id"]),
            xp_reward=int(stats["xp_reward"]),
            sprite_key=str(stats["sprite_key"]),
        )
    return tiers
