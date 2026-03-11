"""Tests for surface utility helpers — src/utils/surface_utils.py

Covers blur_surface(), the cheap box-blur approximation used by PostRound to
create the frozen background from the last rendered GameScene frame.
"""
import pygame
import pytest

from src.utils.surface_utils import blur_surface


# ── Return type and dimensions ─────────────────────────────────────────────────

class TestBlurSurfaceOutput:

    def test_returns_pygame_surface(self, pygame_init):
        surf = pygame.Surface((200, 150))
        result = blur_surface(surf, radius=4)
        assert isinstance(result, pygame.Surface)

    def test_output_width_matches_input(self, pygame_init):
        surf = pygame.Surface((320, 240))
        result = blur_surface(surf, radius=4)
        assert result.get_width() == 320

    def test_output_height_matches_input(self, pygame_init):
        surf = pygame.Surface((320, 240))
        result = blur_surface(surf, radius=4)
        assert result.get_height() == 240

    def test_output_size_tuple_matches_input(self, pygame_init):
        w, h = 640, 480
        surf = pygame.Surface((w, h))
        result = blur_surface(surf, radius=4)
        assert result.get_size() == (w, h)

    def test_game_resolution_preserved(self, pygame_init):
        """Standard 1280×720 game surface keeps its dimensions after blurring."""
        surf = pygame.Surface((1280, 720))
        result = blur_surface(surf, radius=4)
        assert result.get_size() == (1280, 720)


# ── Non-destructive (original surface unchanged) ───────────────────────────────

class TestBlurSurfaceNonDestructive:

    def test_original_pixel_colour_unchanged(self, pygame_init):
        surf = pygame.Surface((100, 100))
        surf.fill((200, 50, 50))
        original_colour = surf.get_at((50, 50))
        blur_surface(surf, radius=4)
        assert surf.get_at((50, 50)) == original_colour

    def test_returns_new_object_not_same_reference(self, pygame_init):
        surf = pygame.Surface((100, 100))
        result = blur_surface(surf, radius=4)
        assert result is not surf


# ── Various radii ──────────────────────────────────────────────────────────────

class TestBlurSurfaceRadii:

    @pytest.mark.parametrize("radius", [1, 2, 4, 8, 16])
    def test_various_radii_preserve_dimensions(self, pygame_init, radius):
        w, h = 256, 256
        surf = pygame.Surface((w, h))
        result = blur_surface(surf, radius=radius)
        assert result.get_size() == (w, h)

    def test_radius_one_still_returns_surface(self, pygame_init):
        surf = pygame.Surface((100, 100))
        result = blur_surface(surf, radius=1)
        assert isinstance(result, pygame.Surface)
        assert result.get_size() == (100, 100)

    def test_large_radius_still_returns_surface(self, pygame_init):
        surf = pygame.Surface((64, 64))
        result = blur_surface(surf, radius=16)
        assert isinstance(result, pygame.Surface)
        assert result.get_size() == (64, 64)


# ── Edge-case surfaces ─────────────────────────────────────────────────────────

class TestBlurSurfaceEdgeCases:

    def test_small_surface_1x1(self, pygame_init):
        surf = pygame.Surface((1, 1))
        result = blur_surface(surf, radius=1)
        assert result.get_size() == (1, 1)

    def test_solid_colour_surface_does_not_raise(self, pygame_init):
        surf = pygame.Surface((200, 200))
        surf.fill((0, 245, 255))   # ACCENT_CYAN
        result = blur_surface(surf, radius=4)
        assert isinstance(result, pygame.Surface)

    def test_transparent_surface_does_not_raise(self, pygame_init):
        surf = pygame.Surface((128, 128), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        result = blur_surface(surf, radius=4)
        assert result.get_size() == (128, 128)

    def test_non_square_surface_preserves_both_dimensions(self, pygame_init):
        surf = pygame.Surface((400, 100))
        result = blur_surface(surf, radius=4)
        assert result.get_width() == 400
        assert result.get_height() == 100
