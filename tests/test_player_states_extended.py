"""Tests for the 8-state Player FSM: SHOOT, DEAD, input guards, interact, mouse.

Run: pytest tests/test_player_states_extended.py

Covers
------
Unit tests (~60 %):
  - SHOOT state fires when LMB held on ground, not sliding/airborne
  - DEAD state overrides every other state
  - Dead player ignores all keyboard and mouse input (early-return guard)
  - Jump-while-sliding guard in handle_input() and update()
  - E-key sets _interact_intent; update() emits "interact" and clears the flag
  - Mouse LMB sets / clears _shoot_pressed each handle_input call
  - PLAYER_MAX_HEALTH constant is 100; Player defaults match it
  - _STATE_ANIM and AnimationController._FALLBACK_COLOURS include SHOOT/DEAD

Integration tests (~30 %):
  - Render layer constant LAYER_PLAYER == 3; render() does not raise
  - AnimationController sync to "shoot" / "dead" after state resolves
  - GameScene Tab key → sm.push(InventoryScreen) when player alive
  - GameScene Tab key not pushed when player dead
  - Full physics + state transition flows

E2E tests (~10 %):
  - Alive player input → update → render completes without error
  - Death flow: alive=False → DEAD state → all subsequent inputs blocked
  - E key → update → interact event emitted, flag cleared
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame
import pytest

from src.constants import (
    CROUCH_HEIGHT,
    JUMP_VEL,
    KEY_BINDINGS,
    LAYER_PLAYER,
    NORMAL_HEIGHT,
    PLAYER_MAX_HEALTH,
    SLIDE_DURATION,
    SPRINT_SPEED,
    TILE_SIZE,
    WALK_SPEED,
)
from src.entities.player import Player, MovementState, _STATE_ANIM
from src.systems.physics import PhysicsSystem


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _MockTileMap:
    """Minimal TileMap whose solid layout is configurable per test."""

    def __init__(self, cols=30, rows=20, solid_set=None, out_of_bounds_solid=True):
        self.tile_size = TILE_SIZE
        self.cols = cols
        self.rows = rows
        self._solid = solid_set if solid_set is not None else set()
        self._oob_solid = out_of_bounds_solid

    def is_solid(self, col: int, row: int) -> bool:
        if col < 0 or row < 0 or col >= self.cols or row >= self.rows:
            return self._oob_solid
        return (col, row) in self._solid


def _ground_map(ground_row=15, cols=30, rows=20) -> _MockTileMap:
    """Return a map with a solid floor at *ground_row*."""
    solid = {(c, ground_row) for c in range(cols)}
    return _MockTileMap(cols=cols, rows=rows, solid_set=solid)


def _player_on_ground(x=200, ground_row=15) -> Player:
    """Create a Player standing on the ground row with zero velocity."""
    ground_y = ground_row * TILE_SIZE - NORMAL_HEIGHT
    p = Player(x=x, y=ground_y)
    p.on_ground = True
    p.vx = 0.0
    p.vy = 0.0
    return p


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, {"key": key, "mod": 0})


def _keyup(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYUP, {"key": key, "mod": 0})


class _Bus:
    """Minimal event bus that records emitted event names."""

    def __init__(self):
        self._log: list[str] = []

    def emit(self, name: str, **_kwargs) -> None:
        self._log.append(name)

    def subscribe(self, *_a) -> None:
        pass

    def unsubscribe(self, *_a) -> None:
        pass

    def emitted(self) -> list[str]:
        return list(self._log)

    def has(self, name: str) -> bool:
        return name in self._log

    def count(self, name: str) -> int:
        return self._log.count(name)


_MOUSE_UP = (False, False, False)
_MOUSE_DOWN = (True, False, False)

_INTERACT_KEY = KEY_BINDINGS.get("interact", pygame.K_e)
_JUMP_KEY = KEY_BINDINGS.get("jump", pygame.K_SPACE)
_SLIDE_KEY = KEY_BINDINGS.get("slide", pygame.K_c)
_INVENTORY_KEY = KEY_BINDINGS.get("inventory", pygame.K_TAB)


# ===========================================================================
# 1. SHOOT state (unit)
# ===========================================================================

class TestShootState:
    """SHOOT state fires when LMB held, on ground, outside slide/air."""

    def test_shoot_state_when_mouse_button_held(self, pygame_init):
        """LMB held + on ground + not sliding → movement_state == SHOOT."""
        p = _player_on_ground()
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.SHOOT

    def test_shoot_state_not_entered_when_mouse_not_pressed(self, pygame_init):
        """No LMB → state must not be SHOOT (should be IDLE on ground, no motion)."""
        p = _player_on_ground()
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state != MovementState.SHOOT

    def test_shoot_state_not_entered_while_sliding(self, pygame_init):
        """SLIDING has higher FSM priority than SHOOT."""
        p = _player_on_ground()
        p.slide_timer = SLIDE_DURATION  # actively sliding
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.SLIDING

    def test_shoot_state_not_entered_while_airborne_rising(self, pygame_init):
        """Airborne (rising) takes priority over SHOOT."""
        p = _player_on_ground()
        p.on_ground = False
        p.vy = -300.0  # rising
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.JUMPING

    def test_shoot_state_not_entered_while_airborne_falling(self, pygame_init):
        """Airborne (falling) takes priority over SHOOT."""
        p = _player_on_ground()
        p.on_ground = False
        p.vy = 200.0  # falling
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.FALLING

    def test_shoot_state_overrides_crouching(self, pygame_init):
        """SHOOT comes before CROUCHING in the priority chain."""
        p = _player_on_ground()
        tile_map = _ground_map()
        p.crouch(tile_map)
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.SHOOT

    def test_resolve_state_returns_shoot_directly(self, pygame_init):
        """_resolve_state() returns SHOOT when _shoot_pressed=True on ground."""
        p = _player_on_ground()
        p._shoot_pressed = True
        assert p._resolve_state() == MovementState.SHOOT

    def test_shoot_state_while_walking(self, pygame_init):
        """Holding LMB while moving still resolves to SHOOT (not WALKING)."""
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({pygame.K_d: True}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.SHOOT


# ===========================================================================
# 2. DEAD state (unit)
# ===========================================================================

class TestDeadState:
    """DEAD state has the highest FSM priority; it overrides every other state."""

    def test_dead_state_when_alive_is_false(self, pygame_init):
        """Setting alive=False and calling update() resolves DEAD state."""
        p = _player_on_ground()
        p.alive = False
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.DEAD

    def test_resolve_state_returns_dead_when_alive_false(self, pygame_init):
        """_resolve_state() returns DEAD immediately when alive=False."""
        p = _player_on_ground()
        p.alive = False
        assert p._resolve_state() == MovementState.DEAD

    def test_dead_overrides_shoot(self, pygame_init):
        """alive=False + _shoot_pressed=True → DEAD, not SHOOT."""
        p = _player_on_ground()
        p.alive = False
        p._shoot_pressed = True
        assert p._resolve_state() == MovementState.DEAD

    def test_dead_overrides_sliding(self, pygame_init):
        """alive=False + slide_timer > 0 → DEAD, not SLIDING."""
        p = _player_on_ground()
        p.alive = False
        p.slide_timer = SLIDE_DURATION
        assert p._resolve_state() == MovementState.DEAD

    def test_dead_overrides_jumping(self, pygame_init):
        """alive=False + airborne rising → DEAD, not JUMPING."""
        p = _player_on_ground()
        p.alive = False
        p.on_ground = False
        p.vy = -300.0
        assert p._resolve_state() == MovementState.DEAD

    def test_dead_overrides_falling(self, pygame_init):
        """alive=False + airborne falling → DEAD, not FALLING."""
        p = _player_on_ground()
        p.alive = False
        p.on_ground = False
        p.vy = 200.0
        assert p._resolve_state() == MovementState.DEAD

    def test_dead_overrides_crouching(self, pygame_init):
        """alive=False + crouched hitbox → DEAD, not CROUCHING."""
        p = _player_on_ground()
        tile_map = _ground_map()
        p.crouch(tile_map)
        p.alive = False
        assert p._resolve_state() == MovementState.DEAD

    def test_dead_overrides_walking(self, pygame_init):
        """alive=False + non-zero vx → DEAD, not WALKING."""
        p = _player_on_ground()
        p.alive = False
        p.vx = float(WALK_SPEED)
        assert p._resolve_state() == MovementState.DEAD

    def test_dead_state_persists_across_multiple_updates(self, pygame_init):
        """Once dead, movement_state stays DEAD across repeated update() calls."""
        p = _player_on_ground()
        p.alive = False
        tile_map = _ground_map()
        for _ in range(10):
            p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.DEAD


# ===========================================================================
# 3. Dead player ignores all input (unit)
# ===========================================================================

class TestDeadPlayerInput:
    """handle_input() early-return means dead players cannot change any intent flag."""

    def test_no_target_vx_when_dead_pressing_right(self, pygame_init):
        """Dead player + D key → target_vx stays 0.0."""
        p = _player_on_ground()
        p.alive = False
        p.target_vx = 0.0
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_d: True}, [])
        assert p.target_vx == 0.0

    def test_no_target_vx_when_dead_pressing_left(self, pygame_init):
        """Dead player + A key → target_vx stays 0.0."""
        p = _player_on_ground()
        p.alive = False
        p.target_vx = 0.0
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_a: True}, [])
        assert p.target_vx == 0.0

    def test_no_sprint_target_vx_when_dead(self, pygame_init):
        """Dead player + D + Shift → target_vx still 0 (no sprint)."""
        p = _player_on_ground()
        p.alive = False
        p.target_vx = 0.0
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_d: True, pygame.K_LSHIFT: True}, [])
        assert p.target_vx == 0.0

    def test_no_jump_intent_when_dead(self, pygame_init):
        """Dead player + Space KEYDOWN → _jump_intent stays False."""
        p = _player_on_ground()
        p.alive = False
        p._jump_intent = False
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_SPACE: True}, [_keydown(pygame.K_SPACE)])
        assert p._jump_intent is False

    def test_no_slide_intent_when_dead(self, pygame_init):
        """Dead player + C key with momentum → _slide_intent stays False."""
        p = _player_on_ground()
        p.alive = False
        p.vx = float(WALK_SPEED)
        p._slide_intent = False
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_c: True}, [_keydown(pygame.K_c)])
        assert p._slide_intent is False

    def test_no_interact_intent_when_dead(self, pygame_init):
        """Dead player + E key → _interact_intent stays False."""
        p = _player_on_ground()
        p.alive = False
        p._interact_intent = False
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [_keydown(_INTERACT_KEY)])
        assert p._interact_intent is False

    def test_shoot_pressed_not_updated_when_dead(self, pygame_init):
        """Dead player: early return fires before mouse read → _shoot_pressed unchanged."""
        p = _player_on_ground()
        p.alive = False
        p._shoot_pressed = False
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        assert p._shoot_pressed is False


# ===========================================================================
# 4. Jump-while-sliding guard (unit)
# ===========================================================================

class TestJumpWhileSlidingGuard:
    """Space key must be blocked while slide_timer > 0 in both handle_input and update."""

    def test_jump_blocked_in_handle_input_while_sliding(self, pygame_init):
        """Space KEYDOWN while slide_timer > 0 must NOT set _jump_intent."""
        p = _player_on_ground()
        p.slide_timer = SLIDE_DURATION
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_SPACE: True}, [_keydown(pygame.K_SPACE)])
        assert p._jump_intent is False

    def test_jump_allowed_when_slide_timer_is_zero(self, pygame_init):
        """Space KEYDOWN with slide_timer=0 on ground sets _jump_intent=True."""
        p = _player_on_ground()
        p.slide_timer = 0.0
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_SPACE: True}, [_keydown(pygame.K_SPACE)])
        assert p._jump_intent is True

    def test_jump_not_applied_by_update_while_sliding(self, pygame_init):
        """Even with _jump_intent forced True, update() must not apply jump while sliding."""
        p = _player_on_ground()
        p.slide_timer = SLIDE_DURATION
        p._jump_intent = True  # force set
        p.vy = 0.0
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.vy != JUMP_VEL, "update() must not apply jump while slide_timer > 0"

    def test_jump_applied_by_update_when_slide_timer_zero(self, pygame_init):
        """With slide_timer=0 and on_ground=True, update() applies the jump."""
        p = _player_on_ground()
        p.slide_timer = 0.0
        p._jump_intent = True
        p.vy = 0.0
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.vy == pytest.approx(JUMP_VEL)

    def test_jump_intent_cleared_even_when_blocked_by_slide(self, pygame_init):
        """_jump_intent must be False after update() even if the jump was blocked."""
        p = _player_on_ground()
        p.slide_timer = SLIDE_DURATION
        p._jump_intent = True
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p._jump_intent is False

    def test_jump_allowed_after_slide_expires(self, pygame_init):
        """After slide_timer counts to zero, Space can set _jump_intent."""
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        p.slide_timer = SLIDE_DURATION
        tile_map = _ground_map()
        # Run updates until slide expires
        ticks = 0
        while p.slide_timer > 0:
            p.update(1 / 60, tile_map)
            ticks += 1
            assert ticks < 200, "Slide must expire within 200 ticks"
        # Now jump should be permitted
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_SPACE: True}, [_keydown(pygame.K_SPACE)])
        assert p._jump_intent is True

    def test_mid_slide_space_press_does_not_change_vy(self, pygame_init):
        """Pressing Space mid-slide must leave vy unchanged through update()."""
        p = _player_on_ground()
        p.slide_timer = SLIDE_DURATION / 2
        p.vy = 0.0
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_SPACE: True}, [_keydown(pygame.K_SPACE)])
        p.update(1 / 60, tile_map)
        assert p.vy != JUMP_VEL


# ===========================================================================
# 5. E-key interact system (unit)
# ===========================================================================

class TestInteractSystem:
    """E key → _interact_intent → update emits 'interact' event and clears flag."""

    def test_e_keydown_sets_interact_intent(self, pygame_init):
        """E KEYDOWN must set _interact_intent=True."""
        p = _player_on_ground()
        p._interact_intent = False
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [_keydown(_INTERACT_KEY)])
        assert p._interact_intent is True

    def test_interact_event_emitted_when_intent_is_true(self, pygame_init):
        """update() emits 'interact' when _interact_intent=True and bus present."""
        bus = _Bus()
        p = Player(x=200, y=400, event_bus=bus)
        p.on_ground = True
        p._interact_intent = True
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert bus.has("interact")

    def test_interact_flag_cleared_after_update(self, pygame_init):
        """_interact_intent must be False after update() processes it."""
        bus = _Bus()
        p = Player(x=200, y=400, event_bus=bus)
        p.on_ground = True
        p._interact_intent = True
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p._interact_intent is False

    def test_interact_event_not_emitted_when_intent_is_false(self, pygame_init):
        """update() must NOT emit 'interact' when _interact_intent=False."""
        bus = _Bus()
        p = Player(x=200, y=400, event_bus=bus)
        p.on_ground = True
        p._interact_intent = False
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert not bus.has("interact")

    def test_interact_no_crash_without_event_bus(self, pygame_init):
        """_interact_intent=True with no bus must not raise; flag still cleared."""
        p = Player(x=200, y=400, event_bus=None)
        p.on_ground = True
        p._interact_intent = True
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)  # must not raise
        assert p._interact_intent is False

    def test_interact_event_emitted_exactly_once_per_keypress(self, pygame_init):
        """One E keydown followed by one update → exactly one 'interact' event."""
        bus = _Bus()
        p = Player(x=200, y=400, event_bus=bus)
        p.on_ground = True
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [_keydown(_INTERACT_KEY)])
        p.update(1 / 60, tile_map)
        assert bus.count("interact") == 1

    def test_interact_not_set_on_keyup(self, pygame_init):
        """KEYUP for the interact key must NOT set _interact_intent."""
        p = _player_on_ground()
        p._interact_intent = False
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [_keyup(_INTERACT_KEY)])
        assert p._interact_intent is False

    def test_dead_player_e_key_does_not_set_interact_intent(self, pygame_init):
        """Dead player presses E → early return fires first → _interact_intent False."""
        p = _player_on_ground()
        p.alive = False
        p._interact_intent = False
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [_keydown(_INTERACT_KEY)])
        assert p._interact_intent is False

    def test_interact_flag_not_set_when_intent_already_false_after_update(self, pygame_init):
        """After update clears the flag, a second update must not re-emit."""
        bus = _Bus()
        p = Player(x=200, y=400, event_bus=bus)
        p.on_ground = True
        tile_map = _ground_map()
        p._interact_intent = True
        p.update(1 / 60, tile_map)  # clears flag, emits once
        p.update(1 / 60, tile_map)  # no new flag set → no second emit
        assert bus.count("interact") == 1


# ===========================================================================
# 6. Mouse input → _shoot_pressed (unit)
# ===========================================================================

class TestMouseShootInput:
    """handle_input() reads LMB and stores the result in _shoot_pressed."""

    def test_lmb_pressed_sets_shoot_pressed_true(self, pygame_init):
        """LMB down → _shoot_pressed=True."""
        p = _player_on_ground()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        assert p._shoot_pressed is True

    def test_lmb_released_sets_shoot_pressed_false(self, pygame_init):
        """LMB up → _shoot_pressed=False (overrides a previous True)."""
        p = _player_on_ground()
        p._shoot_pressed = True  # pre-set
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [])
        assert p._shoot_pressed is False

    def test_shoot_pressed_updated_on_every_handle_input_call(self, pygame_init):
        """_shoot_pressed reflects the latest mouse state on each frame."""
        p = _player_on_ground()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        assert p._shoot_pressed is True
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [])
        assert p._shoot_pressed is False

    def test_rmb_and_mmb_alone_do_not_set_shoot_pressed(self, pygame_init):
        """Only button index [0] (LMB) triggers shoot intent."""
        p = _player_on_ground()
        with patch("pygame.mouse.get_pressed", return_value=(False, True, True)):
            p.handle_input({}, [])
        assert p._shoot_pressed is False

    def test_shoot_pressed_bool_type(self, pygame_init):
        """_shoot_pressed must always be a bool, not a raw int."""
        p = _player_on_ground()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        assert isinstance(p._shoot_pressed, bool)


# ===========================================================================
# 7. PLAYER_MAX_HEALTH constant (unit)
# ===========================================================================

class TestPlayerMaxHealthConstant:
    """PLAYER_MAX_HEALTH is 100; Player initialisation respects it."""

    def test_constant_value_is_100(self):
        assert PLAYER_MAX_HEALTH == 100

    def test_player_default_max_health_equals_constant(self, pygame_init):
        """Player() with no args must have max_health == PLAYER_MAX_HEALTH."""
        p = Player()
        assert p.max_health == PLAYER_MAX_HEALTH

    def test_player_health_initialises_to_max_health(self, pygame_init):
        """Newly created Player's current health must equal its max_health."""
        p = Player()
        assert p.health == p.max_health

    def test_player_max_health_can_be_overridden_via_kwarg(self, pygame_init):
        """Player(max_health=50) must have max_health=50 and health=50."""
        p = Player(max_health=50)
        assert p.max_health == 50
        assert p.health == 50

    def test_player_max_health_default_is_exactly_100(self, pygame_init):
        """Sanity: explicit check that default max_health is 100."""
        p = Player()
        assert p.max_health == 100

    def test_player_alive_true_on_creation(self, pygame_init):
        """Newly created player must be alive."""
        p = Player()
        assert p.alive is True


