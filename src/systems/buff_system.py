"""Buff system — manages timed stat modifiers on entities."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.entities.player import Player


@dataclass
class ActiveBuff:
    """A single active timed buff applied to an entity."""
    stat: str            # e.g. "speed", "damage"
    modifier: float      # additive modifier value
    duration: float      # total duration in seconds
    remaining: float     # seconds left
    label: str = ""      # display name
    icon: object = None  # pygame.Surface icon or None


class BuffSystem:
    """Manages active buffs across all entities.

    Stores buffs in a dict keyed by entity id (id(entity)).
    """

    def __init__(self) -> None:
        self._buffs: dict[int, list[ActiveBuff]] = {}

    def add_buff(self, entity: object, buff: ActiveBuff) -> None:
        """Add *buff* to *entity*'s active buff list."""
        key = id(entity)
        if key not in self._buffs:
            self._buffs[key] = []
        self._buffs[key].append(buff)

    def update(self, dt: float) -> None:
        """Tick all buff durations; remove expired ones."""
        for key in list(self._buffs.keys()):
            buffs = self._buffs[key]
            expired = [b for b in buffs if b.remaining <= 0]
            for b in expired:
                buffs.remove(b)
            for b in buffs:
                b.remaining -= dt
            if not buffs:
                del self._buffs[key]

    def get_modifiers(self, entity: object, stat_name: str) -> list[float]:
        """Return all active modifier values for *stat_name* on *entity*."""
        key = id(entity)
        if key not in self._buffs:
            return []
        return [b.modifier for b in self._buffs[key] if b.stat == stat_name]

    def get_buffs(self, entity: object) -> list[ActiveBuff]:
        """Return all active buffs for *entity*."""
        return list(self._buffs.get(id(entity), []))

    def remove_entity(self, entity: object) -> None:
        """Remove all buff state for *entity* (call when entity is destroyed)."""
        self._buffs.pop(id(entity), None)
