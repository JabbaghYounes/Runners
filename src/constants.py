"""
Game-wide constants for Runners.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
SCREEN_W: int = 1280
SCREEN_H: int = 720
DEFAULT_WIDTH: int = 1280
DEFAULT_HEIGHT: int = 720
DEFAULT_FPS: int = 60
FPS: int = 60
FIXED_TIMESTEP: float = 1 / 60
MAX_FRAME_TIME: float = 0.25

# ---------------------------------------------------------------------------
# Physics / movement
# ---------------------------------------------------------------------------
GRAVITY: float = 980.0
ACCEL: float = 1200.0
DECEL: float = 1500.0
WALK_SPEED: float = 180.0
SPRINT_SPEED: float = 300.0
PLAYER_SPEED: float = 200.0
JUMP_VEL: float = -550.0
PLAYER_JUMP_VEL: float = -500.0
CROUCH_SPEED: float = 90.0
SLIDE_VEL: float = 400.0
SLIDE_DECEL: float = 600.0
SLIDE_DURATION: float = 0.38

# ---------------------------------------------------------------------------
# Entity sizes
# ---------------------------------------------------------------------------
TILE_SIZE: int = 32
NORMAL_HEIGHT: int = 48
CROUCH_HEIGHT: int = 24

# ---------------------------------------------------------------------------
# Rendering layers
# ---------------------------------------------------------------------------
LAYER_TILES: int = 0
LAYER_LOOT: int = 1
LAYER_ENEMIES: int = 2
LAYER_PLAYER: int = 3
LAYER_PROJECTILES: int = 4
LAYER_HUD: int = 5

# ---------------------------------------------------------------------------
# Colours (RGB)
# ---------------------------------------------------------------------------
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
NEON_GREEN = (57, 255, 20)
NEON_CYAN = (0, 255, 255)
NEON_ORANGE = (255, 165, 0)
NEON_RED = (255, 50, 50)
ACCENT_GREEN = (57, 255, 20)
ACCENT_CYAN = (0, 255, 255)
ACCENT_ORANGE = (255, 165, 0)
ACCENT_RED = (255, 50, 50)
ACCENT_MAGENTA = (255, 0, 180)
HEALTH_COLOR = (80, 255, 80)
ARMOR_COLOR = (80, 160, 255)
XP_COLOR = (160, 80, 255)
BG_DEEP = (13, 17, 23)
BG_MID = (15, 22, 38)
DARK_BG = (13, 17, 23)
PANEL_BG = (22, 27, 34)
BORDER_BRIGHT = (80, 120, 160)
BORDER_DIM = (40, 60, 80)
TEXT_PRIMARY = (220, 230, 240)
TEXT_SECONDARY = (100, 110, 120)
TEXT_BRIGHT = (220, 230, 240)
TEXT_DIM = (100, 110, 120)
RARITY_COLORS = {
    "common": (180, 180, 180),
    "uncommon": (30, 200, 30),
    "rare": (30, 80, 220),
    "epic": (128, 0, 220),
    "legendary": (255, 165, 0),
}

# ---------------------------------------------------------------------------
# Gameplay
# ---------------------------------------------------------------------------
ROUND_DURATION_SECS: int = 900
PICKUP_RADIUS: int = 48

# ---------------------------------------------------------------------------
# Default key bindings (pygame key constants as ints)
# ---------------------------------------------------------------------------
DEFAULT_KEYS: dict = {
    "move_left": 97,
    "move_right": 100,
    "jump": 32,
    "crouch": 115,
    "reload": 114,
    "interact": 101,
    "inventory": 9,
    "map": 109,
    "pause": 27,
}
KEY_BINDINGS: dict = DEFAULT_KEYS

# ---------------------------------------------------------------------------
# PvP mechanics
# ---------------------------------------------------------------------------
PVP_KILL_XP: int = 150
PVP_AGENT_COUNT: int = 3
PVP_FRIENDLY_FIRE: bool = True
PVP_AGENT_AGGRO_RANGE: float = 300.0
PVP_AGENT_SHOOT_RANGE: float = 150.0
