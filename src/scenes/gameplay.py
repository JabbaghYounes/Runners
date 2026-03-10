"""Main gameplay scene — integrates world, entities, round manager, and HUD."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from src.entities.base import Entity
from src.entities.extraction_zone import ExtractionZoneMarker
from src.events import EventBus
from src.map import Camera, TileMap
from src.round import RoundManager, RoundPhase
from src.ui.hud import HUD

if TYPE_CHECKING:
    pass

# Default map path
DEFAULT_MAP = Path("data/maps/map_01.json")


class GameplayScene:
    """The main gameplay scene.

    Owns the game world (tilemap, camera, entities) and orchestrates the
    round lifecycle via ``RoundManager``.  Delegates HUD rendering to
    ``src.ui.hud.HUD``.
    """

    def __init__(self, game, map_path: str | Path | None = None) -> None:
        self.game = game
        self._event_bus: EventBus = getattr(game, "event_bus", EventBus())

        # Settings
        screen_w = getattr(game, "screen_width", 1280)
        screen_h = getattr(game, "screen_height", 720)

        # World
        self._tilemap = TileMap()
        map_file = Path(map_path) if map_path else DEFAULT_MAP
        if map_file.exists():
            self._tilemap.load(map_file)

        self._camera = Camera(screen_w, screen_h)

        # Player (stub entity — full Player class comes from player-movement feature)
        self._player = Entity(x=128.0, y=128.0, health=100, width=32, height=32)
        self._player.alive = True

        # Round manager
        self._round_manager = RoundManager(self._event_bus)
        self._round_manager.start_round(self._player, self._tilemap)

        # Extraction zone visual markers
        self._zone_markers: list[ExtractionZoneMarker] = []
        for zone in self._round_manager.extraction_zones:
            self._zone_markers.append(ExtractionZoneMarker(zone))

        # HUD
        self._hud = HUD(self._event_bus, screen_w, screen_h)

        # Track whether we've already triggered a scene transition
        self._transitioning = False

    # ------------------------------------------------------------------
    # Scene interface
    # ------------------------------------------------------------------

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN:
                # E key — begin extraction if near a zone
                if event.key == pygame.K_e:
                    if (
                        self._round_manager.phase == RoundPhase.PLAYING
                        and self._round_manager.is_near_extraction
                    ):
                        zone = self._round_manager.nearest_extraction_zone
                        if zone is not None:
                            self._round_manager.begin_extraction(zone)

                # Escape — pause (stub, handled by pause scene feature)
                elif event.key == pygame.K_ESCAPE:
                    pass

            # Forward movement keys to player (stub — player-movement feature)
            elif event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
                self._handle_player_input(event)

    def update(self, dt: float) -> None:
        # Update round manager
        self._round_manager.update(dt, self._player)

        # Update player (stub)
        self._player.update(dt)

        # Update camera to follow player
        self._camera.update(self._player.pos, dt)

        # Update extraction zone markers
        for marker in self._zone_markers:
            marker.update(dt)

        # Update HUD
        self._hud.update(dt)

        # Check for round completion → scene transition
        if self._round_manager.is_finished and not self._transitioning:
            self._transitioning = True
            self._handle_round_end()

    def draw(self, surface: pygame.Surface) -> None:
        # Clear
        surface.fill((10, 14, 23))

        # Draw tilemap
        self._tilemap.draw(surface, self._camera)

        # Draw extraction zone markers
        for marker in self._zone_markers:
            marker.draw(surface, self._camera)

        # Draw player (stub)
        self._draw_player(surface)

        # Draw off-screen extraction indicators
        for marker in self._zone_markers:
            marker.draw_indicator(surface, self._camera, self._player.pos)

        # Draw HUD (screen-space, always on top)
        self._hud.draw(surface)

    # ------------------------------------------------------------------
    # Player input handling (stub for player-movement feature)
    # ------------------------------------------------------------------

    def _handle_player_input(self, event: pygame.event.Event) -> None:
        """Forward movement input to the player entity.

        This is a stub — the full player-movement feature will implement
        WASD, sprint, crouch, jump, slide, etc.
        """
        speed = 200.0  # pixels/second placeholder
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_w:
                self._player.velocity.y = -speed
            elif event.key == pygame.K_s:
                self._player.velocity.y = speed
            elif event.key == pygame.K_a:
                self._player.velocity.x = -speed
            elif event.key == pygame.K_d:
                self._player.velocity.x = speed
        elif event.type == pygame.KEYUP:
            if event.key in (pygame.K_w, pygame.K_s):
                self._player.velocity.y = 0
            elif event.key in (pygame.K_a, pygame.K_d):
                self._player.velocity.x = 0

    def _draw_player(self, surface: pygame.Surface) -> None:
        """Draw a placeholder player sprite."""
        screen_pos = self._camera.world_to_screen(self._player.pos)
        player_rect = pygame.Rect(
            int(screen_pos.x) - 16,
            int(screen_pos.y) - 16,
            32,
            32,
        )
        pygame.draw.rect(surface, (0, 200, 255), player_rect)

    # ------------------------------------------------------------------
    # Round-end transitions
    # ------------------------------------------------------------------

    def _handle_round_end(self) -> None:
        """Transition to the appropriate end-of-round scene."""
        result = self._round_manager.result_data
        phase = self._round_manager.phase

        if phase == RoundPhase.EXTRACTED:
            from src.scenes.extraction_summary import ExtractionSummaryScene
            self.game.replace_scene(ExtractionSummaryScene(self.game, result))
        elif phase == RoundPhase.FAILED:
            from src.scenes.game_over import GameOverScene
            self.game.replace_scene(GameOverScene(self.game, result))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release resources and unsubscribe from events."""
        self._round_manager.cleanup()
        self._hud.cleanup()