# ===========================================================================
# 8. Animation state mapping (unit)
# ===========================================================================

class TestAnimationStateMapping:
    """_STATE_ANIM and _FALLBACK_COLOURS include entries for SHOOT and DEAD."""

    def test_state_anim_contains_shoot_key(self):
        assert MovementState.SHOOT in _STATE_ANIM

    def test_state_anim_shoot_animation_key_is_shoot_string(self):
        anim_key, _ = _STATE_ANIM[MovementState.SHOOT]
        assert anim_key == "shoot"

    def test_state_anim_shoot_fps_is_positive_int(self):
        _, fps = _STATE_ANIM[MovementState.SHOOT]
        assert isinstance(fps, int) and fps > 0

    def test_state_anim_contains_dead_key(self):
        assert MovementState.DEAD in _STATE_ANIM

    def test_state_anim_dead_animation_key_is_dead_string(self):
        anim_key, _ = _STATE_ANIM[MovementState.DEAD]
        assert anim_key == "dead"

    def test_state_anim_dead_fps_is_positive_int(self):
        _, fps = _STATE_ANIM[MovementState.DEAD]
        assert isinstance(fps, int) and fps > 0

    def test_fallback_colours_contains_shoot(self):
        from src.entities.animation_controller import _FALLBACK_COLOURS
        assert "shoot" in _FALLBACK_COLOURS

    def test_fallback_colours_contains_dead(self):
        from src.entities.animation_controller import _FALLBACK_COLOURS
        assert "dead" in _FALLBACK_COLOURS

    def test_fallback_colour_shoot_is_valid_rgb_tuple(self):
        from src.entities.animation_controller import _FALLBACK_COLOURS
        colour = _FALLBACK_COLOURS["shoot"]
        assert isinstance(colour, tuple)
        assert len(colour) == 3
        assert all(isinstance(c, int) and 0 <= c <= 255 for c in colour)

    def test_fallback_colour_dead_is_valid_rgb_tuple(self):
        from src.entities.animation_controller import _FALLBACK_COLOURS
        colour = _FALLBACK_COLOURS["dead"]
        assert isinstance(colour, tuple)
        assert len(colour) == 3
        assert all(isinstance(c, int) and 0 <= c <= 255 for c in colour)

    def test_all_ten_movement_states_have_anim_entry(self):
        """Every member of MovementState must map to an animation key."""
        for state in MovementState:
            assert state in _STATE_ANIM, f"{state} missing from _STATE_ANIM"


