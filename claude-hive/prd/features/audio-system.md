Play background music per zone and sound effects for key game events.

Depends on: core-infrastructure

- `AudioSystem` subscribes to EventBus events and plays associated sounds (shooting, reload, footsteps, robot attack, loot pick-up)
- Background music loops per zone; transitions crossfade when the player enters a new zone
- Volume levels controlled by settings (master, SFX, music channels separately)
- `AssetManager` returns `None` for missing sounds; `AudioSystem` guards all playback with `if sound:`
- Audio initialisation fails gracefully (silent fallback) when no audio device is available
- All audio assets loaded exclusively through `AssetManager` (no direct `pygame.mixer.Sound()` calls)

