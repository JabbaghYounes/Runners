"""HUD state dataclasses — a pure-data snapshot passed from GameScene to the HUD.

These dataclasses carry no logic; they exist solely to decouple the HUD
renderer from the game-state internals.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any


@dataclass
class ZoneInfo:
    name: str
    color: Tuple[int, int, int] = (60, 120, 180)
    world_rect: Any = None  # pygame.Rect
    # Legacy field kept for backward compat
    rect_tuple: Tuple[int, int, int, int] | None = None


@dataclass
class BuffEntry:
    label: str
    seconds_left: float
    icon: Any = None
    # Legacy field names kept for backward compat
    name: str = ""
    duration_remaining: float = 0.0


@dataclass
class WeaponInfo:
    name: str
    ammo_current: int = 0
    ammo_reserve: int = 0
    icon: Any = None
    reloading: bool = False
    reload_progress: float = 0.0
    # Legacy field names
    ammo: int = 0
    max_ammo: int = 0


@dataclass
class ChallengeInfo:
    name: str
    progress: int = 0
    target: int = 0
    completed: bool = False


@dataclass
class ConsumableSlot:
    label: str
    count: int = 0
    icon: Any = None


@dataclass
class HUDState:
    hp: int = 100
    max_hp: int = 100
    armor: int = 0
    max_armor: int = 100
    level: int = 1
    xp: float = 0.0
    xp_to_next: float = 100.0
    seconds_remaining: float = 900.0
    active_buffs: List[BuffEntry] = field(default_factory=list)
    player_world_pos: Tuple[float, float] = (0.0, 0.0)
    map_world_rect: Optional[Any] = None  # pygame.Rect
    zones: List[ZoneInfo] = field(default_factory=list)
    extraction_pos: Optional[Tuple[float, float]] = None
    equipped_weapon: Optional[WeaponInfo] = None
    consumable_slots: List[ConsumableSlot] = field(default_factory=list)
    active_challenges: List[ChallengeInfo] = field(default_factory=list)
    in_extraction_zone: bool = False
    extraction_progress: float = 0.0
    currency: int = 0
    active_quick_slot: int = -1
