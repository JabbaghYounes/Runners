Implement per-zone vendor challenges that grant bonus rewards on completion.

Depends on: tile-map, pve-robot-enemies, loot-system

- Challenges are defined in `data/challenges.json` with type, zone, target count, and reward
- Challenge types (MVP): kill N robots in zone, collect N items, reach a location
- `ChallengeSystem` subscribes to relevant EventBus events and tracks per-challenge progress
- Completing a challenge emits `"challenge_completed"` with reward payload (XP, money, item)
- Active challenge progress is displayed in the HUD challenge widget
- Challenges reset each round; completed ones grant rewards at extraction/round-end

