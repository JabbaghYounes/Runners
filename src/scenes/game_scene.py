"""GameScene — owns the in-round game state: map, entities, systems, and HUD."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.progression.home_base import HomeBase
    from src.core.event_bus import EventBus
    from src.systems.audio_system import AudioSystem
    from src.core.settings import Settings
    from src.map.zone import Zone


class _StubPlayer:
    """Minimal player stand-in used until the full Player entity is wired in."""

    def __init__(self) -> None:
        import pygame
        from src.inventory.inventory import Inventory
        self.rect = pygame.Rect(0, 0, 32, 48)
        self.health: int = 100
        self.max_health: int = 100
        self.armor: int = 0
        self.max_armor: int = 100
        self.inventory = Inventory()
        self.velocity_x: float = 0.0
        self.velocity_y: float = 0.0

    def is_moving(self) -> bool:
        return self.velocity_x != 0.0 or self.velocity_y != 0.0


class GameScene:
    """Owns all in-round state: tile map, entity lists, game systems, and HUD.

    Constructor args:
        event_bus:  Shared :class:`~src.core.event_bus.EventBus` instance.
        audio:      :class:`~src.systems.audio_system.AudioSystem` (or mock).
        settings:   :class:`~src.core.settings.Settings` (or mock).
        zones:      Optional list of :class:`~src.map.zone.Zone` objects.
                    When *None*, three default stub zones are created.
        home_base:  Optional :class:`~src.progression.home_base.HomeBase` whose
                    round-start bonuses are applied to the player on construction.
    """

    def __init__(
        self,
        event_bus: "EventBus",
        audio: "AudioSystem",
        settings: "Settings",
        zones: "Optional[list[Zone]]" = None,
        home_base: "Optional[HomeBase]" = None,
    ) -> None:
        self._event_bus = event_bus
        self._audio = audio
        self._settings = settings

        self._zones: "list[Zone]" = zones if zones is not None else self._default_zones()
        self._prev_zone: "Optional[Zone]" = None

        # Loot value bonus applied by Armory facility
        self.loot_value_bonus: float = 0.0

        # Player stub (real Player will replace this when entity layer is wired)
        self._player = _StubPlayer()

        # Apply home-base round-start bonuses
        if home_base is not None:
            self._apply_home_base_bonuses(self._player, home_base)

        # HUD (lazy-import to avoid circular deps at module load)
        self._hud = None
        self._init_hud()

    # ── Initialisation helpers ─────────────────────────────────────────────

    def _init_hud(self) -> None:
        """Instantiate the HUD. Deferred so tests can patch before it's created."""
        try:
            from src.ui.hud import HUD
            self._hud = HUD(self._event_bus)
        except Exception:
            self._hud = None

    def _apply_home_base_bonuses(self, player: "_StubPlayer", home_base: "HomeBase") -> None:
        """Apply round-start stat bonuses derived from facility upgrade levels.

        Args:
            player:    The player entity to modify.
            home_base: The home-base whose ``get_round_bonuses()`` determines
                       which stat adjustments to apply.
        """
        bonuses = home_base.get_round_bonuses()
        extra_hp: int = int(bonuses.get('extra_hp', 0))
        extra_slots: int = int(bonuses.get('extra_slots', 0))
        player.health += extra_hp
        player.max_health += extra_hp
        player.inventory.expand_capacity(extra_slots)
        self.loot_value_bonus = float(bonuses.get('loot_value_bonus', 0.0))

    def _zone_for_player(self) -> "Optional[Zone]":
        """Return the first zone that contains the player, or *None*."""
        pos = self._player.rect.center
        for zone in self._zones:
            if zone.contains(pos):
                return zone
        return None

    @staticmethod
    def _default_zones() -> "list[Zone]":
        """Return three stub zones for testing without a real map."""
        import pygame
        from src.map.zone import Zone

        def music(track: str) -> str:
            return track

        return [
            Zone(
                name='zone_alpha',
                rect=pygame.Rect(0, 0, 427, 720),
                music_track=music('zone_alpha'),
            ),
            Zone(
                name='zone_beta',
                rect=pygame.Rect(427, 0, 426, 720),
                music_track=music('zone_beta'),
            ),
            Zone(
                name='zone_gamma',
                rect=pygame.Rect(853, 0, 427, 720),
                music_track=music('zone_gamma'),
            ),
        ]

    # ── Per-frame lifecycle ────────────────────────────────────────────────

    def handle_events(self, events: list) -> None:
        """Process raw pygame events (input forwarded to player, etc.)."""
        import pygame
        for evt in events:
            if evt.type == pygame.KEYDOWN:
                if evt.key == pygame.K_LEFT:
                    self._player.rect.x -= 8
                elif evt.key == pygame.K_RIGHT:
                    self._player.rect.x += 8
                elif evt.key == pygame.K_UP:
                    self._player.rect.y -= 8
                elif evt.key == pygame.K_DOWN:
                    self._player.rect.y += 8

    def update(self, dt: float) -> None:
        """Update all game systems; must be called every frame.

        Zone-change detection fires ``zone_entered`` on the EventBus whenever
        the player crosses a zone boundary (or first enters a zone).
        """
        current_zone = self._zone_for_player()
        if current_zone is not self._prev_zone:
            if current_zone is not None:
                self._event_bus.emit('zone_entered', zone=current_zone)
            self._prev_zone = current_zone

        self._audio.update(
            dt_received=dt,
            player_zone=current_zone,
            player_is_moving=self._player.is_moving(),
        )

        # Update HUD
        if self._hud is not None:
            try:
                state = self._build_hud_state()
                self._hud.update(state, dt)
            except Exception:
                pass

    def render(self, screen: object) -> None:
        """Draw the game world."""
        import pygame

        zone_colors = [
            (30, 20, 50),
            (20, 40, 30),
            (40, 30, 20),
        ]
        for i, zone in enumerate(self._zones):
            color = zone_colors[i % len(zone_colors)]
            pygame.draw.rect(screen, color, zone.rect)

        # Zone label
        font = pygame.font.SysFont('monospace', 16)
        if self._prev_zone:
            name_surf = font.render('ZONE: ' + self._prev_zone.name.upper(), True, (200, 200, 200))
            cx = screen.get_width() // 2 - name_surf.get_width() // 2
            screen.blit(name_surf, (cx, 8))

        # HUD (rendered last, on top of everything else)
        if self._hud is not None:
            try:
                self._hud.draw(screen)
            except Exception:
                pass

    # ── HUD state assembly ─────────────────────────────────────────────────

    def _build_hud_state(self) -> object:
        """Assemble a HUDState snapshot from current game system state."""
        from src.ui.hud_state import HUDState, ZoneInfo
        import pygame

        player = self._player
        hp = float(getattr(player, 'health', 100))
        max_hp = float(getattr(player, 'max_health', 100))
        armor = float(getattr(player, 'armor', 0))
        max_armor = float(getattr(player, 'max_armor', 100))

        # Zone info for minimap
        zone_palette = [
            (80, 60, 120),
            (60, 100, 80),
            (110, 80, 60),
        ]
        zones_info = []
        for i, z in enumerate(self._zones):
            color = zone_palette[i % len(zone_palette)]
            zones_info.append(ZoneInfo(name=z.name, color=color, world_rect=z.rect))

        # Map world rect (union of all zones)
        if self._zones:
            try:
                rects = [z.rect for z in self._zones]
                map_rect = rects[0].unionall(rects[1:])
            except Exception:
                map_rect = pygame.Rect(0, 0, 1280, 720)
        else:
            map_rect = pygame.Rect(0, 0, 1280, 720)

        # Player world position
        try:
            player_pos = tuple(player.rect.center)
        except Exception:
            player_pos = (0.0, 0.0)

        return HUDState(
            hp=hp,
            max_hp=max_hp,
            armor=armor,
            max_armor=max_armor,
            level=1,
            xp=0.0,
            xp_to_next=100.0,
            seconds_remaining=900.0,
            active_buffs=[],
            player_world_pos=player_pos,
            map_world_rect=map_rect,
            zones=zones_info,
            extraction_pos=None,
            equipped_weapon=None,
            consumable_slots=[],
            active_challenges=[],
        )
