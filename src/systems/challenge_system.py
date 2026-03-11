from typing import Any, Dict

class ChallengeSystem:
    def __init__(self, event_bus: Any):
        self._event_bus = event_bus
        self.kills: int = 0
        self.loot_collected: int = 0
        self.zones_visited: set = set()
        self.active_challenges: list = []
        event_bus.subscribe('enemy_killed', self._on_kill)
        event_bus.subscribe('item_picked_up', self._on_item)
        event_bus.subscribe('zone_entered', self._on_zone)

    def _on_kill(self, **kwargs: Any) -> None:
        self.kills += 1
        self._check_challenges()

    def _on_item(self, **kwargs: Any) -> None:
        self.loot_collected += 1
        self._check_challenges()

    def _on_zone(self, **kwargs: Any) -> None:
        zone = kwargs.get('zone')
        if zone:
            self.zones_visited.add(zone.name)
        self._check_challenges()

    def _check_challenges(self) -> None:
        pass

    def get_active_challenges(self) -> list:
        return self.active_challenges
