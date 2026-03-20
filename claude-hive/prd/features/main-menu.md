Implement the main menu scene with navigation to Start Game, Home Base, Settings, and Exit.

Depends on: core-infrastructure

- Displays game title and navigation buttons: Start Game, Home Base, Settings, Exit
- Start Game transitions to the game scene via `replace`
- Home Base transitions to `HomeBaseScene` via `replace`
- Settings opens `SettingsScene` via `push` (overlay)
- Exit cleanly shuts down Pygame and the process
- Menu renders at the configured resolution with futuristic visual theme

