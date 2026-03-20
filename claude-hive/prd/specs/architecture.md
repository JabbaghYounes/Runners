# Runners — System Architecture

> **Status:** Baseline architecture as of 2026-03-20.
> Reflects the codebase as-built; gaps and next-steps are called out explicitly.

---

## 1. System Overview

Runners is a single-process, single-threaded 2-D extraction shooter. The runtime is a
**Pygame fixed-timestep game loop** that drives a **scene stack**. All cross-system
communication flows through a **synchronous EventBus** (pub-sub). Persistent state is
stored in a single versioned JSON save file.

```
┌──────────────────────────────────────────────────────────────────────┐
│                          GameApp (main loop)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────┐  │
│  │  Settings   │  │ AssetManager │  │  EventBus  │  │  Clock    │  │
│  └─────────────┘  └──────────────┘  └────────────┘  └───────────┘  │
│                                                                      │
│  ┌──────────────────── SceneManager (stack) ────────────────────┐   │
│  │  [MainMenu | HomeBaseScene | GameScene | PauseMenu | ...]    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

```
┌──────────────────────────────── GameScene ───────────────────────────────────┐
│                                                                               │
│  Entities              Systems                  UI Layer                      │
│  ┌──────────┐          ┌────────────────┐       ┌────────────────────────┐   │
│  │  Player  │◄────────►│ PhysicsSystem  │       │  HUD (health/XP/timer) │   │
│  ├──────────┤          ├────────────────┤       ├────────────────────────┤   │
│  │RobotEnemy│◄────────►│   AISystem     │       │  MiniMap               │   │
│  ├──────────┤          ├────────────────┤       ├────────────────────────┤   │
│  │PlayerAgt │◄────────►│  CombatSystem  │       │  ChallengeWidget       │   │
│  ├──────────┤          ├────────────────┤       ├────────────────────────┤   │
│  │Projectile│◄────────►│ ShootingSystem │       │  MapOverlay (M key)    │   │
│  ├──────────┤          ├────────────────┤       └────────────────────────┘   │
│  │ LootItem │◄────────►│  LootSystem    │                                     │
│  └──────────┘          ├────────────────┤       Data Sources                  │
│                        │ ExtractionSys  │       ┌────────────────────────┐   │
│  Map                   ├────────────────┤       │  TileMap (map_01.json) │   │
│  ┌──────────┐          │ ChallengeSystem│       ├────────────────────────┤   │
│  │ TileMap  │          ├────────────────┤       │  ItemDatabase          │   │
│  ├──────────┤          │  BuffSystem    │       ├────────────────────────┤   │
│  │  Camera  │          ├────────────────┤       │  EnemyDatabase         │   │
│  ├──────────┤          │  AudioSystem   │       └────────────────────────┘   │
│  │  Zone[]  │          ├────────────────┤                                     │
│  └──────────┘          │  RoundTimer    │                                     │
│                        └────────────────┘                                     │
│                                 │                                             │
│                            EventBus ◄──────── all systems subscribe/emit     │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Responsibilities

### 2.1 Core Infrastructure (`src/core/`)

| Module | Class | Responsibility |
|---|---|---|
| `game.py` | `GameApp` | Pygame init; display & audio setup; owns shared services; runs fixed-timestep loop (`1/60 s`, capped at `0.25 s`); routes `scene_request` events |
| `scene_manager.py` | `SceneManager` | Push/pop scene stack; routes `handle_events`, `update`, `render` to top scene only |
| `event_bus.py` | `EventBus` | Synchronous pub-sub; `subscribe`, `emit`, `unsubscribe`, `clear`; keyword-arg dispatch |
| `asset_manager.py` | `AssetManager` | Centralized image/sound/font loading; magenta-32×32 placeholder for missing images; `None` for missing sounds |
| `settings.py` | `Settings` | Loads/saves `settings.json`; exposes `resolution`, `fullscreen`, `target_fps`, `volume`, `key_bindings` |
| `round_summary.py` | `RoundSummary` | Accumulates per-round statistics (kills, loot value, challenges completed) for PostRound display |

