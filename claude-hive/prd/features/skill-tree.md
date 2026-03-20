Implement a prerequisite-based skill tree that players unlock with XP or skill points earned per level.

Depends on: xp-leveling

- Skill tree structure and prerequisites defined in `data/skill_tree.json`
- Player earns 1 skill point per level-up
- Unlocking a skill requires all prerequisite skills to be unlocked and sufficient skill points
- Skills grant passive stat bonuses (e.g. +10% move speed, +5 max HP, +1 armor)
- `SkillTree` screen renders nodes as a graph with locked/available/unlocked visual states
- Unlocked skills are persisted in save data and applied on player spawn each round

