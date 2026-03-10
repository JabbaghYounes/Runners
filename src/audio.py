"""Centralised audio system: zone-based music with crossfade and pooled SFX.

The :class:`AudioManager` is the single service responsible for all game audio.
It is owned by the ``Game`` core object and updated once per frame.

Usage::

    settings = Settings.load()
    bus = EventBus()
    audio = AudioManager(settings, bus)

    # Each frame inside the gameplay loop:
    audio.update(dt, current_zone="challenge")

    # Direct SFX trigger (e.g. footsteps from player code):
    audio.play_sfx("footstep")
"""

from __future__ import annotations

import enum
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.events import EventBus
    from src.settings import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Asset registries – paths relative to project root
# ---------------------------------------------------------------------------

SOUND_REGISTRY: dict[str, str] = {
    "shoot": "assets/sounds/shoot.wav",
    "reload": "assets/sounds/reload.wav",
    "footstep": "assets/sounds/footstep.wav",
    "robot_attack": "assets/sounds/robot_attack.wav",
    "pickup": "assets/sounds/pickup.wav",
    "extraction": "assets/sounds/extraction.wav",
    "hit": "assets/sounds/hit.wav",
}

MUSIC_REGISTRY: dict[str, str] = {
    "menu": "assets/music/menu.ogg",
    "spawn": "assets/music/zone_spawn.ogg",
    "challenge": "assets/music/zone_challenge.ogg",
    "extraction": "assets/music/zone_extraction.ogg",
}

# ---------------------------------------------------------------------------
# Footstep cooldown intervals per movement state (seconds)
# ---------------------------------------------------------------------------

FOOTSTEP_INTERVALS: dict[str, float] = {
    "walk": 0.5,
    "sprint": 0.3,
    "crouch": 0.7,
}


# ---------------------------------------------------------------------------
# Crossfade state machine
# ---------------------------------------------------------------------------

class _FadeState(enum.Enum):
    IDLE = "idle"
    FADING_OUT = "fading_out"
    LOADING = "loading"
    FADING_IN = "fading_in"


# ---------------------------------------------------------------------------
# NullSound – silent no-op stand-in for missing audio files
# ---------------------------------------------------------------------------

class NullSound:
    """Drop-in replacement for :class:`pygame.mixer.Sound`.

    Every method is a harmless no-op so callers never need to check
    whether a real Sound was loaded.
    """

    def play(self, *args, **kwargs) -> None:  # noqa: D401
        pass

    def stop(self) -> None:
        pass

    def set_volume(self, volume: float) -> None:
        pass

    def get_length(self) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# AudioManager
# ---------------------------------------------------------------------------