### 2.2 Entities (`src/entities/`)

| Module | Class | Responsibility |
|---|---|---|
| `entity.py` | `Entity` | Base: `pygame.Rect`, `alive` flag, `render(screen, camera_offset)` |
| `player.py` | `Player` | 8-state movement FSM; input intent flags (`target_vx`, `jump_intent`, `slide_intent`); health/armor; buff application; inventory reference; animation controller |
| `robot_enemy.py` | `RobotEnemy` | PvE enemy: HP, aggro/attack ranges, patrol waypoints, loot table ref, XP reward; state driven by AISystem |
| `player_agent.py` | `PlayerAgent` | AI-controlled PvP bot; minimal inventory; `is_player_controlled = False`; driven by InputDriver |
| `projectile.py` | `Projectile` | Constant-velocity bullet; TTL-based lifetime; `owner` reference for friendly-fire gating |
| `loot_item.py` | `LootItem` | World-space item with `Item` payload; proximity pickup trigger |
| `input_driver.py` | `InputDriver` | Translates raw `pygame` key state to entity intent flags; abstraction for AI-driven agents |
| `animation_controller.py` | `AnimationController` | Sprite sheet animation; state-keyed frame sequences; facing direction flip |

### 2.3 Systems (`src/systems/`)

Systems are stateless processors (or carry minimal cross-frame state). They are
instantiated by `GameScene` and updated once per fixed timestep.

| Module | Class | Responsibility |
|---|---|---|
| `physics.py` | `PhysicsSystem` | Gravity; horizontal accel/decel; tile-axis-aligned collision (X then Y); writes `on_ground` |
| `combat.py` | `CombatSystem` | Projectile × target AABB collision; armor-aware damage `max(1, raw − armor)`; friendly-fire gate; emits `enemy_killed`, `player_killed` |
| `ai_system.py` | `AISystem` | PATROL→AGGRO→ATTACK→DEAD FSM per `RobotEnemy`; BFS pathfinding on walkability grid every `0.5 s`; emits `enemy_killed` after death animation |
| `shooting_system.py` | `ShootingSystem` | Fire-rate timer; reload state machine; creates `Projectile` entities; emits `weapon_fired` |
| `weapon_system.py` | `WeaponSystem` | Manages weapon stats (damage, fire rate, magazine) with attachment modifiers applied |
| `loot_system.py` | `LootSystem` | Proximity pickup (48 px radius, E-key); spawns `LootItem` drops from `loot_table` on enemy death; emits `item_picked_up` |
| `buff_system.py` | `BuffSystem` | Tracks timed `ActiveBuff` per entity; computes `get_modifiers(entity, stat)` |
| `challenge_system.py` | `ChallengeSystem` | Loads pool from `data/challenges.json`; selects `N=3` per round; tracks kills/loot/zones via EventBus; emits `challenge_completed` |
| `extraction.py` / `extraction_system.py` | `ExtractionSystem` | Player-in-zone dwell timer (hold E); round countdown; emits `extraction_success` / `extraction_failed` |
| `spawn_system.py` | `SpawnSystem` | Zone-aware enemy spawning from `EnemyDatabase` at round start |
| `audio_system.py` | `AudioSystem` | Subscribes to game events; plays SFX; manages per-zone BGM crossfade; gracefully disables on missing audio device |
| `round_timer.py` | `RoundTimer` | 15-minute countdown; emits `round_expired` when time is up |

### 2.4 Map (`src/map/`)

| Module | Class | Responsibility |
|---|---|---|
| `tile_map.py` | `TileMap` | JSON loader; 32×32 tile grid; `is_solid(col, row)`; `walkability_grid` for BFS; holds `zones`, `loot_spawns`, `extraction_rect`, `player_spawn` |
| `camera.py` | `Camera` | World→screen transform; scroll clamped to map bounds; `offset` tuple |
| `zone.py` | `Zone` | Named rectangular area; `contains(pos)`; music track ref; spawn point list |
| `extraction_zone.py` | `ExtractionZone` | Specialised zone with extraction interaction rect |
| `map_overlay.py` | `MapOverlay` | Full-screen zoomed-out map view (M key); renders zones, player pos, extraction point, enemies |

