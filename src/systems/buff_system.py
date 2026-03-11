"""Buff system — timed stat modifiers applied to entities."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.entities.player import Player

from src.core import event_bus as _event_bus_module


@dataclass
class ActiveBuff:
    """A timed stat modifier."""
    stat: str
    value: float
    duration: float  # seconds remaining; -1 = permanent
    source: str = ""


class BuffSystem:
    """Manages active buffs across all entities.

    Stores buffs in a dict keyed by entity id (id(entity)).
    """

    def __init__(self) -> None:
        self._buffs: dict[int, list[ActiveBuff]] = {}

    def add_buff(self, entity, buff: ActiveBuff) -> None:
        """Add *buff* to *entity*'s active buff list."""
        key = id(entity)
        if key not in self._buffs:
            self._buffs[key] = []
        self._buffs[key].append(buff)

    def update(self, dt: float) -> None:
        """Tick all buff durations; remove expired ones."""
        for buffs in self._buffs.values():
            expired = [b for b in buffs if b.duration >= 0 and b.duration <= 0]
            for b in expired:
                buffs.remove(b)
            for b in buffs:
                if b.duration >= 0:
                    b.duration -= dt

    def get_modifiers(self, entity, stat_name: str) -> list[float]:
        """Return all active modifier values for *stat_name* on *entity*."""
        key = id(entity)
        return [b.value for b in self._buffs.get(key, []) if b.stat == stat_name]

    def remove_entity(self, entity) -> None:
        """Remove all buff state for *entity* (call when entity is destroyed)."""
        self._buffs.pop(id(entity), None)
