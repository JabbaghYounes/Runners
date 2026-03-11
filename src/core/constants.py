"""Global UI constants — single source of truth for colors, screen geometry, and layout grid."""
from __future__ import annotations

# Screen
SCREEN_W: int = 1280
SCREEN_H: int = 720
FPS: int = 60

# Layout grid
MARGIN: int = 16
PADDING: int = 16
BASE_UNIT: int = 16
BORDER_RADIUS: int = 6

# Color palette (RGB tuples)
BG_DEEP:         tuple[int, int, int] = (10,  14,  26)
BG_PANEL:        tuple[int, int, int] = (20,  24,  38)
ACCENT_CYAN:     tuple[int, int, int] = (0,   245, 255)
ACCENT_MAGENTA:  tuple[int, int, int] = (255, 0,   128)
ACCENT_AMBER:    tuple[int, int, int] = (255, 184, 0)
ACCENT_GREEN:    tuple[int, int, int] = (57,  255, 20)
DANGER_RED:      tuple[int, int, int] = (255, 32,  64)
BORDER_DIM:      tuple[int, int, int] = (42,  48,  80)
BORDER_GLOW:     tuple[int, int, int] = (0,   245, 255)
TEXT_PRIMARY:    tuple[int, int, int] = (255, 255, 255)
TEXT_SECONDARY:  tuple[int, int, int] = (154, 163, 192)
TEXT_DISABLED:   tuple[int, int, int] = (58,  64,  96)

# Rarity colors
RARITY_COMMON:    tuple[int, int, int] = (170, 170, 170)
RARITY_UNCOMMON:  tuple[int, int, int] = (57,  255, 20)
RARITY_RARE:      tuple[int, int, int] = (0,   165, 255)
RARITY_EPIC:      tuple[int, int, int] = (192, 64,  255)
RARITY_LEGENDARY: tuple[int, int, int] = (255, 140, 0)