### 2.5 Inventory (`src/inventory/`)

| Module | Class | Responsibility |
|---|---|---|
| `inventory.py` | `Inventory` | 24 main slots + 4 quick slots; weight-capped; `equip`/`unequip`; `use_consumable`; `expand_capacity`; serializable |
| `item.py` | `Item`, `Weapon`, `Armor`, `Consumable` | Type hierarchy; `to_save_dict` / `make_item` round-trip |
| `item_database.py` | `ItemDatabase` | Singleton JSON registry; `create(item_id)` factory |
| `weapon_attachments.py` | `WeaponAttachment` | Mod/scope/barrel/stock stat modifiers; composed onto `Weapon` |

### 2.6 Progression (`src/progression/`)

| Module | Class | Responsibility |
|---|---|---|
| `xp_system.py` | `XPSystem` | XP accumulation; `level` derived from thresholds; `xp_to_next_level()` |
| `skill_tree.py` | `SkillTree` | JSON node graph; prerequisite validation; currency-gated unlock; `get_stat_bonuses()` aggregation; serializable |
| `home_base.py` | `HomeBase` | JSON-defined facilities (armory, med_bay, storage, comms); upgrade tiers; `get_round_bonuses()` |
| `currency.py` | `Currency` | Balance; `earn(n)` / `spend(n)`; guards against negative balance |

### 2.7 Scenes (`src/scenes/`)

| Module | Class | Stack Op | Purpose |
|---|---|---|---|
| `main_menu.py` | `MainMenu` | initial push | Title screen; route to HomeBase or GameScene |
| `game_scene.py` | `GameScene` | replace | In-round; orchestrates all systems; handles scene transitions on extract/death |
| `pause_menu.py` | `PauseMenu` | push (overlay) | Resume / Settings / Exit to Menu |
| `settings_screen.py` | `SettingsScene` | push (overlay) | Resolution, volume, key rebinding |
| `post_round.py` | `PostRoundScreen` | replace | Loot summary; XP/money earned; queue next round |
| `home_base_scene.py` | `HomeBaseScene` | replace | Upgrade facilities; manage skill tree; start next round |

### 2.8 UI (`src/ui/`)

| Module | Class | Rendered By |
|---|---|---|
| `hud.py` | `HUD` | GameScene (LAYER_HUD) |
| `hud_state.py` | `HUDState`, `ZoneInfo`, `WeaponInfo`, `ChallengeInfo` | Data-transfer objects fed to HUD each frame |
| `mini_map.py` | `MiniMap` | HUD |
| `challenge_widget.py` | `ChallengeWidget` | HUD |
| `inventory_screen.py` | `InventoryScreen` | Pushed as overlay scene (Tab key) |
| `skill_tree_screen.py` | `SkillTreeScreen` | HomeBaseScene |
| `home_base_screen.py` | `HomeBaseScreen` | HomeBaseScene |
| `widgets.py` | `Button`, `ProgressBar`, `Label`, `Panel` | Reused by all scenes |

### 2.9 Save (`src/save/`)

| Module | Class | Responsibility |
|---|---|---|
| `save_manager.py` | `SaveManager` | Atomic JSON write (`.tmp` → rename); versioned schema (v1); `load`/`save`/`restore` API; corrupt/missing → new-game fallback |

### 2.10 Data (`data/`)

| File | Content | Consumed By |
|---|---|---|
| `enemies.json` | Enemy archetypes (stats, animations, loot tables) | `EnemyDatabase` → `SpawnSystem` |
| `items.json` | Item catalog (weapons, armor, consumables, ammo, attachments) | `ItemDatabase` |
| `skill_tree.json` | Node graph (combat / mobility branches) | `SkillTree` |
| `home_base.json` | Facility definitions and per-tier bonuses | `HomeBase` |
| `challenges.json` | Challenge pool (criteria, targets, rewards) | `ChallengeSystem` |
| `assets/maps/map_01.json` | Tile grid, zones, spawn/loot points | `TileMap` |

