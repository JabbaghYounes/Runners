"""AudioSystem -- manages background music and sound effects."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.core.asset_manager import AssetManager
    from src.core.settings import Settings
    from src.map.zone import Zone

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SFX_DIR = os.path.join(_ROOT, "assets", "audio", "sfx")

_SFX_MAP: dict[str, str] = {
    "shoot":              "shoot.wav",
    "reload":             "reload.wav",
    "footstep":           "footstep.wav",
    "robot_attack":       "robot_attack.wav",
    "loot_pickup":        "loot_pickup.wav",
    "extraction_success": "extraction_success.wav",
    "extraction_fail":    "extraction_fail.wav",
}

_FOOTSTEP_INTERVAL: float = 0.35


class AudioSystem:
    """Owns and drives all audio output for the game."""

    def __init__(
        self,
        event_bus: "EventBus",
        asset_manager: "AssetManager",
        settings: "Settings | None" = None,
    ) -> None:
        self._event_bus = event_bus
        self._asset_manager = asset_manager
        self._settings = settings

        self._mixer_ok: bool = self._init_mixer()
        self._sfx_sounds: dict[str, object] = {}
        self._current_track: str | None = None
        self._footstep_timer: float = 0.0

        self._load_sfx()
        self._subscribe_events()
        if settings is not None:
            self.apply_volumes()

    @staticmethod
    def _init_mixer() -> bool:
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, buffer=512)
            return True
        except Exception:
            return False

    def _load_sfx(self) -> None:
        for name, filename in _SFX_MAP.items():
            path = os.path.join(_SFX_DIR, filename)
            try:
                self._sfx_sounds[name] = self._asset_manager.load_sound(path)
            except Exception:
                self._sfx_sounds[name] = None

    def _subscribe_events(self) -> None:
        eb = self._event_bus
        eb.subscribe("zone_entered", self._on_zone_entered)
        eb.subscribe("player_shot", lambda **_: self.play_sfx("shoot"))
        eb.subscribe("player_reloaded", lambda **_: self.play_sfx("reload"))
        eb.subscribe("enemy_attack", lambda **_: self.play_sfx("robot_attack"))
        eb.subscribe("item_picked_up", lambda **_: self.play_sfx("loot_pickup"))
        eb.subscribe("extraction_success", lambda **_: self.play_sfx("extraction_success"))
        eb.subscribe("extraction_failed", lambda **_: self.play_sfx("extraction_fail"))

    def play_music(self, track_path: str) -> None:
        if not self._mixer_ok:
            return
        if track_path == self._current_track:
            return
        try:
            import pygame
            pygame.mixer.music.fadeout(500)
            pygame.mixer.music.load(track_path)
            pygame.mixer.music.play(loops=-1, fade_ms=500)
            self._current_track = track_path
        except Exception:
            pass

    def stop_music(self) -> None:
        if not self._mixer_ok:
            return
        try:
            import pygame
            pygame.mixer.music.stop()
            self._current_track = None
        except Exception:
            pass

    def play_sfx(self, name: str) -> None:
        if not self._mixer_ok:
            return
        sound = self._sfx_sounds.get(name)
        if sound is None:
            return
        try:
            sound.play()
        except Exception:
            pass

    def apply_volumes(self) -> None:
        if not self._mixer_ok or self._settings is None:
            return
        s = self._settings
        master = getattr(s, 'master_volume', getattr(s, 'volume_master', 1.0))
        music = getattr(s, 'music_volume', getattr(s, 'volume_music', 0.7))
        sfx = getattr(s, 'sfx_volume', getattr(s, 'volume_sfx', 1.0))
        eff_music = max(0.0, min(1.0, master * music))
        eff_sfx = max(0.0, min(1.0, master * sfx))
        try:
            import pygame
            pygame.mixer.music.set_volume(eff_music)
        except Exception:
            pass
        for sound in self._sfx_sounds.values():
            if sound is not None:
                try:
                    sound.set_volume(eff_sfx)
                except Exception:
                    pass

    def set_volume(self, master: float, music: float, sfx: float) -> None:
        if not self._mixer_ok:
            return
        try:
            import pygame
            pygame.mixer.music.set_volume(master * music)
        except Exception:
            pass

    def update(self, dt: float = 0.0, player_is_moving: bool = False, zone_name: str = '') -> None:
        if not self._mixer_ok:
            return
        if player_is_moving:
            self._footstep_timer += dt
            if self._footstep_timer >= _FOOTSTEP_INTERVAL:
                self.play_sfx("footstep")
                self._footstep_timer = 0.0
        else:
            self._footstep_timer = 0.0

    def _on_zone_entered(self, zone: "Zone" = None, **_: object) -> None:
        if zone is None:
            return
        track = getattr(zone, "music_track", None)
        if track:
            self.play_music(track)
        else:
            self.stop_music()
