Implement humanoid robot enemies with a 4-state AI FSM and BFS pathfinding.

Depends on: tile-map, combat-shooting

- States: PATROL → AGGRO → ATTACK → DEAD
- `AISystem` runs BFS pathfinding on the 32×32 tile grid, recalculated every 0.5 s
- Robots detect the player within a configurable aggro range and disengage when out of range
- Robots fire at the player during ATTACK state using the same `CombatSystem` as players
- Robot stats (HP, speed, damage, aggro range, XP value) are data-driven via `data/enemies.json`
- Robots render on `LAYER_ENEMIES` (Z = 2) with idle, walk, and attack animations
- Death emits `"enemy_killed"` on the EventBus

