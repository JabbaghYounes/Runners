"""AudioSystem — manages background music and sound effects.

Design principles:
* Single responsibility: owns ``pygame.mixer.music`` (BGM) and a dict of
  ``pygame.mixer.Sound`` objects (SFX).
* Safe by default: if ``pygame.mixer`` cannot be initialised (no audio
  device), every public method becomes a no-op so the game still runs.
* Decoupled: listens for game events via :class:`EventBus`; no scene or
  system imports this module directly (they just emit events).
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.core.asset_manager import AssetManager
    from src.core.settings import Settings
    from src.map.zone import Zone

# Paths relative to project root
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SFX_DIR = os.path.join(_ROOT, "assets", "audio", "sfx")

# SFX filename map:  logical name → filename under assets/audio/sfx/
_SFX_MAP: dict[str, str] = {
    "shoot":              "shoot.wav",
    "reload":             "reload.wav",
    "footstep":           "footstep.wav",
    "robot_attack":       "robot_attack.wav",
    "loot_pickup":        "loot_pickup.wav",
    "extraction_success": "extraction_success.wav",
    "extraction_fail":    "extraction_fail.wav",
}

# Time between footstep SFX (seconds)
_FOOTSTEP_INTERVAL: float = 0.35


class AudioSystem:
    """Owns and drives all audio output for the game.

    Parameters
    ----------
    event_bus:
        Shared :class:`EventBus` instance.  AudioSystem subscribes to the
        events it cares about in ``__init__``.
    asset_manager:
        Cache-backed loader; used to load ``pygame.mixer.Sound`` objects.
    settings:
        Live :class:`Settings` reference — volumes are read from here in
        :meth:`apply_volumes`.
    """

    def __init__(
        self,
        event_bus: "EventBus",
        asset_manager: "AssetManager",
        settings: "Settings",
    ) -> None:
        self._event_bus = event_bus
        self._asset_manager = asset_manager
        self._settings = settings

        self._mixer_ok: bool = self._init_mixer()
        self._sfx_sounds: dict[str, object] = {}   # name → Sound | None
        self._current_track: str | None = None
        self._footstep_timer: float = 0.0

        self._load_sfx()
        self._subscribe_events()
        self.apply_volumes()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _init_mixer() -> bool:
        """Attempt to initialise ``pygame.mixer``; return success flag."""
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
            self._sfx_sounds[name] = self._asset_manager.load_sound(path)

    def _subscribe_events(self) -> None:
        eb = self._event_bus
        eb.subscribe("zone_entered",       self._on_zone_entered)
        eb.subscribe("player_shot",        lambda **_: self.play_sfx("shoot"))
        eb.subscribe("player_reloaded",    lambda **_: self.play_sfx("reload"))
        eb.subscribe("enemy_attack",       lambda **_: self.play_sfx("robot_attack"))
        eb.subscribe("item_picked_up",     lambda **_: self.play_sfx("loot_pickup"))
        eb.subscribe("extraction_success", lambda **_: self.play_sfx("extraction_success"))
        eb.subscribe("extraction_failed",  lambda **_: self.play_sfx("extraction_fail"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play_music(self, track_path: str) -> None:
        """Fade out current BGM then fade in *track_path* (looping).

        No-op when the mixer is unavailable or *track_path* is already
        playing.
        """
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
        """Stop background music immediately."""
        if not self._mixer_ok:
            return
        try:
            import pygame
            pygame.mixer.music.stop()
            self._current_track = None
        except Exception:
            pass

    def play_sfx(self, name: str) -> None:
        """Play a one-shot sound effect by logical *name*.

        Non-blocking — pygame handles channel mixing automatically.
        No-op when the mixer is unavailable or *name* is unknown.
        """
        if not self._mixer_ok:
            return
        sound = self._sfx_sounds.get(name)
        if sound is None:
            return
        try:
            sound.play()  # type: ignore[union-attr]
        except Exception:
            pass

    def apply_volumes(self) -> None:
        """Re-apply volume settings to all mixer objects.

        Must be called after any :class:`Settings` volume field is changed.
        """
        if not self._mixer_ok:
            return
        s = self._settings
        eff_music = max(0.0, min(1.0, s.volume_master * s.volume_music))
        eff_sfx   = max(0.0, min(1.0, s.volume_master * s.volume_sfx))
        try:
            import pygame
            pygame.mixer.music.set_volume(eff_music)
        except Exception:
            pass
        for sound in self._sfx_sounds.values():
            if sound is not None:
                try:
                    sound.set_volume(eff_sfx)  # type: ignore[union-attr]
                except Exception:
                    pass

    def update(self, dt: float, player_is_moving: bool = False) -> None:
        """Advance audio logic by *dt* seconds.

        Must be called every game frame (after all other systems).

        Parameters
        ----------
        dt:
            Elapsed time in **seconds** since the last frame.
        player_is_moving:
            ``True`` when the player has non-zero velocity this frame.
        """
        if not self._mixer_ok:
            return
        if player_is_moving:
            self._footstep_timer += dt
            if self._footstep_timer >= _FOOTSTEP_INTERVAL:
                self.play_sfx("footstep")
                self._footstep_timer = 0.0
        else:
            self._footstep_timer = 0.0

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_zone_entered(self, zone: "Zone" = None, **_: object) -> None:  # type: ignore[assignment]
        if zone is None:
            return
        track = getattr(zone, "music_track", None)
        if track:
            self.play_music(track)
        else:
            self.stop_music()