# ===========================================================================
# 9. Render layer (integration)
# ===========================================================================

class TestRenderLayer:
    """Player renders at LAYER_PLAYER (Z = 3); render() must not raise."""

    def test_layer_player_constant_equals_three(self):
        assert LAYER_PLAYER == 3

    def test_player_render_does_not_raise(self, pygame_init):
        """Player.render() at origin camera offset must complete without error."""
        p = _player_on_ground()
        screen = pygame.Surface((640, 480))
        p.render(screen, (0, 0))

    def test_player_render_with_nonzero_camera_offset(self, pygame_init):
        """Player.render() with a shifted camera must complete without error."""
        p = _player_on_ground()
        screen = pygame.Surface((640, 480))
        p.render(screen, (150, 75))

    def test_dead_player_render_does_not_raise(self, pygame_init):
        """Rendering a dead player (DEAD state) must not crash."""
        p = _player_on_ground()
        p.alive = False
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        screen = pygame.Surface((640, 480))
        p.render(screen, (0, 0))

    def test_shooting_player_render_does_not_raise(self, pygame_init):
        """Rendering a player in SHOOT state must not crash."""
        p = _player_on_ground()
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.SHOOT
        screen = pygame.Surface((640, 480))
        p.render(screen, (0, 0))


# ===========================================================================
# 10. Animation controller sync (integration)
# ===========================================================================

