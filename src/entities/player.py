"""Player entity — input intent, state machine, hitbox management, animation."""
from __future__ import annotations

from enum import Enum, auto
from typing import List, Optional

import pygame

from src.constants import (
    WALK_SPEED, SPRINT_SPEED, CROUCH_SPEED,
    JUMP_VEL, SLIDE_VEL, SLIDE_DURATION,
    NORMAL_HEIGHT, CROUCH_HEIGHT,
    KEY_BINDINGS,
)
from src.entities.entity import Entity
from src.entities.animation_controller import AnimationController


class MovementState(Enum):
    IDLE        = auto()
    WALKING     = auto()
    SPRINTING   = auto()
    CROUCHING   = auto()
    CROUCH_WALK = auto()
    SLIDING     = auto()
    JUMPING     = auto()
    FALLING     = auto()


# Map MovementState → animation key and FPS
_STATE_ANIM: dict[MovementState, tuple[str, int]] = {
    MovementState.IDLE:        ("idle",        6),
    MovementState.WALKING:     ("walk",        10),
    MovementState.SPRINTING:   ("sprint",      14),
    MovementState.CROUCHING:   ("crouch",      6),
    MovementState.CROUCH_WALK: ("crouch_walk", 8),
    MovementState.SLIDING:     ("slide",       12),
    MovementState.JUMPING:     ("jump",        4),
    MovementState.FALLING:     ("fall",        4),
}

_FOOTSTEP_INTERVAL_WALK   = 0.30   # seconds between footstep events while walking
_FOOTSTEP_INTERVAL_SPRINT  = 0.18  # seconds between footstep events while sprinting
_MIN_FOOTSTEP_VX           = 10.0  # |vx| must exceed this to emit footsteps


