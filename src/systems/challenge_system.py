"""Data-driven vendor challenge system.

Loads a pool of challenges from ``data/challenges.json``, randomly selects a
configurable number per round, tracks progress via EventBus events, and emits
reward events when a challenge is completed.

Each challenge definition in JSON has:
- ``id``: unique string identifier
- ``description``: human-readable text
- ``criteria_type``: event type that advances progress
  (``enemy_killed``, ``item_picked_up``, ``zone_entered``, ``reach_location``)
- ``target``: numeric goal
- ``zone_filter``: optional zone name key (e.g. ``"cargo_bay"``); when set,
  only events in that zone count.  For ``reach_location``, the player must
  visit the named zone at least once.
- ``reward_xp``: XP granted on completion
- ``reward_money``: currency granted on completion
- ``reward_item_id``: optional item ID granted on completion (``null`` for none)
"""
from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.ui.hud_state import ChallengeInfo

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_CHALLENGES_PATH = os.path.join(_ROOT, "data", "challenges.json")

# Number of challenges selected per round by default
DEFAULT_CHALLENGES_PER_ROUND = 3

_log = logging.getLogger(__name__)


@dataclass
class _ActiveChallenge:
    """Internal mutable state for a single active challenge."""

    id: str
    description: str
    criteria_type: str
    target: int
    zone_filter: Optional[str]
    reward_xp: int
    reward_money: int
    reward_item_id: Optional[str] = None
    progress: int = 0
    completed: bool = False


