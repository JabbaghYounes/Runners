import random
from typing import List, Any, Optional

class LootSystem:
    PICKUP_RADIUS = 48

    def __init__(self, event_bus: Any, item_db: Any):
        self._event_bus = event_bus
        self._item_db = item_db
        self._pending_drops: List[dict] = []
        event_bus.subscribe('enemy_killed', self._on_enemy_killed)

    def _on_enemy_killed(self, **kwargs: Any) -> None:
        loot_table = kwargs.get('loot_table', [])
        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        item_ids = self.roll_loot_table(loot_table)
        for item_id in item_ids:
            self._pending_drops.append({'item_id': item_id, 'x': x, 'y': y})

    def roll_loot_table(self, table: List[dict]) -> List[str]:
        if not table:
            return []
        total = sum(e.get('weight', 1) for e in table)
        roll = random.uniform(0, total)
        cumulative = 0
        for entry in table:
            cumulative += entry.get('weight', 1)
            if roll <= cumulative:
                return [entry['item_id']]
        return []

    def update(self, e_key_pressed: bool, loot_items: List[Any],
               players: List[Any]) -> List[Any]:
        new_drops = []
        for drop in self._pending_drops:
            item = self._item_db.create(drop['item_id'])
            if item:
                new_drops.append(self.spawn_at((drop['x'], drop['y']), item))
        self._pending_drops.clear()

        if e_key_pressed:
            for loot in loot_items:
                if loot.despawn:
                    continue
                for player in players:
                    import math
                    dx = loot.rect.centerx - player.rect.centerx
                    dy = loot.rect.centery - player.rect.centery
                    if math.hypot(dx, dy) <= self.PICKUP_RADIUS:
                        if player.inventory.add(loot.item):
                            loot.despawn = True
                            self._event_bus.emit('item_picked_up', item=loot.item)
                            break

        return new_drops

    def spawn_at(self, pos: tuple, item: Any) -> Any:
        from src.entities.loot_item import LootItem
        drop = LootItem(pos[0], pos[1], item)
        return drop