### 2.11 Utils (`src/utils/`)

| Module | Content |
|---|---|
| `pathfinding.py` | BFS on walkability grid; `world_to_cell`, `cell_to_world`, `bfs` |
| `animation.py` | Frame timing helpers |
| `surface_utils.py` | Surface scaling / tinting helpers |

---

## 3. Data Flow

### 3.1 Game Loop (per frame)

```
GameApp.run()
  │
  ├─ pygame.event.get() ──► SceneManager.handle_events(events)
  │                             └─ active_scene.handle_events(events)
  │                                   └─ Player.handle_input(keys, events)
  │                                         └─ sets intent flags on Player
  │
  ├─ [fixed-step × N] SceneManager.update(FIXED_TIMESTEP)
  │     └─ GameScene._update_full(dt)
  │           ├─ PhysicsSystem.update([player]+enemies, tile_map, dt)
  │           │     └─ applies gravity, accel/decel, tile collision
  │           ├─ Projectile.update(dt)  [each projectile]
  │           ├─ CombatSystem.update(projectiles, targets, dt)
  │           │     └─ hit → target.take_damage() → EventBus("enemy_killed" / "player_killed")
  │           ├─ AISystem.update(enemies, player, tile_map, dt, bus)
  │           │     └─ FSM transitions + BFS chase + attack → EventBus("player.damaged")
  │           ├─ LootSystem.update(e_held, loot_items, [player])
  │           │     └─ pickup → EventBus("item_picked_up")
  │           ├─ ExtractionSystem.update([player], dt, e_held)
  │           │     └─ dwell complete → EventBus("extraction_success")
  │           ├─ BuffSystem.update(dt)
  │           ├─ Camera.update(player.rect)
  │           ├─ Zone detection → EventBus("zone_entered")
  │           └─ HUD.update(HUDState, dt)
  │
  └─ SceneManager.render(screen)
        └─ GameScene.render(screen)
              ├─ TileMap.render(screen, camera)        [LAYER_TILES]
              ├─ LootItem.render(screen, cam_off)      [LAYER_LOOT]
              ├─ RobotEnemy.render(screen, cam_off)    [LAYER_ENEMIES]
              ├─ Player.render(screen, cam_off)        [LAYER_PLAYER]
              ├─ Projectile.render(screen, cam_off)    [LAYER_PROJECTILES]
              └─ HUD.draw(screen)                      [LAYER_HUD]
```

### 3.2 EventBus Event Catalog

```
Emitter                     Event                       Subscribers
──────────────────────────  ──────────────────────────  ─────────────────────────
AISystem / CombatSystem     enemy_killed                GameScene (XP award)
                                                        LootSystem (drop spawn)
                                                        ChallengeSystem (kill count)

CombatSystem                player_killed               (PostRound transition)
Player.take_damage()        player_killed               GameScene._on_player_dead

Player.heal()               player_healed               AudioSystem
Player.update()             player_slide, footstep,     AudioSystem
                            player_landed

AISystem._do_attack()       player.damaged              AudioSystem, HUD

LootSystem                  item_picked_up              ChallengeSystem (loot count)
                                                        AudioSystem

Inventory.use_consumable()  consumable_used             AudioSystem, BuffSystem

BuffSystem                  buff_applied                HUD

GameScene._update_full()    zone_entered                ChallengeSystem (zone count)
                                                        AudioSystem (BGM switch)

ExtractionSystem            extraction_success          GameScene._on_extract
                            extraction_failed           GameScene._on_extract_failed

ChallengeSystem             challenge_completed         GameScene (XP/money award)

XPSystem (via GameScene)    level.up                    HUD

GameApp                     scene_request               GameApp._on_scene_request
ShootingSystem              weapon_fired                AudioSystem
```

### 3.3 Scene Navigation Flow

