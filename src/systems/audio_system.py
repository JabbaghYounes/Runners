"""Audio system — music and SFX management."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.core.asset_manager import AssetManager
    from src.core.settings import Settings
    from src.map.zone import Zone


class AudioSystem:
    """Manages background music and sound effects.

    Design notes:
    - Subscribes to EventBus events for SFX triggers.
    - Swaps background music on zone transition.
    - Silent fallback if pygame.mixer is unavailable.
    """

    def __init__(self, event_bus, asset_manager, settings) -> None:
        self._event_bus = event_bus
        self._asset_manager = asset_manager
        self._settings = settings
        self._current_track: str | None = None
        self._sfx_cache: dict = {}
        self._init_mixer()
        self._subscribe_events()

    def _init_mixer(self) -> None:
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception:
            pass

    def _load_sfx(self, name: str):
        if name not in self._sfx_cache:
            self._sfx_cache[name] = self._asset_manager.load_sound(
                f"assets/audio/sfx/{name}.wav"
            )
        return self._sfx_cache[name]

    def _subscribe_events(self) -> None:
        self._event_bus.subscribe("zone_entered", self._on_zone_entered)

    def play_music(self, track: str) -> None:
        if track == self._current_track:
            return
        try:
            import pygame
            path = f"assets/audio/music/{track}.ogg"
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(
                self._settings.master_volume * self._settings.music_volume
            )
            pygame.mixer.music.play(-1)
            self._current_track = track
        except Exception:
            pass

    def stop_music(self) -> None:
        try:
            import pygame
            pygame.mixer.music.stop()
            self._current_track = None
        except Exception:
            pass

    def play_sfx(self, name: str) -> None:
        sound = self._load_sfx(name)
        if sound:
            try:
                sound.set_volume(
                    self._settings.master_volume * self._settings.sfx_volume
                )
                sound.play()
            except Exception:
                pass

    def apply_volumes(self) -> None:
        try:
            import pygame
            vol = self._settings.master_volume * self._settings.music_volume
            pygame.mixer.music.set_volume(vol)
        except Exception:
            pass

    def update(self, player_zone=None) -> None:
        pass

    def _on_zone_entered(self, payload: dict) -> None:
        zone = payload.get("zone")
        if zone and hasattr(zone, "music_track") and zone.music_track:
            self.play_music(zone.music_track)
