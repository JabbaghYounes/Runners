Spawn loot items in the world, drop them from killed enemies, and handle pick-up.

Depends on: inventory-items, pve-robot-enemies

- `LootSystem` subscribes to `"enemy_killed"` and spawns `LootItem` entities at the death position based on enemy loot table
- Static loot is placed in the map data file and spawned by `LootSystem` at round start
- `LootItem` renders on `LAYER_LOOT` (Z = 1) with a sprite matching item rarity (color-coded border)
- Item rarity distribution: Common → Uncommon → Rare → Epic (weights configurable in JSON)
- Monetary value is derived from rarity tier (higher rarity = higher base value)
- Loot items that were not picked up despawn when the round ends

