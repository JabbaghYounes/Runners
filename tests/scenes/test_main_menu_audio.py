# Run: pytest tests/scenes/test_main_menu_audio.py
"""Tests for MainMenu audio kwarg — storage and forwarding to SettingsScreen.

MainMenu must:
  - Accept an ``audio=`` keyword argument and store it as ``self._audio``
  - Forward that reference to SettingsScreen when ``_on_settings()`` is called
    with a SceneManager in scope, enabling live volume preview from the menu
  - Default ``_audio`` to None when the kwarg is omitted
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

import pygame

from src.core.asset_manager import AssetManager
from src.core.event_bus import EventBus
from src.core.scene_manager import SceneManager
from src.core.settings import Settings
from src.scenes.main_menu import MainMenu
from src.scenes.settings_screen import SettingsScreen


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _menu_with_sm(audio=None):
    """Return (MainMenu, mock_sm) using the SceneManager-based constructor."""
    sm = MagicMock(spec=SceneManager)
    menu = MainMenu(sm, Settings(), AssetManager(), audio=audio)
    return menu, sm


def _pushed_scene(sm):
    """Return the single scene that was pushed onto the mock scene manager."""
    assert sm.push.call_count == 1, (
        f"Expected exactly one push, got {sm.push.call_count}"
    )
    return sm.push.call_args[0][0]


# ---------------------------------------------------------------------------
# Audio kwarg storage
# ---------------------------------------------------------------------------

class TestMainMenuAudioStorage:
    def test_audio_kwarg_stored_when_sm_provided(self):
        mock_audio = MagicMock()
        menu, _ = _menu_with_sm(audio=mock_audio)
        assert menu._audio is mock_audio

    def test_audio_is_none_when_kwarg_omitted(self):
        menu, _ = _menu_with_sm()
        assert menu._audio is None

    def test_audio_accepts_arbitrary_object(self):
        sentinel = object()
        menu, _ = _menu_with_sm(audio=sentinel)
        assert menu._audio is sentinel

    def test_audio_none_on_bus_only_constructor(self):
        """Style-1 constructor (settings, assets, bus) must default _audio to None."""
        bus = EventBus()
        menu = MainMenu(Settings(), AssetManager(), bus)
        assert menu._audio is None

    def test_audio_preserved_across_update_calls(self):
        """update() must not clear or modify the stored audio reference."""
        mock_audio = MagicMock()
        menu, _ = _menu_with_sm(audio=mock_audio)
        menu.update(0.016)
        assert menu._audio is mock_audio


# ---------------------------------------------------------------------------
# _on_settings — audio forwarded to SettingsScreen
# ---------------------------------------------------------------------------

class TestMainMenuSettingsScreenAudioForwarding:
    def test_settings_screen_receives_audio_reference(self):
        """The SettingsScreen pushed by _on_settings must hold the same audio ref."""
        mock_audio = MagicMock()
        menu, sm = _menu_with_sm(audio=mock_audio)
        menu._on_settings()
        pushed = _pushed_scene(sm)
        assert isinstance(pushed, SettingsScreen)
        assert pushed._audio is mock_audio

    def test_settings_screen_audio_is_none_when_menu_has_none(self):
        menu, sm = _menu_with_sm(audio=None)
        menu._on_settings()
        pushed = _pushed_scene(sm)
        assert pushed._audio is None

    def test_on_settings_does_not_raise_when_audio_is_none(self):
        menu, _ = _menu_with_sm(audio=None)
        menu._on_settings()  # must not raise

    def test_on_settings_without_sm_falls_back_to_bus_emit(self):
        """When no sm is available, _on_settings emits a bus event instead of pushing."""
        bus = EventBus()
        received = []
        bus.subscribe("scene_request", lambda **kw: received.append(kw))
        menu = MainMenu(Settings(), AssetManager(), bus)
        menu._on_settings()
        assert any(kw.get("scene") == "settings" for kw in received)

    def test_each_settings_open_pushes_exactly_one_scene(self):
        menu, sm = _menu_with_sm(audio=MagicMock())
        menu._on_settings()
        assert sm.push.call_count == 1