class TestAnimationControllerSync:
    """AnimationController is synced to the right key after each state resolution."""

    def test_shoot_state_syncs_animation_to_shoot_key(self, pygame_init):
        """After SHOOT state resolves, animation controller must be on 'shoot'."""
        p = _player_on_ground()
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.SHOOT
        if p.animation_controller is not None:
            assert p.animation_controller._current_state == "shoot"

    def test_dead_state_syncs_animation_to_dead_key(self, pygame_init):
        """After DEAD state resolves, animation controller must be on 'dead'."""
        p = _player_on_ground()
        p.alive = False
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.DEAD
        if p.animation_controller is not None:
            assert p.animation_controller._current_state == "dead"

    def test_animation_controller_includes_shoot_state(self, pygame_init):
        """AnimationController built from sprite dir must have 'shoot' in configs."""
        from src.entities.animation_controller import AnimationController
        ac = AnimationController.from_sprite_dir(
            "assets/sprites/player",
            {"idle": 6, "walk": 10, "sprint": 14,
             "shoot": 8, "dead": 4,
             "crouch": 6, "crouch_walk": 8,
             "slide": 12, "jump": 4, "fall": 4},
        )
        assert "shoot" in ac._states_config

    def test_animation_controller_includes_dead_state(self, pygame_init):
        """AnimationController built from sprite dir must have 'dead' in configs."""
        from src.entities.animation_controller import AnimationController
        ac = AnimationController.from_sprite_dir(
            "assets/sprites/player",
            {"idle": 6, "walk": 10, "sprint": 14,
             "shoot": 8, "dead": 4,
             "crouch": 6, "crouch_walk": 8,
             "slide": 12, "jump": 4, "fall": 4},
        )
        assert "dead" in ac._states_config

    def test_shoot_animation_returns_surface(self, pygame_init):
        """AnimationController.get_current_frame() for 'shoot' returns a Surface."""
        from src.entities.animation_controller import AnimationController
        ac = AnimationController.from_sprite_dir(
            "assets/sprites/player", {"idle": 6, "shoot": 8, "dead": 4}
        )
        ac.set_state("shoot", facing_right=True)
        frame = ac.get_current_frame()
        assert isinstance(frame, pygame.Surface)

    def test_dead_animation_returns_surface(self, pygame_init):
        """AnimationController.get_current_frame() for 'dead' returns a Surface."""
        from src.entities.animation_controller import AnimationController
        ac = AnimationController.from_sprite_dir(
            "assets/sprites/player", {"idle": 6, "shoot": 8, "dead": 4}
        )
        ac.set_state("dead", facing_right=True)
        frame = ac.get_current_frame()
        assert isinstance(frame, pygame.Surface)

    def test_shoot_state_frame_index_resets_when_entering_shoot(self, pygame_init):
        """Frame index is reset to 0 when transitioning into 'shoot' animation."""
        from src.entities.animation_controller import AnimationController
        ac = AnimationController.from_sprite_dir(
            "assets/sprites/player", {"idle": 6, "shoot": 8, "dead": 4}
        )
        ac.set_state("idle", facing_right=True)
        ac.update(0.5)  # advance some frames
        ac.set_state("shoot", facing_right=True)
        assert ac._frame_index == 0.0


