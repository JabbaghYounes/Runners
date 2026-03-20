Now I have a complete picture of the codebase. Let me produce the implementation plan.

---

## ARCHITECTURE

### Overview
The Home Base hub is a between-rounds upgrade screen where players spend earned currency on facility upgrades (Armory, Med Bay, Storage). Most of the domain logic is already production-quality (`HomeBase`, `Currency`, `SaveManager`). The bulk of work is in the scene layer: wiring the real data into the UI, attaching interactive upgrade buttons, emitting the `currency_spent` event, saving after each transaction, and plumbing the scene into both MainMenu and PostRound.

### Components Involved
| Component | Status | Role |
|---|---|---|
| `HomeBase` model | ✅ Complete | `upgrade()`, `can_upgrade()`, `get_facility_display()`, `get_round_bonuses()`, serialization |
| `Currency` model | ✅ Complete | `spend()` is called inside `HomeBase.upgrade()`; `add()` used by PostRound |
| `SaveManager` | ✅ Complete | Atomic write; called after every upgrade and after PostRound |
| `data/home_base.json` | ✅ Complete | 3 facilities × 5 levels; cost, bonus_type, bonus_value, description |
| `HomeBaseScene` | ⚠️ Stub | Renders cards from wrong data source; no upgrade buttons; no EventBus or SaveManager wiring |
| `MainMenu` | ⚠️ Missing nav | Has no "Home Base" entry point; "Start Game" goes directly to GameScene |
| `PostRound` | ⚠️ Broken nav | `_activate_button()` calls `HomeBaseScene()` bare — will crash |

### Data Flow

```
┌─────────────────── MainMenu ──────────────────────┐
│  _on_home_base()                                   │
│    SaveManager().restore(hb, cur, xp, st)         │
│    sm.replace(HomeBaseScene(sm, …, hb, st, cur,   │
│                              xp, event_bus, save)) │
└───────────────────────────────────────────────────┘
           │                           ▲
           ▼                           │  BACK button
┌─── HomeBaseScene ──────────────────────────────────┐
│  render:                                            │
│    for fid in home_base.facility_ids:               │
│      data = home_base.get_facility_display(fid)     │
│      draw card (locked / available / maxed)         │
│      if can_upgrade → draw UPGRADE button           │
│                                                     │
│  _on_upgrade(fid):                                  │
│    cost = home_base.upgrade_cost(fid)               │
│    if home_base.upgrade(fid, currency):             │  ←── deducts currency
│      event_bus.emit("currency_spent",               │
│                      amount=cost, facility=fid)     │
│      save_manager.save(home_base, currency,         │
│                         xp_system, skill_tree)      │  ←── atomic write
│                                                     │
│  QUEUE FOR ROUND → GameScene (existing path)        │
└─────────────────────────────────────────────────────┘
           │ PostRound "Home Base" button
           ▼
┌─────────────────── PostRound ──────────────────────┐
│  __init__ now also accepts:                         │
│    home_base, skill_tree, event_bus, settings,      │
│    assets  (carried from GameScene)                 │
│                                                     │
│  _activate_button(1):                               │
│    sm.replace(HomeBaseScene(sm, settings, assets,   │
│               home_base, skill_tree, currency,      │
│               xp_system, event_bus, save_manager))  │
└─────────────────────────────────────────────────────┘
```

**Facility card state logic** (`get_facility_display()` drives rendering):
- `level == max_level` → **MAXED** (no button, green border)
- `level < max_level AND can_upgrade()` → **AVAILABLE** (cyan UPGRADE button)
- `level < max_level AND NOT can_upgrade()` → **LOCKED** (dim button, shows cost)

---

## FILES TO MODIFY

- `src/scenes/home_base_scene.py` — Core scene rewire: correct data source, upgrade buttons, EventBus + SaveManager plumbing
- `src/scenes/main_menu.py` — Add "Home Base" menu item and `_on_home_base()` handler
- `src/scenes/post_round.py` — Extend constructor with missing objects; fix bare `HomeBaseScene()` call in `_activate_button()`

## FILES TO CREATE

- `tests/test_home_base_scene.py` — Headless unit/integration tests for upgrade flow, event emission, save-after-purchase, edge cases

---

