import pygame
from typing import Any, Optional, Dict

class AudioSystem:
    def __init__(self, event_bus: Any, assets: Any):
        self._event_bus = event_bus
        self._assets = assets
        self._current_track: Optional[str] = None
        self._mixer_ok: bool = False
        self._init_mixer()
        self._subscribe_events()

    def _init_mixer(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._mixer_ok = True
        except Exception:
            self._mixer_ok = False

    def _subscribe_events(self) -> None:
        self._event_bus.subscribe('zone_entered', self._on_zone_entered)

    def _on_zone_entered(self, **kwargs: Any) -> None:
        zone = kwargs.get('zone')
        if zone and hasattr(zone, 'music_track') and zone.music_track:
            self.play_music(zone.music_track)

    def play_music(self, track: str) -> None:
        if not self._mixer_ok or track == self._current_track:
            return
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.play(-1)
            self._current_track = track
        except Exception:
            pass

    def play_sfx(self, name: str) -> None:
        if not self._mixer_ok:
            return
        sound = self._assets.load_sound(name)
        if sound:
            try:
                sound.play()
            except Exception:
                pass

    def update(self, zone_name: str = '') -> None:
        pass

    def set_volume(self, master: float, music: float, sfx: float) -> None:
        if not self._mixer_ok:
            return
        try:
            pygame.mixer.music.set_volume(master * music)
        except Exception:
            pass
