"""Project-wide constants: screen geometry, timing, key bindings, and color palette.

Import this module wherever magic numbers would otherwise appear.  Never load
``settings.json`` here — this file contains compile-time constants only.
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
TIMER_WARN_SECS: int = 300    # 5 minutes → switch to amber
TIMER_DANGER_SECS: int = 60   # 1 minute  → switch to red + pulse

# Pulse animation frequency for the danger-state timer (Hz)
TIMER_PULSE_HZ: float = 2.0

# ---------------------------------------------------------------------------
# Key bindings (defaults — may be overridden by settings.json at runtime)
# ---------------------------------------------------------------------------
KEY_EXTRACT: int = pygame.K_f   # hold to channel extraction

# ---------------------------------------------------------------------------
# Extraction system
# ---------------------------------------------------------------------------
# Minimum velocity magnitude (px/s) that counts as "player is moving"
MOVE_THRESHOLD: float = 5.0

# ---------------------------------------------------------------------------
# Color palette  (from UX spec §Design System)
# ---------------------------------------------------------------------------
BG_DEEP       = (10,   14,  26)   # #0A0E1A  — screen backgrounds / overlays
BG_PANEL      = (20,   24,  38)   # #141826  — panel fill (at 85 % opacity where used)
ACCENT_CYAN   = (0,  245, 255)    # #00F5FF  — primary actions, player dot, health
ACCENT_MAGENTA= (255,  0, 128)    # #FF0080  — secondary actions, enemy indicators
ACCENT_AMBER  = (255, 184,   0)   # #FFB800  — timer warnings, currency
ACCENT_GREEN  = (57,  255,  20)   # #39FF14  — success states, extraction zone, XP
DANGER_RED    = (255,  32,  64)   # #FF2040  — danger, critical health, failure
BORDER_DIM    = (42,   48,  80)   # #2A3050  — inactive borders
TEXT_PRIMARY  = (255, 255, 255)   # #FFFFFF  — headings, values
TEXT_SECONDARY= (154, 163, 192)   # #9AA3C0  — labels, descriptions
TEXT_DISABLED = (58,   64,  96)   # #3A4060  — disabled states

# ---------------------------------------------------------------------------
# HUD layout helpers
# ---------------------------------------------------------------------------
HUD_MARGIN: int = 16   # px from screen edges (1 base-unit per UX spec)
