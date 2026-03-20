"""Extraction system — FSM that manages the player's extraction attempt.

State machine
-------------

::

    IDLE ──(player enters zone)──► IN_ZONE
                                      │
                            (F held)  │  (player leaves zone)
                                      ▼
                                  CHANNELING ──(movement OR F released)──► IN_ZONE
                                      │
                            (elapsed ≥ EXTRACTION_CHANNEL_SECS)
                                      ▼
                                    DONE  ──► publishes player_extracted

    Any state except DONE ──(round_end received)──► publishes extraction_failed

Events published
----------------
``zone_entered(zone)``
    Player rect overlaps extraction zone for the first time this transition.
``extraction_started()``
    Channel begins (player held F while standing in zone).
``extraction_cancelled()``
    Channel was interrupted by movement, key release, or player death.
``player_extracted(inventory_snapshot)``
    Channel completed successfully; payload carries an inventory snapshot list.
``extraction_failed()``
    Round timer reached zero before extraction completed.
"""

from __future__ import annotations

import enum

from src.constants import (
    EXTRACTION_CHANNEL_SECS,
    KEY_EXTRACT,
    MOVE_THRESHOLD,
)
from src.core.event_bus import EventBus
from src.entities.player import Player
from src.map.extraction_zone import ExtractionZone


class ExtractionState(enum.Enum):
    """States of the extraction FSM."""
    IDLE = "IDLE"
    IN_ZONE = "IN_ZONE"
    CHANNELING = "CHANNELING"
    DONE = "DONE"


class ExtractionSystem:
    """Drives the extraction channel FSM each game frame.

    Args:
        event_bus:  Shared :class:`~src.core.event_bus.EventBus` instance.
        zone:       The :class:`~src.map.extraction_zone.ExtractionZone` for
                    this round's map.
        channel_duration: Seconds the player must hold F without moving.
                    Defaults to :data:`~src.constants.EXTRACTION_CHANNEL_SECS`.
    """

    def __init__(
        self,
        event_bus: EventBus,
        zone: ExtractionZone,
        channel_duration: float = EXTRACTION_CHANNEL_SECS,
    ) -> None:
        self._bus = event_bus
        self._zone = zone
        self._channel_duration = channel_duration

        self.state: ExtractionState = ExtractionState.IDLE
        self._channel_elapsed: float = 0.0

        # Subscribe to round_end so we can emit extraction_failed if needed.
        self._bus.subscribe("round_end", self._on_round_end)

    # ------------------------------------------------------------------
    # Per-frame update — call from GameScene.update(dt)
    # ------------------------------------------------------------------

    def update(self, dt: float, player: Player, pressed_keys) -> None:
        """Advance the FSM by one frame.

        Args:
            dt:           Frame delta time in seconds.
            player:       The :class:`~src.entities.player.Player` instance.
            pressed_keys: Return value of ``pygame.key.get_pressed()`` (or
                          any sequence/mapping supporting ``[key]`` lookup).
        """
        if self.state is ExtractionState.DONE:
            return

        in_zone = self._zone.rect.colliderect(player.rect)
        key_held = bool(pressed_keys[KEY_EXTRACT])
        is_moving = player.velocity.length() > MOVE_THRESHOLD

        if self.state is ExtractionState.IDLE:
            if in_zone:
                self.state = ExtractionState.IN_ZONE
                self._bus.publish("zone_entered", zone=self._zone)

        elif self.state is ExtractionState.IN_ZONE:
            if not in_zone:
                # Player walked back out without starting a channel.
                self.state = ExtractionState.IDLE
            elif key_held and not is_moving:
                self.state = ExtractionState.CHANNELING
                self._channel_elapsed = 0.0
                self._bus.publish("extraction_started")

        elif self.state is ExtractionState.CHANNELING:
            # Dead player cancels channeling immediately.
            if not getattr(player, 'alive', True):
                self.state = ExtractionState.IN_ZONE
                self._channel_elapsed = 0.0
                self._bus.publish("extraction_cancelled")
                return

            if is_moving or not key_held:
                # Any movement or releasing F cancels the channel.
                self.state = ExtractionState.IN_ZONE
                self._channel_elapsed = 0.0
                self._bus.publish("extraction_cancelled")
            else:
                self._channel_elapsed += dt
                if self._channel_elapsed >= self._channel_duration:
                    self._channel_elapsed = self._channel_duration
                    self.state = ExtractionState.DONE
                    # Snapshot the live inventory (a shallow copy).
                    inventory_snapshot = list(player.inventory)
                    self._bus.publish(
                        "player_extracted",
                        inventory_snapshot=inventory_snapshot,
                    )

    # ------------------------------------------------------------------
    # Properties read by UI widgets and GameScene
    # ------------------------------------------------------------------

    @property
    def channel_progress(self) -> float:
        """Fraction of the channel that has elapsed (0.0 – 1.0).

        Returns ``0.0`` when not channeling and ``1.0`` when done.
        """
        if self.state is ExtractionState.DONE:
            return 1.0
        if self._channel_duration <= 0:
            return 0.0
        return min(self._channel_elapsed / self._channel_duration, 1.0)

    @property
    def extraction_progress(self) -> float:
        """Alias for :attr:`channel_progress` — used by HUD/GameScene."""
        return self.channel_progress

    @property
    def seconds_remaining(self) -> float:
        """Timer placeholder — this FSM does not own the round timer.

        The round timer is managed by :class:`~src.systems.extraction.ExtractionSystem`
        (the simpler system) or by a dedicated ``RoundTimer``.  Returns ``0.0``
        so HUD code that guards with ``hasattr`` falls back gracefully.
        """
        return 0.0

    @property
    def is_done(self) -> bool:
        """``True`` once extraction completed successfully."""
        return self.state is ExtractionState.DONE

    @property
    def is_in_zone(self) -> bool:
        """``True`` while the player is inside the extraction zone."""
        return self.state in (
            ExtractionState.IN_ZONE,
            ExtractionState.CHANNELING,
        )

    def is_player_in_zone(self, player: Player) -> bool:
        """Return ``True`` if *player*'s rect overlaps the zone.

        Provided for compatibility with the HUD state builder and the simpler
        :class:`~src.systems.extraction.ExtractionSystem` interface.
        """
        return self._zone.rect.colliderect(player.rect)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_round_end(self, **_kwargs) -> None:
        """React to ``round_end``; emit ``extraction_failed`` if not done."""
        if self.state is not ExtractionState.DONE:
            self._bus.publish("extraction_failed")
