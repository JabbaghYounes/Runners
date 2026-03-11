"""Unit tests for src.core.asset_manager.AssetManager.

Requires pygame to be initialised (provided by the session-scoped fixture in
conftest.py).
"""
import pygame
import pytest

from src.core.asset_manager import AssetManager


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

class TestLoadFont:
    def test_none_name_returns_font(self, assets):
        font = assets.load_font(None, 24)
        assert isinstance(font, pygame.font.Font)

    def test_returns_font_for_various_sizes(self, assets):
        for size in (8, 12, 18, 24, 36, 48):
            font = assets.load_font(None, size)
            assert isinstance(font, pygame.font.Font)

    def test_same_args_returns_cached_object(self, assets):
        """Two calls with identical arguments must return the *same* object."""
        f1 = assets.load_font(None, 16)
        f2 = assets.load_font(None, 16)
        assert f1 is f2

    def test_different_sizes_return_different_objects(self, assets):
        f1 = assets.load_font(None, 12)
        f2 = assets.load_font(None, 24)
        assert f1 is not f2

    def test_nonexistent_path_falls_back_without_raising(self, assets):
        """A missing font file should fall back to the system monospace font."""
        font = assets.load_font("/nonexistent/path/font.ttf", 20)
        assert isinstance(font, pygame.font.Font)

    def test_nonexistent_path_result_is_cached(self):
        """Even fallback results are cached to avoid repeated disk hits."""
        am = AssetManager()
        f1 = am.load_font("/fake/font.ttf", 14)
        f2 = am.load_font("/fake/font.ttf", 14)
        assert f1 is f2

    def test_fresh_manager_has_empty_font_cache(self):
        am = AssetManager()
        assert len(am._font_cache) == 0

    def test_cache_grows_after_load(self, assets):
        initial = len(assets._font_cache)
        assets.load_font(None, 99)          # Unlikely to be cached already
        assert len(assets._font_cache) > initial


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

class TestLoadImage:
    def test_missing_image_raises(self, assets):
        """Unlike sounds, a missing image should raise since there is no
        graceful fallback defined in the implementation."""
        with pytest.raises(Exception):
            assets.load_image("/no/such/image.png")


# ---------------------------------------------------------------------------
# Sounds
# ---------------------------------------------------------------------------

class TestLoadSound:
    def test_missing_file_returns_none(self, assets):
        result = assets.load_sound("/no/such/sound.wav")
        assert result is None

    def test_missing_file_result_is_cached(self):
        """The None sentinel is stored so the disk is not hit twice."""
        am = AssetManager()
        am.load_sound("/fake/audio.wav")
        # Cache must now contain the key
        assert "/fake/audio.wav" in am._sound_cache
        result = am.load_sound("/fake/audio.wav")
        assert result is None

    def test_missing_file_same_path_returns_none_twice(self, assets):
        r1 = assets.load_sound("/fake/path.ogg")
        r2 = assets.load_sound("/fake/path.ogg")
        assert r1 is None
        assert r2 is None


# ---------------------------------------------------------------------------
# Cache isolation between instances
# ---------------------------------------------------------------------------

def test_two_managers_have_separate_caches():
    am1 = AssetManager()
    am2 = AssetManager()
    f1 = am1.load_font(None, 14)
    f2 = am2.load_font(None, 14)
    # Both are valid fonts but from independent cache dictionaries.
    assert isinstance(f1, pygame.font.Font)
    assert isinstance(f2, pygame.font.Font)
    # The cache of am1 must not bleed into am2's cache.
    assert am1._font_cache is not am2._font_cache
