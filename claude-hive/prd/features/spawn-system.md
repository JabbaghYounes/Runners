Manage the spawning of the player, robot enemies, PvP bots, and static loot at round start.

Depends on: tile-map, pve-robot-enemies, pvp-bots, loot-system

- Spawn points for all entity types are defined in the map data file
- `SpawnSystem` instantiates entities at round start in dependency order: map → loot → enemies → player
- Player spawns at a random valid player spawn point each round
- Robot and PvP bot counts are configurable per zone in the map data file
- Spawning emits `"entity_spawned"` on the EventBus for each entity
- Round end tears down all spawned entities and resets the scene for the next round

