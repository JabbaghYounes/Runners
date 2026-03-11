"""Global constants: color tokens, screen dimensions, FPS, and default key map."""
import pygame

# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------
SCREEN_W = 1280
SCREEN_H = 720
FPS = 60

VERSION = "v0.1.0"

# ---------------------------------------------------------------------------
# Color Palette  (from UX spec)
# ---------------------------------------------------------------------------
BG_DEEP = (10, 14, 26)           # #0A0E1A — screen backgrounds, overlays
BG_PANEL = (20, 24, 38)          # #141826 — panel fill (85% opacity)
ACCENT_CYAN = (0, 245, 255)      # #00F5FF — primary actions, player dot, health
ACCENT_MAGENTA = (255, 0, 128)   # #FF0080 — secondary actions, enemy indicators
ACCENT_AMBER = (255, 184, 0)     # #FFB800 — timer, warnings, currency
ACCENT_GREEN = (57, 255, 20)     # #39FF14 — success, extraction zone, XP
DANGER_RED = (255, 32, 64)       # #FF2040 — danger, critical health, failure
BORDER_DIM = (42, 48, 80)        # #2A3050 — inactive borders
BORDER_GLOW = (0, 245, 255)      # #00F5FF — active / hover borders (same as ACCENT_CYAN)
TEXT_PRIMARY = (255, 255, 255)   # #FFFFFF — headings, values
TEXT_SECONDARY = (154, 163, 192) # #9AA3C0 — labels, descriptions
TEXT_DISABLED = (58, 64, 96)     # #3A4060 — disabled states

# ---------------------------------------------------------------------------
# Rarity colors
# ---------------------------------------------------------------------------
RARITY_COMMON = (170, 170, 170)
RARITY_UNCOMMON = (57, 255, 20)
RARITY_RARE = (0, 165, 255)
RARITY_EPIC = (192, 64, 255)
RARITY_LEGENDARY = (255, 140, 0)

# ---------------------------------------------------------------------------
# Default key bindings (pygame key constants)
# Loaded before pygame.init() may have been called, so we use integer literals
# that match the pygame.K_* values and resolve them lazily via a dict.
# ---------------------------------------------------------------------------
KEY_BINDINGS: dict[str, int] = {}  # Populated by _init_key_bindings() below


def _init_key_bindings() -> None:
    """Populate KEY_BINDINGS with pygame constants.

    Call this after pygame.init() has been invoked (so pygame.K_* are valid).
    """
    global KEY_BINDINGS
    KEY_BINDINGS = {
        "move_up": pygame.K_w,
        "move_down": pygame.K_s,
        "move_left": pygame.K_a,
        "move_right": pygame.K_d,
        "jump": pygame.K_SPACE,
        "crouch": pygame.K_LCTRL,
        "sprint": pygame.K_LSHIFT,
        "slide": pygame.K_c,
        "interact": pygame.K_e,
        "inventory": pygame.K_TAB,
        "map": pygame.K_m,
        "pause": pygame.K_ESCAPE,
    }
