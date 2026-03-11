"""LootSystem -- world loot spawning and proximity pickup."""
from __future__ import annotations
import random
from typing import Any, List, Optional

from src.core.event_bus import event_bus as _global_bus
from src.entities.loot_item import LootItem

_DEFAULT_LOOT_TABLE: list[dict] = []


class LootSystem:
    """Manages all world loot: spawning on kill and proximity pickup."""

    PICKUP_RADIUS = 64

    def __init__(self, event_bus: Any = None, item_db: Any = None) -> None:
        self._event_bus = event_bus or _global_bus
        self._item_db = item_db
        self._loot_items: list = []
        self._pending_drops: list[dict] = []
        self._loot_tables: dict[str, list[dict]] = {}
        self._load_loot_tables()
        self._event_bus.subscribe('enemy_killed', self._on_enemy_killed)
        self._event_bus.subscribe('player_killed', self._on_player_killed)

    def _load_loot_tables(self) -> None:
        """Load loot tables from enemies.json and build a named registry."""
        import json
        from pathlib import Path
        enemies_path = Path("data") / "enemies.json"
        if not enemies_path.exists():
            return
        try:
            with enemies_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)

            # Load named loot tables from the "loot_tables" section
            raw_tables = data.get("loot_tables", {})
            for table_name, table_data in raw_tables.items():
                entries = table_data.get("entries", [])
                if entries:
                    self._loot_tables[table_name] = entries

            # Map enemy type_ids to their loot table entries
            enemies = data.get("enemies", {})
            all_items: list[dict] = []
            if isinstance(enemies, dict):
                for type_id, enemy_data in enemies.items():
                    table_ref = enemy_data.get("loot_table", "")
                    if isinstance(table_ref, str) and table_ref in self._loot_tables:
                        self._loot_tables[type_id] = self._loot_tables[table_ref]
                        all_items.extend(self._loot_tables[table_ref])
                    elif isinstance(table_ref, list):
                        self._loot_tables[type_id] = table_ref
                        all_items.extend(table_ref)
            else:
                # Legacy list format
                for enemy in enemies:
                    table = enemy.get("loot_table", [])
                    type_id = enemy.get("type_id", "")
                    if isinstance(table, str) and table in self._loot_tables:
                        self._loot_tables[type_id] = self._loot_tables[table]
                        all_items.extend(self._loot_tables[table])
                    elif isinstance(table, list):
                        self._loot_tables[type_id] = table
                        all_items.extend(table)

            if all_items:
                self._loot_tables["default"] = all_items
        except Exception:
            pass

    @property
    def loot_items(self) -> list:
        return list(self._loot_items)

    def _on_enemy_killed(self, *args: Any, **kwargs: Any) -> list:
        """Handle enemy kill for loot spawning.

        Supports:
        - _on_enemy_killed(killer, enemy)  -- direct call from tests
        - _on_enemy_killed(**kwargs)       -- event bus subscription
        """
        # Positional args: (killer, enemy)
        if len(args) >= 2:
            killer = args[0]
            enemy = args[1]
        else:
            killer = kwargs.get('killer')
            enemy = kwargs.get('enemy')

        if enemy is None:
            return []

        loot_table_id = getattr(enemy, 'loot_table_id', None)
        loot_table = kwargs.get('loot_table', [])
        if not loot_table and not loot_table_id:
            loot_table = getattr(enemy, 'loot_table', [])

        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        if not x and not y:
            rect = getattr(enemy, 'rect', None)
            if rect is not None:
                center = getattr(rect, 'center', (0, 0))
                x, y = center
            else:
                x = getattr(enemy, 'x', 0)
                y = getattr(enemy, 'y', 0)

        # If loot_table_id is set, use roll_loot_table
        if loot_table_id:
            item_ids = self.roll_loot_table(loot_table_id)
            spawned = []
            for item_id in item_ids:
                loot = self.spawn_at(item_id, (x, y))
                if loot is not None:
                    spawned.append(loot)
            return spawned

        # If we have an explicit loot_table (list of dicts), use it
        if loot_table:
            self.spawn_loot(x, y, loot_table)
            return list(self._loot_items[-1:])

        # Fallback: use default loot table
        if "default" in self._loot_tables:
            item_ids = self.roll_loot_table("default")
            spawned = []
            for item_id in item_ids:
                if item_id:
                    loot = self.spawn_at(item_id, (x, y))
                    if loot is not None:
                        spawned.append(loot)
            return spawned

        return []

    def spawn_at(self, item_id: str, pos: tuple) -> Any:
        """Spawn a loot item by ID at the given position."""
        x, y = pos
        try:
            if self._item_db is not None:
                item = self._item_db.create(item_id)
            else:
                from src.inventory.item_database import ItemDatabase
                item = ItemDatabase.instance().create(item_id)
        except (KeyError, Exception):
            return None
        loot = LootItem(item, x, y)
        self._loot_items.append(loot)
        return loot

    def spawn_loot(self, x: float, y: float, loot_table: list | None = None) -> None:
        table = loot_table if loot_table is not None else self._loot_tables.get("default", _DEFAULT_LOOT_TABLE)
        if not table:
            return
        item_id = self._weighted_choice(table)
        if item_id is None:
            return
        try:
            if self._item_db is not None:
                item = self._item_db.create(item_id)
            else:
                from src.inventory.item_database import ItemDatabase
                item = ItemDatabase.instance().create(item_id)
            from src.entities.loot_item import LootItem
            self._loot_items.append(LootItem(item, x, y))
        except Exception:
            pass

    def update(self, *args, **kwargs) -> list:
        """Flexible update signature to support multiple calling conventions."""
        # Support: update(e_key_pressed, loot_items, players)
        # Support: update(loot_items, players, e_key_pressed=True)
        # Support: update(player, e_key_pressed=False)
        if len(args) >= 2 and isinstance(args[0], bool):
            # Old style: update(e_key_pressed, loot_items, players)
            e_key_pressed = args[0]
            loot_items = args[1] if len(args) > 1 else []
            players = args[2] if len(args) > 2 else []
            return self._update_old(e_key_pressed, loot_items, players)
        elif len(args) >= 2 and isinstance(args[0], list) and isinstance(args[1], list):
            # Test style: update(loot_items, players, e_key_pressed=True)
            loot_items = args[0]
            players = args[1]
            e_key_pressed = kwargs.get('e_key_pressed', False)
            return self._update_old(e_key_pressed, loot_items, players)
        elif len(args) >= 1 and not isinstance(args[0], bool):
            # New style: update(player, e_key_pressed=False)
            player = args[0]
            e_key_pressed = kwargs.get('e_key_pressed', False)
            if player is not None:
                self._check_pickup(player, e_key_pressed)
            return []
        else:
            e_key_pressed = kwargs.get('e_key_pressed', False)
            return []

    def _check_pickup(self, player: Any, e_key_pressed: bool) -> None:
        # Always clean up dead loot items
        self._loot_items = [l for l in self._loot_items if getattr(l, 'alive', True)]

        if not e_key_pressed or player is None:
            return
        import math
        px = getattr(getattr(player, 'rect', None), 'centerx', 0)
        py = getattr(getattr(player, 'rect', None), 'centery', 0)
        consumed = []
        for loot in list(self._loot_items):
            if not getattr(loot, 'alive', True):
                consumed.append(loot)
                continue
            cx, cy = getattr(loot, 'center', (getattr(loot, 'x', 0), getattr(loot, 'y', 0)))
            dx = cx - px
            dy = cy - py
            if math.hypot(dx, dy) <= 64:
                inv = getattr(player, 'inventory', None)
                if inv is not None:
                    slot = inv.add_item(loot.item)
                    if slot is not None:
                        loot.alive = False
                        loot.picked_up = True
                        consumed.append(loot)
                        self._event_bus.emit('item_picked_up', player=player, item=loot.item)
        for loot in consumed:
            if loot in self._loot_items:
                self._loot_items.remove(loot)

    def _update_old(self, e_key_pressed: bool, loot_items: list, players: list) -> list:
        """Legacy update style."""
        new_drops = []
        for drop in self._pending_drops:
            item_id = drop.get('item_id')
            if item_id and self._item_db:
                item = self._item_db.create(item_id)
                if item:
                    new_drops.append(self._spawn_at((drop['x'], drop['y']), item))
        self._pending_drops.clear()

        if e_key_pressed:
            import math
            for loot in loot_items:
                if not getattr(loot, 'alive', True):
                    continue
                if getattr(loot, 'despawn', False):
                    continue
                for player in players:
                    prect = getattr(player, 'rect', None)
                    lrect = getattr(loot, 'rect', None)
                    if prect and lrect:
                        dx = lrect.centerx - prect.centerx
                        dy = lrect.centery - prect.centery
                        if math.hypot(dx, dy) < self.PICKUP_RADIUS:
                            inv = getattr(player, 'inventory', None)
                            if inv is not None:
                                slot = inv.add_item(loot.item)
                                if slot is not None:
                                    loot.alive = False
                                    loot.despawn = True
                                    self._event_bus.emit('item_picked_up', item=loot.item, player=player)
                                    break
                                else:
                                    # Inventory full
                                    self._event_bus.emit('inventory_full', player=player)

        return new_drops

    def _spawn_at(self, pos: tuple, item: Any) -> Any:
        from src.entities.loot_item import LootItem
        return LootItem(item, pos[0], pos[1])

    def _on_player_killed(self, **kwargs: Any) -> None:
        """Drop the victim's inventory items as world loot on PvP kill."""
        killer = kwargs.get('killer')
        victim = kwargs.get('victim')
        if victim is None:
            return []

        inv = getattr(victim, 'inventory', None)
        if inv is None:
            return []

        cx, cy = getattr(getattr(victim, 'rect', None), 'center', (0, 0))

        items_to_drop: list = []
        # Collect inventory slot items
        slots = getattr(inv, 'slots', [])
        items_to_drop.extend(list(slots))
        # Collect equipped weapon and armor
        equipped_weapon = getattr(inv, 'equipped_weapon', None)
        equipped_armor = getattr(inv, 'equipped_armor', None)
        if equipped_weapon is not None:
            items_to_drop.append(equipped_weapon)
        if equipped_armor is not None:
            items_to_drop.append(equipped_armor)

        spawned: list = []
        for item in items_to_drop:
            # Scatter items near the death position (within 32px radius)
            import random as _rand
            import math as _math
            angle = _rand.uniform(0, 2 * _math.pi)
            dist = _rand.uniform(0, 32)
            dx = dist * _math.cos(angle)
            dy = dist * _math.sin(angle)
            lx = cx + dx
            ly = cy + dy
            loot = LootItem(item, lx, ly)
            spawned.append(loot)

        # Clear victim's inventory
        if hasattr(inv, 'clear'):
            inv.clear()

        return spawned

    def teardown(self) -> None:
        self._event_bus.unsubscribe('enemy_killed', self._on_enemy_killed)
        try:
            self._event_bus.unsubscribe('player_killed', self._on_player_killed)
        except Exception:
            pass

    @staticmethod
    def _weighted_choice(table: list) -> Any:
        if not table:
            return None
        item_ids = [entry.get('item_id') for entry in table]
        weights = [entry.get('weight', 1) for entry in table]
        return random.choices(item_ids, weights=weights, k=1)[0]

    def roll_loot_table(self, table) -> list:
        """Roll on a loot table.

        Args:
            table: either a string table name or a list of dicts.
        """
        if isinstance(table, str):
            table_data = self._loot_tables.get(table, _DEFAULT_LOOT_TABLE)
        else:
            table_data = table
        if not table_data:
            return []
        result = self._weighted_choice(table_data)
        return [result] if result else []
