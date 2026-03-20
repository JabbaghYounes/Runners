"""CurrencySystem -- event-driven currency award and round-earnings tracker."""
from __future__ import annotations

from typing import Any


class CurrencySystem:
    """Awards currency live during a round and tracks per-round earnings.

    Subscribes to:

    - ``"player_extracted"`` — sums ``int(item.monetary_value)`` for every
      item in the ``loot`` payload and credits the persistent balance.
    - ``"challenge_completed"`` — reads ``reward_money`` from the payload
      (clamped to ``≥ 0``) and credits the persistent balance.

    Both handlers accumulate into :attr:`round_earnings`.  Call
    :meth:`reset_round` at the start of each new round to clear the counter.
    Call :meth:`teardown` on scene exit to unsubscribe from the event bus.
    """

    def __init__(self, currency: Any, event_bus: Any = None) -> None:
        self._currency = currency
        self._event_bus = event_bus
        self._round_earnings: int = 0

        if event_bus is not None:
            event_bus.subscribe("player_extracted", self._on_player_extracted)
            event_bus.subscribe("challenge_completed", self._on_challenge_completed)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_player_extracted(self, **kwargs: Any) -> None:
        """Sum monetary value of all extracted items and credit the balance."""
        loot = kwargs.get("loot") or []
        total = 0
        for item in loot:
            try:
                total += int(item.monetary_value)
            except (AttributeError, TypeError, ValueError):
                pass
        if total > 0:
            self._currency.add(total)
            self._round_earnings += total

    def _on_challenge_completed(self, **kwargs: Any) -> None:
        """Credit the ``reward_money`` from a completed challenge."""
        raw = kwargs.get("reward_money", 0)
        try:
            amount = max(0, int(raw or 0))
        except (TypeError, ValueError):
            amount = 0
        if amount > 0:
            self._currency.add(amount)
            self._round_earnings += amount

    # ------------------------------------------------------------------
    # Round management
    # ------------------------------------------------------------------

    @property
    def round_earnings(self) -> int:
        """Total currency earned so far in the current round."""
        return self._round_earnings

    def reset_round(self) -> None:
        """Reset the per-round earnings counter (call at round start)."""
        self._round_earnings = 0

    def teardown(self) -> None:
        """Unsubscribe from the event bus (call on scene exit)."""
        if self._event_bus is not None:
            self._event_bus.unsubscribe(
                "player_extracted", self._on_player_extracted
            )
            self._event_bus.unsubscribe(
                "challenge_completed", self._on_challenge_completed
            )
