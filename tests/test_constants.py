"""Unit tests for src/constants.py.

Validates compile-time constants: loop timings, resolution defaults, colour
palette, render-layer ordering, physics values, rarity colours, and short-form
aliases.

No Pygame display is required — the module imports Pygame constants
(plain integers) which are available before pygame.init().
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Keep SDL from trying to open a real display or audio device when the
# pygame module is imported as a side-effect of importing constants.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import src.constants as C  # noqa: E402


# ── Loop / timestep ───────────────────────────────────────────────────────────

class TestLoopConstants:
    def test_fixed_timestep_is_one_over_sixty(self):
        assert abs(C.FIXED_TIMESTEP - (1.0 / 60)) < 1e-9

    def test_max_frame_time_is_quarter_second(self):
        assert C.MAX_FRAME_TIME == 0.25

    def test_sixty_fixed_steps_sum_to_one_second(self):
        """60 ticks at FIXED_TIMESTEP must equal exactly 1 s (within float error)."""
        assert abs(60 * C.FIXED_TIMESTEP - 1.0) < 1e-6

    def test_default_fps_is_sixty(self):
        assert C.DEFAULT_FPS == 60

    def test_fps_alias_matches_default_fps(self):
        assert C.FPS == C.DEFAULT_FPS

    def test_max_frame_time_greater_than_fixed_timestep(self):
        """Spiral-of-death cap must be larger than a single tick."""
        assert C.MAX_FRAME_TIME > C.FIXED_TIMESTEP


# ── Resolution defaults & aliases ─────────────────────────────────────────────

class TestResolutionConstants:
    def test_default_width_is_1280(self):
        assert C.DEFAULT_WIDTH == 1280

    def test_default_height_is_720(self):
        assert C.DEFAULT_HEIGHT == 720

    def test_screen_w_alias_matches_default_width(self):
        assert C.SCREEN_W == C.DEFAULT_WIDTH

    def test_screen_h_alias_matches_default_height(self):
        assert C.SCREEN_H == C.DEFAULT_HEIGHT

    def test_tile_size_is_positive(self):
        assert C.TILE_SIZE > 0


# ── Colour tuples ─────────────────────────────────────────────────────────────

class TestColourTuples:
    """Every colour constant must be a valid (R, G, B) 3-tuple in [0, 255]."""

    _CANONICAL = [
        "BLACK", "WHITE", "DARK_BG", "PANEL_BG",
        "NEON_CYAN", "NEON_GREEN", "NEON_ORANGE", "NEON_RED",
        "TEXT_PRIMARY", "TEXT_DIM",
    ]
    _ALIASES = [
        "ACCENT_CYAN", "ACCENT_GREEN", "ACCENT_ORANGE", "ACCENT_RED",
        "ACCENT_MAGENTA", "BG_DEEP", "BG_MID",
        "BORDER_DIM", "BORDER_BRIGHT",
        "TEXT_BRIGHT", "TEXT_SECONDARY",
        "HEALTH_COLOR", "ARMOR_COLOR", "XP_COLOR",
    ]

    def _assert_valid_colour(self, name: str) -> None:
        colour = getattr(C, name)
        assert len(colour) == 3, f"{name} must have exactly 3 components"
        r, g, b = colour
        assert 0 <= r <= 255, f"{name}.r={r} out of [0, 255]"
        assert 0 <= g <= 255, f"{name}.g={g} out of [0, 255]"
        assert 0 <= b <= 255, f"{name}.b={b} out of [0, 255]"

    def test_canonical_colours_are_valid_tuples(self):
        for name in self._CANONICAL:
            self._assert_valid_colour(name)

    def test_alias_colours_are_valid_tuples(self):
        for name in self._ALIASES:
            self._assert_valid_colour(name)

    def test_black_is_zero_zero_zero(self):
        assert C.BLACK == (0, 0, 0)

    def test_white_is_255_255_255(self):
        assert C.WHITE == (255, 255, 255)

    def test_dark_bg_is_not_pure_black(self):
        """DARK_BG is a deep-space colour, not #000000."""
        assert C.DARK_BG != (0, 0, 0)


# ── Colour aliases match canonical names ──────────────────────────────────────

class TestColourAliases:
    def test_accent_cyan_equals_neon_cyan(self):
        assert C.ACCENT_CYAN == C.NEON_CYAN

    def test_accent_green_equals_neon_green(self):
        assert C.ACCENT_GREEN == C.NEON_GREEN

    def test_accent_orange_equals_neon_orange(self):
        assert C.ACCENT_ORANGE == C.NEON_ORANGE

    def test_accent_red_equals_neon_red(self):
        assert C.ACCENT_RED == C.NEON_RED

    def test_bg_deep_equals_dark_bg(self):
        assert C.BG_DEEP == C.DARK_BG

    def test_text_bright_equals_text_primary(self):
        assert C.TEXT_BRIGHT == C.TEXT_PRIMARY

    def test_text_secondary_equals_text_dim(self):
        assert C.TEXT_SECONDARY == C.TEXT_DIM


