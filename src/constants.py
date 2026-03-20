"""Compile-time constants.

These values are baked in at import time and never read from settings.json.
Runtime user preferences (volume, resolution overrides, key bindings) live in
src/core/settings.py and are loaded from settings.json.
"""

import enum

import pygame  # pygame constants are plain integers — safe to import before init()


# ── Faction enum ───────────────────────────────────────────────────────────────
class Faction(enum.Enum):
    """Combat faction tag — used by CombatSystem to route projectile damage."""
    PLAYER = "player"
    ENEMY = "enemy"

# ── Display ───────────────────────────────────────────────────────────────────
DEFAULT_WIDTH  = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS    = 60

# Fixed-timestep constants
FIXED_TIMESTEP = 1.0 / DEFAULT_FPS  # seconds per physics/logic tick  (~16.67 ms)
MAX_FRAME_TIME = 0.25               # spiral-of-death cap: ignore time past 250 ms

# ── Tile grid ─────────────────────────────────────────────────────────────────
TILE_SIZE = 32  # pixels

# ── Physics ───────────────────────────────────────────────────────────────────
GRAVITY         =  980.0   # px/s²  (downward)
PLAYER_SPEED    =  200.0   # px/s   horizontal walk speed
PLAYER_JUMP_VEL = -500.0   # px/s   upward velocity on jump (negative = up)

# ── Round ─────────────────────────────────────────────────────────────────────
ROUND_DURATION_SECS = 15 * 60  # 15-minute extraction window

# ── Render layers (Z-order) ───────────────────────────────────────────────────
LAYER_TILES       = 0
LAYER_LOOT        = 1
LAYER_ENEMIES     = 2
LAYER_PLAYER      = 3
LAYER_PROJECTILES = 4
LAYER_HUD         = 5

# ── Colour palette — neon retro theme ─────────────────────────────────────────
BLACK        = (  0,   0,   0)
WHITE        = (255, 255, 255)
DARK_BG      = ( 13,  17,  23)   # #0D1117  deep background
PANEL_BG     = ( 22,  27,  34)   # #16181A  panel / card surface
NEON_CYAN    = (  0, 255, 255)   # primary accent
NEON_GREEN   = ( 57, 255,  20)   # selection / active highlight
NEON_ORANGE  = (255, 165,   0)   # warning / timer
NEON_RED     = (255,  50,  50)   # damage / danger
TEXT_PRIMARY = (220, 230, 240)   # readable body text
TEXT_DIM     = (100, 110, 120)   # disabled / secondary text

# ── Rarity colours ────────────────────────────────────────────────────────────
RARITY_COLORS: dict[str, tuple[int, int, int]] = {
    "common":    (180, 180, 180),
    "uncommon":  ( 30, 200,  30),
    "rare":      ( 30,  80, 220),
    "epic":      (128,   0, 220),
    "legendary": (255, 165,   0),
}

# ── Short-form aliases ────────────────────────────────────────────────────────
# Every scene, system, and UI module should use these names.  The verbose
# canonical names above document intent; these keep call-site code concise.

SCREEN_W = DEFAULT_WIDTH
SCREEN_H = DEFAULT_HEIGHT
FPS      = DEFAULT_FPS

BG_DEEP        = DARK_BG
BG_MID         = ( 15,  22,  38)    # slightly lighter mid-tone for layering
BG_PANEL       = ( 20,  24,  38)    # #141826 -- panel fill

ACCENT_CYAN    = NEON_CYAN
ACCENT_GREEN   = NEON_GREEN
ACCENT_ORANGE  = NEON_ORANGE
ACCENT_RED     = NEON_RED
ACCENT_MAGENTA = (255,   0, 180)    # secondary accent / special alerts
DANGER_RED     = (255,  32,  64)    # #FF2040 -- danger, critical health

BORDER_DIM     = ( 40,  60,  80)
BORDER_BRIGHT  = ( 80, 120, 160)

TEXT_BRIGHT    = TEXT_PRIMARY
TEXT_SECONDARY = TEXT_DIM

HEALTH_COLOR = ( 80, 255,  80)
ARMOR_COLOR  = ( 80, 160, 255)
XP_COLOR     = (160,  80, 255)

# ── Player stats ──────────────────────────────────────────────────────────────
PLAYER_MAX_HEALTH: int = 100   # default HP for a new player

