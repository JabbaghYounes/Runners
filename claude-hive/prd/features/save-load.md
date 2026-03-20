Persist and restore player progression (inventory at home base, skill tree, home base upgrades, currency, XP/level).

Depends on: inventory-items, skill-tree, home-base, currency, xp-leveling

- `SaveManager` writes JSON to a `.tmp` file then renames atomically to prevent corruption
- Saved state includes: currency balance, XP + level, unlocked skills, purchased home base upgrades, stash inventory
- Save is triggered only from `PostRoundScreen` and `HomeBaseScene`
- On startup, save file is loaded; missing or corrupt file silently initialises a new-game state
- `CLAUDE.md` convention: `CLAUDE.md` is added to `.gitignore` in any new project init

