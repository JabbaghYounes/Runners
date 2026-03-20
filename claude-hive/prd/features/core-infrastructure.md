Establish the foundational game engine layer: fixed-timestep game loop, synchronous pub-sub EventBus, SceneManager stack, AssetManager, and runtime Settings.

- `GameApp` runs at a fixed 1/60 s timestep with a frame-time cap of 0.25 s to prevent spiral-of-death
- `EventBus` supports `subscribe(name, cb)` and `emit(name, payload)` with synchronous delivery; systems never import each other directly
- `SceneManager` exposes `push`, `pop`, `replace`, and `replace_all` with correct `on_enter / on_exit / on_pause / on_resume` lifecycle hooks
- `AssetManager` loads images and sounds through a single interface; returns a magenta 32×32 placeholder for missing images and `None` for missing sounds
- `Settings` reads/writes `settings.json` (resolution, fullscreen, FPS cap, volume, key bindings) with hardcoded fallback defaults
- `from __future__ import annotations` and fully typed signatures are enforced across all modules

