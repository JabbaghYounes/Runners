from dataclasses import dataclass, field
from typing import Dict, List, Any

@dataclass
class ActiveBuff:
    name: str
    duration: float
    modifiers: Dict[str, float] = field(default_factory=dict)
    source_id: int = 0

class BuffSystem:
    def __init__(self):
        self._buffs: List[ActiveBuff] = []

    def add_buff(self, buff: ActiveBuff) -> None:
        self._buffs.append(buff)

    def update(self, dt: float) -> None:
        for b in self._buffs:
            b.duration -= dt
        self._buffs = [b for b in self._buffs if b.duration > 0]

    def get_modifiers(self) -> Dict[str, float]:
        combined: Dict[str, float] = {}
        for buff in self._buffs:
            for k, v in buff.modifiers.items():
                combined[k] = combined.get(k, 0.0) + v
        return combined

    def remove_entity(self, source_id: int) -> None:
        self._buffs = [b for b in self._buffs if b.source_id != source_id]

    def get_active_buff_names(self) -> List[str]:
        return [b.name for b in self._buffs]
