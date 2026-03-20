"""Player entity — input intent, state machine, hitbox, health, buffs, stats."""
from __future__ import annotations

from enum import Enum, auto
from typing import List, Optional, TYPE_CHECKING

import pygame

from src.constants import (
    WALK_SPEED, SPRINT_SPEED, CROUCH_SPEED,
    JUMP_VEL, SLIDE_VEL, SLIDE_DURATION,
    NORMAL_HEIGHT, CROUCH_HEIGHT,
    KEY_BINDINGS, PLAYER_MAX_HEALTH,
)
from src.entities.entity import Entity

if TYPE_CHECKING:
    from src.inventory.inventory import Inventory
    from src.systems.buff_system import ActiveBuff, BuffSystem


class MovementState(Enum):
    IDLE        = auto()
    WALKING     = auto()
    SPRINTING   = auto()
    CROUCHING   = auto()
    CROUCH_WALK = auto()
    SLIDING     = auto()
    JUMPING     = auto()
    FALLING     = auto()
    SHOOT       = auto()
    DEAD        = auto()


# Map MovementState -> animation key and FPS
_STATE_ANIM: dict[MovementState, tuple[str, int]] = {
    MovementState.IDLE:        ("idle",        6),
    MovementState.WALKING:     ("walk",        10),
    MovementState.SPRINTING:   ("sprint",      14),
    MovementState.CROUCHING:   ("crouch",      6),
    MovementState.CROUCH_WALK: ("crouch_walk", 8),
    MovementState.SLIDING:     ("slide",       12),
    MovementState.JUMPING:     ("jump",        4),
    MovementState.FALLING:     ("fall",        4),
    MovementState.SHOOT:       ("shoot",       8),
    MovementState.DEAD:        ("dead",        4),
}

_FOOTSTEP_INTERVAL_WALK   = 0.30
_FOOTSTEP_INTERVAL_SPRINT = 0.18
_MIN_FOOTSTEP_VX          = 10.0

# Default per-character base stats (before skill-tree / home-base bonuses).
_BASE_STATS: dict[str, float] = {
    "speed": 200.0,
    "damage": 25.0,
    "armor": 0.0,
}


