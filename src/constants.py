import pygame

# ---------------------------------------------------------------------------
# Screen / display
# ---------------------------------------------------------------------------
SCREEN_W = 1280
SCREEN_H = 720
FPS = 60
TILE_SIZE = 32

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BG_DEEP = (8, 12, 20)
BG_MID = (15, 22, 38)
ACCENT_CYAN = (0, 220, 255)
ACCENT_GREEN = (0, 255, 120)
ACCENT_MAGENTA = (255, 0, 180)
ACCENT_ORANGE = (255, 160, 0)
ACCENT_RED = (255, 60, 60)
BORDER_DIM = (40, 60, 80)
BORDER_BRIGHT = (80, 120, 160)
PANEL_BG = (12, 18, 30)
TEXT_BRIGHT = (220, 235, 255)
TEXT_DIM = (100, 130, 160)
HEALTH_COLOR = (80, 255, 80)
ARMOR_COLOR = (80, 160, 255)
XP_COLOR = (160, 80, 255)

# ---------------------------------------------------------------------------
# Physics / movement
# ---------------------------------------------------------------------------
GRAVITY: float = 800.0

WALK_SPEED: int = 180       # px/s
SPRINT_SPEED: int = 300     # px/s
CROUCH_SPEED: int = 90      # px/s while crouching
JUMP_VEL: int = -550        # px/s (negative = upward)
SLIDE_VEL: int = 400        # initial slide burst px/s

# Smooth acceleration / deceleration rates (px/s²)
ACCEL: int = 1200
DECEL: int = 1500
SLIDE_DECEL: int = 600      # friction while sliding

# Timing
SLIDE_DURATION: float = 0.38    # seconds

# Hitbox heights
NORMAL_HEIGHT: int = 48
CROUCH_HEIGHT: int = 24

# ---------------------------------------------------------------------------
# Key bindings (populated after pygame.init() by _init_key_bindings())
# ---------------------------------------------------------------------------
KEY_BINDINGS: dict = {}


def _init_key_bindings() -> None:
    """Populate KEY_BINDINGS with pygame key constants.

    Must be called after ``pygame.init()`` so that key constants are valid.
    """
    KEY_BINDINGS.update(
        {
            "move_left": pygame.K_a,
            "move_right": pygame.K_d,
            "jump": pygame.K_SPACE,
            "crouch": pygame.K_LCTRL,
            "slide": pygame.K_c,
            "sprint": pygame.K_LSHIFT,
            "interact": pygame.K_e,
            "map": pygame.K_m,
            "inventory": pygame.K_TAB,
            "pause": pygame.K_ESCAPE,
            "shoot": 1,  # left mouse button
        }
    )
