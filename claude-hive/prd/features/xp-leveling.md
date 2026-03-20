Award XP for kills and challenge completions, and track player level progression.

Depends on: combat-shooting, challenge-system

- `XPSystem` subscribes to `"enemy_killed"` (XP per enemy, data-driven) and `"challenge_completed"` (XP reward)
- Player level is computed from cumulative XP via a configurable XP-per-level curve
- Level-up emits `"player_leveled_up"` on the EventBus
- Player level and XP-to-next-level are persisted across rounds in save data
- HUD displays current level and an XP progress bar
- Player level is visible on the post-round summary screen