## IMPLEMENTATION PHASES

### Phase 1: Core Logic — Happy Path Only

**Scope:** A player can navigate to HomeBaseScene from MainMenu, see all three facility cards with correct level/cost data, click UPGRADE on an affordable facility, have currency deducted and the level saved, with `currency_spent` emitted. PostRound can also navigate to HomeBaseScene with the same objects it already holds.

**Boundary:** A single full upgrade transaction completes end-to-end (navigate → view → buy → persisted), under the assumption the player has sufficient currency.

**Tasks:**

1. **Add `event_bus` and `save_manager` parameters to `HomeBaseScene.__init__`** — `src/scenes/home_base_scene.py`
   - Store as `self._event_bus` and `self._save_manager`
   - Make both optional (`Any = None`) to preserve backward compat with existing call sites in `_queue_round()`

2. **Fix `_draw_facilities()` to read from `get_facility_display()`** — `src/scenes/home_base_scene.py`
   - Replace `self._home_base.get_facilities()` loop with `for fid in self._home_base.facility_ids:`
   - Call `self._home_base.get_facility_display(fid)` → dict with `name`, `level`, `max_level`, `cost`, `bonus_description`, `current_bonus_description`
   - Render: facility name, `Level N/M`, current bonus description, next level description + cost (or "MAXED")
   - Determine card border colour by state: `BORDER_BRIGHT` (available), `ACCENT_GREEN` (maxed), `BORDER_DIM` (locked/can't afford)

3. **Build per-facility upgrade `Button` widgets and wire `_on_upgrade(fid)`** — `src/scenes/home_base_scene.py`
   - In `__init__`, create `self._upgrade_btns: dict[str, Button]` — one button per facility, positioned inside the facility card rect
   - `_on_upgrade(fid)`: get cost, call `home_base.upgrade(fid, currency)`, on `True` → `event_bus.emit("currency_spent", amount=cost, facility=fid)` and `save_manager.save(home_base=..., currency=..., xp_system=..., skill_tree=...)`
   - `handle_events()`: route events to `_upgrade_btns[fid].handle_event(event)` for each facility
   - `render()`: draw each upgrade button during `_draw_facilities()`

4. **Extend `PostRound.__init__` to accept and store `home_base`, `skill_tree`, `event_bus`, `settings`, `assets`** — `src/scenes/post_round.py`
   - Add these five kwargs to the constructor, stored as instance attributes
   - Guard with the existing `sm is not None` legacy-path early return to avoid breakage

5. **Fix `PostRound._activate_button(1)` to construct `HomeBaseScene` with full args** — `src/scenes/post_round.py`
   - Replace bare `HomeBaseScene()` with `HomeBaseScene(sm, self._settings, self._assets, self._home_base, self._skill_tree, self._currency, self._xp_system, self._event_bus, self._save_manager)`
   - Guard: if any required object is `None`, fall back to `MainMenu` instead of crashing

6. **Add "Home Base" to `MainMenu._MENU_ITEMS` and implement `_on_home_base()`** — `src/scenes/main_menu.py`
   - Insert `"Home Base"` between `"Start Game"` and `"Settings"` in `_MENU_ITEMS`
   - `_on_home_base()`: import and instantiate fresh `HomeBase`, `Currency`, `XPSystem`, `SkillTree`, `SaveManager`, `EventBus`; call `save_manager.restore(currency=..., xp_system=..., home_base=..., skill_tree=...)`; then `self._sm.replace(HomeBaseScene(self._sm, self._settings, self._assets, hb, st, cur, xp, eb, save_mgr))`
   - If `self._sm is None` (bus mode), emit `scene_request` event as existing fallback

---

### Phase 2: Error Handling and Edge Cases

**Scope:** Handle all foreseeable bad states: insufficient funds, maxed facilities, None dependencies, rapid double-click, and scenes constructed without the new optional args.

**Boundary:** Every valid and invalid user action leaves the game in a consistent, non-crashed state.

**Tasks:**

1. **Visually disable upgrade button when player can't afford or facility is maxed** — `src/scenes/home_base_scene.py`
   - In `_draw_facilities()`, set button `style` dynamically: `'primary'` if `can_upgrade()`, `'ghost'` if can't afford (show cost anyway), omit/hide button entirely if maxed
   - `Button` is already drawn with `ghost` style that shows dim border with no fill — no new widget logic needed

2. **Guard `event_bus` and `save_manager` with `if self._event_bus:` / `if self._save_manager:`** — `src/scenes/home_base_scene.py`
   - Already planned as optional in Phase 1 Task 1, but add explicit guards in `_on_upgrade()` so tests can pass `None` safely

3. **Guard `_on_upgrade()` against double-fire** — `src/scenes/home_base_scene.py`
   - `HomeBase.upgrade()` already returns `False` for insufficient funds or maxed state; `Currency.spend()` returns `False` if balance is insufficient; no additional locking needed — but verify the event + save are only called on `True` return (correct in Phase 1 plan)

4. **Write `tests/test_home_base_scene.py` with headless coverage** — `tests/test_home_base_scene.py`
   - **Happy path**: `_on_upgrade("storage")` on `Currency(balance=500)` → level becomes 1, balance decremented, `currency_spent` emitted with `{amount: 200, facility: "storage"}`, `save_manager.save()` called once
   - **Insufficient funds**: `_on_upgrade("armory")` on `Currency(balance=100)` → level stays 0, no event, no save
   - **Maxed facility**: set `home_base._levels["storage"] = 5`, call `_on_upgrade("storage")` → no change, no event, no save
   - **Render data correctness**: `get_facility_display("med_bay")` at level 2 returns `cost=700`, `current_bonus_description="+50 starting HP"`, `bonus_description="+75 starting HP"`
   - **None dependencies**: construct `HomeBaseScene(..., event_bus=None, save_manager=None)`, call `_on_upgrade()` on affordable facility — no crash, level still increments

5. **Protect `PostRound._activate_button()` when new fields are None** — `src/scenes/post_round.py`
   - If `self._home_base is None` when index==1, fall back to `sm.replace(MainMenu(sm, self._settings, self._assets))` rather than crashing

---

### Phase 3: Polish and Optimization

**Scope:** Visual quality, observability, and minor code hygiene.

**Boundary:** The scene is visually complete and production-ready.

**Tasks:**

1. **Show current active bonus on each facility card** — `src/scenes/home_base_scene.py`
   - Under the "Level N/M" line, render `current_bonus_description` in `TEXT_DIM` colour (e.g. "currently: +25 starting HP" or "Not built" at level 0)
   - Already available from `get_facility_display()` → no model changes needed

2. **Add level pip indicators to facility cards** — `src/scenes/home_base_scene.py`
   - Draw `max_level` small squares (8×8 px) below the card name; fill `ACCENT_CYAN` for each purchased level, `BORDER_DIM` for unpurchased — gives instant visual state at a glance

3. **Ensure `from __future__ import annotations` and full type signatures on all new methods** — `src/scenes/home_base_scene.py`, `src/scenes/post_round.py`, `src/scenes/main_menu.py`
   - Follows the codebase convention stated in CLAUDE.md

---

## DEPENDENCIES

```
Phase 1, Task 1 (fix _draw_facilities data source)
  └── must complete before Task 3 (upgrade buttons reference card rects from Task 1 layout)

Phase 1, Task 4 (PostRound constructor fields)
  └── must complete before Task 5 (PostRound._activate_button uses those fields)

Phase 1, Tasks 1–5 ALL
  └── must complete before any Phase 2 tasks

Phase 2, Task 4 (write tests)
  └── depends on Phase 2, Tasks 1–3 (tests cover the guarded behaviours)

Phase 2 ALL
  └── must complete before Phase 3 tasks

Phase 1, Task 6 (MainMenu nav) and Tasks 1–5
  └── independent of each other — can be implemented concurrently
```

**Cross-phase hard rule:** `GameScene → PostRound` currently does not pass `home_base`, `skill_tree`, `event_bus`, `settings`, `assets` to PostRound. Phase 1 Task 4 adds those params as optional kwargs with `None` defaults, so existing GameScene call sites will not break. A follow-on task (outside this feature's scope) should update `GameScene` to forward those objects to PostRound — but the new navigation path will function correctly for the MainMenu → HomeBaseScene → GameScene → PostRound path once PostRound holds those fields.