class Player(Entity):
    """Playable character.

    Parameters
    ----------
    x, y:
        Initial world-space position (top-left of rect).
    event_bus:
        Optional EventBus instance.  Player emits ``"footstep"``,
        ``"player_landed"``, and ``"player_slide"`` events.
    """

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        event_bus=None,
    ) -> None:
        super().__init__(x, y, w=28, h=NORMAL_HEIGHT)

        # Physics state (written by PhysicsSystem)
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.on_ground: bool = False

        # Intent flags (written by handle_input, consumed by update / PhysicsSystem)
        self.target_vx: float = 0.0
        self._jump_intent: bool = False
        self._slide_intent: bool = False

        # Slide state
        self.slide_timer: float = 0.0
        self.slide_dir: int = 1        # +1 right, -1 left

        # Crouch state
        self._crouching: bool = False
        self._force_crouched: bool = False  # True when ceiling prevents uncrouch
        self._sprinting: bool = False

        # Movement state machine
        self.movement_state: MovementState = MovementState.IDLE
        self._on_ground_last_frame: bool = False

        # Footstep timer
        self._footstep_timer: float = 0.0

        # EventBus (optional)
        self._event_bus = event_bus

        # Animation controller (falls back to solid-colour surfaces if no assets)
        state_fps_map = {anim: fps for anim, fps in _STATE_ANIM.values()}
        self.animation_controller = AnimationController.from_sprite_dir(
            "assets/sprites/player", state_fps_map
        )

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_input(self, keys: dict, events: List[pygame.event.Event]) -> None:
        """Translate raw key state + event list into intent flags.

        Modifies ``target_vx``, ``_jump_intent``, and ``_slide_intent``.
        Does NOT write ``vx`` or ``vy`` directly.
        """
        bindings = KEY_BINDINGS if KEY_BINDINGS else {
            "move_left": pygame.K_a, "move_right": pygame.K_d,
            "jump": pygame.K_SPACE, "crouch": pygame.K_LCTRL,
            "slide": pygame.K_c,    "sprint": pygame.K_LSHIFT,
        }

        left  = keys.get(bindings.get("move_left",  pygame.K_a), False)
        right = keys.get(bindings.get("move_right", pygame.K_d), False)
        self._sprinting = keys.get(bindings.get("sprint", pygame.K_LSHIFT), False)
        self._crouching = keys.get(bindings.get("crouch", pygame.K_LCTRL),  False)

        if self._crouching or self._force_crouched:
            speed = CROUCH_SPEED
        elif self._sprinting:
            speed = SPRINT_SPEED
        else:
            speed = WALK_SPEED

        if right and not left:
            self.target_vx = speed
            self.slide_dir = 1
        elif left and not right:
            self.target_vx = -speed
            self.slide_dir = -1
        else:
            self.target_vx = 0.0

        for event in events:
            if event.type == pygame.KEYDOWN:
                jump_key  = bindings.get("jump",  pygame.K_SPACE)
                slide_key = bindings.get("slide", pygame.K_c)

                if event.key == jump_key and self.on_ground:
                    self._jump_intent = True

                if (
                    event.key == slide_key
                    and self.on_ground
                    and abs(self.vx) > 50
                    and self.slide_timer <= 0
                ):
                    self._slide_intent = True

    # ------------------------------------------------------------------
    # Per-frame update (state machine + hitbox + animation)
    # ------------------------------------------------------------------

    def update(self, dt: float, tile_map=None) -> None:  # type: ignore[override]
        """Advance slide timer, manage hitbox, resolve MovementState, sync animation."""

        # --- Slide timer countdown ---
        if self.slide_timer > 0:
            self.slide_timer -= dt
            if self.slide_timer <= 0:
                self.slide_timer = 0.0
                # Remain crouched only if Ctrl is held; otherwise stand
                if not (self._crouching or self._force_crouched):
                    self.uncrouch(tile_map)

        # --- Crouch enter / exit ---
        currently_crouched = self.rect.height == CROUCH_HEIGHT
        wants_crouch = self._crouching or self._force_crouched or self.slide_timer > 0

        if wants_crouch and not currently_crouched:
            self.crouch(tile_map)
        elif not wants_crouch and currently_crouched:
            self.uncrouch(tile_map)

        # --- Apply jump intent ---
        if self._jump_intent and self.on_ground:
            self.vy = JUMP_VEL
            self.on_ground = False
            self._jump_intent = False

        # --- Apply slide intent ---
        if self._slide_intent:
            self.vx = float(SLIDE_VEL * self.slide_dir)
            self.slide_timer = SLIDE_DURATION
            if self.rect.height != CROUCH_HEIGHT:
                self.crouch(tile_map)
            self._slide_intent = False
            if self._event_bus is not None:
                self._event_bus.emit("player_slide")

        # --- Emit player_landed on rising edge of on_ground ---
        if self.on_ground and not self._on_ground_last_frame:
            if self._event_bus is not None:
                self._event_bus.emit("player_landed")
        self._on_ground_last_frame = self.on_ground

        # --- Footstep events ---
        if self.on_ground and abs(self.vx) > _MIN_FOOTSTEP_VX:
            interval = (
                _FOOTSTEP_INTERVAL_SPRINT
                if self.movement_state == MovementState.SPRINTING
                else _FOOTSTEP_INTERVAL_WALK
            )
            self._footstep_timer -= dt
            if self._footstep_timer <= 0:
                self._footstep_timer = interval
                if self._event_bus is not None:
                    self._event_bus.emit("footstep")
        else:
            self._footstep_timer = 0.0

        # --- Resolve MovementState ---
        self.movement_state = self._resolve_state()

        # --- Sync animation controller ---
        anim_key, _ = _STATE_ANIM[self.movement_state]
        facing_right = self.slide_dir >= 0
        if self.animation_controller is not None:
            self.animation_controller.set_state(anim_key, facing_right=facing_right)
            self.animation_controller.update(dt)

    def _resolve_state(self) -> MovementState:
        if self.slide_timer > 0:
            return MovementState.SLIDING
        crouched = self.rect.height == CROUCH_HEIGHT
        if not self.on_ground:
            return MovementState.JUMPING if self.vy < 0 else MovementState.FALLING
        if crouched:
            return MovementState.CROUCH_WALK if abs(self.vx) > 1 else MovementState.CROUCHING
        if abs(self.vx) < 1:
            return MovementState.IDLE
        if abs(self.vx) >= SPRINT_SPEED * 0.9:
            return MovementState.SPRINTING
        return MovementState.WALKING

    # ------------------------------------------------------------------
    # Hitbox helpers
    # ------------------------------------------------------------------

    def crouch(self, tile_map=None) -> None:
        """Shrink hitbox to CROUCH_HEIGHT, keeping rect.bottom fixed."""
        if self.rect.height == CROUCH_HEIGHT:
            return
        delta = self.rect.height - CROUCH_HEIGHT
        self.rect.height = CROUCH_HEIGHT
        self.rect.y += delta   # shift top down so bottom stays fixed
        self._crouching = True
        self.movement_state = MovementState.CROUCHING

    def start_slide(self) -> None:
        """Begin a slide: apply burst velocity, set timer, shrink hitbox."""
        self.vx = float(SLIDE_VEL * self.slide_dir)
        self.slide_timer = SLIDE_DURATION
        if self.rect.height != CROUCH_HEIGHT:
            self.crouch()

    def uncrouch(self, tile_map=None) -> None:
        """Attempt to restore NORMAL_HEIGHT; blocked by ceiling tiles."""
        if self.rect.height == NORMAL_HEIGHT:
            self._force_crouched = False
            return

        # Ceiling check: would the restored rect collide with solid tiles?
        if tile_map is not None:
            delta = NORMAL_HEIGHT - CROUCH_HEIGHT
            test_top = self.rect.y - delta
            # Sample tiles in the vertical band [test_top, rect.top]
            from src.constants import TILE_SIZE
            left_col  = self.rect.left  // TILE_SIZE
            right_col = (self.rect.right - 1) // TILE_SIZE
            top_row   = test_top // TILE_SIZE
            for col in range(left_col, right_col + 1):
                if tile_map.is_solid(col, top_row):
                    self._force_crouched = True
                    return

        # Clear — restore height
        delta = NORMAL_HEIGHT - CROUCH_HEIGHT
        self.rect.y -= delta
        self.rect.height = NORMAL_HEIGHT
        self._force_crouched = False

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, screen: pygame.Surface, camera_offset) -> None:  # type: ignore[override]
        super().render(screen, camera_offset)
