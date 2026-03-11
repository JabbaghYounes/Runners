"""
LootSystem — scatters a victim's inventory as LootItems on player_killed.
"""
from __future__ import annotations

import math
import random
from typing import Any


class LootItem:
    """A dropped item entity in the world."""

    def __init__(self, item: Any, x: float, y: float) -> None:
        self.item = item
        self.x = x
        self.y = y
        self.alive: bool = True


class LootSystem:
    """Listens for ``player_killed`` and spawns loot from the victim's inventory."""

    def __init__(self, event_bus: Any, item_db: Any) -> None:
        self._event_bus = event_bus
        self._item_db = item_db
        event_bus.subscribe("player_killed", self._on_player_killed)

    def _on_player_killed(self, killer: Any, victim: Any) -> list[LootItem]:
        """Spawn a LootItem for every item in the victim's inventory."""
        cx, cy = victim.rect.center

        # Gather items to drop
        items_to_drop: list[Any] = list(victim.inventory.slots)
        if victim.inventory.equipped_weapon is not None:
            items_to_drop.append(victim.inventory.equipped_weapon)
        if victim.inventory.equipped_armor is not None:
            items_to_drop.append(victim.inventory.equipped_armor)

        spawned: list[LootItem] = []
        for item in items_to_drop:
            # Pick a random position within a 32-px radius of the death location
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(0, 32)
            loot = LootItem(item, cx + radius * math.cos(angle), cy + radius * math.sin(angle))
            spawned.append(loot)

        victim.inventory.clear()
        return spawned
