"""GameScene — main in-game scene.

Responsibilities relevant to the audio system:
* Track which zone the player currently occupies each frame.
* Emit ``zone_entered`` on the EventBus when the zone changes.
* Forward ``player_is_moving`` and ``dt`` to :meth:`AudioSystem.update`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.systems.audio_system import AudioSystem
    from src.core.settings import Settings
    from src.map.zone import Zone


class _StubPlayer:
    """Minimal player stub until the player feature is implemented."""

    def __init__(self) -> None:
        self.rect = type("Rect", (), {"center": (640, 360), "x": 0, "y": 0})()
        self.velocity_x: float = 0.0
        self.velocity_y: float = 0.0

    @property
    def is_moving(self) -> bool:
        return self.velocity_x != 0.0 or self.velocity_y != 0.0


class GameScene:
    """Main gameplay scene.

    Parameters
    ----------
    event_bus:
        Shared event bus.
    audio:
        The live :class:`AudioSystem` instance (owned by :class:`GameApp`).
    settings:
        Live settings reference.
    zones:
        List of :class:`Zone` objects that make up the current map.  If
        omitted, stub zones are created so the scene is runnable immediately.
    """

    def __init__(
        self,
        event_bus: "EventBus",
        audio: "AudioSystem",
        settings: "Settings",
        zones: Optional[list["Zone"]] = None,
    ) -> None:
        self._event_bus = event_bus
        self._audio = audio
        self._settings = settings

        self._player = _StubPlayer()
        self._zones: list["Zone"] = zones if zones is not None else self._default_zones()
        self._prev_zone: Optional["Zone"] = None

    # ------------------------------------------------------------------
    # Scene lifecycle
    # ------------------------------------------------------------------

    def handle_events(self, events: list) -> None:
        """Process raw pygame events (input forwarded to player, etc.)."""
        try:
            import pygame
            for evt in events:
                if evt.type == pygame.KEYDOWN:
                    if evt.key == pygame.K_w:
                        self._player.velocity_y = -200.0
                    elif evt.key == pygame.K_s:
                        self._player.velocity_y = 200.0
                    elif evt.key == pygame.K_a:
                        self._player.velocity_x = -200.0
                    elif evt.key == pygame.K_d:
                        self._player.velocity_x = 200.0
                elif evt.type == pygame.KEYUP:
                    if evt.key in (pygame.K_w, pygame.K_s):
                        self._player.velocity_y = 0.0
                    elif evt.key in (pygame.K_a, pygame.K_d):
                        self._player.velocity_x = 0.0
        except Exception:
            pass

    def update(self, dt: float) -> None:
        """Update all game systems; must be called every frame.

        Zone-change detection fires ``zone_entered`` on the EventBus when the
        player crosses into a new zone.  ``AudioSystem.update`` is called last,
        after all other in-game systems.
        """
        # --- Move player (stub physics) ---
        self._player.rect.x = int(
            self._player.rect.x + self._player.velocity_x * dt
        )
        self._player.rect.y = int(
            self._player.rect.y + self._player.velocity_y * dt
        )
        self._player.rect.center = (self._player.rect.x, self._player.rect.y)

        # --- Zone detection ---
        current_zone = self._zone_for_player()
        if current_zone is not self._prev_zone:
            if current_zone is not None:
                self._event_bus.emit("zone_entered", zone=current_zone)
            self._prev_zone = current_zone

        # --- Audio (always last) ---
        self._audio.update(dt, player_is_moving=self._player.is_moving)

    def render(self, screen: object) -> None:
        """Draw the game world."""
        # Stub: draw zone outlines + player dot using pygame when available.
        try:
            import pygame
            for zone in self._zones:
                pygame.draw.rect(screen, (30, 60, 80), zone.rect, 2)
            cx, cy = self._player.rect.center
            pygame.draw.circle(screen, (0, 255, 180), (cx, cy), 8)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _zone_for_player(self) -> Optional["Zone"]:
        """Return the first zone that contains the player, or *None*."""
        pos = self._player.rect.center
        for zone in self._zones:
            if zone.contains(pos):
                return zone
        return None

    @staticmethod
    def _default_zones() -> list["Zone"]:
        """Return three stub zones for testing without a real map."""
        from src.map.zone import Zone
        import os
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        def music(name: str) -> str:
            return os.path.join(root, "assets", "audio", "music", f"{name}.ogg")

        return [
            Zone("zone_alpha", (0,    0, 426, 720), music_track=music("zone_alpha")),
            Zone("zone_beta",  (426,  0, 427, 720), music_track=music("zone_beta")),
            Zone("zone_gamma", (853,  0, 427, 720), music_track=music("zone_gamma")),
        ]
