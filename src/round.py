"""Round lifecycle manager — timer, extraction channel, and phase FSM.

Controls the full lifecycle of a single gameplay round:
    SPAWNING → PLAYING → EXTRACTING → EXTRACTED / FAILED

The ``RoundManager`` is a state machine that owns the 15-minute countdown
timer and the 5-second extraction channel, coordinating with the
``EventBus`` for decoupled communication with HUD, audio, scenes, and
progression systems.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from src.events import EventBus
    from src.entities.base import Entity
    from src.map import TileMap, Zone


class RoundPhase(Enum):
    """Phases of a single gameplay round."""

    SPAWNING = auto()
    PLAYING = auto()
    EXTRACTING = auto()
    EXTRACTED = auto()
    FAILED = auto()


class RoundManager:
    """Manages the lifecycle of a single gameplay round.

    Parameters:
        event_bus: The global event bus for publishing round events.
        round_duration: Total round time in seconds (default 900 = 15 min).
        extraction_duration: Extraction channel time in seconds (default 5).
    """

    def __init__(
        self,
        event_bus: EventBus,
        round_duration: float = 900.0,
        extraction_duration: float = 5.0,
    ) -> None:
        self._event_bus = event_bus
        self._round_duration = round_duration
        self._extraction_duration = extraction_duration

        # Phase state
        self._phase = RoundPhase.SPAWNING
        self._finished = False

        # Timer
        self._timer = round_duration

        # Extraction channel state
        self._extraction_elapsed = 0.0
        self._active_extraction_zone: Zone | None = None
        self._nearest_extraction_zone: Zone | None = None

        # Warning thresholds (published exactly once each)
        self._warned_60s = False
        self._warned_30s = False

        # Failure cause tracking
        self._fail_cause: str = ""

        # Player and map references (set on start_round)
        self._player: Entity | None = None
        self._tilemap: TileMap | None = None
        self._extraction_zones: list[Zone] = []

        # Result data built on completion
        self._result_data: dict = {}

        # Subscribe to player_damaged for extraction interruption
        self._event_bus.subscribe("player_damaged", self._on_player_damaged)

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def phase(self) -> RoundPhase:
        """Current round phase."""
        return self._phase

    @property
    def timer(self) -> float:
        """Seconds remaining on the round clock."""
        return max(0.0, self._timer)

    @property
    def extraction_progress(self) -> float:
        """Seconds elapsed in the current extraction channel (0 if not extracting)."""
        if self._phase != RoundPhase.EXTRACTING:
            return 0.0
        return self._extraction_elapsed

    @property
    def extraction_progress_ratio(self) -> float:
        """Extraction progress as a 0.0–1.0 ratio."""
        if self._phase != RoundPhase.EXTRACTING:
            return 0.0
        return min(self._extraction_elapsed / self._extraction_duration, 1.0)

    @property
    def is_finished(self) -> bool:
        """``True`` once the round has concluded (EXTRACTED or FAILED)."""
        return self._finished

    @property
    def extraction_zones(self) -> list[Zone]:
        """All extraction zones found on the current map."""
        return list(self._extraction_zones)

    @property
    def active_extraction_zone(self) -> Zone | None:
        """The zone being used for extraction, or ``None``."""
        return self._active_extraction_zone

    @property
    def nearest_extraction_zone(self) -> Zone | None:
        """The extraction zone the player is currently inside, or ``None``."""
        return self._nearest_extraction_zone

    @property
    def is_near_extraction(self) -> bool:
        """``True`` if the player is inside any extraction zone rect."""
        return self._nearest_extraction_zone is not None

    @property
    def result_data(self) -> dict:
        """Data dict summarising the round outcome for scene transitions."""
        return dict(self._result_data)

    @property
    def round_duration(self) -> float:
        """Total round duration in seconds."""
        return self._round_duration

    @property
    def extraction_duration(self) -> float:
        """Extraction channel duration in seconds."""
        return self._extraction_duration

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_round(self, player: Entity, tilemap: TileMap) -> None:
        """Initialise and start a new round.

        Finds extraction zones from the tilemap, places the player at the
        spawn zone, resets the timer, and transitions to PLAYING.
        """
        self._player = player
        self._tilemap = tilemap

        # Reset all state for potential re-use
        self._timer = self._round_duration
        self._extraction_elapsed = 0.0
        self._active_extraction_zone = None
        self._nearest_extraction_zone = None
        self._warned_60s = False
        self._warned_30s = False
        self._fail_cause = ""
        self._finished = False
        self._result_data = {}

        # Gather extraction zones from the tilemap
        self._extraction_zones = [
            z for z in tilemap.zones if z.zone_type == "extraction"
        ]

        # Place player at the first spawn zone (if present)
        spawn_zones = [z for z in tilemap.zones if z.zone_type == "spawn"]
        if spawn_zones:
            spawn = spawn_zones[0]
            player.pos.x = float(spawn.rect.centerx)
            player.pos.y = float(spawn.rect.centery)

        # Transition to PLAYING
        self._phase = RoundPhase.PLAYING
        self._event_bus.publish("round_started", timer=self._round_duration)

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(self, dt: float, player: Entity) -> None:
        """Advance round state by *dt* seconds.

        Must be called every frame from the gameplay scene.
        """
        self._player = player

        if self._phase == RoundPhase.PLAYING:
            self._update_playing(dt, player)
        elif self._phase == RoundPhase.EXTRACTING:
            self._update_extracting(dt, player)
        elif self._phase == RoundPhase.EXTRACTED:
            self._finalise_extracted()
        elif self._phase == RoundPhase.FAILED:
            self._finalise_failed()

    # ------------------------------------------------------------------
    # PLAYING phase logic
    # ------------------------------------------------------------------

    def _update_playing(self, dt: float, player: Entity) -> None:
        # Decrement timer
        self._timer -= dt

        # Check timeout
        if self._timer <= 0:
            self._timer = 0
            self._fail_cause = "timeout"
            self._phase = RoundPhase.FAILED
            self._event_bus.publish("round_timeout")
            return

        # Check player death
        if not player.alive:
            self._fail_cause = "eliminated"
            self._phase = RoundPhase.FAILED
            return

        # Check player proximity to extraction zones
        player_rect = player.get_rect()
        self._nearest_extraction_zone = None
        for zone in self._extraction_zones:
            if player_rect.colliderect(zone.rect):
                self._nearest_extraction_zone = zone
                break

        # Publish round tick for HUD
        self._event_bus.publish(
            "round_tick",
            remaining=self._timer,
            total=self._round_duration,
        )

        # Timer warnings (published exactly once at each threshold)
        if self._timer < 60.0 and not self._warned_60s:
            self._warned_60s = True
            self._event_bus.publish("timer_warning", remaining=self._timer)
        if self._timer < 30.0 and not self._warned_30s:
            self._warned_30s = True
            self._event_bus.publish("timer_warning", remaining=self._timer)

    # ------------------------------------------------------------------
    # EXTRACTING phase logic
    # ------------------------------------------------------------------

    def _update_extracting(self, dt: float, player: Entity) -> None:
        # Check player still alive
        if not player.alive:
            self._fail_cause = "eliminated"
            self._phase = RoundPhase.FAILED
            return

        # Check player still inside the extraction zone
        if self._active_extraction_zone is not None:
            player_rect = player.get_rect()
            if not player_rect.colliderect(self._active_extraction_zone.rect):
                self.cancel_extraction("left_zone")
                return

        # Advance the channel timer
        self._extraction_elapsed += dt

        # Publish progress for HUD
        self._event_bus.publish(
            "extraction_progress",
            progress=self._extraction_elapsed,
            duration=self._extraction_duration,
        )

        # Check completion
        if self._extraction_elapsed >= self._extraction_duration:
            self._phase = RoundPhase.EXTRACTED

    # ------------------------------------------------------------------
    # Terminal phase finalisation (run once)
    # ------------------------------------------------------------------

    def _finalise_extracted(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._result_data = self._build_success_data()
        self._event_bus.publish(
            "extraction_complete",
            loot_summary=self._result_data,
        )

    def _finalise_failed(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._result_data = self._build_failure_data()
        self._event_bus.publish(
            "round_failed",
            cause=self._fail_cause,
            loot_lost=self._result_data.get("loot_lost", []),
        )

    # ------------------------------------------------------------------
    # Extraction channel control
    # ------------------------------------------------------------------

    def begin_extraction(self, zone: Zone) -> None:
        """Start the extraction channel at *zone*.

        Only valid when in the PLAYING phase and the player is inside
        the zone.
        """
        if self._phase != RoundPhase.PLAYING:
            return
        self._active_extraction_zone = zone
        self._extraction_elapsed = 0.0
        self._phase = RoundPhase.EXTRACTING
        self._event_bus.publish(
            "extraction_started",
            zone_name=zone.name,
            duration=self._extraction_duration,
        )

    def cancel_extraction(self, reason: str = "interrupted") -> None:
        """Cancel the active extraction channel and revert to PLAYING."""
        if self._phase != RoundPhase.EXTRACTING:
            return
        self._phase = RoundPhase.PLAYING
        self._active_extraction_zone = None
        self._extraction_elapsed = 0.0
        self._event_bus.publish("extraction_cancelled", reason=reason)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_player_damaged(self, **data) -> None:
        """Cancel extraction if the player takes damage during the channel."""
        if self._phase == RoundPhase.EXTRACTING:
            self.cancel_extraction("interrupted")

    # ------------------------------------------------------------------
    # Result data builders
    # ------------------------------------------------------------------

    def _build_success_data(self) -> dict:
        """Build the result dict for a successful extraction."""
        items: list[dict] = []
        total_value = 0

        # Gather player inventory items if the player has an inventory
        if hasattr(self._player, "inventory") and self._player.inventory is not None:
            inv = self._player.inventory
            inv_items = getattr(inv, "items", [])
            for item in inv_items:
                item_dict = item.to_dict() if hasattr(item, "to_dict") else {
                    "name": getattr(item, "name", "Unknown"),
                    "rarity": getattr(item, "rarity", "common"),
                    "value": getattr(item, "value", 0),
                }
                items.append(item_dict)
                total_value += getattr(item, "value", 0)

        return {
            "outcome": "extracted",
            "items": items,
            "total_value": total_value,
            "xp_earned": {"extraction_bonus": 50, "survival": 25},
            "money_gained": total_value,
            "level_before": 1,
            "level_after": 1,
        }

    def _build_failure_data(self) -> dict:
        """Build the result dict for a failed round."""
        loot_lost: list[dict] = []
        total_lost = 0

        if hasattr(self._player, "inventory") and self._player.inventory is not None:
            inv = self._player.inventory
            inv_items = getattr(inv, "items", [])
            for item in inv_items:
                item_dict = item.to_dict() if hasattr(item, "to_dict") else {
                    "name": getattr(item, "name", "Unknown"),
                    "rarity": getattr(item, "rarity", "common"),
                    "value": getattr(item, "value", 0),
                }
                loot_lost.append(item_dict)
                total_lost += getattr(item, "value", 0)

        return {
            "outcome": "failed",
            "cause": self._fail_cause,
            "loot_lost": loot_lost,
            "total_lost": total_lost,
            "xp_retained": 10,
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Unsubscribe from events.  Call when the round scene is torn down."""
        self._event_bus.unsubscribe("player_damaged", self._on_player_damaged)
