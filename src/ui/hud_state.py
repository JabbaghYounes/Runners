"""HUDState — immutable snapshot passed to HUD each frame."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BuffEntry:
    """One active timed buff to display on the HUD."""
    label: str
    seconds_left: float
    icon: object = None          # pygame.Surface or None


@dataclass
class WeaponInfo:
    """Display data for the currently equipped weapon."""
    name: str
    ammo_current: int
    ammo_reserve: int
    icon: object = None          # pygame.Surface or None
    reloading: bool = False
    reload_progress: float = 0.0


@dataclass
class ZoneInfo:
    """A single map zone for minimap rendering."""
    name: str
    color: tuple[int, int, int]
    world_rect: object           # pygame.Rect


@dataclass
class ChallengeInfo:
    """One active vendor challenge to display in the challenge tracker."""
    name: str
    progress: int
    target: int
    completed: bool = False


@dataclass
class ConsumableSlot:
    """One consumable quick-slot entry."""
    label: str
    count: int
    icon: object = None          # pygame.Surface or None


@dataclass
class HUDState:
    """Full per-frame snapshot of game state for HUD rendering.

    GameScene assembles this each frame and passes it to HUD.update().
    The HUD never holds direct references to game system objects.
    """
    # ── Player vitals ──────────────────────────────────────────────
    hp: float = 100.0
    max_hp: float = 100.0
    armor: float = 0.0
    max_armor: float = 100.0

    # ── Progression ────────────────────────────────────────────────
    level: int = 1
    xp: float = 0.0
    xp_to_next: float = 100.0

    # ── Round timer ────────────────────────────────────────────────
    seconds_remaining: float = 900.0

    # ── Buffs ──────────────────────────────────────────────────────
    active_buffs: list[BuffEntry] = field(default_factory=list)

    # ── Map / minimap ──────────────────────────────────────────────
    player_world_pos: tuple[float, float] = (0.0, 0.0)
    map_world_rect: object = None    # pygame.Rect or None
    zones: list[ZoneInfo] = field(default_factory=list)
    extraction_pos: Optional[tuple[float, float]] = None

    # ── Inventory ──────────────────────────────────────────────────
    equipped_weapon: Optional[WeaponInfo] = None
    consumable_slots: list[ConsumableSlot] = field(default_factory=list)

    # ── Challenges ─────────────────────────────────────────────────
    active_challenges: list[ChallengeInfo] = field(default_factory=list)