```
           ┌─────────────────────────────────────────────────────┐
           │                   [Boot]                            │
           │            MainMenu  (initial push)                 │
           │          /                    \                     │
           │  replace()               replace()                  │
           │     ↓                         ↓                     │
           │ HomeBaseScene          GameScene (new game)         │
           │     │                      │                        │
           │  replace()         ┌──────┤ ESC                    │
           │     ↓              │  push() ↓                     │
           │  GameScene     PauseMenu (overlay)                  │
           │     │              │  pop() → resume GameScene      │
           │     │              │  replace_all() → MainMenu      │
           │  extract/die       │  push() → SettingsScene        │
           │  replace()         │       pop() → PauseMenu        │
           │     ↓              └──────                          │
           │ PostRoundScreen                                      │
           │     │                                               │
           │  replace()  ──────────────► HomeBaseScene           │
           │  replace()  ──────────────► GameScene (next round)  │
           └─────────────────────────────────────────────────────┘
```

### 3.4 Save / Load Flow

```
HomeBaseScene.on_exit() ──► SaveManager.save(home_base, currency, xp, skill_tree)
PostRoundScreen.on_enter() ─► SaveManager.save(...)
                                     │
                               saves/save.json  (atomic .tmp → rename)

MainMenu / HomeBaseScene ──► SaveManager.restore(currency, xp_system, inventory, skill_tree, home_base)
```

### 3.5 Round Lifecycle

```
1. HomeBaseScene / MainMenu  →  SaveManager.restore() loads progression
2. HomeBaseScene             →  player upgrades facilities, unlocks skill tree nodes
3. GameScene init            →  TileMap.load() + SpawnSystem.spawn_all_zones()
                                + ItemDatabase + EnemyDatabase
                                + _apply_home_base_bonuses() on Player
                                + _apply_skill_tree_bonuses() on Player
4. [15-minute round]         →  physics / AI / combat / loot / challenges
5a. extraction_success       →  PostRoundScreen(extracted=True, loot_items=inventory)
5b. extraction_failed        →  PostRoundScreen(extracted=False, loot_items=[])
5c. player_killed            →  PostRoundScreen(extracted=False, loot_items=[])
6. PostRoundScreen           →  awards XP + money, shows summary, SaveManager.save()
7. → back to 2               →  loop
```

---

## 4. Technology Choices

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.10+ | Existing codebase; type annotations; `match` available |
| Game framework | Pygame 2.x | Existing dependency; hardware-accelerated 2-D; audio mixer |
| Numerics | NumPy (optional) | Available in requirements; used for matrix ops if needed |
| Pathfinding | Custom BFS | Simple tile grid; BFS sufficient; no external dep |
| Persistence | JSON (stdlib `json`) | Human-readable save files; no external dep; versioned with migration |
| Testing | pytest + SDL dummy | Headless CI; `TrackingEventBus` for event assertions |
| Configuration | `settings.json` + `src/constants.py` | Runtime prefs in JSON; compile-time physics in constants |
| Asset pipeline | `AssetManager` + `assets/` directory | Centralised loading; magenta placeholder; graceful audio disable |
| Data | JSON under `data/` | Data-driven content; no code changes for new items/enemies |

---

## 5. File / Directory Structure

