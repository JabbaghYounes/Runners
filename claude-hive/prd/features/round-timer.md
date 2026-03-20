Track a 15-minute countdown per round and trigger round-end events.

Depends on: core-infrastructure

- `RoundTimer` counts down from a configurable duration (default 900 s / 15 min)
- Emits `"round_warning"` at 5 minutes remaining and `"round_end"` when time hits zero
- `"round_end"` forces extraction for all players still on the map (loot is lost if not at extraction zone)
- Timer value is accessible to HUD and other systems via EventBus or direct query
- Timer pauses when the game is paused (pause menu open)
- Timer is reset at the start of each new round