class ChallengeSystem:
    """Vendor challenge manager.

    Parameters
    ----------
    event_bus : EventBus
        Pub/sub broker used to receive game events and emit reward events.
    challenges_path : str | None
        Path to the JSON challenge pool file.  Defaults to
        ``data/challenges.json`` relative to the project root.
    challenges_per_round : int
        How many challenges to activate each round.
    rng_seed : int | None
        Optional seed for deterministic testing.
    """

    def __init__(
        self,
        event_bus: Any,
        challenges_path: Optional[str] = None,
        challenges_per_round: int = DEFAULT_CHALLENGES_PER_ROUND,
        rng_seed: Optional[int] = None,
    ) -> None:
        self._event_bus = event_bus
        self._challenges_per_round = challenges_per_round
        self._rng = random.Random(rng_seed)

        # Tracking counters
        self.kills: int = 0
        self.loot_collected: int = 0
        self.zones_visited: set[str] = set()

        # Per-zone kill/loot counters for zone-filtered challenges
        self._zone_kills: Dict[str, int] = {}
        self._zone_loot: Dict[str, int] = {}

        # Current zone the player is in (for zone-filtered tracking)
        self._current_zone: Optional[str] = None

        # Load the pool and select active challenges
        self._pool: List[Dict[str, Any]] = []
        self._active: List[_ActiveChallenge] = []

        path = challenges_path or _DEFAULT_CHALLENGES_PATH
        self._load_pool(path)
        self._select_challenges()

        # Subscribe to events
        event_bus.subscribe("enemy_killed", self._on_kill)
        event_bus.subscribe("item_picked_up", self._on_item)
        event_bus.subscribe("zone_entered", self._on_zone)

    # ------------------------------------------------------------------
    # Pool loading
    # ------------------------------------------------------------------

    def _load_pool(self, path: str) -> None:
        """Load the challenge pool from a JSON file."""
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self._pool = data.get("challenges", [])
        except (json.JSONDecodeError, OSError):
            self._pool = []

    def load_pool_from_list(self, challenges: List[Dict[str, Any]]) -> None:
        """Load challenges directly from a list (useful for testing)."""
        self._pool = list(challenges)
        self._active.clear()
        self._select_challenges()

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _select_challenges(self) -> None:
        """Randomly select challenges from the pool for this round."""
        if not self._pool:
            return
        count = min(self._challenges_per_round, len(self._pool))
        selected = self._rng.sample(self._pool, count)
        for defn in selected:
            try:
                self._active.append(
                    _ActiveChallenge(
                        id=defn["id"],
                        description=defn.get("description", ""),
                        criteria_type=defn["criteria_type"],
                        target=int(defn["target"]),
                        zone_filter=defn.get("zone_filter"),
                        reward_xp=int(defn.get("reward_xp", 0)),
                        reward_money=int(defn.get("reward_money", 0)),
                        reward_item_id=defn.get("reward_item_id"),
                    )
                )
            except KeyError as exc:
                _log.warning(
                    "[ChallengeSystem] Skipping malformed challenge entry "
                    "(missing required field %s): %r",
                    exc,
                    defn,
                )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_kill(self, **kwargs: Any) -> None:
        self.kills += 1
        if self._current_zone:
            zone_key = self._current_zone.lower().replace(" ", "_")
            self._zone_kills[zone_key] = self._zone_kills.get(zone_key, 0) + 1
        self._check_challenges()

    def _on_item(self, **kwargs: Any) -> None:
        self.loot_collected += 1
        if self._current_zone:
            zone_key = self._current_zone.lower().replace(" ", "_")
            self._zone_loot[zone_key] = self._zone_loot.get(zone_key, 0) + 1
        self._check_challenges()

    def _on_zone(self, **kwargs: Any) -> None:
        zone = kwargs.get("zone")
        if zone:
            name = getattr(zone, "name", str(zone))
            self.zones_visited.add(name)
            self._current_zone = name
        self._check_challenges()

    # ------------------------------------------------------------------
    # Progress checking
    # ------------------------------------------------------------------

    def _check_challenges(self) -> None:
        """Update progress for all active challenges and emit rewards."""
        for ch in self._active:
            if ch.completed:
                continue
            ch.progress = self._compute_progress(ch)
            if ch.progress >= ch.target:
                ch.completed = True
                ch.progress = ch.target
                self._event_bus.emit(
                    "challenge_completed",
                    challenge_id=ch.id,
                    reward_xp=ch.reward_xp,
                    reward_money=ch.reward_money,
                    reward_item_id=ch.reward_item_id,
                )

    def _compute_progress(self, ch: _ActiveChallenge) -> int:
        """Compute the current progress value for a challenge."""
        ct = ch.criteria_type

        if ct == "enemy_killed":
            if ch.zone_filter:
                return self._zone_kills.get(ch.zone_filter, 0)
            return self.kills

        if ct == "item_picked_up":
            if ch.zone_filter:
                return self._zone_loot.get(ch.zone_filter, 0)
            return self.loot_collected

        if ct == "zone_entered":
            return len(self.zones_visited)

        if ct == "reach_location":
            if ch.zone_filter:
                target_key = ch.zone_filter.lower()
                for visited_name in self.zones_visited:
                    if visited_name.lower().replace(" ", "_") == target_key:
                        return 1
            return 0

        # Unknown criteria type — warn once per distinct type and skip
        _log.warning(
            "[ChallengeSystem] Unknown criteria_type %r for challenge %r; "
            "challenge will never complete.",
            ct,
            ch.id,
        )
        # Return current progress unchanged so the challenge stays incomplete
        # without being re-warned on every event.
        return ch.progress

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_active_challenges(self) -> List[ChallengeInfo]:
        """Return a list of ChallengeInfo snapshots for the HUD."""
        return [
            ChallengeInfo(
                name=ch.description,
                progress=min(ch.progress, ch.target),
                target=ch.target,
                completed=ch.completed,
                zone=(
                    ch.zone_filter.replace("_", " ").title()
                    if ch.zone_filter
                    else ""
                ),
            )
            for ch in self._active
        ]

    def get_completed_challenges(self) -> List[_ActiveChallenge]:
        """Return all challenges that have been completed this round."""
        return [ch for ch in self._active if ch.completed]

    def get_active_raw(self) -> List[_ActiveChallenge]:
        """Return the raw internal challenge objects (for testing)."""
        return list(self._active)

    @property
    def active_challenges(self) -> List[ChallengeInfo]:
        """Property alias for backward compatibility."""
        return self.get_active_challenges()

    def reset(self) -> None:
        """Reset all progress and re-select challenges for a new round."""
        self.kills = 0
        self.loot_collected = 0
        self.zones_visited.clear()
        self._zone_kills.clear()
        self._zone_loot.clear()
        self._current_zone = None
        self._active.clear()
        self._select_challenges()
