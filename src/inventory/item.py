from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional

class Rarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"

    @classmethod
    def from_str(cls, s: str) -> 'Rarity':
        mapping = {r.value: r for r in cls}
        return mapping.get(s.lower(), cls.COMMON)

@dataclass
class Item:
    item_id: str
    name: str
    type: str
    rarity: Rarity
    weight: float
    value: int
    stats: Dict[str, Any] = field(default_factory=dict)

    def get_stat(self, key: str, default=0):
        return self.stats.get(key, default)

@dataclass
class Weapon(Item):
    def __post_init__(self):
        self.type = 'weapon'

@dataclass
class Armor(Item):
    def __post_init__(self):
        self.type = 'armor'

@dataclass
class Consumable(Item):
    def __post_init__(self):
        self.type = 'consumable'

@dataclass
class Attachment(Item):
    def __post_init__(self):
        self.type = 'attachment'

def make_item(data: Dict[str, Any]) -> Item:
    item_type = data.get('type', 'item')
    rarity = Rarity.from_str(data.get('rarity', 'common'))
    kwargs = dict(
        item_id=data.get('item_id', 'unknown'),
        name=data.get('name', 'Unknown'),
        type=item_type,
        rarity=rarity,
        weight=float(data.get('weight', 0)),
        value=int(data.get('value', 0)),
        stats=data.get('stats', {}),
    )
    type_map = {
        'weapon': Weapon,
        'armor': Armor,
        'consumable': Consumable,
        'attachment': Attachment,
    }
    cls = type_map.get(item_type, Item)
    return cls(**kwargs)
