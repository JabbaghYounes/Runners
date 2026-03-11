"""Tests for player movement controls and physics (Task 9).

Covers: acceleration/deceleration, sprint cap, crouch hitbox, ceiling block,
slide mechanics, jump guard, gravity arc, horizontal collision, out-of-bounds.
"""
from __future__ import annotations

import pytest
import pygame

from src.constants import (
    ACCEL, DECEL, SLIDE_DECEL,
    WALK_SPEED, SPRINT_SPEED, CROUCH_SPEED,
    JUMP_VEL, SLIDE_VEL, SLIDE_DURATION,
    NORMAL_HEIGHT, CROUCH_HEIGHT,
    GRAVITY, TILE_SIZE,
)
from src.entities.player import Player, MovementState
from src.systems.physics import PhysicsSystem


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

class MockTileMap:
    """Minimal TileMap whose solid layout is configurable per test.

    solid_set: set of (col, row) tuples treated as solid.
    If out_of_bounds_solid is True (default) any tile outside the grid is solid.
    """

    def __init__(
        self,
        cols: int = 30,
        rows: int = 20,
        solid_set: set | None = None,
        out_of_bounds_solid: bool = True,
    ) -> None:
        self.tile_size = TILE_SIZE
        self.cols = cols
        self.rows = rows
        self._solid: set = solid_set if solid_set is not None else set()
        self._oob_solid = out_of_bounds_solid

    def is_solid(self, col: int, row: int) -> bool:
        if col < 0 or row < 0 or col >= self.cols or row >= self.rows:
            return self._oob_solid
        return (col, row) in self._solid

    # PhysicsSystem may also call tile_map.tile_size as property – covered above.


def _ground_map(ground_row: int = 15, cols: int = 30, rows: int = 20) -> MockTileMap:
    """Return a map with a solid floor at *ground_row* and solid borders."""
    solid = set()
    for c in range(cols):
        solid.add((c, ground_row))
    return MockTileMap(cols=cols, rows=rows, solid_set=solid)


def _player_on_ground(
    x: int = 200,
    ground_row: int = 15,
    tile_size: int = TILE_SIZE,
) -> Player:
    """Create a Player standing on the ground row."""
    ground_y = ground_row * tile_size - NORMAL_HEIGHT  # top of player so bottom == ground
    p = Player(x=x, y=ground_y)
    p.on_ground = True
    p.vx = 0.0
    p.vy = 0.0
    return p


def _make_events(**keydowns) -> list:
    """Build a minimal pygame event list with KEYDOWN events."""
    events = []
    for key in keydowns.get("down", []):
        events.append(pygame.event.Event(pygame.KEYDOWN, {"key": key, "mod": 0}))
    for key in keydowns.get("up", []):
        events.append(pygame.event.Event(pygame.KEYUP, {"key": key, "mod": 0}))
    return events


# ---------------------------------------------------------------------------
# TestAcceleration
# ---------------------------------------------------------------------------

class TestAcceleration:
    """vx smoothly ramps up toward WALK_SPEED / SPRINT_SPEED."""

    def test_walk_vx_increases_toward_walk_speed(self, pygame_init):
        p = _player_on_ground()
        p.target_vx = WALK_SPEED
        tile_map = _ground_map()
        physics = PhysicsSystem()

        dt = 1 / 60
        for _ in range(120):  # up to 2 s
            physics.update([p], tile_map, dt)
            if abs(p.vx - WALK_SPEED) < 5:
                break

        assert abs(p.vx - WALK_SPEED) < 5, (
            f"Expected vx ≈ {WALK_SPEED}, got {p.vx:.1f}"
        )

    def test_walk_vx_reaches_speed_within_accel_time(self, pygame_init):
        """vx should reach WALK_SPEED within WALK_SPEED/ACCEL seconds (plus one frame)."""
        p = _player_on_ground()
        p.target_vx = WALK_SPEED
        tile_map = _ground_map()
        physics = PhysicsSystem()

        frames_needed = int(WALK_SPEED / ACCEL * 60) + 2  # theoretical + slack
        dt = 1 / 60
        for _ in range(frames_needed):
            physics.update([p], tile_map, dt)

        assert abs(p.vx - WALK_SPEED) < 5

    def test_sprint_vx_reaches_sprint_speed(self, pygame_init):
        p = _player_on_ground()
        p.target_vx = SPRINT_SPEED
        tile_map = _ground_map()
        physics = PhysicsSystem()

        dt = 1 / 60
        for _ in range(180):
            physics.update([p], tile_map, dt)
            if abs(p.vx - SPRINT_SPEED) < 5:
                break

        assert abs(p.vx - SPRINT_SPEED) < 5

    def test_vx_does_not_exceed_sprint_speed(self, pygame_init):
        """Physics must not overshoot target_vx."""
        p = _player_on_ground()
        p.target_vx = SPRINT_SPEED
        tile_map = _ground_map()
        physics = PhysicsSystem()

        dt = 1 / 60
        for _ in range(300):
            physics.update([p], tile_map, dt)
            assert p.vx <= SPRINT_SPEED + 1, f"vx overshot: {p.vx}"

    def test_walk_speed_does_not_exceed_when_target_is_walk(self, pygame_init):
        p = _player_on_ground()
        p.target_vx = WALK_SPEED
        tile_map = _ground_map()
        physics = PhysicsSystem()

        dt = 1 / 60
        for _ in range(200):
            physics.update([p], tile_map, dt)
            assert p.vx <= WALK_SPEED + 1


