"""LootSystem — world loot spawning and proximity pickup."""
from __future__ import annotations
import random
from typing import TYPE_CHECKING

from src.core import event_bus as _event_bus_module

if TYPE_CHECKING:
    from src.entities.loot_item import LootItem
    from src.inventory.item_database import item_database
    from src.entities.player import Player

_DEFAULT_LOOT_TABLE: list[dict] = []


class LootSystem:
    """Manages all world loot: spawning on kill and proximity pickup.

    Usage (inside GameScene)::

        self.loot_system = LootSystem()
        # Per frame:
        self.loot_system.update(self.player, e_key_pressed=True)
    """

    def __init__(self) -> None:
        self._loot_items: list = []
        _event_bus_module.event_bus.subscribe('enemy_killed', self._on_enemy_killed)

    @property
    def loot_items(self) -> list:
        """Read-only view of currently active loot items in the world."""
        return list(self._loot_items)

    def update(self, player: object, e_key_pressed: bool = False) -> None:
        """Process pickup interactions for one frame.

        For every live LootItem, if the player is close and e_key_pressed,
        add the item to the player's inventory.
        """
        if player is None:
            return
        px = player.rect.centerx
        py = player.rect.centery
        consumed: list = []
        for loot in list(self._loot_items):
            if not loot.alive:
                consumed.append(loot)
                continue
            if e_key_pressed:
                dx = loot.rect.centerx - px
                dy = loot.rect.centery - py
                if (dx * dx + dy * dy) <= 64 * 64:
                    slot = player.inventory.add_item(loot.item)
                    if slot is not None:
                        loot.alive = False
                        consumed.append(loot)
                        _event_bus_module.event_bus.emit('item_picked_up',
                                                         player=player, item=loot.item)
        for loot in consumed:
            self._loot_items.remove(loot)

    def spawn_loot(self, x: float, y: float, loot_table: list | None = None) -> None:
        """Roll *loot_table* and spawn a ``LootItem`` at *(x, y)*."""
        table = loot_table or _DEFAULT_LOOT_TABLE
        if not table:
            return
        item_id = self._weighted_choice(table)
        if item_id is None:
            return
        try:
            from src.inventory.item_database import ItemDatabase
            item = ItemDatabase().create(item_id)
            from src.entities.loot_item import LootItem
            self._loot_items.append(LootItem(item, x, y))
        except Exception:
            pass

    def teardown(self) -> None:
        """Unsubscribe from event bus when the scene is destroyed."""
        _event_bus_module.event_bus.unsubscribe('enemy_killed', self._on_enemy_killed)

    def _on_enemy_killed(self, **payload: object) -> None:
        """EventBus handler for ``enemy_killed``."""
        enemy = payload.get('enemy')
        if enemy is None:
            return
        x = getattr(enemy.rect, 'centerx', 0)
        y = getattr(enemy.rect, 'centery', 0)
        loot_table = getattr(enemy, 'loot_table', None)
        self.spawn_loot(x, y, loot_table)

    @staticmethod
    def _weighted_choice(table: list) -> object:
        """Return one item_id from *table* using weighted random selection."""
        if not table:
            return None
        item_ids = [entry.get('item_id') for entry in table]
        weights = [entry.get('weight', 1) for entry in table]
        return random.choices(item_ids, weights=weights, k=1)[0]
