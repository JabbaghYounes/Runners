"""Loot spawning system — subscribes to enemy_killed and rolls loot tables."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import pygame

from src.entities.loot_drop import LootDrop
from src.events import EventBus
from src.items import Item, ItemType, Rarity


@dataclass
class LootTableEntry:
    item_id: str
    weight: int


@dataclass
class LootTable:
    drop_chance: float
    rolls: int
    items: list[LootTableEntry] = field(default_factory=list)


def load_loot_tables(path: str | Path = "data/loot_tables.json") -> dict[str, LootTable]:
    """Parse ``data/loot_tables.json`` into ``{table_id: LootTable}``."""
    with open(path, "r") as fh:
        data = json.load(fh)

    tables: dict[str, LootTable] = {}
    for table_id, tbl in data.items():
        entries = [LootTableEntry(e["item_id"], e["weight"]) for e in tbl["items"]]
        tables[table_id] = LootTable(
            drop_chance=float(tbl["drop_chance"]),
            rolls=int(tbl["rolls"]),
            items=entries,
        )
    return tables


class LootSpawner:
    """Listens for ``enemy_killed`` events and spawns :class:`LootDrop` entities.

    Parameters:
        event_bus: Central event dispatcher.
        loot_tables: Pre-loaded table mapping.
        item_defs: ``{item_id: Item}`` definitions.  If an item_id is not
            found a generic placeholder item is created.
        loot_group: ``pygame.sprite.Group`` to add new drops to.
    """

    def __init__(
        self,
        event_bus: EventBus,
        loot_tables: dict[str, LootTable],
        item_defs: dict[str, Item] | None = None,
        loot_group: pygame.sprite.Group | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.loot_tables = loot_tables
        self.item_defs = item_defs or {}
        self.loot_group = loot_group if loot_group is not None else pygame.sprite.Group()
        self.event_bus.subscribe("enemy_killed", self._on_enemy_killed)

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    def _on_enemy_killed(self, **kwargs) -> None:
        enemy = kwargs.get("enemy")
        if enemy is None:
            return
        loot_table_id: str = kwargs.get("loot_table_id", "")
        pos = (enemy.pos.x, enemy.pos.y)
        items = self.roll_loot(loot_table_id)
        for item in items:
            self._spawn_drop(pos, item)

    # ------------------------------------------------------------------
    # Rolling
    # ------------------------------------------------------------------

    def roll_loot(self, loot_table_id: str) -> list[Item]:
        """Roll the loot table and return a list of dropped :class:`Item` objects."""
        table = self.loot_tables.get(loot_table_id)
        if table is None:
            return []

        # Check overall drop chance
        if random.random() > table.drop_chance:
            return []

        dropped: list[Item] = []
        for _ in range(table.rolls):
            entry = self._weighted_pick(table.items)
            if entry is not None:
                item = self._resolve_item(entry.item_id)
                dropped.append(item)
        return dropped

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _weighted_pick(entries: Sequence[LootTableEntry]) -> LootTableEntry | None:
        if not entries:
            return None
        total = sum(e.weight for e in entries)
        roll = random.uniform(0, total)
        cumulative = 0.0
        for entry in entries:
            cumulative += entry.weight
            if roll <= cumulative:
                return entry
        return entries[-1]  # pragma: no cover — rounding guard

    def _resolve_item(self, item_id: str) -> Item:
        """Look up *item_id* in ``self.item_defs`` or create a placeholder."""
        if item_id in self.item_defs:
            return self.item_defs[item_id]
        # Placeholder — real items loaded from data/items.json by the inventory feature
        return Item(
            id=item_id,
            name=item_id.replace("_", " ").title(),
            item_type=ItemType.CONSUMABLE,
            rarity=Rarity.COMMON,
            value=10,
        )

    def _spawn_drop(self, pos: tuple[float, float], item: Item) -> LootDrop:
        """Create a :class:`LootDrop` entity at *pos* and add it to the group."""
        # Slight random offset so multiple drops don't stack exactly
        offset_x = random.uniform(-16, 16)
        offset_y = random.uniform(-16, 16)
        drop = LootDrop(pos[0] + offset_x, pos[1] + offset_y, item)
        self.loot_group.add(drop)
        return drop
