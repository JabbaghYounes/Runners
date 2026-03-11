"""Unit tests for src/core/asset_manager.py.

Covers image placeholder fallback, load-once caching, sound graceful
degradation when audio is unavailable or the file is missing, font loading
and caching, set_audio_available toggling, and clear_cache behaviour.

SDL_VIDEODRIVER=dummy + SDL_AUDIODRIVER=dummy keep the suite headless.
A 1×1 dummy display is created so convert() / convert_alpha() do not raise
when a real image would be loaded (even though our tests only exercise the
missing-file placeholder path, the display must exist for the codepath to be
consistent with production use).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.init()
# A minimal display surface is required for Surface.convert() / convert_alpha()
pygame.display.set_mode((1, 1))

from src.core.asset_manager import AssetManager  # noqa: E402


# ── load_image ────────────────────────────────────────────────────────────────

class TestLoadImage:
    """load_image must return a usable Surface and degrade gracefully."""

    def setup_method(self):
        self.am = AssetManager()

    # -- Missing-file placeholder --

    def test_missing_file_returns_surface(self):
        surf = self.am.load_image("nonexistent/sprite.png")
        assert isinstance(surf, pygame.Surface)

    def test_missing_file_placeholder_is_magenta(self):
        surf = self.am.load_image("nonexistent/sprite.png")
        r, g, b, *_ = surf.get_at((0, 0))
        assert (r, g, b) == (255, 0, 255), "Placeholder must be magenta (255, 0, 255)"

    def test_missing_file_default_placeholder_size_is_32x32(self):
        surf = self.am.load_image("nonexistent/sprite.png")
        assert surf.get_size() == (32, 32)

    def test_missing_file_with_scale_placeholder_uses_scale_dimensions(self):
        surf = self.am.load_image("nonexistent/sprite.png", scale=(64, 48))
        assert surf.get_size() == (64, 48)

    def test_missing_file_placeholder_is_still_magenta_when_scaled(self):
        surf = self.am.load_image("nonexistent/sprite.png", scale=(16, 16))
        r, g, b, *_ = surf.get_at((0, 0))
        assert (r, g, b) == (255, 0, 255)

    # -- Caching --

    def test_same_path_same_alpha_same_scale_returns_cached_object(self):
        s1 = self.am.load_image("nonexistent/sprite.png")
        s2 = self.am.load_image("nonexistent/sprite.png")
        assert s1 is s2, "Second call must return the same cached Surface object"

    def test_different_alpha_flag_is_separate_cache_entry(self):
        s_alpha  = self.am.load_image("nonexistent/sprite.png", alpha=True)
        s_opaque = self.am.load_image("nonexistent/sprite.png", alpha=False)
        assert s_alpha is not s_opaque

    def test_different_scale_is_separate_cache_entry(self):
        s_small = self.am.load_image("nonexistent/sprite.png", scale=(32, 32))
        s_large = self.am.load_image("nonexistent/sprite.png", scale=(64, 64))
        assert s_small is not s_large

    def test_explicit_none_scale_and_default_scale_share_cache_entry(self):
        s_default      = self.am.load_image("nonexistent/sprite.png")
        s_explicit_none = self.am.load_image("nonexistent/sprite.png", scale=None)
        assert s_default is s_explicit_none

    def test_different_paths_are_separate_cache_entries(self):
        s_a = self.am.load_image("nonexistent/a.png")
        s_b = self.am.load_image("nonexistent/b.png")
        assert s_a is not s_b


# ── load_sound ────────────────────────────────────────────────────────────────

class TestLoadSound:
    """load_sound must return None gracefully when audio is off or file missing."""

    def setup_method(self):
        self.am = AssetManager()

    def test_audio_unavailable_returns_none_immediately(self):
        self.am.set_audio_available(False)
        result = self.am.load_sound("sfx/shoot.wav")
        assert result is None

    def test_audio_unavailable_is_idempotent_across_calls(self):
        self.am.set_audio_available(False)
        r1 = self.am.load_sound("sfx/shoot.wav")
        r2 = self.am.load_sound("sfx/shoot.wav")
        assert r1 is None
        assert r2 is None

    def test_missing_file_returns_none_even_when_audio_enabled(self):
        """A missing sound file must not raise; it returns None instead."""
        self.am.set_audio_available(True)
        result = self.am.load_sound("nonexistent/sound.wav")
        assert result is None

    def test_missing_file_does_not_populate_cache(self):
        self.am.set_audio_available(True)
        self.am.load_sound("nonexistent/sound.wav")
        assert "nonexistent/sound.wav" not in self.am._sounds


# ── set_audio_available ────────────────────────────────────────────────────────

class TestSetAudioAvailable:
    def test_default_audio_available_is_true(self):
        am = AssetManager()
        assert am._audio_available is True

    def test_set_false_disables_audio(self):
        am = AssetManager()
        am.set_audio_available(False)
        assert am._audio_available is False

    def test_set_true_re_enables_audio(self):
        am = AssetManager()
        am.set_audio_available(False)
        am.set_audio_available(True)
        assert am._audio_available is True


# ── load_font ─────────────────────────────────────────────────────────────────

class TestLoadFont:
    def setup_method(self):
        self.am = AssetManager()

    def test_none_name_returns_font_object(self):
        font = self.am.load_font(None, 24)
        assert isinstance(font, pygame.font.Font)

    def test_different_sizes_return_font_objects(self):
        for size in (12, 24, 48, 80):
            font = self.am.load_font(None, size)
            assert isinstance(font, pygame.font.Font), f"Failed for size={size}"

    def test_same_name_and_size_returns_cached_object(self):
        f1 = self.am.load_font(None, 24)
        f2 = self.am.load_font(None, 24)
        assert f1 is f2

    def test_different_sizes_are_separate_cache_entries(self):
        f_small = self.am.load_font(None, 16)
        f_large = self.am.load_font(None, 48)
        assert f_small is not f_large

    def test_bad_path_falls_back_to_default_font(self):
        """A nonexistent font path must not raise; it falls back to the system font."""
        font = self.am.load_font("/nonexistent/path/font.ttf", 24)
        assert isinstance(font, pygame.font.Font)

    def test_bad_path_is_cached_after_fallback(self):
        f1 = self.am.load_font("/nonexistent/font.ttf", 24)
        f2 = self.am.load_font("/nonexistent/font.ttf", 24)
        assert f1 is f2


# ── clear_cache ───────────────────────────────────────────────────────────────

class TestClearCache:
    def setup_method(self):
        self.am = AssetManager()

    def test_clear_cache_forces_fresh_image_load_on_next_call(self):
        s1 = self.am.load_image("nonexistent/sprite.png")
        self.am.clear_cache()
        s2 = self.am.load_image("nonexistent/sprite.png")
        assert s1 is not s2, "After clear_cache, a new Surface must be created"

    def test_clear_cache_forces_fresh_font_load_on_next_call(self):
        f1 = self.am.load_font(None, 24)
        self.am.clear_cache()
        f2 = self.am.load_font(None, 24)
        assert f1 is not f2

    def test_clear_cache_empties_image_dict(self):
        self.am.load_image("nonexistent/a.png")
        self.am.load_image("nonexistent/b.png")
        self.am.clear_cache()
        assert len(self.am._images) == 0

    def test_clear_cache_empties_font_dict(self):
        self.am.load_font(None, 24)
        self.am.load_font(None, 48)
        self.am.clear_cache()
        assert len(self.am._fonts) == 0

    def test_clear_cache_empties_sound_dict(self):
        # Put a fake entry in the sounds cache to verify clear works
        self.am._sounds["fake"] = object()  # type: ignore[assignment]
        self.am.clear_cache()
        assert len(self.am._sounds) == 0

    def test_clear_cache_on_empty_manager_does_not_raise(self):
        """clear_cache must be safe to call even with an empty cache."""
        fresh = AssetManager()
        fresh.clear_cache()  # should not raise
