"""LootSystem — spawns loot on enemy death and handles E-key pickup.

Subscribes to the ``enemy_killed`` EventBus event; rolls the enemy's
loot table (or a default table) and spawns ``LootItem`` entities.
Each frame, ``update()`` checks whether the player is close enough and
pressing E, then transfers the item to the player's inventory.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from src.core.event_bus import event_bus
from src.entities.loot_item import LootItem
from src.inventory.item_database import item_database

if TYPE_CHECKING:
    from src.entities.player import Player


# Default loot table used when an enemy carries no explicit table.
_DEFAULT_LOOT_TABLE: list[dict] = [
    {"item_id": "medkit_small", "weight": 50},
    {"item_id": "medkit_large", "weight": 20},
    {"item_id": "stim_speed",   "weight": 20},
    {"item_id": "stim_damage",  "weight": 10},
]


class LootSystem:
    """Manages all world loot: spawning on kill and proximity pickup.

    Usage (inside GameScene)::

        self.loot_system = LootSystem()
        # Per frame:
        self.loot_system.update(self.player, e_key_pressed)
        # On scene exit:
        self.loot_system.teardown()
    """

    def __init__(self) -> None:
        self._loot_items: list[LootItem] = []
        event_bus.subscribe("enemy_killed", self._on_enemy_killed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def loot_items(self) -> list[LootItem]:
        """Read-only view of currently active loot items in the world."""
        return self._loot_items

    def update(self, player: "Player", e_key_pressed: bool) -> None:
        """Process pickup interactions for one frame.

        For every live LootItem, if the player presses E and is within
        pickup range, the item is transferred to the player's inventory
        and the LootItem is removed from the world.
        """
        px, py = player.center
        consumed: list[LootItem] = []

        for loot in self._loot_items:
            if not loot.alive:
                consumed.append(loot)
                continue
            if e_key_pressed and loot.in_pickup_range(px, py):
                item = loot.pickup()
                if player.inventory is not None:
                    slot = player.inventory.add_item(item)
                    if slot is not None:
                        event_bus.emit(
                            "item_picked_up", {"player": player, "item": item}
                        )
                consumed.append(loot)

        for loot in consumed:
            if loot in self._loot_items:
                self._loot_items.remove(loot)

    def spawn_loot(
        self,
        x: float,
        y: float,
        loot_table: list[dict] | None = None,
    ) -> None:
        """Roll *loot_table* and spawn a ``LootItem`` at *(x, y)*."""
        table = loot_table if loot_table is not None else _DEFAULT_LOOT_TABLE
        item_id = self._weighted_choice(table)
        if item_id is None:
            return
        try:
            item = item_database.create(item_id)
            self._loot_items.append(LootItem(item, x, y))
        except KeyError:
            pass  # Unknown item ID — skip silently.

    def teardown(self) -> None:
        """Unsubscribe from event bus when the scene is destroyed."""
        event_bus.unsubscribe("enemy_killed", self._on_enemy_killed)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_enemy_killed(self, payload: dict) -> None:
        """EventBus handler for ``enemy_killed``."""
        enemy = payload.get("enemy")
        if enemy is None:
            return
        x = float(getattr(enemy, "x", 0))
        y = float(getattr(enemy, "y", 0))
        loot_table = getattr(enemy, "loot_table", None)
        self.spawn_loot(x, y, loot_table)

    @staticmethod
    def _weighted_choice(table: list[dict]) -> str | None:
        """Return one item_id from *table* using weighted random selection."""
        if not table:
            return None
        item_ids = [entry["item_id"] for entry in table]
        weights = [entry.get("weight", 1) for entry in table]
        return random.choices(item_ids, weights=weights, k=1)[0]
