"""Active buff tracking and per-frame tick system.

``BuffSystem`` is owned by ``GameScene`` and updated each frame.
Player (or any entity) delegates ``apply_buff()`` calls here so the
system can centrally expire buffs and emit the relevant EventBus events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.core.event_bus import event_bus

if TYPE_CHECKING:
    from src.entities.player import Player


@dataclass
class ActiveBuff:
    """A single in-progress stat modifier applied to an entity.

    Attributes:
        buff_type:      Stat name this modifies, e.g. ``"speed"``, ``"damage"``.
        value:          Additive modifier magnitude.
        duration:       Original total duration in seconds.
        time_remaining: Seconds left before the buff expires.
        icon_key:       AssetManager sprite key for the HUD icon.
    """

    buff_type: str
    value: float
    duration: float
    time_remaining: float
    icon_key: str = ""


class BuffSystem:
    """Manages active buffs across all entities."""

    def __init__(self) -> None:
        self._entity_buffs: dict[int, list[ActiveBuff]] = {}

    def add_buff(self, entity: "Player", buff: ActiveBuff) -> None:
        key = id(entity)
        if key not in self._entity_buffs:
            self._entity_buffs[key] = entity.active_buffs
        entity.active_buffs.append(buff)
        event_bus.emit(
            "buff_applied",
            entity=entity,
            buff_type=buff.buff_type,
            value=buff.value,
            duration=buff.duration,
            icon_key=buff.icon_key,
        )

    def update(self, dt: float) -> None:
        for buffs in list(self._entity_buffs.values()):
            expired: list[ActiveBuff] = []
            for buff in buffs:
                buff.time_remaining -= dt
                if buff.time_remaining <= 0:
                    expired.append(buff)
            for buff in expired:
                buffs.remove(buff)
                event_bus.emit("buff_expired", buff_type=buff.buff_type)

    def get_modifiers(self, entity: "Player", stat_name: str) -> float:
        return sum(
            b.value for b in entity.active_buffs if b.buff_type == stat_name
        )

    def remove_entity(self, entity: "Player") -> None:
        key = id(entity)
        if key in self._entity_buffs:
            entity.active_buffs.clear()
            del self._entity_buffs[key]

    # Legacy aliases
    def get_active_buff_names(self) -> list[str]:
        names = []
        for buffs in self._entity_buffs.values():
            names.extend(b.buff_type for b in buffs)
        return names