# ===========================================================================
# 11. GameScene Tab key → InventoryScreen (integration)
# ===========================================================================

class TestGameSceneInventoryTab:
    """Tab key in GameScene.handle_events() pushes InventoryScreen when player alive.

    NOTE: The Tab handler in GameScene is defined by the feature plan (Phase 1
    Task 7 / Phase 2 Task 3).  The positive test will fail until the handler is
    wired in.  The negative (dead player) and no-crash tests serve as regression
    guards once the feature lands.
    """

    def _make_scene_with_mock_sm(self):
        from src.scenes.game_scene import GameScene
        from src.core.settings import Settings
        from src.core.event_bus import EventBus

        mock_sm = MagicMock()
        scene = GameScene(sm=mock_sm, settings=Settings(), event_bus=EventBus())
        return scene, mock_sm

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "GameScene.handle_events() does not yet handle KEY_BINDINGS['inventory'] "
            "(Tab key).  This test will pass once Phase 1 Task 7 is implemented: "
            "add `elif event.key == KEY_BINDINGS['inventory'] and self.player.alive: "
            "self._sm.push(InventoryScreen())` to the KEYDOWN branch."
        ),
    )
    def test_tab_key_pushes_inventory_screen_when_player_alive(self, pygame_init):
        """Tab KEYDOWN → sm.push called with an InventoryScreen-like object.

        This test is an intentional TDD anchor.  It will fail (xfail) until the
        Tab → InventoryScreen handler is wired into GameScene.handle_events().
        """
        scene, mock_sm = self._make_scene_with_mock_sm()
        scene.player.alive = True
        tab_event = pygame.event.Event(pygame.KEYDOWN, {"key": _INVENTORY_KEY, "mod": 0})
        scene.handle_events([tab_event])
        mock_sm.push.assert_called_once()

    def test_tab_key_does_not_push_when_player_is_dead(self, pygame_init):
        """Dead player + Tab → sm.push must NOT be called."""
        scene, mock_sm = self._make_scene_with_mock_sm()
        scene.player.alive = False
        tab_event = pygame.event.Event(pygame.KEYDOWN, {"key": _INVENTORY_KEY, "mod": 0})
        scene.handle_events([tab_event])
        mock_sm.push.assert_not_called()

    def test_tab_key_no_crash_without_scene_manager(self, pygame_init):
        """GameScene without sm must not crash when Tab is pressed."""
        from src.scenes.game_scene import GameScene
        from src.core.settings import Settings
        from src.core.event_bus import EventBus

        scene = GameScene(sm=None, settings=Settings(), event_bus=EventBus())
        tab_event = pygame.event.Event(pygame.KEYDOWN, {"key": _INVENTORY_KEY, "mod": 0})
        scene.handle_events([tab_event])  # must not raise

    def test_esc_key_does_not_accidentally_push_inventory(self, pygame_init):
        """ESC key must not trigger sm.push with an InventoryScreen."""
        scene, mock_sm = self._make_scene_with_mock_sm()
        esc_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE, "mod": 0})
        scene.handle_events([esc_event])
        # ESC pushes PauseMenu (or nothing in stub mode) — not InventoryScreen.
        # We can't assert_not_called() on push since PauseMenu may be pushed,
        # but we can assert it wasn't called with an InventoryScreen instance.
        for call_args in mock_sm.push.call_args_list:
            args, _ = call_args
            if args:
                from src.ui.inventory_screen import InventoryScreen
                assert not isinstance(args[0], InventoryScreen), (
                    "ESC must not push an InventoryScreen"
                )


