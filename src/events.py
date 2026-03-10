"""Lightweight publish/subscribe event bus for decoupled system communication."""

from __future__ import annotations

from typing import Callable


class EventBus:
    """Central event dispatcher.

    Systems publish named events with keyword data; subscribers receive callbacks.

    Core events:
        enemy_killed(enemy, killer, xp_reward, loot_table_id)
        player_damaged(target, damage, source)
        player_died(player)
        item_picked_up(item, player)
        extraction_started(player)
        extraction_complete(player, loot_summary)
        round_timeout()
        level_up(player, new_level)
        challenge_complete(challenge_id, rewards)
        money_changed(player, amount)
        entity_hit(target, damage, source)
        shot_fired(source)
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Register *callback* to be invoked when *event_type* is published."""
        self._listeners.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Remove a previously registered callback."""
        listeners = self._listeners.get(event_type, [])
        if callback in listeners:
            listeners.remove(callback)

    def publish(self, event_type: str, **data) -> None:
        """Publish *event_type*, calling every subscriber with **data kwargs."""
        for callback in self._listeners.get(event_type, []):
            callback(**data)
