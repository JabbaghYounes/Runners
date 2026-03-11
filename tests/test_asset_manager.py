"""Tests for AssetManager — cache behaviour, missing files, mixer unavailable."""
import sys
from unittest.mock import MagicMock, patch
import pygame
import pytest

from src.core.asset_manager import AssetManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pygame_mock(*, mixer_init: bool = True) -> MagicMock:
    """Return a minimal pygame mock whose mixer.get_init() returns *mixer_init*."""
    pm = MagicMock()
    pm.mixer.get_init.return_value = mixer_init
    pm.mixer.Sound.return_value = MagicMock()
    return pm


# ---------------------------------------------------------------------------
# load_sound — cache hit
# ---------------------------------------------------------------------------

class TestLoadSoundCacheHit:
    def test_second_call_returns_cached_object(self, tmp_path):
        """pygame.mixer.Sound must be invoked only once for the same path."""
        wav = tmp_path / "beep.wav"
        wav.write_bytes(b"\x00" * 44)

        pm = _make_pygame_mock(mixer_init=True)
        with patch.dict(sys.modules, {"pygame": pm}):
            manager = AssetManager()
            r1 = manager.load_sound(str(wav))
            r2 = manager.load_sound(str(wav))

        assert pm.mixer.Sound.call_count == 1
        assert r1 is r2

    def test_different_paths_load_independently(self, tmp_path):
        """Two distinct paths each get their own load call."""
        wav1 = tmp_path / "a.wav"
        wav2 = tmp_path / "b.wav"
        wav1.write_bytes(b"\x00" * 44)
        wav2.write_bytes(b"\x00" * 44)

        pm = _make_pygame_mock(mixer_init=True)
        with patch.dict(sys.modules, {"pygame": pm}):
            manager = AssetManager()
            manager.load_sound(str(wav1))
            manager.load_sound(str(wav2))

        assert pm.mixer.Sound.call_count == 2


# ---------------------------------------------------------------------------
# load_sound — mixer unavailable
# ---------------------------------------------------------------------------

class TestLoadSoundMixerUnavailable:
    def test_returns_none_when_mixer_not_initialised(self, tmp_path):
        """If pygame.mixer.get_init() is False the loader returns None."""
        wav = tmp_path / "beep.wav"
        wav.write_bytes(b"\x00" * 44)

        pm = _make_pygame_mock(mixer_init=False)
        with patch.dict(sys.modules, {"pygame": pm}):
            manager = AssetManager()
            result = manager.load_sound(str(wav))

        assert result is None

    def test_returns_none_when_pygame_not_importable(self, tmp_path):
        """If the pygame package itself is absent the loader returns None."""
        wav = tmp_path / "beep.wav"
        wav.write_bytes(b"\x00" * 44)

        with patch.dict(sys.modules, {"pygame": None}):
            manager = AssetManager()
            result = manager.load_sound(str(wav))

        assert result is None

    def test_unavailable_result_is_cached_as_none(self, tmp_path):
        """A failed load is cached; pygame.mixer.Sound is never retried."""
        wav = tmp_path / "beep.wav"
        wav.write_bytes(b"\x00" * 44)

        pm = _make_pygame_mock(mixer_init=False)
        with patch.dict(sys.modules, {"pygame": pm}):
            manager = AssetManager()
            manager.load_sound(str(wav))
            manager.load_sound(str(wav))

        # get_init is checked once per call, but Sound is never invoked
        pm.mixer.Sound.assert_not_called()


# ---------------------------------------------------------------------------
# load_sound — missing or corrupt file
# ---------------------------------------------------------------------------

class TestLoadSoundBadFile:
    def test_returns_none_for_nonexistent_file(self):
        """A missing file path returns None rather than raising."""
        pm = _make_pygame_mock(mixer_init=True)
        pm.mixer.Sound.side_effect = FileNotFoundError("no such file")

        with patch.dict(sys.modules, {"pygame": pm}):
            manager = AssetManager()
            result = manager.load_sound("/nonexistent/boom.wav")

        assert result is None

    def test_returns_none_when_sound_ctor_raises_generic_error(self):
        """Any exception from pygame.mixer.Sound is swallowed and None returned."""
        pm = _make_pygame_mock(mixer_init=True)
        pm.mixer.Sound.side_effect = RuntimeError("corrupt file")

        with patch.dict(sys.modules, {"pygame": pm}):
            manager = AssetManager()
            result = manager.load_sound("/bad.wav")

        assert result is None

    def test_bad_file_cached_as_none_not_retried(self):
        """Failed loads are cached so the file is attempted at most once."""
        pm = _make_pygame_mock(mixer_init=True)
        pm.mixer.Sound.side_effect = OSError("read error")

        with patch.dict(sys.modules, {"pygame": pm}):
            manager = AssetManager()
            manager.load_sound("/bad.wav")
            manager.load_sound("/bad.wav")

        assert pm.mixer.Sound.call_count == 1


# ---------------------------------------------------------------------------
# load_image stub
# ---------------------------------------------------------------------------

class TestLoadImageStub:
    def test_returns_fallback_surface(self):
        result = AssetManager().load_image("any/sprite.png")
        assert isinstance(result, pygame.Surface)

    def test_repeated_calls_return_same_fallback(self):
        manager = AssetManager()
        r1 = manager.load_image("sprite.png")
        r2 = manager.load_image("sprite.png")
        assert isinstance(r1, pygame.Surface)
        assert r1 is r2


# ---------------------------------------------------------------------------
# load_font stub
# ---------------------------------------------------------------------------

class TestLoadFontStub:
    def test_returns_fallback_font(self):
        result = AssetManager().load_font("any/font.ttf", 16)
        assert isinstance(result, pygame.font.Font)

    def test_different_sizes_return_fallback_fonts(self):
        manager = AssetManager()
        r1 = manager.load_font("font.ttf", 14)
        r2 = manager.load_font("font.ttf", 32)
        assert isinstance(r1, pygame.font.Font)
        assert isinstance(r2, pygame.font.Font)

    def test_font_cached_by_path_and_size(self):
        manager = AssetManager()
        r1 = manager.load_font("font.ttf", 16)
        r2 = manager.load_font("font.ttf", 16)
        assert r1 is r2
