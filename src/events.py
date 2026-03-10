"""Lightweight publish/subscribe event bus for decoupled system communication.

Event contracts
---------------
Core events (pre-existing):
    enemy_killed(enemy, killer, xp_reward, loot_table_id)
    player_damaged(target, damage, source)
    player_died(player)
    item_picked_up(item, player)
    entity_hit(target, damage, source)
    shot_fired(source)
    level_up(player, new_level)
    challenge_complete(challenge_id, rewards)
    money_changed(player, amount)

Round / extraction events (added by extraction-round feature):
    round_started(timer: float)
        Published when a new round begins.  *timer* is the total round
        duration in seconds (default 900).

    round_tick(remaining: float, total: float)
        Published every frame during the PLAYING phase with the seconds
        left on the round clock.

    timer_warning(remaining: float)
        Published **once** when the timer drops below 60 s and again when
        it drops below 30 s.

    extraction_started(zone_name: str, duration: float)
        Published when the player begins the extraction channel.

    extraction_progress(progress: float, duration: float)
        Published every frame while the extraction channel is active.
        *progress* is seconds elapsed; *duration* is total channel time.

    extraction_cancelled(reason: str)
        Published when the extraction channel is interrupted.
        *reason* is one of ``"left_zone"``, ``"interrupted"``.

    extraction_complete(loot_summary: dict)
        Published on successful extraction.

    round_timeout()
        Published when the round timer reaches zero.

    round_failed(cause: str, loot_lost: list)
        Published when the round ends in failure.
        *cause* is ``"timeout"`` or ``"eliminated"``.
"""

from __future__ import annotations

from typing import Callable


class EventBus:
    """Central event dispatcher.

    Systems publish named events with keyword data; subscribers receive
    callbacks.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[..., None]) -> None:
        """Register *callback* to be invoked when *event_type* is published."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        if callback not in self._listeners[event_type]:
            self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[..., None]) -> None:
        """Remove a previously registered callback (no-op if absent)."""
        listeners = self._listeners.get(event_type)
        if listeners is not None:
            try:
                listeners.remove(callback)
            except ValueError:
                pass

    def publish(self, event_type: str, **data) -> None:
        """Publish *event_type*, calling every subscriber with **data kwargs."""
        for callback in self._listeners.get(event_type, []):
            callback(**data)
