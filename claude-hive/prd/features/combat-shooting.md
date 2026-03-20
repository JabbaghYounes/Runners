Implement hitscan/projectile weapons, a shooting system, and armor-aware damage resolution.

Depends on: player-movement

- Aim direction derived from mouse cursor relative to player world position
- `ShootingSystem` spawns `Projectile` entities that travel at configured speed and despawn on tile collision or max range
- Projectiles render on `LAYER_PROJECTILES` (Z = 4)
- Damage formula: `effective = max(1, raw − armor)`; `PVP_FRIENDLY_FIRE` constant gates whether player projectiles harm other players
- `CombatSystem` emits `"damage_taken"` and `"entity_killed"` events on the `EventBus`
- Weapons have configurable fire rate, magazine size, and reload time (defined in JSON data file)