```
Runners/
├── main.py                         # Entry point: GameApp().run()
├── requirements.txt                # pygame>=2.0, numpy, pytest
├── pyproject.toml
├── pytest.ini
├── conftest.py                     # SDL dummy, pygame reinit fixture
├── settings.json                   # Runtime user settings
│
├── src/
│   ├── __init__.py
│   ├── constants.py                # Compile-time constants (physics, colors, layers)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── game.py                 # GameApp: main loop, shared services
│   │   ├── scene_manager.py        # SceneManager: push/pop/replace/replace_all
│   │   ├── event_bus.py            # EventBus: synchronous pub-sub
│   │   ├── asset_manager.py        # AssetManager: centralized asset loading
│   │   ├── settings.py             # Settings: load/save settings.json
│   │   ├── constants.py            # (legacy alias — prefer src/constants.py)
│   │   └── round_summary.py        # RoundSummary: per-round stat accumulator
│   │
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── entity.py               # Entity base class
│   │   ├── player.py               # Player: 8-state FSM, input, health, inventory
│   │   ├── robot_enemy.py          # RobotEnemy: PvE with 4-state FSM
│   │   ├── player_agent.py         # PlayerAgent: AI-driven PvP bot
│   │   ├── projectile.py           # Projectile: constant-velocity bullet
│   │   ├── loot_item.py            # LootItem: world-space item pickup
│   │   ├── input_driver.py         # InputDriver: key → intent flag translation
│   │   └── animation_controller.py # AnimationController: sprite sheet animation
│   │
│   ├── systems/
│   │   ├── __init__.py
│   │   ├── physics.py              # PhysicsSystem: gravity, collision
│   │   ├── combat.py               # CombatSystem: projectile hits, armor damage
│   │   ├── ai_system.py            # AISystem: FSM + BFS pathfinding
│   │   ├── shooting_system.py      # ShootingSystem: fire rate, reload, projectile spawn
│   │   ├── weapon_system.py        # WeaponSystem: weapon stat management
│   │   ├── loot_system.py          # LootSystem: pickup, drop spawn
│   │   ├── buff_system.py          # BuffSystem: timed stat modifiers
│   │   ├── challenge_system.py     # ChallengeSystem: vendor challenges
│   │   ├── extraction.py           # ExtractionSystem (primary implementation)
│   │   ├── extraction_system.py    # ExtractionSystem (alternate — consolidate)
│   │   ├── spawn_system.py         # SpawnSystem: zone-aware enemy spawning
│   │   ├── audio_system.py         # AudioSystem: SFX + BGM via EventBus
│   │   └── round_timer.py          # RoundTimer: 15-minute countdown
│   │
│   ├── map/
│   │   ├── __init__.py
│   │   ├── tile_map.py             # TileMap: JSON loader, solid query, walkability
│   │   ├── camera.py               # Camera: world↔screen transform
│   │   ├── zone.py                 # Zone: named rect with music + spawn data
│   │   ├── extraction_zone.py      # ExtractionZone: extraction tile specialization
│   │   └── map_overlay.py          # MapOverlay: full-screen map (M key)
│   │
│   ├── inventory/
│   │   ├── __init__.py
│   │   ├── inventory.py            # Inventory: 24 slots + 4 quick slots
│   │   ├── item.py                 # Item, Weapon, Armor, Consumable, make_item()
│   │   ├── item_database.py        # ItemDatabase: singleton JSON registry
│   │   └── weapon_attachments.py   # WeaponAttachment: mod/scope/barrel/stock
│   │
│   ├── progression/
│   │   ├── __init__.py
│   │   ├── xp_system.py            # XPSystem: XP accumulation, leveling
│   │   ├── skill_tree.py           # SkillTree: node graph, prerequisites, bonuses
│   │   ├── home_base.py            # HomeBase: facility upgrades, round bonuses
│   │   └── currency.py             # Currency: balance, earn/spend
│   │
│   ├── scenes/
│   │   ├── __init__.py
│   │   ├── base_scene.py           # BaseScene: on_enter/exit/pause/resume interface
│   │   ├── main_menu.py            # MainMenu: title screen
│   │   ├── game_scene.py           # GameScene: in-round orchestrator
│   │   ├── pause_menu.py           # PauseMenu: overlay (push/pop)
│   │   ├── settings_screen.py      # SettingsScene: resolution/volume/keys
│   │   ├── post_round.py           # PostRoundScreen: loot summary, XP/money
│   │   └── home_base_scene.py      # HomeBaseScene: upgrades, skill tree
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── hud.py                  # HUD: in-game overlay
│   │   ├── hud_state.py            # HUDState, ZoneInfo, WeaponInfo, ChallengeInfo (DTOs)
│   │   ├── mini_map.py             # MiniMap: player + extraction dot overlay
│   │   ├── challenge_widget.py     # ChallengeWidget: challenge progress bars
│   │   ├── inventory_screen.py     # InventoryScreen: grid display
│   │   ├── skill_tree_screen.py    # SkillTreeScreen: node graph UI
│   │   ├── home_base_screen.py     # HomeBaseScreen: facility upgrade UI
│   │   └── widgets.py              # Button, ProgressBar, Label, Panel
│   │
│   ├── save/
│   │   ├── __init__.py
│   │   └── save_manager.py         # SaveManager: atomic JSON, versioned schema
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   └── enemy_database.py       # EnemyDatabase: loads enemies.json
│   │
│   └── utils/
│       ├── __init__.py
│       ├── pathfinding.py          # BFS, world_to_cell, cell_to_world
│       ├── animation.py            # Frame timing helpers
│       └── surface_utils.py        # Surface scale/tint utilities
│
├── data/
│   ├── enemies.json                # Enemy archetypes + loot tables
│   ├── items.json                  # Item catalog (weapons, armor, consumables)
│   ├── skill_tree.json             # Skill tree node graph (combat / mobility)
│   ├── home_base.json              # Facility definitions and upgrade bonuses
│   └── challenges.json             # Vendor challenge pool
│
├── assets/
│   ├── maps/
│   │   └── map_01.json             # Tile grid, zones, spawn/loot data
│   ├── sprites/
│   │   ├── player/                 # Player animation frames (idle/walk/sprint/...)
│   │   ├── enemies/                # Enemy sprite sheets (grunt/heavy/sniper)
│   │   ├── items/                  # Item icons
│   │   ├── tiles/                  # Tile textures
│   │   └── ui/                     # UI atlas (health bar, crosshair, ...)
│   └── audio/
│       ├── music/                  # Per-zone OGG loop tracks
│       └── sfx/                    # WAV sound effects
│
├── saves/
│   └── save.json                   # Player progression (JSON, v1 schema)
│
├── tests/
│   ├── conftest.py                 # SDL dummy, pygame reinit, TrackingEventBus
│   ├── core/                       # Unit tests for core modules
│   ├── scenes/                     # Scene lifecycle and integration tests
│   ├── systems/                    # System-level unit tests
│   ├── ui/                         # UI widget and HUD tests
│   ├── utils/                      # Utility unit tests
│   └── test_*.py                   # Top-level integration tests
│
└── claude-hive/
    └── prd/
        └── specs/
            ├── architecture.md     # ← this document
            ├── feature-plan.md
            └── ux-spec.md
```

