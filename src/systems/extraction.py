"""ExtractionSystem — manages the 15-minute round timer and extraction logic.

Responsibilities:
- Counts down the round timer (15 minutes by default).
- Detects when the player's rect overlaps the extraction zone from TileMap.
- When overlapping: accumulates a 2-second hold channel time.
- On channel completion: emits ``extraction_success`` with the player's
  current inventory items.
- On timer expiry without extraction: emits ``extraction_failed``.

EventBus events emitted:
    extraction_success  { player, extracted_items: list[Item] }
    extraction_failed   { player }
    extraction_progress { player, progress: float }   (0.0 – 1.0, each frame)
    round_timer_tick    { time_remaining: float }      (every second)

The system sets a flag on the HUD-visible state dict (``hud_state``) so
the HUD can render the "Hold E to Extract" prompt without importing this
module.
"""

from __future__ import annotations

from typing import Any

ROUND_DURATION: float = 15.0 * 60.0   # 15 minutes in seconds
CHANNEL_DURATION: float = 2.0          # seconds to hold E for extraction


class ExtractionSystem:
    """Manages the round countdown and extraction zone channelling.

    Args:
        event_bus:        The shared :class:`~src.core.event_bus.EventBus`.
        extraction_rect:  A ``pygame.Rect`` (or duck-typed rect with
                          ``colliderect``) marking the extraction zone on the
                          map.  If ``None`` the system still counts down but
                          extraction is impossible.
        round_duration:   Total round time in seconds.
        channel_duration: How long the player must hold E to extract.
    """

    def __init__(
        self,
        event_bus: Any,
        extraction_rect: Any = None,
        *,
        round_duration: float = ROUND_DURATION,
        channel_duration: float = CHANNEL_DURATION,
    ) -> None:
        self._event_bus = event_bus
        self._extraction_rect = extraction_rect
        self._round_duration = round_duration
        self._channel_duration = channel_duration

        self.time_remaining: float = round_duration
        self._channel_time: float = 0.0
        self._in_zone: bool = False
        self._extracted: bool = False
        self._failed: bool = False
        self._last_tick_second: int = int(round_duration)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def round_complete(self) -> bool:
        """True once extraction_success or extraction_failed has been emitted."""
        return self._extracted or self._failed

    @property
    def channel_progress(self) -> float:
        """Extraction channel progress in [0.0, 1.0]."""
        if self._channel_duration <= 0:
            return 0.0
        return min(self._channel_time / self._channel_duration, 1.0)

    def set_extraction_rect(self, rect: Any) -> None:
        """Update the extraction zone rect (called by GameScene when map loads)."""
        self._extraction_rect = rect

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(
        self,
        player: Any,
        dt: float,
        *,
        e_key_held: bool = False,
        hud_state: dict[str, Any] | None = None,
    ) -> None:
        """Advance the timer and handle extraction channelling.

        Args:
            player:      The active :class:`~src.entities.player.Player`.
            dt:          Delta time in seconds since last frame.
            e_key_held:  Whether the player is currently holding the E key.
            hud_state:   Optional shared dict for HUD flags.  This system
                         sets ``hud_state["show_extract_prompt"]`` and
                         ``hud_state["extract_progress"]``.
        """
        if self.round_complete:
            return

        # --- Countdown timer ---
        self.time_remaining = max(0.0, self.time_remaining - dt)

        # Emit a tick event once per second.
        current_second = int(self.time_remaining)
        if current_second < self._last_tick_second:
            self._last_tick_second = current_second
            self._event_bus.emit(
                "round_timer_tick",
                time_remaining=self.time_remaining,
            )

        # --- Timer expiry ---
        if self.time_remaining <= 0 and not self._extracted:
            self._fail(player)
            return

        # --- Extraction zone overlap ---
        in_zone = self._player_in_zone(player)
        self._in_zone = in_zone

        if hud_state is not None:
            hud_state["show_extract_prompt"] = in_zone
            hud_state["extract_progress"] = self.channel_progress

        if in_zone and e_key_held:
            self._channel_time += dt
            self._event_bus.emit(
                "extraction_progress",
                player=player,
                progress=self.channel_progress,
            )
            if self._channel_time >= self._channel_duration:
                self._succeed(player)
        else:
            # Reset channel if player leaves zone or releases E.
            if self._channel_time > 0:
                self._channel_time = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _player_in_zone(self, player: Any) -> bool:
        """Return True if the player rect overlaps the extraction zone."""
        if self._extraction_rect is None:
            return False
        try:
            return bool(self._extraction_rect.colliderect(player.rect))
        except AttributeError:
            return False

    def _succeed(self, player: Any) -> None:
        """Emit extraction_success and mark round complete."""
        self._extracted = True
        extracted_items = self._get_player_items(player)
        self._event_bus.emit(
            "extraction_success",
            player=player,
            extracted_items=extracted_items,
        )

    def _fail(self, player: Any) -> None:
        """Emit extraction_failed and mark round complete."""
        self._failed = True
        self._event_bus.emit(
            "extraction_failed",
            player=player,
        )

    @staticmethod
    def _get_player_items(player: Any) -> list[Any]:
        """Safely retrieve the player's inventory items as a flat list."""
        try:
            inventory = player.inventory
            # Support both .items() method and .items attribute.
            if callable(getattr(inventory, "items", None)):
                return list(inventory.items())
            return list(getattr(inventory, "items", []))
        except AttributeError:
            return []

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def formatted_time(self) -> str:
        """Return the remaining time formatted as ``MM:SS``."""
        total_seconds = int(self.time_remaining)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
