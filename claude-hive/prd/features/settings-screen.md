Implement a settings screen for configuring resolution, fullscreen, FPS cap, volume, and key bindings.

Depends on: core-infrastructure

- Settings are read from and written to `settings.json` via `Settings` class
- Configurable options: resolution, fullscreen toggle, FPS cap, master/SFX/music volume, key bindings
- Key binding rebinding: press action → press new key → confirm saves to `settings.json`
- Changes apply immediately; resolution/fullscreen changes require restart or live reinit
- Cancel button reverts unsaved changes; Save button persists them
- Accessible from both main menu and pause menu

