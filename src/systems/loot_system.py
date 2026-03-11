"""LootSystem — spawns loot on enemy death and handles E-key pickup.

Subscribes to the ``enemy_killed`` EventBus event; rolls the enemy's
loot table (or a default table) and spawns ``LootItem`` entities.
Each frame, ``update()`` checks whether the player is close enough and
pressing E, then transfers the item to the player's inventory.
"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from src.entities.loot_item import LootItem

if TYPE_CHECKING:
    pass

try:
    from src.core.constants import PICKUP_RADIUS
except (ImportError, ModuleNotFoundError):
    PICKUP_RADIUS = 64

# Default loot table — each entry has an item id and a relative probability weight.
_DEFAULT_LOOT_TABLE: list[dict] = [
    {"id": "medkit_small", "weight": 0.50},
    {"id": "medkit_large", "weight": 0.30},
    {"id": "stim_speed", "weight": 0.15},
    {"id": "stim_damage", "weight": 0.05},
]

# Named loot tables available to the system.
_LOOT_TABLES: dict[str, list[dict]] = {
    "default": _DEFAULT_LOOT_TABLE,
}


class LootSystem:
    """Manages loot spawning and item pickup for all players."""

    def __init__(self, event_bus, item_db) -> None:
        self._event_bus = event_bus
        self._item_db = item_db

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(self, loot_items, players, *, e_key_pressed: bool) -> list:
        """Check proximity + E-key and transfer items to inventories.

        Returns an empty list (reserved for future world-spawn notifications).
        """
        if not e_key_pressed:
            return []

        for loot in loot_items:
            if not loot.alive:
                continue
            for player in players:
                dist = math.dist(loot.rect.center, player.rect.center)
                if dist < PICKUP_RADIUS:
                    added = player.inventory.add(loot.item)
                    if added:
                        loot.alive = False
                        self._event_bus.emit(
                            "item_picked_up", player=player, item=loot.item
                        )
                    else:
                        self._event_bus.emit("inventory_full", player=player)
                    break  # item can only be picked up by one player

        return []

    # ------------------------------------------------------------------
    # Loot table rolling
    # ------------------------------------------------------------------

    def roll_loot_table(self, table_name: str) -> list[str]:
        """Roll *table_name* and return a list of item-id strings.

        Returns an empty list for unknown table names.
        """
        table = _LOOT_TABLES.get(table_name, [])
        if not table:
            return []

        # Weighted random selection — 0 or 1 item per roll
        ids = [e["id"] for e in table]
        weights = [e["weight"] for e in table]
        chosen = random.choices(ids, weights=weights, k=1)
        return chosen

    # ------------------------------------------------------------------
    # Spawning
    # ------------------------------------------------------------------

    def spawn_at(self, item_id: str, position: tuple) -> LootItem:
        """Create an Item via the database and wrap it in a LootItem at *position*."""
        item = self._item_db.create(item_id)
        loot = LootItem(item, position[0], position[1])
        return loot

    # ------------------------------------------------------------------
    # Enemy-killed handler
    # ------------------------------------------------------------------

    def _on_enemy_killed(self, killer, enemy) -> list:
        """Roll the enemy's loot table and spawn LootItems at the death position.

        Returns the list of spawned LootItem instances.
        """
        item_ids = self.roll_loot_table(enemy.loot_table_id)
        spawned = []
        for item_id in item_ids:
            loot = self.spawn_at(item_id, enemy.rect.center)
            spawned.append(loot)
        return spawned
