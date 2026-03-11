"""Project-wide constants: screen geometry, timing, key bindings, and color palette.

Import this module wherever magic numbers would otherwise appear.  Never load
``settings.json`` here -- this file contains compile-time constants only.
"""

import pygame

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
SCREEN_W: int = 1280
SCREEN_H: int = 720
FPS: int = 60

# ---------------------------------------------------------------------------
# Round timing
# ---------------------------------------------------------------------------
ROUND_DURATION_SECS: float = 900.0   # 15 minutes
EXTRACTION_CHANNEL_SECS: float = 3.0  # hold time required to extract

# Timer color-change thresholds (seconds remaining)
TIMER_WARN_SECS: int = 300    # 5 minutes -> switch to amber
TIMER_DANGER_SECS: int = 60   # 1 minute  -> switch to red + pulse

# Pulse animation frequency for the danger-state timer (Hz)
TIMER_PULSE_HZ: float = 2.0

# ---------------------------------------------------------------------------
# Key bindings (defaults -- may be overridden by settings.json at runtime)
# ---------------------------------------------------------------------------
KEY_EXTRACT: int = pygame.K_f   # hold to channel extraction

# ---------------------------------------------------------------------------
# Extraction system
# ---------------------------------------------------------------------------
# Minimum velocity magnitude (px/s) that counts as "player is moving"
MOVE_THRESHOLD: float = 5.0

# ---------------------------------------------------------------------------
# Item rarity value multipliers (re-exported for convenience)
# ---------------------------------------------------------------------------
from src.inventory.item import RARITY_VALUE_MULTIPLIERS  # noqa: E402  re-export

# ---------------------------------------------------------------------------
# Pickup
# ---------------------------------------------------------------------------
PICKUP_RADIUS: int = 64

# ---------------------------------------------------------------------------
# Color palette  (from UX spec)
# ---------------------------------------------------------------------------
BG_DEEP       = (10,   14,  26)
BG_PANEL      = (20,   24,  38)
ACCENT_CYAN   = (0,  245, 255)
ACCENT_MAGENTA= (255,  0, 128)
ACCENT_AMBER  = (255, 184,   0)
ACCENT_GREEN  = (57,  255,  20)
DANGER_RED    = (255,  32,  64)
BORDER_DIM    = (42,   48,  80)
TEXT_PRIMARY  = (255, 255, 255)
TEXT_SECONDARY= (154, 163, 192)
TEXT_DISABLED = (58,   64,  96)

# ---------------------------------------------------------------------------
# HUD layout helpers
# ---------------------------------------------------------------------------
HUD_MARGIN: int = 16
MARGIN: int = 16
PADDING: int = 16
BORDER_GLOW = ACCENT_CYAN