---

## 6. Integration Points and Boundaries

### 6.1 `GameApp` ↔ `SceneManager`
`GameApp` owns the `SceneManager`. Scenes request transitions by emitting
`bus.emit("scene_request", scene="home_base")`. The `_on_scene_request` handler in
`GameApp` is the single place that knows the scene graph topology. Currently a stub —
**this must be fully wired** to construct and push/replace scenes with the correct
progression objects (`xp_system`, `currency`, `home_base`, `skill_tree`).

### 6.2 `GameScene` ↔ Systems
`GameScene._init_full()` constructs all systems and wires them together. Systems do not
import each other; inter-system communication happens exclusively through `EventBus`.
`GameScene` is the only orchestrator that holds references to all runtime objects.

### 6.3 `ShootingSystem` / `WeaponSystem` Integration Gap ⚠️
`ShootingSystem` and `WeaponSystem` exist in `src/systems/` but are **not yet wired
into `GameScene._update_full()`**. Currently shooting is handled ad-hoc via
`CombatSystem.fire()`. These systems need to be instantiated in `_init_full` and
called each tick, receiving mouse input forwarded from `Player`.

### 6.4 `ExtractionSystem` Duplication ⚠️
Two implementations exist: `src/systems/extraction.py` and
`src/systems/extraction_system.py`. `GameScene` falls back between them with a
try/except. The two should be consolidated into a single canonical module.

### 6.5 Progression Objects Lifecycle
`XPSystem`, `Currency`, `HomeBase`, `SkillTree` are long-lived (persist across rounds).
They are created once (in `main.py` or `GameApp.__init__`) and passed into each
`GameScene` and `HomeBaseScene` by reference. `SaveManager` serialises/restores them
at the boundaries described in §3.4.