class Player(Entity):
    """Playable character with movement physics, health, buffs, and inventory.

    Supports two construction modes:
    - Positional:  Player(x, y)              -- used by movement/physics tests
    - Keyword:     Player(max_health=100, buff_system=bs) -- used by consumable tests
    """

    is_player_controlled: bool = True

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        event_bus=None,
        *,
        max_health: int = PLAYER_MAX_HEALTH,
        buff_system: "BuffSystem | None" = None,
        inventory: "Inventory | None" = None,
        width: int = 28,
        height: int | None = None,
    ) -> None:
        h = height if height is not None else NORMAL_HEIGHT
        super().__init__(x, y, w=width, h=h)

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
        self.slide_dir: int = 1

        # Crouch state
        self._crouching: bool = False
        self._force_crouched: bool = False
        self._sprinting: bool = False

        # Movement state machine
        self.movement_state: MovementState = MovementState.IDLE
        self._on_ground_last_frame: bool = False

        # Footstep timer
        self._footstep_timer: float = 0.0

        # EventBus (optional)
        self._event_bus = event_bus

        # Health / armor
        self.max_health: int = max_health
        self.health: int = max_health
        self.base_armor: int = 0
        self.armor: int = 0      # effective armor — recalculated from equipped item
        self.max_armor: int = 100

        # Buff system
        self.active_buffs: list = []
        self._buff_system = buff_system

        # Inventory — defaults to an Inventory object when none is given
        if inventory is not None:
            self.inventory = inventory
        else:
            try:
                from src.inventory.inventory import Inventory
                self.inventory = Inventory()
            except Exception:
                self.inventory = []

        # Shooting / interaction
        self._shoot_pressed: bool = False
        self._interact_intent: bool = False

        # Animation controller (optional -- falls back to solid-colour)
        self.animation_controller = None
        try:
            from src.entities.animation_controller import AnimationController
            state_fps_map = {anim: fps for anim, fps in _STATE_ANIM.values()}
            self.animation_controller = AnimationController.from_sprite_dir(
                "assets/sprites/player", state_fps_map
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Dependency injection
    # ------------------------------------------------------------------

    def set_buff_system(self, buff_system: "BuffSystem") -> None:
        self._buff_system = buff_system

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def heal(self, amount: int) -> int:
        """Restore HP clamped to max_health. Returns actual HP gained."""
        if amount <= 0:
            return 0
        before = self.health
        self.health = min(self.max_health, self.health + amount)
        gained = self.health - before
        if gained > 0:
            from src.core.event_bus import event_bus as _bus
            _bus.emit("player_healed", player=self, amount=gained)
        return gained

    def take_damage(self, amount: int) -> int:
        """Apply *amount* HP of damage directly.

        Armor reduction is performed upstream by :class:`CombatSystem` via
        :meth:`get_effective_armor` before this method is called, so no
        second reduction is applied here.

        Returns:
            The amount of damage applied (≥ 0).
        """
        self.health = max(0, self.health - amount)
        if self.health == 0 and self.alive:
            self.alive = False
            from src.core.event_bus import event_bus as _bus
            _bus.emit("player_killed", victim=self)
        return amount

    # ------------------------------------------------------------------
    # Armor helpers
    # ------------------------------------------------------------------

    def get_effective_armor(self) -> float:
        """Return the player's current effective armor value.

        Called by :class:`CombatSystem` before computing hit damage.
        Returns a ``float`` so subclasses can apply fractional multipliers
        (e.g. Iron Skin at low health).
        """
        return float(self.armor)

    def _recalculate_armor(self) -> None:
        """Recompute ``self.armor`` from the equipped armor item.

        Called automatically whenever :meth:`Inventory.equip_armor` or
        :meth:`Inventory.unequip_armor` fires the ``on_armor_changed`` hook.
        """
        equipped = getattr(self.inventory, 'equipped_armor', None)
        rating = equipped.armor_rating if equipped is not None else 0
        self.armor = self.base_armor + rating

    # ------------------------------------------------------------------
    # Buffs
    # ------------------------------------------------------------------

    def apply_buff(self, buff: "ActiveBuff") -> None:
        if self._buff_system is not None:
            self._buff_system.add_buff(self, buff)
        else:
            self.active_buffs.append(buff)
            from src.core.event_bus import event_bus as _bus
            _bus.emit(
                "buff_applied",
                entity=self,
                buff_type=buff.buff_type,
                value=buff.value,
                duration=buff.duration,
                icon_key=buff.icon_key,
            )

    # ------------------------------------------------------------------
    # Stat access
    # ------------------------------------------------------------------

    def get_stat(self, name: str) -> float:
        base = _BASE_STATS.get(name, 0.0)
        if self._buff_system is not None:
            modifier = self._buff_system.get_modifiers(self, name)
        else:
            modifier = sum(
                b.value for b in self.active_buffs if b.buff_type == name
            )
        return base + modifier

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_input(self, keys, events: List[pygame.event.Event]) -> None:
        # Dead players cannot issue any input.
        if not self.alive:
            return

        # Update shoot intent from mouse state every input frame.
        self._shoot_pressed = bool(pygame.mouse.get_pressed()[0])

        bindings = KEY_BINDINGS if KEY_BINDINGS else {
            "move_left": pygame.K_a, "move_right": pygame.K_d,
            "jump": pygame.K_SPACE, "crouch": pygame.K_LCTRL,
            "slide": pygame.K_c,    "sprint": pygame.K_LSHIFT,
        }

        left  = keys.get(bindings.get("move_left",  pygame.K_a), False) if isinstance(keys, dict) else keys[bindings.get("move_left", pygame.K_a)]
        right = keys.get(bindings.get("move_right", pygame.K_d), False) if isinstance(keys, dict) else keys[bindings.get("move_right", pygame.K_d)]
        self._sprinting = keys.get(bindings.get("sprint", pygame.K_LSHIFT), False) if isinstance(keys, dict) else keys[bindings.get("sprint", pygame.K_LSHIFT)]
        self._crouching = keys.get(bindings.get("crouch", pygame.K_LCTRL),  False) if isinstance(keys, dict) else keys[bindings.get("crouch", pygame.K_LCTRL)]

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
                jump_key     = bindings.get("jump",     pygame.K_SPACE)
                slide_key    = bindings.get("slide",    pygame.K_c)
                interact_key = bindings.get("interact", pygame.K_e)

                # Jump is only allowed on the ground and outside of a slide.
                if event.key == jump_key and self.on_ground and self.slide_timer <= 0:
                    self._jump_intent = True

                if (
                    event.key == slide_key
                    and self.on_ground
                    and abs(self.vx) > 50
                    and self.slide_timer <= 0
                ):
                    self._slide_intent = True

                if event.key == interact_key:
                    self._interact_intent = True

    # ------------------------------------------------------------------
    # Per-frame update (state machine + hitbox + animation)
    # ------------------------------------------------------------------

    def update(self, dt: float, tile_map=None) -> None:  # type: ignore[override]
        # --- Slide timer countdown ---
        if self.slide_timer > 0:
            self.slide_timer -= dt
            if self.slide_timer <= 0:
                self.slide_timer = 0.0
                if not (self._crouching or self._force_crouched):
                    self.uncrouch(tile_map)

        # --- Crouch enter / exit ---
        currently_crouched = self.rect.height == CROUCH_HEIGHT
        wants_crouch = self._crouching or self._force_crouched or self.slide_timer > 0

        if wants_crouch and not currently_crouched:
            self.crouch(tile_map)
        elif not wants_crouch and currently_crouched:
            self.uncrouch(tile_map)

        # --- Apply jump intent (guard: must be on ground and not sliding) ---
        if self._jump_intent and self.on_ground and self.slide_timer <= 0:
            self.vy = JUMP_VEL
            self.on_ground = False
            self._jump_intent = False
        else:
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

        # --- Emit interact event and clear flag ---
        if self._interact_intent:
            if self._event_bus is not None:
                self._event_bus.emit("interact")
            self._interact_intent = False

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
        if self.animation_controller is not None:
            anim_key, _ = _STATE_ANIM[self.movement_state]
            facing_right = self.slide_dir >= 0
            self.animation_controller.set_state(anim_key, facing_right=facing_right)
            self.animation_controller.update(dt)

    def _resolve_state(self) -> MovementState:
        # Highest priority: death overrides every other state.
        if not self.alive:
            return MovementState.DEAD
        if self.slide_timer > 0:
            return MovementState.SLIDING
        crouched = self.rect.height == CROUCH_HEIGHT
        if not self.on_ground:
            return MovementState.JUMPING if self.vy < 0 else MovementState.FALLING
        # Shooting takes priority over idle/walk/sprint but not over slide/air.
        if self._shoot_pressed:
            return MovementState.SHOOT
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
        if self.rect.height == CROUCH_HEIGHT:
            return
        delta = self.rect.height - CROUCH_HEIGHT
        self.rect.height = CROUCH_HEIGHT
        self.rect.y += delta
        self._crouching = True
        self.movement_state = MovementState.CROUCHING

    def start_slide(self) -> None:
        self.vx = float(SLIDE_VEL * self.slide_dir)
        self.slide_timer = SLIDE_DURATION
        if self.rect.height != CROUCH_HEIGHT:
            self.crouch()

    def uncrouch(self, tile_map=None) -> None:
        if self.rect.height == NORMAL_HEIGHT:
            self._force_crouched = False
            return

        if tile_map is not None:
            delta = NORMAL_HEIGHT - CROUCH_HEIGHT
            test_top = self.rect.y - delta
            from src.constants import TILE_SIZE
            left_col  = self.rect.left  // TILE_SIZE
            right_col = (self.rect.right - 1) // TILE_SIZE
            top_row   = test_top // TILE_SIZE
            for col in range(left_col, right_col + 1):
                if tile_map.is_solid(col, top_row):
                    self._force_crouched = True
                    return

        delta = NORMAL_HEIGHT - CROUCH_HEIGHT
        self.rect.y -= delta
        self.rect.height = NORMAL_HEIGHT
        self._force_crouched = False

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def x(self) -> float:
        return float(self.rect.x)

    @x.setter
    def x(self, val: float) -> None:
        self.rect.x = int(val)

    @property
    def y(self) -> float:
        return float(self.rect.y)

    @y.setter
    def y(self, val: float) -> None:
        self.rect.y = int(val)

    @property
    def center(self):
        return (self.rect.centerx, self.rect.centery)

    @property
    def velocity(self):
        return pygame.math.Vector2(self.vx, self.vy)

    @velocity.setter
    def velocity(self, val):
        if isinstance(val, pygame.math.Vector2):
            self.vx = val.x
            self.vy = val.y
        else:
            self.vx = val[0]
            self.vy = val[1]

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, screen: pygame.Surface, camera_offset=(0, 0)) -> None:  # type: ignore[override]
        super().render(screen, camera_offset)
