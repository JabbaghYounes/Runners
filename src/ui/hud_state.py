from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any

@dataclass
class ZoneInfo:
    name: str
    rect_tuple: Tuple[int, int, int, int]  # (x, y, w, h)
    color: Tuple[int, int, int] = (60, 120, 180)

@dataclass
class BuffEntry:
    name: str
    duration_remaining: float

@dataclass
class WeaponInfo:
    name: str
    ammo: int = 0
    max_ammo: int = 0

@dataclass
class HUDState:
    hp: int = 100
    max_hp: int = 100
    armor: int = 0
    max_armor: int = 100
    level: int = 1
    xp: int = 0
    xp_to_next: int = 900
    seconds_remaining: float = 900.0
    active_buffs: List[BuffEntry] = field(default_factory=list)
    player_world_pos: Tuple[float, float] = (0.0, 0.0)
    map_world_rect: Optional[Any] = None  # pygame.Rect
    zones: List[ZoneInfo] = field(default_factory=list)
    extraction_pos: Optional[Tuple[float, float]] = None
    equipped_weapon: Optional[WeaponInfo] = None
    consumable_slots: List[Optional[Any]] = field(default_factory=list)
    active_challenges: List[Any] = field(default_factory=list)
    in_extraction_zone: bool = False
    extraction_progress: float = 0.0
    currency: int = 0