class AudioManager:
    """Manages all game audio: zone-based background music with smooth
    crossfade transitions and pooled sound effects triggered by game
    events or direct calls.

    Parameters
    ----------
    settings:
        Provides ``music_volume`` and ``sfx_volume`` (0.0–1.0).
    event_bus:
        Optional :class:`EventBus` – if provided the manager subscribes
        to gameplay events and plays matching SFX automatically.
    fade_duration:
        Time in seconds for a full crossfade transition (out + in).
    """

    def __init__(
        self,
        settings: Settings,
        event_bus: EventBus | None = None,
        fade_duration: float = 1.0,
    ) -> None:
        self._settings = settings
        self._event_bus = event_bus
        self._enabled: bool = True

        # Crossfade configuration
        self._fade_duration = fade_duration
        self._fade_speed: float = 1.0 / (fade_duration / 2.0) if fade_duration > 0 else 100.0

        # Crossfade state
        self._fade_state: _FadeState = _FadeState.IDLE
        self._current_zone: str | None = None
        self._target_zone: str | None = None
        self._queued_zone: str | None = None
        self._fade_volume: float = 0.0  # current interpolated music volume

        # SFX pool
        self._sounds: dict[str, object] = {}  # str -> Sound | NullSound

        # Footstep cooldown tracking
        self._footstep_timer: float = 0.0

        # --- Pygame mixer initialisation ---
        try:
            import pygame
            self._pygame = pygame

            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 512)
                pygame.mixer.init()

            pygame.mixer.set_num_channels(16)
        except Exception as exc:
            logger.warning("Audio mixer initialisation failed: %s – audio disabled.", exc)
            self._enabled = False
            self._pygame = None

        # Pre-load SFX
        self._load_all_sounds()

        # Subscribe to EventBus
        if self._event_bus is not None:
            self._subscribe_events()

    # ------------------------------------------------------------------
    # Music – public API
    # ------------------------------------------------------------------

    def update(self, dt: float, current_zone: str | None = None) -> None:
        """Called once per frame to drive zone-based music transitions.

        Parameters
        ----------
        dt:
            Frame delta time in seconds.
        current_zone:
            The zone name the player is currently in (e.g. ``"spawn"``,
            ``"challenge"``, ``"extraction"``).  ``None`` means no zone.
        """
        if not self._enabled:
            return

        # Tick footstep cooldown
        if self._footstep_timer > 0:
            self._footstep_timer -= dt

        # Detect zone change
        if current_zone is not None and current_zone != self._current_zone:
            if current_zone in MUSIC_REGISTRY:
                self._request_zone_change(current_zone)

        # Drive crossfade FSM
        self._fade_step(dt)

    def play_music(self, zone_name: str) -> None:
        """Immediately start playing the track for *zone_name* (no fade).

        Useful for the very first track when entering a scene.
        """
        if not self._enabled:
            return
        path = MUSIC_REGISTRY.get(zone_name)
        if path is None:
            logger.warning("No music track mapped for zone '%s'.", zone_name)
            return
        if not Path(path).exists():
            logger.warning("Music file missing: %s – skipping.", path)
            return
        try:
            self._pygame.mixer.music.load(path)
            self._pygame.mixer.music.set_volume(self._settings.music_volume)
            self._pygame.mixer.music.play(-1)  # loop indefinitely
            self._current_zone = zone_name
            self._fade_state = _FadeState.IDLE
            self._fade_volume = self._settings.music_volume
        except Exception as exc:
            logger.warning("Failed to play music for zone '%s': %s", zone_name, exc)

    def stop_music(self, fade_ms: int = 1000) -> None:
        """Stop background music with an optional fade-out."""
        if not self._enabled:
            return
        try:
            self._pygame.mixer.music.fadeout(fade_ms)
        except Exception as exc:
            logger.warning("Failed to stop music: %s", exc)
        self._current_zone = None
        self._fade_state = _FadeState.IDLE

    def set_music_volume(self, volume: float) -> None:
        """Update music volume.  Clamped to ``[0.0, 1.0]``."""
        volume = max(0.0, min(1.0, volume))
        self._settings.music_volume = volume
        if not self._enabled:
            return
        try:
            # Only set mixer volume when we are not mid-fade (otherwise
            # the fade step manages the mixer volume each frame).
            if self._fade_state == _FadeState.IDLE:
                self._pygame.mixer.music.set_volume(volume)
            self._fade_volume = volume
        except Exception as exc:
            logger.warning("Failed to set music volume: %s", exc)

    # ------------------------------------------------------------------
    # SFX – public API
    # ------------------------------------------------------------------

    def play_sfx(self, name: str, volume: float | None = None) -> None:
        """Play a named sound effect.

        Parameters
        ----------
        name:
            Key from :data:`SOUND_REGISTRY` (e.g. ``"shoot"``).
        volume:
            Optional override.  Falls back to ``settings.sfx_volume``.
        """
        if not self._enabled:
            return
        sound = self._sounds.get(name)
        if sound is None:
            logger.debug("Unknown SFX name: '%s'.", name)
            return
        if isinstance(sound, NullSound):
            return
        vol = volume if volume is not None else self._settings.sfx_volume
        vol = max(0.0, min(1.0, vol))
        try:
            sound.set_volume(vol)
            sound.play()
        except Exception as exc:
            logger.warning("Failed to play SFX '%s': %s", name, exc)

    def play_footstep(self, movement_state: str, dt: float) -> None:
        """Rate-limited footstep SFX.

        Call every frame while the player is grounded and moving.
        ``movement_state`` should be ``"walk"``, ``"sprint"``, or
        ``"crouch"``.  Other states (idle, jump, slide) are ignored.

        Parameters
        ----------
        movement_state:
            One of ``"walk"``, ``"sprint"``, ``"crouch"``.
        dt:
            Frame delta time (unused directly — cooldown tracked internally
            via :meth:`update`).
        """
        interval = FOOTSTEP_INTERVALS.get(movement_state)
        if interval is None:
            return  # idle / jump / slide — no footstep
        if self._footstep_timer <= 0:
            self.play_sfx("footstep")
            self._footstep_timer = interval

    def set_sfx_volume(self, volume: float) -> None:
        """Update SFX volume.  Clamped to ``[0.0, 1.0]``."""
        self._settings.sfx_volume = max(0.0, min(1.0, volume))

    # ------------------------------------------------------------------
    # EventBus callbacks
    # ------------------------------------------------------------------

    def _on_shot_fired(self, **data) -> None:
        self.play_sfx("shoot")

    def _on_reload(self, **data) -> None:
        self.play_sfx("reload")

    def _on_item_picked_up(self, **data) -> None:
        self.play_sfx("pickup")

    def _on_extraction_started(self, **data) -> None:
        self.play_sfx("extraction")

    def _on_extraction_complete(self, **data) -> None:
        self.play_sfx("extraction")

    def _on_entity_hit(self, **data) -> None:
        self.play_sfx("hit")

    def _on_enemy_attack(self, **data) -> None:
        self.play_sfx("robot_attack")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        """Wire up EventBus subscriptions."""
        bus = self._event_bus
        if bus is None:
            return
        bus.subscribe("shot_fired", self._on_shot_fired)
        bus.subscribe("reload", self._on_reload)
        bus.subscribe("item_picked_up", self._on_item_picked_up)
        bus.subscribe("extraction_started", self._on_extraction_started)
        bus.subscribe("extraction_complete", self._on_extraction_complete)
        bus.subscribe("entity_hit", self._on_entity_hit)
        bus.subscribe("enemy_attack", self._on_enemy_attack)

    def _load_all_sounds(self) -> None:
        """Pre-load every entry in :data:`SOUND_REGISTRY`."""
        for name, path in SOUND_REGISTRY.items():
            self._sounds[name] = self._load_sound(path)

    def _load_sound(self, path: str) -> object:
        """Attempt to load a :class:`pygame.mixer.Sound`.

        Returns a :class:`NullSound` on any failure so callers never
        need to handle ``None``.
        """
        if not self._enabled:
            return NullSound()
        if not Path(path).exists():
            logger.warning("Sound file missing: %s – using silent fallback.", path)
            return NullSound()
        try:
            return self._pygame.mixer.Sound(path)
        except Exception as exc:
            logger.warning("Failed to load sound %s: %s – using silent fallback.", path, exc)
            return NullSound()

    # ------------------------------------------------------------------
    # Crossfade state machine
    # ------------------------------------------------------------------

    def _request_zone_change(self, zone_name: str) -> None:
        """Initiate (or queue) a zone-music transition."""
        if self._fade_state == _FadeState.IDLE:
            # Start a fresh crossfade — begin from current music volume
            self._target_zone = zone_name
            self._fade_volume = self._settings.music_volume
            self._fade_state = _FadeState.FADING_OUT
        else:
            # A transition is already running — queue the new zone.
            # The current transition will pick this up when it reaches
            # LOADING and re-evaluate.
            self._queued_zone = zone_name

    def _fade_step(self, dt: float) -> None:
        """Advance the crossfade FSM by one frame."""
        if self._fade_state == _FadeState.IDLE:
            return

        if self._fade_state == _FadeState.FADING_OUT:
            self._fade_volume -= self._fade_speed * dt
            if self._fade_volume <= 0.0:
                self._fade_volume = 0.0
                self._fade_state = _FadeState.LOADING
            try:
                self._pygame.mixer.music.set_volume(max(0.0, self._fade_volume))
            except Exception:
                pass

        if self._fade_state == _FadeState.LOADING:
            # If a newer zone was queued while we were fading out, use
            # that instead.
            if self._queued_zone is not None:
                self._target_zone = self._queued_zone
                self._queued_zone = None

            zone = self._target_zone
            path = MUSIC_REGISTRY.get(zone, "") if zone else ""
            if path and Path(path).exists():
                try:
                    self._pygame.mixer.music.load(path)
                    self._pygame.mixer.music.set_volume(0.0)
                    self._pygame.mixer.music.play(-1)
                except Exception as exc:
                    logger.warning("Failed to load zone music '%s': %s", zone, exc)
                    self._fade_state = _FadeState.IDLE
                    return
            else:
                # No valid track – abort transition and stay silent.
                logger.warning("No playable track for zone '%s' – aborting crossfade.", zone)
                self._current_zone = zone
                self._fade_state = _FadeState.IDLE
                return

            self._current_zone = zone
            self._fade_state = _FadeState.FADING_IN
            self._fade_volume = 0.0

        if self._fade_state == _FadeState.FADING_IN:
            target = self._settings.music_volume
            self._fade_volume += self._fade_speed * dt
            if self._fade_volume >= target:
                self._fade_volume = target
                self._fade_state = _FadeState.IDLE
            try:
                self._pygame.mixer.music.set_volume(max(0.0, min(1.0, self._fade_volume)))
            except Exception:
                pass
