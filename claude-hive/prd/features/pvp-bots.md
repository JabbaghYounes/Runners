Add AI-controlled PvP bots that behave as hostile players using the same AI framework as robots.

Depends on: pve-robot-enemies

- PvP bots share the `AISystem` FSM but are tagged as `PLAYER` faction for damage routing
- Bots equip random loadouts from the item database at spawn
- `PVP_FRIENDLY_FIRE` constant controls whether bots damage each other
- Bots attempt to collect loot items encountered on their patrol path
- Bot count and spawn locations are configurable in the map data file
- Killing a PvP bot awards XP and causes it to drop its current inventory as loot

