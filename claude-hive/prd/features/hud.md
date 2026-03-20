Render the in-game HUD overlay with health, XP, timer, challenge progress, and quick slots.

Depends on: player-movement, xp-leveling, round-timer, inventory-items, challenge-system

- Health bar reflects current/max HP and updates on `"damage_taken"` / `"item_used"` events
- XP bar and level indicator update on `"player_leveled_up"` and XP gain events
- Round timer displayed as MM:SS, turns red at ≤ 5 minutes remaining
- Quick-slot bar shows 4 slots with item icons; active slot highlighted
- Challenge widget shows current challenge name and progress (e.g. "3 / 5 robots killed")
- Active buff icons with countdown timers displayed in a separate HUD region
- Mini-map rendered as a small overlay in a HUD corner showing player position and extraction zones
- HUD renders on `LAYER_HUD` (Z = 5) and does not block game input

