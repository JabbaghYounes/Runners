Implement the player entity with an 8-state FSM and full keyboard/mouse input handling.

Depends on: core-infrastructure, tile-map

- States: IDLE, WALK, RUN (Shift), JUMP (Space), CROUCH (Ctrl), SLIDE (C), SHOOT, DEAD
- `InputDriver` sets intent flags (`target_vx`, `jump_intent`, `slide_intent`); `PhysicsSystem` consumes them each tick
- `PhysicsSystem` applies gravity, resolves tile collisions, and enforces state transition rules (e.g. can't jump while sliding)
- Player renders on `LAYER_PLAYER` (Z = 3) with correct animation frame for each state
- E key triggers item pick-up interaction; Tab opens inventory; M opens map
- Player has configurable max HP, move speed, and jump force (constants in `src/constants.py`)