### 6.6 `Player` ↔ `Inventory`
`Player` holds an `Inventory` reference. `LootSystem` calls `player.inventory.add_item()`
on pickup. `InventoryScreen` renders it as an overlay scene. The `GameScene` extracts
`player.inventory.get_items()` to pass to `PostRoundScreen`.

### 6.7 Assets and Placeholders
All sprites and audio files currently have `.gitkeep` placeholders. `AssetManager`
handles missing files gracefully (magenta 32×32 / `None` audio). The render pipeline
is sprite-ready; dropping real assets into the correct paths is sufficient to enable
them.

### 6.8 `EventBus` Module-Level Singleton
`src/core/event_bus.py` exports a module-level `event_bus` singleton used by some
modules (e.g. `Player.heal()`) that cannot receive the bus by dependency injection.
Scene-level systems receive the bus by constructor injection. Both patterns coexist;
tests use `_TrackingEventBus` injected via fixture.

---

## 7. Architectural Invariants

1. **No direct system-to-system imports.** Systems communicate exclusively via `EventBus`.
2. **Asset loading through `AssetManager` only.** Never call `pygame.image.load()`,
   `pygame.mixer.Sound()`, or `pygame.font.Font()` directly.
3. **Absolute imports only.** Always `from src.xxx import`, never relative imports.
4. **`from __future__ import annotations` at top of every module.**
5. **Type all function signatures** including return types.
6. **`TYPE_CHECKING` guard for circular imports.**
7. **Atomic saves only.** Write to `.tmp` then `rename`; never write directly to
   `save.json`.
8. **Fixed timestep.** All physics/logic runs at `FIXED_TIMESTEP = 1/60 s`. Rendering
   runs at `target_fps`. Never use wall-clock time inside a system `update()` call.
9. **Render layers.** Draw order: `TILES(0) → LOOT(1) → ENEMIES(2) → PLAYER(3) →
   PROJECTILES(4) → HUD(5)`.

---

## 8. Known Gaps and Next Steps

| # | Gap | Location | Action |
|---|---|---|---|
| 1 | `_on_scene_request` stub | `src/core/game.py:147` | Implement full scene routing; construct progression objects once and thread them through scene transitions |
| 2 | `ShootingSystem` not in game loop | `src/scenes/game_scene.py` | Instantiate in `_init_full`; add update call in `_update_full`; forward mouse input from Player |
| 3 | Dual `ExtractionSystem` implementations | `src/systems/extraction.py` vs `extraction_system.py` | Consolidate to one module; remove the fallback try/except in GameScene |
| 4 | `PlayerAgent` AI not driven during round | `src/entities/player_agent.py` | Spawn `PVP_AGENT_COUNT` bots via `SpawnSystem`; drive with `InputDriver` + simple PvP AI using `PVP_AGENT_AGGRO_RANGE` / `PVP_AGENT_SHOOT_RANGE` constants |
| 5 | Character class selection | PRD §3 | Add `CharacterClass` model with unique ability; expose class picker in `HomeBaseScene` or `MainMenu` |
| 6 | Weapon attachment equip flow | `src/inventory/weapon_attachments.py` | Wire `WeaponSystem` to apply attachment modifiers when weapon is equipped |
| 7 | Sprite assets absent | `assets/sprites/` | All subdirectories are `.gitkeep`; deliver final assets or quality placeholder sheets |
| 8 | `InventoryScreen` scene push | `src/scenes/game_scene.py` | Handle `KEY_BINDINGS["inventory"]` (Tab) in `GameScene.handle_events` to push `InventoryScreen` as overlay |
| 9 | `RoundTimer` not wired to `ExtractionSystem` | `src/systems/round_timer.py` | `RoundTimer` should emit `extraction_failed` when countdown reaches zero; connect in `_init_full` |
|10 | `WeaponInfo` in `HUDState` unpopulated | `src/ui/hud_state.py` | Populate from `Player.inventory.equipped_weapon` in `GameScene._build_hud_state()` |