# ── Rarity colours ────────────────────────────────────────────────────────────

class TestRarityColours:
    _REQUIRED = {"common", "uncommon", "rare", "epic", "legendary"}

    def test_all_five_rarities_defined(self):
        assert set(C.RARITY_COLORS.keys()) == self._REQUIRED

    def test_rarity_colours_are_valid_three_tuples(self):
        for name, colour in C.RARITY_COLORS.items():
            assert len(colour) == 3, f"Rarity '{name}' must have 3 components"
            r, g, b = colour
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255

    def test_rarity_colours_are_all_distinct(self):
        colours = list(C.RARITY_COLORS.values())
        assert len(colours) == len(set(colours)), "All rarity colours must be unique"


# ── Render layers ─────────────────────────────────────────────────────────────

class TestRenderLayers:
    _ALL_LAYERS = [
        "LAYER_TILES", "LAYER_LOOT", "LAYER_ENEMIES",
        "LAYER_PLAYER", "LAYER_PROJECTILES", "LAYER_HUD",
    ]

    def test_all_six_layers_are_defined(self):
        for name in self._ALL_LAYERS:
            assert hasattr(C, name), f"Missing constant: {name}"

    def test_layers_are_unique_integers(self):
        values = [getattr(C, n) for n in self._ALL_LAYERS]
        assert len(values) == len(set(values)), "Render layers must be unique"

    def test_layers_are_non_negative(self):
        for name in self._ALL_LAYERS:
            assert getattr(C, name) >= 0, f"{name} must be >= 0"

    def test_tiles_is_lowest_layer(self):
        assert C.LAYER_TILES == min(getattr(C, n) for n in self._ALL_LAYERS)

    def test_hud_is_highest_layer(self):
        assert C.LAYER_HUD == max(getattr(C, n) for n in self._ALL_LAYERS)

    def test_ascending_z_order(self):
        assert C.LAYER_TILES < C.LAYER_LOOT < C.LAYER_ENEMIES
        assert C.LAYER_ENEMIES < C.LAYER_PLAYER < C.LAYER_PROJECTILES
        assert C.LAYER_PROJECTILES < C.LAYER_HUD


# ── Physics constants ─────────────────────────────────────────────────────────

class TestPhysicsConstants:
    def test_gravity_is_positive(self):
        assert C.GRAVITY > 0

    def test_player_speed_is_positive(self):
        assert C.PLAYER_SPEED > 0

    def test_player_jump_vel_is_negative(self):
        """Upward velocity must be negative (pygame y-axis points downward)."""
        assert C.PLAYER_JUMP_VEL < 0

    def test_walk_speed_less_than_sprint_speed(self):
        assert C.WALK_SPEED < C.SPRINT_SPEED

    def test_crouch_speed_less_than_walk_speed(self):
        assert C.CROUCH_SPEED < C.WALK_SPEED

    def test_jump_vel_is_negative(self):
        assert C.JUMP_VEL < 0

    def test_slide_vel_is_positive(self):
        assert C.SLIDE_VEL > 0

    def test_accel_and_decel_are_positive(self):
        assert C.ACCEL > 0
        assert C.DECEL > 0

    def test_slide_duration_is_positive(self):
        assert C.SLIDE_DURATION > 0

    def test_normal_height_greater_than_crouch_height(self):
        assert C.NORMAL_HEIGHT > C.CROUCH_HEIGHT

    def test_pickup_radius_is_positive(self):
        assert C.PICKUP_RADIUS > 0

    def test_round_duration_is_positive(self):
        assert C.ROUND_DURATION_SECS > 0


# ── Default key bindings ──────────────────────────────────────────────────────

class TestDefaultKeys:
    _REQUIRED_ACTIONS = [
        "move_left", "move_right", "jump", "crouch",
        "reload", "interact", "inventory", "map", "pause",
    ]

    def test_all_required_actions_present(self):
        for action in self._REQUIRED_ACTIONS:
            assert action in C.DEFAULT_KEYS, f"Missing default binding for '{action}'"

    def test_all_keycodes_are_integers(self):
        for action, keycode in C.DEFAULT_KEYS.items():
            assert isinstance(keycode, int), f"Keycode for '{action}' is not an int"

    def test_all_keycodes_are_positive(self):
        for action, keycode in C.DEFAULT_KEYS.items():
            assert keycode > 0, f"Keycode for '{action}' must be > 0"

    def test_no_duplicate_keycodes(self):
        codes = list(C.DEFAULT_KEYS.values())
        assert len(codes) == len(set(codes)), "Duplicate default key bindings detected"