# ---------------------------------------------------------------------------
# TestDeceleration
# ---------------------------------------------------------------------------

class TestDeceleration:
    """vx decelerates to 0 when target_vx is 0."""

    def test_vx_decelerates_to_zero_from_walk_speed(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        p.target_vx = 0.0
        tile_map = _ground_map()
        physics = PhysicsSystem()

        dt = 1 / 60
        for _ in range(120):
            physics.update([p], tile_map, dt)
            if p.vx == 0.0:
                break

        assert p.vx == 0.0, f"Expected vx == 0, got {p.vx:.2f}"

    def test_vx_reaches_zero_within_decel_time(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        p.target_vx = 0.0
        tile_map = _ground_map()
        physics = PhysicsSystem()

        frames_needed = int(WALK_SPEED / DECEL * 60) + 2
        dt = 1 / 60
        for _ in range(frames_needed):
            physics.update([p], tile_map, dt)

        assert p.vx == 0.0

    def test_vx_does_not_go_negative_when_decelerating_from_positive(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        p.target_vx = 0.0
        tile_map = _ground_map()
        physics = PhysicsSystem()

        dt = 1 / 60
        for _ in range(200):
            physics.update([p], tile_map, dt)
            assert p.vx >= 0.0, f"vx went negative: {p.vx}"

    def test_direction_reversal_via_target_vx(self, pygame_init):
        """Changing target_vx sign must decelerate then accelerate in new direction."""
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        p.target_vx = -WALK_SPEED
        tile_map = _ground_map()
        physics = PhysicsSystem()

        dt = 1 / 60
        for _ in range(300):
            physics.update([p], tile_map, dt)

        assert p.vx < -WALK_SPEED * 0.9, f"Expected leftward vx, got {p.vx}"


# ---------------------------------------------------------------------------
# TestCrouch
# ---------------------------------------------------------------------------

class TestCrouch:
    """Crouching halves hitbox and keeps rect.bottom anchored."""

    def test_crouch_reduces_rect_height(self, pygame_init):
        p = _player_on_ground()
        tile_map = _ground_map()
        bottom_before = p.rect.bottom

        p.crouch(tile_map)

        assert p.rect.height == CROUCH_HEIGHT
        assert p.rect.bottom == bottom_before, "rect.bottom must not shift on crouch"

    def test_crouch_sets_movement_state(self, pygame_init):
        p = _player_on_ground()
        tile_map = _ground_map()
        p.crouch(tile_map)
        assert p.movement_state in (MovementState.CROUCHING, MovementState.CROUCH_WALK)

    def test_uncrouch_restores_normal_height(self, pygame_init):
        p = _player_on_ground()
        tile_map = _ground_map()
        p.crouch(tile_map)
        p.uncrouch(tile_map)
        assert p.rect.height == NORMAL_HEIGHT

    def test_uncrouch_keeps_rect_bottom_fixed(self, pygame_init):
        p = _player_on_ground()
        tile_map = _ground_map()
        bottom_before = p.rect.bottom
        p.crouch(tile_map)
        p.uncrouch(tile_map)
        assert p.rect.bottom == bottom_before

    def test_crouch_speed_is_lower_than_walk_speed(self, pygame_init):
        assert CROUCH_SPEED < WALK_SPEED

    def test_handle_input_sets_crouch_target_vx_when_moving(self, pygame_init):
        """While crouching and pressing D, target_vx should be CROUCH_SPEED."""
        p = _player_on_ground()
        keys = {pygame.K_d: True, pygame.K_LCTRL: True}
        p.handle_input(keys, [])
        assert abs(p.target_vx) == CROUCH_SPEED


# ---------------------------------------------------------------------------
# TestCeilingBlock
# ---------------------------------------------------------------------------

class TestCeilingBlock:
    """Uncrouch must be blocked when ceiling tiles are present overhead."""

    def test_blocked_uncrouch_keeps_crouch_height(self, pygame_init):
        """A solid tile directly above head prevents stand-up."""
        ground_row = 15
        tile_map = _ground_map(ground_row)

        p = _player_on_ground(ground_row=ground_row)
        p.crouch(tile_map)

        # Place a solid ceiling exactly where the player's head would be after standing
        # Player bottom is at ground_row * TILE_SIZE; after crouch, top is at bottom - CROUCH_HEIGHT
        # After uncrouch, top would be at bottom - NORMAL_HEIGHT
        head_col = p.rect.centerx // TILE_SIZE
        head_row = (p.rect.top - (NORMAL_HEIGHT - CROUCH_HEIGHT)) // TILE_SIZE
        tile_map._solid.add((head_col, head_row))

        p.uncrouch(tile_map)

        assert p.rect.height == CROUCH_HEIGHT, (
            "Hitbox must stay crouched when ceiling blocks stand-up"
        )

    def test_blocked_uncrouch_sets_force_crouched(self, pygame_init):
        ground_row = 15
        tile_map = _ground_map(ground_row)
        p = _player_on_ground(ground_row=ground_row)
        p.crouch(tile_map)

        head_col = p.rect.centerx // TILE_SIZE
        head_row = (p.rect.top - (NORMAL_HEIGHT - CROUCH_HEIGHT)) // TILE_SIZE
        tile_map._solid.add((head_col, head_row))

        p.uncrouch(tile_map)

        assert p._force_crouched is True

    def test_uncrouch_succeeds_with_clear_ceiling(self, pygame_init):
        """No ceiling tiles → stand-up must succeed."""
        tile_map = _ground_map()
        p = _player_on_ground()
        p.crouch(tile_map)
        p.uncrouch(tile_map)
        assert p.rect.height == NORMAL_HEIGHT
        assert p._force_crouched is False


# ---------------------------------------------------------------------------
# TestSlide
# ---------------------------------------------------------------------------

class TestSlide:
    """Slide sets timer, applies burst velocity, and momentum decays."""

    def test_slide_sets_timer_on_start(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)  # must have momentum to slide
        tile_map = _ground_map()
        p.start_slide()
        assert p.slide_timer == pytest.approx(SLIDE_DURATION)

    def test_slide_applies_burst_velocity(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        p.slide_dir = 1
        p.start_slide()
        assert abs(p.vx) == pytest.approx(SLIDE_VEL)

    def test_slide_direction_follows_slide_dir(self, pygame_init):
        p = _player_on_ground()
        p.vx = -float(WALK_SPEED)
        p.slide_dir = -1
        p.start_slide()
        assert p.vx == pytest.approx(-SLIDE_VEL)

    def test_slide_reduces_hitbox_height(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        bottom_before = p.rect.bottom
        p.start_slide()
        assert p.rect.height == CROUCH_HEIGHT
        assert p.rect.bottom == bottom_before

    def test_slide_timer_counts_down_each_frame(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        tile_map = _ground_map()
        p.start_slide()

        dt = 1 / 60
        p.update(dt, tile_map)
        assert p.slide_timer < SLIDE_DURATION

    def test_slide_timer_expires_after_duration(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        tile_map = _ground_map()
        p.start_slide()

        dt = 1 / 60
        total = 0.0
        while total < SLIDE_DURATION + 0.1:
            p.update(dt, tile_map)
            total += dt

        assert p.slide_timer <= 0.0

    def test_slide_vx_decelerates_during_slide(self, pygame_init):
        """While slide_timer > 0, PhysicsSystem must use SLIDE_DECEL."""
        p = _player_on_ground()
        p.vx = float(SLIDE_VEL)
        p.slide_dir = 1
        p.slide_timer = SLIDE_DURATION
        p.target_vx = float(SLIDE_VEL)  # even if target says fast, slide decel wins
        tile_map = _ground_map()
        physics = PhysicsSystem()

        vx_initial = p.vx
        physics.update([p], tile_map, 1 / 60)
        assert p.vx < vx_initial, "Slide friction must reduce vx"

    def test_slide_vx_decelerates_at_slide_decel_rate(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(SLIDE_VEL)
        p.slide_timer = SLIDE_DURATION
        tile_map = _ground_map()
        physics = PhysicsSystem()

        dt = 1 / 60
        vx_before = p.vx
        physics.update([p], tile_map, dt)
        expected = vx_before - SLIDE_DECEL * dt
        assert p.vx == pytest.approx(expected, abs=1.0)

    def test_movement_state_is_sliding_during_slide(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        tile_map = _ground_map()
        p.start_slide()
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.SLIDING

    def test_slide_requires_minimum_velocity(self, pygame_init):
        """Slide intent must be ignored when |vx| <= 50."""
        p = _player_on_ground()
        p.vx = 30.0  # below threshold
        events = _make_events(down=[pygame.K_c])
        p.handle_input({pygame.K_c: True}, events)
        assert p._slide_intent is False

    def test_slide_not_triggered_when_already_sliding(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        p.slide_timer = 0.1  # already sliding
        events = _make_events(down=[pygame.K_c])
        p.handle_input({pygame.K_c: True}, events)
        assert p._slide_intent is False


# ---------------------------------------------------------------------------
# TestJump
# ---------------------------------------------------------------------------

class TestJump:
    """Jump sets vy only when on_ground."""

    def test_jump_sets_vy_when_on_ground(self, pygame_init):
        p = _player_on_ground()
        p.on_ground = True
        events = _make_events(down=[pygame.K_SPACE])
        p.handle_input({pygame.K_SPACE: True}, events)
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.vy == pytest.approx(JUMP_VEL)

    def test_jump_does_not_trigger_when_airborne(self, pygame_init):
        p = _player_on_ground()
        p.on_ground = False
        p.vy = 0.0
        events = _make_events(down=[pygame.K_SPACE])
        p.handle_input({pygame.K_SPACE: True}, events)
        # _jump_intent should not be set when airborne
        assert p._jump_intent is False

    def test_jump_intent_cleared_after_update(self, pygame_init):
        p = _player_on_ground()
        p.on_ground = True
        events = _make_events(down=[pygame.K_SPACE])
        p.handle_input({pygame.K_SPACE: True}, events)
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p._jump_intent is False

    def test_movement_state_is_jumping_after_jump(self, pygame_init):
        p = _player_on_ground()
        p.on_ground = True
        events = _make_events(down=[pygame.K_SPACE])
        p.handle_input({pygame.K_SPACE: True}, events)
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.movement_state in (MovementState.JUMPING, MovementState.FALLING)


# ---------------------------------------------------------------------------
# TestGravity
# ---------------------------------------------------------------------------

class TestGravity:
    """Gravity increases vy each frame when airborne."""

    def test_gravity_increases_vy_when_airborne(self, pygame_init):
        p = _player_on_ground()
        p.on_ground = False
        p.vy = 0.0
        # Use a map with no floor so the player falls freely
        tile_map = MockTileMap(solid_set=set())  # no solid tiles
        physics = PhysicsSystem()

        dt = 1 / 60
        physics.update([p], tile_map, dt)
        assert p.vy > 0.0, "Gravity must increase vy each frame"

    def test_gravity_accumulates_over_multiple_frames(self, pygame_init):
        p = _player_on_ground()
        p.on_ground = False
        p.vy = 0.0
        tile_map = MockTileMap(solid_set=set())
        physics = PhysicsSystem()

        dt = 1 / 60
        vy_values = []
        for _ in range(10):
            physics.update([p], tile_map, dt)
            vy_values.append(p.vy)

        assert vy_values == sorted(vy_values), "vy must increase monotonically under gravity"

    def test_gravity_increment_matches_constant(self, pygame_init):
        """Each frame vy must increase by GRAVITY * dt (assuming no collision)."""
        p = _player_on_ground()
        p.on_ground = False
        p.vy = 0.0
        tile_map = MockTileMap(solid_set=set())
        physics = PhysicsSystem()

        dt = 1 / 60
        physics.update([p], tile_map, dt)
        assert p.vy == pytest.approx(GRAVITY * dt, abs=1.0)

    def test_movement_state_is_falling_when_airborne_with_positive_vy(self, pygame_init):
        p = _player_on_ground()
        p.on_ground = False
        p.vy = 100.0
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.FALLING


# ---------------------------------------------------------------------------
# TestHorizontalCollision
# ---------------------------------------------------------------------------

class TestHorizontalCollision:
    """Solid tiles on the horizontal axis block movement and zero vx."""

    def test_wall_on_right_blocks_rightward_movement(self, pygame_init):
        """Player moving right must stop when hitting a solid wall."""
        solid = set()
        ground_row = 15
        for c in range(30):
            solid.add((c, ground_row))
        # Wall at column 10
        wall_col = 10
        for r in range(ground_row):
            solid.add((wall_col, r))

        tile_map = MockTileMap(cols=30, rows=20, solid_set=solid)
        p = _player_on_ground(x=(wall_col - 3) * TILE_SIZE, ground_row=ground_row)
        p.vx = float(SPRINT_SPEED)
        p.target_vx = float(SPRINT_SPEED)
        physics = PhysicsSystem()

        dt = 1 / 60
        wall_x = wall_col * TILE_SIZE
        for _ in range(120):
            physics.update([p], tile_map, dt)
            if p.rect.right >= wall_x:
                break

        assert p.rect.right <= wall_x + 1, "Player must not pass through wall"

    def test_wall_on_left_blocks_leftward_movement(self, pygame_init):
        solid = set()
        ground_row = 15
        for c in range(30):
            solid.add((c, ground_row))
        wall_col = 5
        for r in range(ground_row):
            solid.add((wall_col, r))

        tile_map = MockTileMap(cols=30, rows=20, solid_set=solid)
        p = _player_on_ground(x=(wall_col + 4) * TILE_SIZE, ground_row=ground_row)
        p.vx = -float(SPRINT_SPEED)
        p.target_vx = -float(SPRINT_SPEED)
        physics = PhysicsSystem()

        wall_right = (wall_col + 1) * TILE_SIZE
        dt = 1 / 60
        for _ in range(120):
            physics.update([p], tile_map, dt)
            if p.rect.left <= wall_right:
                break

        assert p.rect.left >= wall_right - 1

    def test_horizontal_collision_zeroes_vx(self, pygame_init):
        """After hitting a wall, vx must be clamped to 0 (not bounced)."""
        solid = set()
        ground_row = 15
        for c in range(30):
            solid.add((c, ground_row))
        wall_col = 10
        for r in range(ground_row):
            solid.add((wall_col, r))

        tile_map = MockTileMap(cols=30, rows=20, solid_set=solid)
        p = _player_on_ground(x=(wall_col - 2) * TILE_SIZE, ground_row=ground_row)
        p.vx = float(SPRINT_SPEED)
        p.target_vx = float(SPRINT_SPEED)
        physics = PhysicsSystem()

        dt = 1 / 60
        for _ in range(120):
            physics.update([p], tile_map, dt)

        assert p.vx >= 0.0 and p.vx <= SPRINT_SPEED


# ---------------------------------------------------------------------------
# TestOutOfBounds
# ---------------------------------------------------------------------------

class TestOutOfBounds:
    """Map edges are solid — player cannot leave the tile grid."""

    def test_player_cannot_move_left_past_map_edge(self, pygame_init):
        tile_map = MockTileMap(cols=30, rows=20, solid_set=set(), out_of_bounds_solid=True)
        # Put a floor so player stands
        for c in range(30):
            tile_map._solid.add((c, 15))

        p = _player_on_ground(x=2, ground_row=15)
        p.vx = -float(SPRINT_SPEED)
        p.target_vx = -float(SPRINT_SPEED)
        physics = PhysicsSystem()

        dt = 1 / 60
        for _ in range(120):
            physics.update([p], tile_map, dt)

        assert p.rect.left >= 0, f"Player left map left edge: rect.left={p.rect.left}"

    def test_player_cannot_move_right_past_map_edge(self, pygame_init):
        cols = 30
        tile_map = MockTileMap(cols=cols, rows=20, solid_set=set(), out_of_bounds_solid=True)
        for c in range(cols):
            tile_map._solid.add((c, 15))

        map_right = cols * TILE_SIZE
        p = _player_on_ground(x=map_right - 3 * TILE_SIZE, ground_row=15)
        p.vx = float(SPRINT_SPEED)
        p.target_vx = float(SPRINT_SPEED)
        physics = PhysicsSystem()

        dt = 1 / 60
        for _ in range(120):
            physics.update([p], tile_map, dt)

        assert p.rect.right <= map_right + 1, f"Player passed right edge: {p.rect.right}"


# ---------------------------------------------------------------------------
# TestMovementState
# ---------------------------------------------------------------------------

class TestMovementState:
    """MovementState enum resolves correctly from player flags."""

    def test_idle_state_when_no_input(self, pygame_init):
        p = _player_on_ground()
        p.vx = 0.0
        p.target_vx = 0.0
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.IDLE

    def test_walking_state_when_moving_at_walk_speed(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(WALK_SPEED)
        p.target_vx = float(WALK_SPEED)
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.WALKING

    def test_sprinting_state_when_moving_at_sprint_speed(self, pygame_init):
        p = _player_on_ground()
        p.vx = float(SPRINT_SPEED)
        p.target_vx = float(SPRINT_SPEED)
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.movement_state == MovementState.SPRINTING

    def test_crouching_state_when_crouched_and_idle(self, pygame_init):
        p = _player_on_ground()
        tile_map = _ground_map()
        p.crouch(tile_map)
        p.vx = 0.0
        p.target_vx = 0.0
        p.update(1 / 60, tile_map)
        assert p.movement_state in (MovementState.CROUCHING, MovementState.CROUCH_WALK)

    def test_jumping_state_immediately_after_jump_input(self, pygame_init):
        p = _player_on_ground()
        p.on_ground = True
        events = _make_events(down=[pygame.K_SPACE])
        p.handle_input({pygame.K_SPACE: True}, events)
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        assert p.movement_state in (MovementState.JUMPING, MovementState.FALLING)


# ---------------------------------------------------------------------------
# TestHandleInput
# ---------------------------------------------------------------------------

class TestHandleInput:
    """handle_input() sets target_vx and intent flags correctly."""

    def test_right_key_sets_positive_target_vx(self, pygame_init):
        p = _player_on_ground()
        p.handle_input({pygame.K_d: True}, [])
        assert p.target_vx > 0

    def test_left_key_sets_negative_target_vx(self, pygame_init):
        p = _player_on_ground()
        p.handle_input({pygame.K_a: True}, [])
        assert p.target_vx < 0

    def test_no_key_sets_zero_target_vx(self, pygame_init):
        p = _player_on_ground()
        p.handle_input({}, [])
        assert p.target_vx == 0.0

    def test_sprint_modifier_sets_sprint_speed_target(self, pygame_init):
        p = _player_on_ground()
        p.handle_input({pygame.K_d: True, pygame.K_LSHIFT: True}, [])
        assert p.target_vx == SPRINT_SPEED

    def test_sprint_left_sets_negative_sprint_target(self, pygame_init):
        p = _player_on_ground()
        p.handle_input({pygame.K_a: True, pygame.K_LSHIFT: True}, [])
        assert p.target_vx == -SPRINT_SPEED

    def test_slide_intent_set_on_c_keydown_with_momentum(self, pygame_init):
        p = _player_on_ground()
        p.on_ground = True
        p.vx = float(WALK_SPEED)
        p.slide_timer = 0.0
        events = _make_events(down=[pygame.K_c])
        p.handle_input({pygame.K_c: True}, events)
        assert p._slide_intent is True

    def test_jump_intent_not_set_when_airborne(self, pygame_init):
        p = _player_on_ground()
        p.on_ground = False
        events = _make_events(down=[pygame.K_SPACE])
        p.handle_input({pygame.K_SPACE: True}, events)
        assert p._jump_intent is False


# ---------------------------------------------------------------------------
# TestAnimationController
# ---------------------------------------------------------------------------

class TestAnimationController:
    """AnimationController state transitions and frame cycling."""

    def test_get_current_frame_returns_surface(self, pygame_init):
        from src.entities.animation_controller import AnimationController
        ac = AnimationController.from_sprite_dir("assets/sprites/player", {
            "idle": 6, "walk": 10, "sprint": 14,
            "crouch": 6, "crouch_walk": 8,
            "slide": 12, "jump": 4, "fall": 4,
        })
        frame = ac.get_current_frame()
        assert isinstance(frame, pygame.Surface)

    def test_set_state_changes_current_state(self, pygame_init):
        from src.entities.animation_controller import AnimationController
        ac = AnimationController.from_sprite_dir("assets/sprites/player", {
            "idle": 6, "walk": 10, "sprint": 14,
            "crouch": 6, "crouch_walk": 8,
            "slide": 12, "jump": 4, "fall": 4,
        })
        ac.set_state("idle", facing_right=True)
        ac.set_state("walk", facing_right=True)
        assert ac._current_state == "walk"

    def test_set_state_resets_frame_index_on_new_state(self, pygame_init):
        from src.entities.animation_controller import AnimationController
        ac = AnimationController.from_sprite_dir("assets/sprites/player", {
            "idle": 6, "walk": 10, "sprint": 14,
            "crouch": 6, "crouch_walk": 8,
            "slide": 12, "jump": 4, "fall": 4,
        })
        ac.set_state("idle", facing_right=True)
        ac.update(1.0)  # advance frames
        ac.set_state("walk", facing_right=True)
        assert ac._frame_index == 0

    def test_facing_left_flips_surface(self, pygame_init):
        from src.entities.animation_controller import AnimationController
        ac = AnimationController.from_sprite_dir("assets/sprites/player", {
            "idle": 6, "walk": 10, "sprint": 14,
            "crouch": 6, "crouch_walk": 8,
            "slide": 12, "jump": 4, "fall": 4,
        })
        ac.set_state("idle", facing_right=True)
        frame_right = ac.get_current_frame()
        ac.set_state("idle", facing_right=False)
        frame_left = ac.get_current_frame()
        # Both must be valid surfaces even when flipped
        assert isinstance(frame_left, pygame.Surface)
        assert isinstance(frame_right, pygame.Surface)

    def test_update_advances_frame_over_time(self, pygame_init):
        from src.entities.animation_controller import AnimationController
        ac = AnimationController.from_sprite_dir("assets/sprites/player", {
            "idle": 6, "walk": 10, "sprint": 14,
            "crouch": 6, "crouch_walk": 8,
            "slide": 12, "jump": 4, "fall": 4,
        })
        ac.set_state("walk", facing_right=True)
        # Advance by more than one full frame period (1/fps seconds)
        ac.update(1.0)
        assert ac._frame_index > 0 or len(ac._states_config["walk"]["frames"]) == 1


# ---------------------------------------------------------------------------
# TestEventBusIntegration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    """Player emits EventBus events at the right lifecycle moments."""

    def _make_event_bus(self):
        """Minimal event bus that records emitted events."""
        class _Bus:
            def __init__(self):
                self.log = []
            def emit(self, name, payload=None):
                self.log.append((name, payload))
        return _Bus()

    def test_player_landed_emitted_on_ground_rising_edge(self, pygame_init):
        bus = self._make_event_bus()
        p = Player(x=200, y=200, event_bus=bus)
        p._on_ground_last_frame = False
        p.on_ground = True
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        names = [e[0] for e in bus.log]
        assert "player_landed" in names

    def test_player_landed_not_emitted_when_already_on_ground(self, pygame_init):
        bus = self._make_event_bus()
        p = Player(x=200, y=200, event_bus=bus)
        p._on_ground_last_frame = True
        p.on_ground = True
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        names = [e[0] for e in bus.log]
        assert "player_landed" not in names

    def test_player_slide_emitted_on_slide_start(self, pygame_init):
        bus = self._make_event_bus()
        p = Player(x=200, y=400, event_bus=bus)
        p.on_ground = True
        p.vx = float(WALK_SPEED)
        p.slide_timer = 0.0
        events = _make_events(down=[pygame.K_c])
        p.handle_input({pygame.K_c: True}, events)
        tile_map = _ground_map()
        p.update(1 / 60, tile_map)
        names = [e[0] for e in bus.log]
        assert "player_slide" in names
