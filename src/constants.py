import pygame

SCREEN_W = 1280
SCREEN_H = 720
FPS = 60
TILE_SIZE = 32

# Colors
BLACK        = (0,   0,   0)
WHITE        = (255, 255, 255)
BG_DEEP      = (8,   12,  20)
BG_MID       = (15,  22,  38)
ACCENT_CYAN  = (0,   220, 255)
ACCENT_GREEN = (0,   255, 120)
ACCENT_MAGENTA = (255, 0, 180)
ACCENT_ORANGE  = (255, 160,  0)
ACCENT_RED   = (255,  60,  60)
BORDER_DIM   = (40,   60,  80)
BORDER_BRIGHT = (80, 120, 160)
PANEL_BG     = (12,   18,  30)
TEXT_BRIGHT  = (220, 235, 255)
TEXT_DIM     = (100, 130, 160)
HEALTH_COLOR = (80,  255,  80)
ARMOR_COLOR  = (80,  160, 255)
XP_COLOR     = (160,  80, 255)

GRAVITY     = 800.0
WALK_SPEED  = 180
SPRINT_SPEED = 300
JUMP_VEL    = -550
SLIDE_VEL   = 400

KEY_BINDINGS = {}

def _init_key_bindings():
    KEY_BINDINGS.update({
        'move_left':  pygame.K_a,
        'move_right': pygame.K_d,
        'jump':       pygame.K_w,
        'crouch':     pygame.K_s,
        'sprint':     pygame.K_LSHIFT,
        'interact':   pygame.K_e,
        'map':        pygame.K_m,
        'inventory':  pygame.K_TAB,
        'pause':      pygame.K_ESCAPE,
        'shoot':      1,  # mouse button 1
    })
