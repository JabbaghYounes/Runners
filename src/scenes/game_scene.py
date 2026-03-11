"""GameScene — main in-game scene.

Responsibilities relevant to the audio system:
* Track which zone the player currently occupies each frame.
* Emit ``zone_entered`` on the EventBus when the zone changes.
* Forward ``player_is_moving`` and ``dt`` to :meth:`AudioSystem.update`
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.progression.home_base import HomeBase

from src.core.event_bus import EventBus
from src.systems.audio_system import AudioSystem
from src.core.settings import Settings
from src.map.zone import Zone


class _StubPlayer:
    """Minimal player stub used until the full player entity is wired in."""

    def __init__(self) -> None:
        import pygame
        self.rect = pygame.Rect(-200, 200, 32, 48)
        self.health: int = 100
        self.max_health: int = 100
        from src.inventory.inventory import Inventory
        self.inventory = Inventory()

    def is_moving(self) -> bool:
        return False


class GameScene:
    """Main in-round game scene.

    Args:
        event_bus: Shared EventBus instance.
        audio: AudioSystem for music/SFX.
        settings: Settings object.
        zones: List of Zone objects, or None to use default stubs.
        home_base: Optional HomeBase — bonuses applied to player at round start.
    """

    def __init__(
        self,
        event_bus: EventBus,
        audio: AudioSystem,
        settings: Settings,
        zones=None,
        home_base=None,
    ) -> None:
        self._event_bus = event_bus
        self._audio = audio
        self._settings = settings
        self._zones: list[Zone] = zones if zones is not None else self._default_zones()
        self._current_zone: Optional[Zone] = None

        # Round-scoped bonus from home base upgrades (used by PostRound for loot tally)
        self.loot_value_bonus: float = 0.0

        # Create stub player and apply HomeBase bonuses
        self._player = _StubPlayer()
        self._apply_home_base_bonuses(self._player, home_base)

    # ------------------------------------------------------------------
    # HomeBase bonus application
    # ------------------------------------------------------------------

    def _apply_home_base_bonuses(self, player, home_base) -> None:
        """Apply round-start stat bonuses derived from facility upgrade levels.

        Args:
            player: The player entity to modify.
            home_base: HomeBase instance, or None (no-op).
        """
        if home_base is None:
            return
        bonuses = home_base.get_round_bonuses()

        # Extra starting HP
        extra_hp = bonuses.get("extra_hp", 0)
        if extra_hp:
            player.health += extra_hp
            player.max_health += extra_hp

        # Extra inventory slots
        extra_slots = bonuses.get("extra_slots", 0)
        if extra_slots > 0:
            player.inventory.expand_capacity(extra_slots)

        # Loot value multiplier — store for PostRound to apply
        self.loot_value_bonus = bonuses.get("loot_value_bonus", 0.0)

    # ------------------------------------------------------------------
    # Zone helpers
    # ------------------------------------------------------------------

    def _zone_for_player(self, pos) -> Optional[Zone]:
        """Return the first zone that contains the player, or *None*."""
        for zone in self._zones:
            if zone.contains(pos):
                return zone
        return None

    @staticmethod
    def _default_zones() -> list[Zone]:
        """Return three stub zones for testing without a real map."""
        import pygame

        def music(name: str) -> str:
            return name

        return [
            Zone("zone_alpha", pygame.Rect(0, 0, 640, 360),    music_track=music("zone_alpha")),
            Zone("zone_beta",  pygame.Rect(640, 0, 640, 360),  music_track=music("zone_beta")),
            Zone("zone_gamma", pygame.Rect(0, 360, 1280, 360), music_track=music("zone_gamma")),
        ]

    # ------------------------------------------------------------------
    # BaseScene interface
    # ------------------------------------------------------------------

    def handle_events(self, events: list) -> None:
        """Process raw pygame events (input forwarded to player, etc.)."""
        import pygame
        for evt in events:
            if evt.type == pygame.KEYDOWN:
                # Placeholder: arrow key movement for stub player
                if evt.key == pygame.K_LEFT:
                    self._player.rect.x -= 200
                elif evt.key == pygame.K_RIGHT:
                    self._player.rect.x += 200
                elif evt.key == pygame.K_UP:
                    self._player.rect.y -= 200
                elif evt.key == pygame.K_DOWN:
                    self._player.rect.y += 200

    def update(self, dt: float) -> None:
        """Update all game systems; must be called every frame.

        Zone-change detection fires ``zone_entered`` on the EventBus when the
        player crosses into a new zone.  ``AudioSystem.update`` is called last,
        after all other in-game systems.
        """
        current_zone = self._zone_for_player(self._player.rect.center)
        if current_zone is not self._current_zone:
            self._current_zone = current_zone
            if current_zone is not None:
                self._event_bus.emit("zone_entered", {"zone": current_zone})
        self._audio.update(player_zone=self._current_zone)

    def render(self, screen) -> None:
        """Draw the game world."""
        import pygame
        # Draw zones as coloured rectangles (placeholder until TileMap)
        zone_colors = [(30, 50, 80), (50, 30, 80), (30, 80, 50)]
        for i, zone in enumerate(self._zones):
            color = zone_colors[i % len(zone_colors)]
            pygame.draw.rect(screen, color, zone.rect)
            font = pygame.font.SysFont("monospace", 14)
            name_surf = font.render(zone.name, True, (100, 120, 160))
            screen.blit(name_surf, (zone.rect.x + 8, zone.rect.y + 8))

        # Draw stub player
        import pygame
        cx, cy = self._player.rect.x, self._player.rect.y
        pygame.draw.rect(screen, (0, 245, 255), self._player.rect)

        # Draw zone name overlay if in a zone
        if self._current_zone:
            font = pygame.font.SysFont("monospace", 20, bold=True)
            txt = f"ZONE: {self._current_zone.name.upper()}"
            surf = font.render(txt, True, (0, 245, 255))
            screen.blit(surf, (screen.get_width() // 2 - surf.get_width() // 2, 8))

        # HUD: health bar
        bar_w = 200
        bar_h = 14
        bar_x, bar_y = 8, 8
        pygame.draw.rect(screen, (30, 34, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        hp_frac = max(0, self._player.health / max(1, self._player.max_health))
        pygame.draw.rect(screen, (0, 200, 200),
                         (bar_x, bar_y, int(bar_w * hp_frac), bar_h), border_radius=3)
        font_sm = pygame.font.SysFont("monospace", 11)
        hp_txt = f"HP {self._player.health}/{self._player.max_health}"
        screen.blit(font_sm.render(hp_txt, True, (255, 255, 255)), (bar_x + 4, bar_y + 1))

        # Inventory slot count
        slot_count = len(self._player.inventory.slots)
        inv_txt = f"Slots: {slot_count}"
        screen.blit(font_sm.render(inv_txt, True, (180, 180, 180)), (bar_x, bar_y + 20))
