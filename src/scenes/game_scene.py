"""GameScene — main in-game scene.

Responsibilities relevant to the audio system:
* Track which zone the player currently occupies each frame.
* Emit ``zone_entered`` on the EventBus when the zone changes.
* Forward ``player_is_moving`` and ``dt`` to :meth:`AudioSystem.update`

Enemy AI responsibilities (enemy-ai-pve feature):
* Own the ``enemies`` list; instantiate via EnemyDatabase + SpawnSystem.
* Call AISystem.update() each frame, then purge dead robots.
* Depth-sort and render enemies by ``rect.bottom``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.systems.audio_system import AudioSystem
    from src.core.settings import Settings
    from src.map.zone import Zone


# ---------------------------------------------------------------------------
# Stub player — replaced once player-character feature lands
# ---------------------------------------------------------------------------

class _StubPlayer:
    """Minimal player stub until the player feature is implemented."""

    def __init__(self) -> None:
        self.rect = type("Rect", (), {"center": (640, 360), "x": 0, "y": 0,
                                      "centerx": 640, "centery": 360})()
        self.velocity_x = 0.0
        self.velocity_y = 0.0

    @property
    def is_moving(self) -> bool:
        return self.velocity_x != 0.0 or self.velocity_y != 0.0


# ---------------------------------------------------------------------------
# GameScene
# ---------------------------------------------------------------------------

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
        zones: Optional[List["Zone"]] = None,
    ) -> None:
        self._event_bus = event_bus
        self._audio = audio
        self._settings = settings

        self._player = _StubPlayer()
        self._zones: List["Zone"] = (
            zones if zones is not None else self._default_zones()
        )
        self._prev_zone: Optional["Zone"] = None
        self._tilemap: object = None

        # --- Enemy AI subsystems (enemy-ai-pve feature) ---
        from src.systems.ai_system import AISystem
        self._ai_system = AISystem()
        self.enemies: list = []
        self._init_enemies()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_enemies(self) -> None:
        """Attempt to load enemy config and populate self.enemies."""
        try:
            from src.data.enemy_database import EnemyDatabase
            from src.systems.spawn_system import SpawnSystem
            enemy_db = EnemyDatabase()
            spawn = SpawnSystem()
            self.enemies = spawn.spawn_all_zones(self._zones, enemy_db)
        except FileNotFoundError:
            # enemies.json not yet present — safe to skip.
            self.enemies = []
        except Exception:
            # Any other config or import error must not crash the scene.
            self.enemies = []

    # ------------------------------------------------------------------
    # Scene interface
    # ------------------------------------------------------------------

    def handle_events(self, events: list) -> None:
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
        # --- Player movement (stub) ---
        self._player.rect.x = int(self._player.rect.x + self._player.velocity_x * dt)
        self._player.rect.y = int(self._player.rect.y + self._player.velocity_y * dt)
        self._player.rect.center = (self._player.rect.x, self._player.rect.y)

        # --- Zone detection ---
        current_zone = self._zone_for_player()
        if current_zone is not self._prev_zone:
            if current_zone is not None:
                self._event_bus.emit("zone_entered", {"zone": current_zone})
            self._prev_zone = current_zone

        # --- Audio ---
        self._audio.update(dt, player_is_moving=self._player.is_moving)

        # --- Enemy AI ---
        self._ai_system.update(
            self.enemies, self._player, self._tilemap, dt, self._event_bus
        )
        # Purge robots whose death animation has finished.
        self.enemies = [e for e in self.enemies if e.alive]

    def render(self, screen: object) -> None:
        try:
            import pygame

            # Draw zone outlines.
            for zone in self._zones:
                pygame.draw.rect(screen, (30, 60, 80), zone.rect, 2)

            # Depth-sort enemies by their bottom edge (Y-order rendering).
            sorted_enemies = sorted(
                self.enemies,
                key=lambda e: getattr(getattr(e, "rect", None), "bottom", e.y + e.height),
            )
            for robot in sorted_enemies:
                if getattr(robot, "visible", True):
                    robot.render(screen, (0.0, 0.0))

            # Draw player (placeholder rectangle).
            pygame.draw.rect(screen, (0, 245, 255), self._player.rect)

        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _zone_for_player(self) -> Optional["Zone"]:
        """Return the first zone that contains the player's position, or None."""
        pos = self._player.rect.center
        for zone in self._zones:
            if zone.contains(pos):
                return zone
        return None

    @staticmethod
    def _default_zones() -> List["Zone"]:
        """Create three placeholder zones that span a 1 280 × 720 world."""
        from src.map.zone import Zone
        return [
            Zone(
                name="zone_alpha",
                rect=(0, 0, 427, 720),
                music_track="assets/audio/music/zone_alpha.ogg",
            ),
            Zone(
                name="zone_beta",
                rect=(427, 0, 426, 720),
                music_track="assets/audio/music/zone_beta.ogg",
            ),
            Zone(
                name="zone_gamma",
                rect=(853, 0, 427, 720),
                music_track="assets/audio/music/zone_gamma.ogg",
            ),
        ]