# ── Extended physics constants ────────────────────────────────────────────────
WALK_SPEED     = 180.0
SPRINT_SPEED   = 300.0
CROUCH_SPEED   =  90.0
JUMP_VEL       = -550.0   # px/s upward (negative = up)
SLIDE_VEL      =  400.0
ACCEL          = 1200.0   # px/s² acceleration toward target_vx
DECEL          = 1500.0   # px/s² deceleration when no directional input
SLIDE_DECEL    =  600.0
SLIDE_DURATION =    0.38  # seconds a slide lasts

NORMAL_HEIGHT = 48   # pixels — standing player hitbox height
CROUCH_HEIGHT = 24   # pixels — crouching / sliding hitbox height

PICKUP_RADIUS = 48   # pixels — loot interaction distance

# ── XP constants ──────────────────────────────────────────────────────────
EXTRACTION_XP: int = 200

# ── Weapon defaults ──────────────────────────────────────────────────────
PROJECTILE_SPEED   = 600.0   # px/s — default bullet speed
PROJECTILE_TTL     = 2.0     # seconds — default bullet lifetime

# Default weapon stats (used when no weapon is equipped)
DEFAULT_WEAPON_STATS: dict[str, float] = {
    "fire_rate": 5.0,          # rounds per second
    "damage": 15.0,            # HP per hit
    "magazine_size": 12.0,     # rounds before reload
    "reload_time": 1.5,        # seconds to reload
    "projectile_speed": 600.0, # px/s
}

# Crosshair rendering
CROSSHAIR_SIZE   = 16   # pixels — half-length of each crosshair line
CROSSHAIR_GAP    =  4   # pixels — gap around the centre dot
CROSSHAIR_COLOR  = NEON_CYAN

# ── PvP constants ──────────────────────────────────────────────────────────
PVP_KILL_XP: int = 150
PVP_AGENT_COUNT: int = 3
PVP_FRIENDLY_FIRE: bool = True
PVP_AGENT_AGGRO_RANGE: float = 300.0
PVP_AGENT_SHOOT_RANGE: float = 150.0
PVP_AGENT_PATROL_SPEED: float = 60.0    # px/s — bot patrol speed
PVP_AGENT_MOVE_SPEED: float = 120.0     # px/s — bot chase speed
PVP_LOOT_DETECT_RANGE: float = 96.0    # px — bot loot pickup detection radius

# ── Extraction constants ──────────────────────────────────────────────────────
KEY_EXTRACT             = pygame.K_f      # hold this key to channel extraction
EXTRACTION_CHANNEL_SECS = 3.0             # seconds to hold still in zone
MOVE_THRESHOLD          = 5.0             # px/s below which player is "stationary"

# ── Extraction zone visuals ───────────────────────────────────────────────────
EXTRACTION_ZONE_COLOR        = (  0, 255, 180)   # teal highlight fill
EXTRACTION_ZONE_ALPHA        = 60                # base fill alpha (0–255)
EXTRACTION_ZONE_BORDER_COLOR = NEON_CYAN         # border colour
EXTRACTION_ZONE_PULSE_SPEED  = 2.0               # pulses per second
EXTRACTION_CHANNEL_BAR_COLOR = NEON_GREEN        # progress bar fill

# ── Default key bindings (fallback when settings.json is missing a binding) ───
# Bindable actions: move_left, move_right, jump, crouch, sprint, slide,
#                  reload, interact, inventory, map, pause
DEFAULT_KEYS: dict[str, int] = {
    "move_left":  pygame.K_a,
    "move_right": pygame.K_d,
    "jump":       pygame.K_SPACE,
    "crouch":     pygame.K_s,
    "sprint":     pygame.K_LSHIFT,
    "slide":      pygame.K_c,
    "reload":     pygame.K_r,
    "interact":   pygame.K_e,
    "inventory":  pygame.K_TAB,
    "map":        pygame.K_m,
    "pause":      pygame.K_ESCAPE,
}

# Active key bindings — populated from Settings at start-up; modules that
# need bindings import this dict.  Falls back to DEFAULT_KEYS values.
KEY_BINDINGS: dict[str, int] = {
    "move_left":  pygame.K_a,
    "move_right": pygame.K_d,
    "jump":       pygame.K_SPACE,
    "crouch":     pygame.K_LCTRL,
    "sprint":     pygame.K_LSHIFT,
    "slide":      pygame.K_c,
    "reload":     pygame.K_r,
    "interact":   pygame.K_e,
    "inventory":  pygame.K_TAB,
    "map":        pygame.K_m,
    "pause":      pygame.K_ESCAPE,
}
