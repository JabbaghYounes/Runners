# Runners — UX Specification

> **Status:** Initial draft — 2026-03-20.
> Baseline resolution: **1280×720** (configurable). Art style: **futuristic retro** — dark navy backgrounds, neon cyan/magenta accents.

---

## Table of Contents

1. [User Flows](#1-user-flows)
2. [Screen Descriptions](#2-screen-descriptions)
3. [Component List with Props](#3-component-list-with-props)
4. [State Management](#4-state-management)
5. [Interaction Patterns & Visual Language](#5-interaction-patterns--visual-language)

---

## 1. User Flows

### Flow 1 — First Launch / New Game

```
Launch game
  │
  ▼
Main Menu
  │  "NEW GAME"
  ▼
GameScene (fresh defaults: no save applied)
  │
  ▼
[15-minute round]
  │
  ├─ extract ──────────────────────────────►  PostRoundScreen (extracted=True)
  ├─ timer expires / player killed ────────►  PostRoundScreen (extracted=False)
  └─ (round outcome determined)
       │
       ├─ "RETURN TO BASE" ──────────────►  HomeBaseScene
       └─ "DEPLOY AGAIN" ────────────────►  GameScene (new round)
```

**Steps:**
1. Player launches the game — Main Menu appears.
2. No save file exists; only "NEW GAME" is shown (no "CONTINUE").
3. Click "NEW GAME" → GameScene loads with default player state.
4. Round timer starts; gameplay begins.
5. Round ends by extraction, death, or timer expiry.
6. PostRoundScreen shows results. XP and currency are awarded (extraction success only grants full loot).
7. Player chooses "RETURN TO BASE" to visit HomeBaseScene, or "DEPLOY AGAIN" to jump straight into the next round.

---

### Flow 2 — Returning Player (Continue)

```
Launch game
  │
  ▼
Main Menu  (save file detected)
  │  "CONTINUE"
  ▼
HomeBaseScene  ◄──────────────────────────────────────────────────────┐
  │                                                                    │
  ├─ review/upgrade facilities (HomeBaseScreen tab)                   │
  ├─ review/unlock skill nodes (SkillTreeScreen tab)                  │
  │                                                                    │
  │  "DEPLOY"                                                          │
  ▼                                                                    │
GameScene  ──────────►  PostRoundScreen  ──►  "RETURN TO BASE"  ──────┘
```

**Steps:**
1. Save file found; "CONTINUE" button is active on Main Menu.
2. "CONTINUE" → `SaveManager.restore()` → HomeBaseScene.
3. Player sees current level, currency, and facility tiers.
4. Optional: spend currency to upgrade facilities or unlock skill tree nodes.
5. Click "DEPLOY" → GameScene applies home base and skill tree bonuses to the player, then starts the round.
6. After the round, PostRoundScreen awards XP/currency, then loops back to HomeBaseScene.

---

### Flow 3 — In-Round Gameplay Loop

```
GameScene loads
  │
  ├─ Map + enemies spawn (SpawnSystem)
  ├─ Player spawns at spawn point
  │
  ▼
[Player in-round actions — may happen in any order]
  │
  ├─ Move, jump, slide, sprint (WASD / Space / Ctrl / C / Shift)
  │
  ├─ Combat
  │     └─ Aim + shoot (Mouse)  →  CombatSystem  →  enemy_killed event
  │
  ├─ Loot pickup
  │     ├─ Approach item (within 48 px)
  │     ├─ "[E] Pick Up: {ItemName}" prompt appears
  │     └─ Press E  →  item added to inventory  →  floating "+ItemName" feedback
  │
  ├─ Inventory management (Tab)
  │     └─ InventoryScreen overlay pushed (see Flow 4)
  │
  ├─ Full map view (M)
  │     └─ MapOverlay shows zone layout, extraction point, enemy positions
  │
  ├─ Challenge progress
  │     └─ ChallengeWidget on left HUD tracks 3 active challenges
  │
  └─ Extraction
        └─ See Flow 5
```

---

### Flow 4 — Inventory Management (In-Round Overlay)

```
Press Tab during round
  │
  ▼
InventoryScreen overlay pushed (game world frozen beneath)
  │
  ├─ Browse 6×4 slot grid (24 main slots) + 4 quick slots
  │
  ├─ Hover slot  →  ItemTooltip appears
  │
  ├─ Left-click slot
  │     └─ Slot highlighted; right panel shows item detail + action buttons
  │           ├─ EQUIP   (weapons, armor, attachments)
  │           ├─ USE     (consumables)
  │           └─ DROP    (removes from inventory, spawns loot in world)
  │
  ├─ Right-click slot  →  ItemContextMenu (EQUIP / USE / DROP / INSPECT)
  │
  ├─ Weapon selected  →  WeaponAttachmentPanel (right side) shows
  │     4 socket slots (mod / scope / barrel / stock)
  │     Click empty socket + compatible attachment in grid  →  attach
  │
  └─ Press Tab or Esc  →  InventoryScreen popped, GameScene resumes
```

---

### Flow 5 — Extraction

```
Player navigates to extraction zone (marked on MiniMap + glowing floor)
  │
  ├─ Enter zone  →  "Hold [E] to Extract" prompt appears bottom-center
  │
  ├─ Hold E (3-second dwell)
  │     └─ Circular radial progress bar fills around "Extracting…" text
  │
  ├─ Complete hold without interruption
  │     └─ extraction_success event  →  fade to black  →  PostRoundScreen (extracted=True)
  │
  └─ Player takes damage / leaves zone during hold
        └─ Progress bar resets; prompt remains if still in zone
```

---

### Flow 6 — Post-Round Results

```
PostRoundScreen on_enter()
  │
  ├─ Status banner animates in  ("EXTRACTION SUCCESSFUL" or "MISSION FAILED")
  │
  ├─ Three panels populate with staggered animations:
  │     ├─ Loot Summary  (items kept, total value)
  │     ├─ Round Stats   (kills, damage, zones, survival time)
  │     └─ Rewards       (XP bar fills, currency counter increments, challenges checked)
  │
  ├─ Level-up banner slides in if applicable ("LEVEL UP → Lvl N")
  │
  └─ CTA buttons appear after animations settle:
        ├─ "RETURN TO BASE"  →  replace()  →  HomeBaseScene
        └─ "DEPLOY AGAIN"    →  replace()  →  GameScene
```

---

### Flow 7 — Skill Tree Upgrade (HomeBaseScene)

```
HomeBaseScene  →  click "SKILL TREE" tab
  │
  ▼
SkillTreeScreen (scrollable two-branch node graph: Combat / Mobility)
  │
  ├─ Hover node  →  SkillNodeTooltip: stat bonus description + currency cost
  │
  ├─ Click available node (prerequisites met, currency sufficient)
  │     └─ Confirmation prompt: "Unlock {NodeName} for {N}¤?"
  │           ├─ CONFIRM  →  Currency.spend(N)  →  SkillTree.unlock(node_id)
  │           │             →  node lights up with neon glow; edges to children unlock
  │           └─ CANCEL   →  dismiss prompt
  │
  └─ Locked nodes (prerequisites not met): dimmed, no click; hover shows requirement tooltip
```

---

### Flow 8 — Home Base Facility Upgrade

```
HomeBaseScene  →  "BASE" tab (default)
  │
  ▼
HomeBaseScreen  (2×2 grid of FacilityCards: Armory, Med Bay, Storage, Comms)
  │
  ├─ Each card shows: facility icon, name, current tier, tier pips
  │
  ├─ Click "UPGRADE" button on card (sufficient currency + not max tier)
  │     └─ FacilityUpgradeModal opens:
  │           ├─ Current tier bonuses (left)
  │           ├─ Next tier bonuses (right, highlighted)
  │           ├─ Cost displayed prominently
  │           └─ CONFIRM / CANCEL
  │                 CONFIRM  →  Currency.spend(cost)  →  HomeBase.upgrade(facility_id)
  │                           →  FacilityCard updates tier pips; UPGRADE button grays if max
  │
  └─ MAX tier: "UPGRADE" button replaced with "MAXED" badge (non-interactive)
```

---

### Flow 9 — Settings

```
Main Menu → "SETTINGS"  OR  PauseMenu → "SETTINGS"  →  SettingsScene pushed
  │
  ├─ Tab: DISPLAY
  │     ├─ Resolution dropdown (720p / 1080p / custom)
  │     └─ Fullscreen toggle checkbox
  │
  ├─ Tab: AUDIO
  │     ├─ Master volume slider  (0–100)
  │     ├─ Music volume slider   (0–100)
  │     └─ SFX volume slider     (0–100)
  │
  ├─ Tab: CONTROLS
  │     └─ Scrollable action list: each row = Action Label + current key binding
  │           Click a binding  →  "Press any key…" prompt
  │           Press new key    →  binding updated; conflicts warned
  │
  └─ APPLY  →  Settings.save()  →  pop SettingsScene
     CANCEL  →  discard changes →  pop SettingsScene
```

---

### Flow 10 — Pause and Resume

```
Press Esc during GameScene
  │
  ▼
PauseMenu overlay pushed (game frozen)
  │
  ├─ "RESUME"       →  pop PauseMenu  →  GameScene resumes
  ├─ "SETTINGS"     →  push SettingsScene  (Flow 9)
  │                       └─ back  →  pop SettingsScene  →  PauseMenu
  └─ "EXIT TO MENU" →  replace_all()  →  MainMenu
                         (round progress lost, no save triggered)
```

---

## 2. Screen Descriptions

### Screen 1: Main Menu

**Purpose:** Entry point; route to new game, continue, settings, or exit.

**Layout (1280×720):**
```
┌──────────────────────────────────────────────────────────────────────┐
│  [Full-screen background: futuristic skyline art, subtle parallax]   │
│                                                                      │
│                                                                      │
│                 ██████  ██  ██ ███  ██ ███  ██████  ██████          │
│                 ██  ██  ██  ██ ████ ██ ██ █ ██      ██  ██          │
│                 ██████  ██  ██ ██ ████ ██  ███████  ██████          │
│                 ██ ██   ██  ██ ██  ███ ██  ████  ██ ██ ██           │  ← neon title
│                 ██  ██  ██████ ██   ██ ██  ████████ ██  ██          │
│                                                                      │
│                       [  CONTINUE  ]    ← cyan, only if save exists │
│                       [ NEW GAME  ]                                  │
│                       [ SETTINGS  ]                                  │
│                       [   EXIT    ]                                  │
│                                                                      │
│  v0.1.0                                               [controller?] │
└──────────────────────────────────────────────────────────────────────┘
```

**Elements:**
- `Logo` — large neon-cyan wordmark, top-center; subtle flicker animation
- `Button` stack — vertically centered, 300 px wide, 56 px tall per button, 12 px gap
- "CONTINUE" button only visible when `SaveManager` has a valid save file
- `Label` — version string, bottom-left corner, small muted text
- Background art fades in on load (0.5s)

---

### Screen 2: HomeBaseScene

**Purpose:** Between-round hub for progression management and round deployment.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  ╔══════════════════╗  ┌─────────────────────────────────────────┐  │
│  ║  [Portrait]      ║  │  [ BASE ]  [ SKILL TREE ]               │  │
│  ║  Runner-7        ║  ├─────────────────────────────────────────┤  │
│  ║  Level 12        ║  │                                         │  │
│  ║  ████████░░ XP   ║  │   ┌──────────┐   ┌──────────┐          │  │
│  ║  ¤ 4,200         ║  │   │  ARMORY  │   │ MED BAY  │          │  │
│  ║                  ║  │   │  Tier 2  │   │  Tier 1  │          │  │
│  ║                  ║  │   │ [UPGRADE]│   │ [UPGRADE]│          │  │
│  ║                  ║  │   └──────────┘   └──────────┘          │  │
│  ║                  ║  │   ┌──────────┐   ┌──────────┐          │  │
│  ║                  ║  │   │ STORAGE  │   │  COMMS   │          │  │
│  ║                  ║  │   │  Tier 1  │   │  Tier 0  │          │  │
│  ║                  ║  │   │ [UPGRADE]│   │ [UPGRADE]│          │  │
│  ║                  ║  │   └──────────┘   └──────────┘          │  │
│  ║   [ DEPLOY  ]    ║  │                                         │  │
│  ╚══════════════════╝  └─────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

**Elements:**
- **Left panel** (40% width, full height): Player info card with `CharacterPortrait`, `Label` (name/level), `ProgressBar` (XP), currency display, and `DEPLOY` CTA button.
- **Right panel** (60% width): Tab bar with "BASE" and "SKILL TREE" tabs.
  - BASE tab → `HomeBaseScreen` (facility 2×2 grid)
  - SKILL TREE tab → `SkillTreeScreen` (scrollable node graph)
- `DEPLOY` button is always accessible; pressing it saves any changes and transitions to `GameScene`.
- Keyboard hint row at bottom: `[Tab] Skill Tree | [Enter] Deploy | [Esc] Main Menu`

---

### Screen 3: GameScene — In-Round World

**Purpose:** Main gameplay screen; renders the world with HUD overlay on top.

**Render layers (bottom to top):**
```
LAYER_TILES(0) → LAYER_LOOT(1) → LAYER_ENEMIES(2) →
LAYER_PLAYER(3) → LAYER_PROJECTILES(4) → LAYER_HUD(5)
```

**HUD Layout:**
```
┌──────────────────────────────────────────────────────────────────────┐
│ ┌─────────────────┐       14:23       [¤ 320 | Kills: 3]            │
│ │[Port] HP ██████ │                                                  │
│ │       AR ██░░░░ │                                                  │
│ └─────────────────┘                                                  │
│                                                                      │
│ ┌─ Challenges ─────┐                                                 │
│ │ Kill 5 robots    │                                         ┌──────┐│
│ │ ████████░░  4/5  │                                         │ MAP  ││
│ │ Loot 3 items     │                                         │  ·   ││  ← MiniMap
│ │ ██████░░░░  2/3  │                                         │  ▲  ●││
│ │ Visit East Zone  │                                         │      ││
│ │ ░░░░░░░░░░  0/1  │                                         └──────┘│
│ └──────────────────┘                                                 │
│                                                                      │
│                                                                      │
│ ┌──┐┌──┐┌──┐┌──┐        [AK-47  28 / 90]       (extraction zone↗)  │
│ │1 ││2 ││3 ││4 │        [══════════════]                            │
│ └──┘└──┘└──┘└──┘          reload bar                                │
└──────────────────────────────────────────────────────────────────────┘
```

**HUD Regions:**
| Region | Position | Contents |
|---|---|---|
| Health cluster | Top-left (10, 10), 220×60 px | Portrait, HealthBar (dual HP/armor), level badge |
| Round timer | Top-center | MM:SS countdown; amber < 5 min; red pulse < 2 min |
| Economy strip | Top-right | Currency earned this round + kill counter |
| Challenge widget | Left side, vertical | 3 ChallengeRow bars |
| Quick slots | Bottom-left | 4 quick-slot cells (48×48 px each) |
| Weapon info | Bottom-center | Weapon icon + ammo count + reload bar |
| Mini-map | Bottom-right | 150×150 px circular clipped map |

---

### Screen 3a: Map Overlay (M key)

**Purpose:** Full-screen strategic view of the map.

**Layout:**
- Semi-transparent black background (80% alpha)
- Rendered map scaled to fill screen, player position centered or full map shown
- **White dot** = player position
- **Green rect** = extraction zone
- **Red dots** = detected enemies (within sight-range heuristic)
- **Zone labels** = named rectangular zones
- Press M or Esc to dismiss

---

### Screen 3b: Inventory Overlay (Tab key)

**Purpose:** Full inventory management while in-round (game paused beneath).

**Layout:**
```
┌──────────────────────────────────────────────────────────────────────┐
│  INVENTORY                                    [close: Tab / Esc]     │
│  ┌────────────────────────────────┐  ┌────────────────────────────┐  │
│  │  [□][□][□][□][□][□]            │  │  EQUIPPED                  │  │
│  │  [□][□][□][□][□][□]   Main    │  │  Weapon: [AK-47        ]   │  │
│  │  [□][□][□][□][□][□]   Slots   │  │  Mod:    [Silencer     ]   │  │
│  │  [□][□][□][□][□][□]            │  │  Scope:  [──────────── ]   │  │
│  ├────────────────────────────────┤  │  Barrel: [──────────── ]   │  │
│  │  [□][□][□][□]  Quick Slots     │  │  Stock:  [──────────── ]   │  │
│  └────────────────────────────────┘  │  Armor:  [Chest Plate  ]   │  │
│                                       ├────────────────────────────┤  │
│                                       │  SELECTED ITEM             │  │
│                                       │  Stim Pack  [Consumable]   │  │
│                                       │  Restores 50 HP            │  │
│                                       │  ┌────────┐ ┌──────────┐  │  │
│                                       │  │  USE   │ │  DROP    │  │  │
│                                       │  └────────┘ └──────────┘  │  │
│                                       └────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**Interactions:**
- **Left-click slot** → select; right panel updates to show item details
- **Right-click slot** → context menu (EQUIP / USE / DROP / INSPECT)
- **Drag** (future enhancement) — drag item between slots
- **Weapon selected** → attachment panel shows 4 sockets; click socket + inventory item to attach

---

### Screen 3c: Pause Menu (Esc)

**Purpose:** Pause overlay with navigation options.

**Layout:**
```
┌──────────────────────────────────────────────────────────────────────┐
│  [dim game world behind at 70% opacity]                              │
│                                                                      │
│                       ┌────────────────┐                            │
│                       │    PAUSED      │                            │
│                       ├────────────────┤                            │
│                       │  [ RESUME    ] │                            │
│                       │  [ SETTINGS  ] │                            │
│                       │  [EXIT TO MENU]│                            │
│                       └────────────────┘                            │
└──────────────────────────────────────────────────────────────────────┘
```

- Centered modal, 300×220 px
- Pressing Esc again = "RESUME"

---

### Screen 4: SettingsScene

**Purpose:** Configure display, audio, and key bindings.

**Layout:**
```
┌──────────────────────────────────────────────────────────────────────┐
│  SETTINGS                                                            │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  [ DISPLAY ]  [ AUDIO ]  [ CONTROLS ]                         │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │  DISPLAY TAB                                                   │  │
│  │  Resolution:   [ 1280×720  ▾ ]                                 │  │
│  │  Fullscreen:   [ ✓ ]                                           │  │
│  │                                                                │  │
│  │  AUDIO TAB                                                     │  │
│  │  Master Vol:   [━━━━━━━━━━━━━━━━━━░░░░]  75%                  │  │
│  │  Music Vol:    [━━━━━━━━━━━━━━░░░░░░░░]  60%                  │  │
│  │  SFX Vol:      [━━━━━━━━━━━━━━━━━━░░░░]  75%                  │  │
│  │                                                                │  │
│  │  CONTROLS TAB                                                  │  │
│  │  Move Left     [ A ]                                           │  │
│  │  Move Right    [ D ]                                           │  │
│  │  Jump          [ Space ]                                       │  │
│  │  ...                                                           │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                               [ APPLY ]  [ CANCEL ]                  │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Screen 5: PostRoundScreen

**Purpose:** Show round outcome, rewards, and provide next-action options.

**Layout:**
```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│              ╔═══════════════════════════════════════╗              │
│              ║   ✓  EXTRACTION SUCCESSFUL            ║   ← green   │
│              ╚═══════════════════════════════════════╝              │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  LOOT SUMMARY    │  │  ROUND STATS     │  │  REWARDS         │  │
│  │                  │  │                  │  │                  │  │
│  │  [icon] AK-47    │  │  Kills (PvE): 4  │  │  XP ██████░░ +420│  │
│  │  [icon] Stim ×2  │  │  Kills (PvP): 1  │  │  ¤  +850         │  │
│  │  [icon] Chest Pl │  │  Dmg Dealt: 820  │  │                  │  │
│  │  [icon] Scope    │  │  Dmg Taken: 310  │  │  Challenges:     │  │
│  │                  │  │  Zones: 3        │  │  ✓ Kill 5 robots  │  │
│  │  Total: ¤ 1,340  │  │  Time: 09:42     │  │  ✓ Loot 3 items  │  │
│  └──────────────────┘  └──────────────────┘  │  ✗ Visit E. Zone  │  │
│                                               └──────────────────┘  │
│                                                                      │
│                  [ RETURN TO BASE ]   [ DEPLOY AGAIN ]              │
└──────────────────────────────────────────────────────────────────────┘
```

**Animation sequence (staggered, ~2.5 s total):**
1. Status banner slides in from top (0.3 s)
2. Three panels fade in simultaneously (0.5 s delay, 0.4 s duration)
3. Loot items reveal one-by-one (0.1 s each)
4. XP bar animates fill (0.6 s)
5. Currency counter counts up (0.5 s)
6. Challenge checkmarks pop in
7. Level-up banner (if applicable) slides in from right
8. CTA buttons fade in after all animations settle

**On extraction failure / death:** Loot Summary panel is replaced with "LOOT LOST" message. Rewards show reduced XP (kill XP only) and no currency.

---

## 3. Component List with Props

> File locations follow the existing `src/ui/` structure.

---

### 3.1 Primitive Widgets — `src/ui/widgets.py`

#### `Button`
| Prop | Type | Description |
|---|---|---|
| `label` | `str` | Display text |
| `rect` | `pygame.Rect` | Position and size |
| `style` | `ButtonStyle` | `PRIMARY` / `SECONDARY` / `DANGER` |
| `enabled` | `bool` | False = muted + non-interactive |
| `on_click` | `Callable[[], None]` | Called on left mouse release |

States: `normal` → `hover` (neon glow shadow +2 px) → `pressed` (scale 98%) → `disabled` (30% opacity).

---

#### `ProgressBar`
| Prop | Type | Description |
|---|---|---|
| `rect` | `pygame.Rect` | Bounding rect |
| `value` | `float` | Current value |
| `max_value` | `float` | Maximum value |
| `fill_color` | `tuple[int,int,int]` | Fill color |
| `bg_color` | `tuple[int,int,int]` | Background color |
| `label` | `str \| None` | Optional overlay text (e.g. `"4/5"`) |
| `animate` | `bool` | Smooth interpolation on value change |

---

#### `Label`
| Prop | Type | Description |
|---|---|---|
| `text` | `str` | Display string |
| `rect` | `pygame.Rect` | Bounding rect |
| `font_size` | `int` | Pixel size |
| `color` | `tuple[int,int,int]` | Text color |
| `align` | `Literal["left","center","right"]` | Horizontal alignment |

---

#### `Panel`
| Prop | Type | Description |
|---|---|---|
| `rect` | `pygame.Rect` | Bounding rect |
| `bg_color` | `tuple[int,int,int]` | Fill color |
| `border_color` | `tuple[int,int,int] \| None` | Border color; `None` = no border |
| `border_width` | `int` | Border thickness in px |
| `alpha` | `int` | 0–255 transparency |

---

### 3.2 HUD Components — `src/ui/hud.py`, `hud_state.py`

#### `HUD`
Renders all sub-components using a `HUDState` DTO passed each frame from `GameScene._build_hud_state()`. Never writes back to game state.

| Sub-component | Position | Key Props |
|---|---|---|
| `HealthBar` | Top-left | `hp`, `max_hp`, `armor` |
| `RoundTimerDisplay` | Top-center | `seconds_remaining` |
| `EconomyStrip` | Top-right | `currency_this_round`, `kills` |
| `ChallengeWidget` | Left side | `challenges: list[ChallengeInfo]` |
| `QuickSlotBar` | Bottom-left | `quick_slots: list[Item \| None]` |
| `WeaponInfoPanel` | Bottom-center | `weapon_info: WeaponInfo \| None` |
| `MiniMap` | Bottom-right | `map_surface`, `player_pos`, `extraction_pos`, `enemy_positions` |
| `ZoneBanner` | Top-center (transient) | `zone_info: ZoneInfo \| None` |
| `ExtractionProgressBar` | Center-screen | `extraction_progress: float \| None` |
| `LootPickupPrompt` | Bottom-center | `pickup_prompt: str \| None` |

---

#### `HealthBar`
| Prop | Type | Description |
|---|---|---|
| `hp` | `int` | Current HP |
| `max_hp` | `int` | Maximum HP |
| `armor` | `int` | Current armor value |

Renders dual-layer bar: thin blue armor layer on top of green→red gradient health bar. Animates damage flash (red pulse). Constant red vignette added to screen when HP < 20%.

---

#### `RoundTimerDisplay`
| Prop | Type | Description |
|---|---|---|
| `seconds_remaining` | `int` | Seconds left in round |

Color state: white (> 5 min) → amber (≤ 5 min) → red pulsing (≤ 2 min). Displays as `MM:SS`.

---

#### `MiniMap` — `src/ui/mini_map.py`
| Prop | Type | Description |
|---|---|---|
| `map_surface` | `pygame.Surface` | Pre-rendered full map thumbnail |
| `player_pos` | `tuple[float, float]` | World coordinates |
| `extraction_pos` | `tuple[float, float]` | Extraction zone center |
| `enemy_positions` | `list[tuple[float, float]]` | Visible enemy positions |

Renders as 150×150 px circular clipped surface. Player = white dot; extraction = green dot with pulse; enemies = small red dots.

---

#### `ChallengeWidget` — `src/ui/challenge_widget.py`
| Prop | Type | Description |
|---|---|---|
| `challenges` | `list[ChallengeInfo]` | DTOs with `label`, `progress`, `target`, `completed` |

Left-edge vertical stack of 3 rows. Each row: challenge text + thin ProgressBar. Completed rows show green checkmark and strike-through. Widget collapses (slides off-screen) 3 s after all 3 are complete.

---

#### `ExtractionProgressBar`
| Prop | Type | Description |
|---|---|---|
| `progress` | `float \| None` | 0.0–1.0; `None` = hidden |

Shown center-screen when player holds E in extraction zone. Circular radial fill animation with "Extracting…" label.

---

#### `LootPickupPrompt`
| Prop | Type | Description |
|---|---|---|
| `pickup_prompt` | `str \| None` | Item name string; `None` = hidden |
| `rarity` | `Rarity \| None` | Determines prompt text color |

Bottom-center prompt text: `[E] Pick Up: {ItemName}` in rarity color. Also renders a world-space floating label above the loot item (handled by `LootItem.render()`).

---

### 3.3 Inventory Components — `src/ui/inventory_screen.py`

#### `InventoryScreen`
Full overlay scene. Manages slot selection, context menus, and attachment interactions. Props injected on scene push: `inventory: Inventory`, `event_bus: EventBus`.

---

#### `InventorySlot`
| Prop | Type | Description |
|---|---|---|
| `index` | `int` | Slot index (0–23 main, 0–3 quick) |
| `item` | `Item \| None` | Item in slot; `None` = empty |
| `is_quick_slot` | `bool` | Different border style for quick slots |
| `selected` | `bool` | Highlighted state |

Renders: 48×48 px cell with rarity-color border, item icon, quantity badge (if stackable). Hover triggers `ItemTooltip`.

---

#### `ItemTooltip`
| Prop | Type | Description |
|---|---|---|
| `item` | `Item` | Item to describe |

Floating panel (200×160 px) anchored near cursor. Shows: item name (rarity-colored), type badge, stat block, short description. Z-renders above all inventory UI.

---

#### `WeaponAttachmentPanel`
| Prop | Type | Description |
|---|---|---|
| `weapon` | `Weapon \| None` | Selected weapon; `None` = hidden |
| `inventory` | `Inventory` | Used to find compatible attachments |

4 socket slots (mod / scope / barrel / stock), each 56×56 px. Occupied socket shows attachment icon; empty socket shows socket-type icon + dashed border. Click socket to open attachment picker filtered by socket type.

---

#### `ItemContextMenu`
| Prop | Type | Description |
|---|---|---|
| `item` | `Item` | Item to act on |
| `position` | `tuple[int, int]` | Screen position of menu origin |
| `on_action` | `Callable[[str], None]` | Called with action string (`"equip"`, `"use"`, `"drop"`, `"inspect"`) |

Dropdown list of available actions; unavailable actions are grayed. Dismissed by any click outside.

---

### 3.4 Skill Tree Components — `src/ui/skill_tree_screen.py`

#### `SkillTreeScreen`
Scrollable canvas (virtual size ~1600×900). Two labeled branches side-by-side: **Combat** (left) and **Mobility** (right). Scroll with arrow keys or mouse drag.

---

#### `SkillNode`
| Prop | Type | Description |
|---|---|---|
| `node_id` | `str` | Unique identifier |
| `name` | `str` | Display name |
| `description` | `str` | Stat bonus description |
| `cost` | `int` | Currency cost to unlock |
| `unlocked` | `bool` | Already purchased |
| `available` | `bool` | Prerequisites met, purchasable |
| `icon` | `pygame.Surface` | Node icon |

Visual states: **unlocked** (full neon glow, solid border) → **available** (dashed neon border, brighter icon) → **locked** (dimmed, no border glow). Shape: 72×72 px hexagon. Hover → `SkillNodeTooltip`.

---

#### `SkillEdge`
| Prop | Type | Description |
|---|---|---|
| `from_pos` | `tuple[int, int]` | Start position on canvas |
| `to_pos` | `tuple[int, int]` | End position on canvas |
| `active` | `bool` | Whether the path is unlocked |

Drawn as a 2 px line. Active = bright neon color; inactive = dim gray.

---

#### `SkillNodeTooltip`
| Prop | Type | Description |
|---|---|---|
| `node_id` | `str` | Node reference |
| `name` | `str` | Skill name |
| `description` | `str` | Full bonus description |
| `cost` | `int` | Currency cost |
| `requirement` | `str \| None` | "Requires: {NodeName}" if locked |

---

### 3.5 Home Base Components — `src/ui/home_base_screen.py`

#### `HomeBaseScreen`
2×2 grid of `FacilityCard` widgets. Currency balance displayed top-right of panel.

---

#### `FacilityCard`
| Prop | Type | Description |
|---|---|---|
| `facility_id` | `str` | `"armory"` / `"med_bay"` / `"storage"` / `"comms"` |
| `name` | `str` | Display name |
| `tier` | `int` | Current upgrade tier (0-based) |
| `max_tier` | `int` | Maximum tier |
| `description` | `str` | Current tier benefit summary |
| `upgrade_cost` | `int \| None` | Cost for next tier; `None` if maxed |
| `on_upgrade_click` | `Callable[[], None]` | Opens upgrade modal |

Card: 200×180 px panel. Tier pips at bottom (filled dots = current tier). "UPGRADE" button bottom-right; replaced by "MAXED" badge at max tier.

---

#### `FacilityUpgradeModal`
| Prop | Type | Description |
|---|---|---|
| `facility_id` | `str` | Facility reference |
| `name` | `str` | Facility name |
| `current_tier_desc` | `str` | Current tier benefits |
| `next_tier_desc` | `str` | Next tier benefits |
| `cost` | `int` | Upgrade cost |
| `can_afford` | `bool` | Whether player has sufficient currency |
| `on_confirm` | `Callable[[], None]` | Executes upgrade |
| `on_cancel` | `Callable[[], None]` | Dismisses modal |

Centered modal (500×280 px). Two-column layout: current vs next tier. CONFIRM button disabled + grayed if `can_afford == False`.

---

### 3.6 Post-Round Components — `src/scenes/post_round.py`

#### `LootSummaryList`
| Prop | Type | Description |
|---|---|---|
| `items` | `list[Item]` | Items kept from round |
| `total_value` | `int` | Sum of item monetary values |

Scrollable list rows: item icon (24×24) + rarity-colored name + value. "LOOT LOST" placeholder shown on extraction failure.

---

#### `RewardCounter`
| Prop | Type | Description |
|---|---|---|
| `xp_earned` | `int` | XP gained this round |
| `currency_earned` | `int` | Currency gained this round |
| `level_up` | `bool` | Whether player leveled up |
| `new_level` | `int \| None` | New level if leveled up |

Animated number count-up for both values. XP bar fill animation. Level-up banner ("LEVEL UP → Lvl N") slides in from right on `level_up=True`.

---

#### `ChallengeResultList`
| Prop | Type | Description |
|---|---|---|
| `challenges` | `list[ChallengeResult]` | With `completed: bool`, `description: str`, `xp_reward: int` |

3 rows. Completed = green checkmark. Failed = red X. XP reward shown beside each completed challenge.

---

#### `StatBlock`
| Prop | Type | Description |
|---|---|---|
| `kills_pve` | `int` | PvE kills |
| `kills_pvp` | `int` | PvP kills |
| `damage_dealt` | `int` | Total damage dealt |
| `damage_taken` | `int` | Total damage received |
| `zones_visited` | `int` | Unique zones entered |
| `survival_seconds` | `int` | Time alive in round |

Grid of labeled stat pairs. Rendered as `Label` + value pairs in a 2-column layout.

---

## 4. State Management

### 4.1 Persistent Progression State

Owned by long-lived objects created in `GameApp.__init__()` (or `main.py`). Passed by reference into each scene. Serialized by `SaveManager` at defined save points.

| Object | Persisted Fields | Save Trigger |
|---|---|---|
| `XPSystem` | `xp`, `level` | PostRoundScreen.on_enter(), HomeBaseScene.on_exit() |
| `Currency` | `balance` | PostRoundScreen.on_enter(), HomeBaseScene.on_exit() |
| `SkillTree` | `unlocked_node_ids` | HomeBaseScene.on_exit() |
| `HomeBase` | `facility_tiers` | HomeBaseScene.on_exit() |

Load trigger: `SaveManager.restore()` called in `MainMenu` → "CONTINUE" and in `HomeBaseScene.on_enter()` for refresh.

Corrupt/missing save silently falls back to new-game defaults (no error shown to player).

---

### 4.2 Ephemeral Round State

Lives entirely within `GameScene` and its owned systems. Discarded when `GameScene` exits. Never persisted mid-round.

| State | Owner | Fate on Round End |
|---|---|---|
| Player position, health, buffs | `Player` entity | Discarded |
| Enemy list | `GameScene.enemies` | Discarded |
| Loot items in world | `GameScene.loot_items` | Discarded |
| Round inventory (picked up) | `Player.inventory` | Passed to PostRoundScreen; kept only if extracted |
| Active challenges | `ChallengeSystem` | Results passed to PostRoundScreen |
| Round timer | `RoundTimer` | Discarded |
| Camera offset | `Camera` | Discarded |
| Active buffs | `BuffSystem` | Discarded |
| Round XP/currency accumulator | `RoundSummary` | Passed to PostRoundScreen |

---

### 4.3 UI Overlay State

Local to each scene/screen. Not persisted. Managed by the screen instance.

| Screen | Key State |
|---|---|
| `InventoryScreen` | `selected_slot: int \| None`, `context_menu_open: bool`, `hovered_slot: int \| None` |
| `SkillTreeScreen` | `hovered_node: str \| None`, `scroll_offset: tuple[int,int]`, `pending_unlock: str \| None` |
| `HomeBaseScreen` | `modal_open: str \| None` (facility_id of open upgrade modal) |
| `PostRoundScreen` | `active_tab: Literal["loot","stats","rewards"]`, `anim_phase: float`, `anim_complete: bool` |
| `MapOverlay` | `visible: bool` (toggled by M key in GameScene) |
| `PauseMenu` | No significant state beyond being on the scene stack |

---

### 4.4 HUD State (per-frame data transfer)

`GameScene._build_hud_state()` constructs a `HUDState` DTO each fixed timestep from live game objects and passes it to `HUD.update()`. **One-way push only** — HUD never mutates game state.

```
HUDState
  ├── hp:                  int
  ├── max_hp:              int
  ├── armor:               int
  ├── level:               int
  ├── xp:                  int
  ├── xp_to_next:          int
  ├── seconds_remaining:   int
  ├── currency_this_round: int
  ├── kills_this_round:    int
  ├── zone_info:           ZoneInfo | None       ← fade-in banner on zone change
  ├── weapon_info:         WeaponInfo | None     ← currently gap #10 (unpopulated)
  ├── quick_slots:         list[Item | None]     ← 4 quick-slot items
  ├── challenges:          list[ChallengeInfo]   ← 3 active challenges
  ├── extraction_progress: float | None          ← 0.0–1.0 while holding E
  └── pickup_prompt:       PickupPrompt | None   ← item name + rarity near player
```

---

### 4.5 Settings State

`Settings` loaded from `settings.json` at startup. Mutated by `SettingsScene` on APPLY; written to disk immediately via `Settings.save()`. Fields: `resolution`, `fullscreen`, `target_fps`, `volume` (dict with `master`/`music`/`sfx`), `key_bindings` (dict of action → key).

---

## 5. Interaction Patterns & Visual Language

### 5.1 Keyboard Navigation

| Context | Key | Action |
|---|---|---|
| Any menu | Arrow keys + Enter | Navigate + confirm |
| Any overlay / modal | Esc | Close / go back |
| GameScene | Tab | Toggle InventoryScreen |
| GameScene | M | Toggle MapOverlay |
| GameScene | Esc | Push PauseMenu |
| GameScene | E | Pick up item / hold to extract |
| GameScene | 1–4 | Use quick-slot item |
| GameScene | Shift | Sprint modifier |
| GameScene | Space | Jump |
| GameScene | Ctrl | Crouch |
| GameScene | C | Slide |
| GameScene | WASD | Move |
| PauseMenu | Esc | Resume |

All key bindings are remappable via SettingsScene → Controls tab.

---

### 5.2 Mouse Interaction

| Action | Effect |
|---|---|
| Hover button / slot | Highlight + tooltip |
| Left-click | Primary action (confirm, select, shoot) |
| Right-click (inventory) | Context menu |
| Mouse aim | Rotates player facing; aim direction sent to ShootingSystem |
| Mouse left-hold | Continuous fire (auto weapons) |

---

### 5.3 Visual Feedback Events

| Game Event | Visual Feedback |
|---|---|
| Player takes damage | Red screen vignette pulse (0.2 s); HealthBar drains with animation |
| Player heals | Brief green overlay flash |
| Player death | Red vignette swells to full screen; "YOU DIED" fades in; black fade to PostRound |
| Low HP (< 20%) | Persistent red pulsing vignette |
| Level up | "LEVEL UP → Lvl N" banner slides in top-center, auto-dismisses after 3 s |
| Challenge complete | ChallengeWidget row flashes green; checkmark animates in |
| Item picked up | Floating "+{ItemName}" text rises from player, fades over 1 s |
| Enemy killed | Brief hit-flash on enemy sprite; XP number rises from enemy position |
| Extraction begins | "Extracting…" radial progress appears center-screen |
| Zone entered | Zone name banner fades in/out top-center for 2 s |
| Round timer < 2 min | Timer pulses red; subtle urgency BGM shift |
| Round timer expired | Screen flash; automatic PostRound transition |

---

### 5.4 Color Language

| Meaning | Hex | Usage |
|---|---|---|
| Primary CTA / confirm | `#00E5FF` | Buttons, active borders, extraction |
| Danger / health loss / enemy | `#FF3333` | Enemy dots, damage indicators, low HP |
| Success / heal / extraction | `#00FF7F` | Healing, extraction progress, completed |
| Currency / economy | `#FFB300` | Currency amounts, reward values |
| Locked / unavailable | `#444444` | Locked nodes, disabled buttons |
| UI panel background | `#0A0E1A` | All modal and panel backgrounds |
| UI neon accent / borders | `#FF00CC` | Panel borders, accent highlights |
| Item — Common | `#CCCCCC` | Item name, slot border |
| Item — Uncommon | `#44FF44` | Item name, slot border |
| Item — Rare | `#4488FF` | Item name, slot border |
| Item — Epic | `#AA44FF` | Item name, slot border |
| Item — Legendary | `#FF8800` | Item name, slot border, glow effect |

---

### 5.5 Typography Scale

| Use | Size | Weight | Color |
|---|---|---|---|
| Game title / splash | 72 px | Bold | Neon cyan with glow |
| Screen heading | 32 px | Bold | White |
| Section label | 20 px | SemiBold | Light gray |
| Body / item name | 16 px | Regular | White |
| Caption / hint | 12 px | Regular | Muted gray `#888888` |
| HUD timer | 28 px | Bold Mono | State-dependent (see §5.3) |
| HUD ammo count | 18 px | Bold Mono | White |

All fonts loaded exclusively via `AssetManager` (no direct `pygame.font.Font()` calls).

---

*End of UX Specification.*