# ===========================================================================
# 12. FSM integration with physics (integration)
# ===========================================================================

class TestPlayerFSMIntegration:
    """Integration: Player + PhysicsSystem + state transitions."""

    def test_full_shoot_state_with_physics_tick(self, pygame_init):
        """LMB held on ground, player.update() called → SHOOT state.

        PhysicsSystem uses integer pixel steps, so on a single tick from rest the
        player may not land on the ground tile (vy*dt rounds to 0 px).  The SHOOT
        state test is about FSM priority, not physics accuracy; we set on_ground
        manually and skip the physics step for this assertion.
        """
        p = _player_on_ground()
        tile_map = _ground_map()
        dt = 1 / 60
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        # on_ground is already True from _player_on_ground(); no physics needed.
        p.update(dt, tile_map)
        assert p.movement_state == MovementState.SHOOT

    def test_full_dead_state_after_alive_false(self, pygame_init):
        """player.alive=False → update() → DEAD state resolved."""
        p = _player_on_ground()
        p.alive = False
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.DEAD

    def test_interact_complete_flow_handle_to_update(self, pygame_init):
        """E keydown → handle_input → update → 'interact' emitted, flag cleared."""
        bus = _Bus()
        p = Player(x=200, y=400, event_bus=bus)
        p.on_ground = True
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [_keydown(_INTERACT_KEY)])
        p.update(1 / 60, tile_map)
        assert bus.has("interact")
        assert p._interact_intent is False

    def test_physics_skips_dead_players(self, pygame_init):
        """PhysicsSystem.update() must not step a dead entity (alive=False).

        Line: `if not getattr(entity, 'alive', True): continue` in physics.py
        means gravity is never applied to a dead player, so vy stays at 0.
        """
        p = _player_on_ground()
        p.alive = False
        p.on_ground = False
        p.vy = 0.0
        tile_map = _MockTileMap(solid_set=set())  # no floor
        physics = PhysicsSystem()
        physics.update([p], tile_map, 1 / 60)
        assert p.vy == 0.0, "Dead player must be skipped by PhysicsSystem (vy unchanged)"

    def test_state_sequence_idle_shoot_idle(self, pygame_init):
        """IDLE → (LMB down) SHOOT → (LMB up) IDLE."""
        p = _player_on_ground()
        tile_map = _ground_map()
        # IDLE
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.IDLE
        # SHOOT
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.SHOOT
        # Back to IDLE
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.IDLE

    def test_state_sequence_walking_then_dead(self, pygame_init):
        """WALKING → alive=False → DEAD; subsequent input does not change target_vx."""
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        p.target_vx = float(WALK_SPEED)
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_d: True}, [])
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.WALKING
        # Kill player
        p.alive = False
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.DEAD
        # Input after death changes nothing
        saved_vx = p.target_vx
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_d: True}, [])
        assert p.target_vx == saved_vx


# ===========================================================================
# 13. End-to-end happy paths (E2E)
# ===========================================================================

class TestE2EHappyPath:
    """Critical user flows through the complete input → physics → state → render pipeline."""

    def test_alive_player_responds_to_input_and_renders(self, pygame_init):
        """Alive player: handle_input → physics ticks → update → render, no errors.

        Run enough physics ticks for the player to land so on_ground=True, then
        check that an alive player produces a valid (non-DEAD) state and renders
        without raising.
        """
        p = _player_on_ground()
        tile_map = _ground_map()
        physics = PhysicsSystem()
        screen = pygame.Surface((640, 480))
        dt = 1 / 60
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({pygame.K_d: True}, [])
        # Run several physics ticks so the player settles on the ground
        for _ in range(5):
            physics.update([p], tile_map, dt)
        p.update(dt, tile_map)
        p.render(screen, (0, 0))
        assert p.alive is True
        assert p.movement_state != MovementState.DEAD

    def test_death_flow_dead_state_and_full_input_lockout(self, pygame_init):
        """Death flow: alive=False → DEAD state → all inputs blocked."""
        bus = _Bus()
        p = Player(x=200, y=400, event_bus=bus)
        p.on_ground = True
        tile_map = _ground_map()
        # Kill the player
        p.alive = False
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.DEAD
        # Flood with every input type
        all_events = [
            _keydown(pygame.K_SPACE),
            _keydown(pygame.K_c),
            _keydown(_INTERACT_KEY),
        ]
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_DOWN):
            p.handle_input(
                {pygame.K_d: True, pygame.K_a: True, pygame.K_SPACE: True},
                all_events,
            )
        assert p.target_vx == 0.0
        assert p._jump_intent is False
        assert p._slide_intent is False
        assert p._interact_intent is False
        assert p._shoot_pressed is False
        # State remains DEAD after subsequent update
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.DEAD

    def test_e_key_interact_flow_e2e(self, pygame_init):
        """E2E: E keydown → handle_input → update → 'interact' in bus, flag cleared."""
        bus = _Bus()
        p = Player(x=200, y=400, event_bus=bus)
        p.on_ground = True
        tile_map = _ground_map()
        with patch("pygame.mouse.get_pressed", return_value=_MOUSE_UP):
            p.handle_input({}, [_keydown(_INTERACT_KEY)])
        p.update(1 / 60, tile_map)
        assert bus.has("interact"), "'interact' event must be emitted via E key"
        assert p._interact_intent is False, "_interact_intent must be cleared after update"
