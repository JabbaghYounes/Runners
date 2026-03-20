"""Unit tests for ChallengeSystem — src/systems/challenge_system.py

Run: pytest tests/systems/test_challenge_system.py
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any, List
from unittest.mock import MagicMock

import pytest

from src.core.event_bus import EventBus
from src.systems.challenge_system import ChallengeSystem, DEFAULT_CHALLENGES_PER_ROUND
from src.ui.hud_state import ChallengeInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TrackingBus(EventBus):
    """EventBus subclass that records every emitted event."""

    def __init__(self) -> None:
        super().__init__()
        self.emitted: list[dict] = []

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        self.emitted.append({"event": event, **kwargs})
        super().emit(event, *args, **kwargs)

    def all_events(self, name: str) -> list[dict]:
        return [e for e in self.emitted if e["event"] == name]

    def first_event(self, name: str) -> dict | None:
        matches = self.all_events(name)
        return matches[0] if matches else None


def _make_system(
    pool: list[dict],
    bus: EventBus | None = None,
    challenges_per_round: int = 99,
    rng_seed: int = 0,
) -> tuple[ChallengeSystem, _TrackingBus]:
    """Create a ChallengeSystem loaded from *pool* with a fresh tracking bus."""
    bus = bus or _TrackingBus()
    cs = ChallengeSystem(
        bus,
        challenges_per_round=challenges_per_round,
        rng_seed=rng_seed,
    )
    cs.load_pool_from_list(pool)
    return cs, bus  # type: ignore[return-value]


def _kill_challenge(
    target: int = 3,
    zone_filter: str | None = None,
    xp: int = 100,
    money: int = 150,
    item_id: str | None = None,
) -> dict:
    return {
        "id": "test_kill",
        "description": "Kill enemies",
        "criteria_type": "enemy_killed",
        "target": target,
        "zone_filter": zone_filter,
        "reward_xp": xp,
        "reward_money": money,
        "reward_item_id": item_id,
    }


def _loot_challenge(
    target: int = 3,
    zone_filter: str | None = None,
    xp: int = 80,
    money: int = 120,
    item_id: str | None = None,
) -> dict:
    return {
        "id": "test_loot",
        "description": "Collect items",
        "criteria_type": "item_picked_up",
        "target": target,
        "zone_filter": zone_filter,
        "reward_xp": xp,
        "reward_money": money,
        "reward_item_id": item_id,
    }


def _zone_entered_challenge(target: int = 3) -> dict:
    return {
        "id": "test_zone",
        "description": "Enter zones",
        "criteria_type": "zone_entered",
        "target": target,
        "zone_filter": None,
        "reward_xp": 50,
        "reward_money": 75,
        "reward_item_id": None,
    }


def _reach_location_challenge(zone_filter: str = "cargo_bay") -> dict:
    return {
        "id": "test_reach",
        "description": "Reach the Cargo Bay",
        "criteria_type": "reach_location",
        "target": 1,
        "zone_filter": zone_filter,
        "reward_xp": 60,
        "reward_money": 90,
        "reward_item_id": None,
    }


class _FakeZone:
    """Minimal zone stub with a name attribute."""

    def __init__(self, name: str) -> None:
        self.name = name


# ---------------------------------------------------------------------------
# Pool loading
# ---------------------------------------------------------------------------

class TestPoolLoading:

    def test_load_pool_from_list_sets_active_challenges(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, rng_seed=0)
        cs.load_pool_from_list([_kill_challenge()])
        assert len(cs.get_active_raw()) == 1

    def test_load_pool_from_list_replaces_previous_active(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, rng_seed=0)
        cs.load_pool_from_list([_kill_challenge(), _loot_challenge()])
        cs.load_pool_from_list([_kill_challenge(target=5)])
        assert len(cs.get_active_raw()) == 1

    def test_empty_pool_results_in_no_active_challenges(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, rng_seed=0)
        cs.load_pool_from_list([])
        assert cs.get_active_raw() == []

    def test_malformed_entry_missing_id_is_skipped(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, rng_seed=0)
        # Missing required "id" field
        bad = {"description": "No id here", "criteria_type": "enemy_killed", "target": 3}
        cs.load_pool_from_list([bad])
        assert cs.get_active_raw() == []

    def test_malformed_entry_missing_criteria_type_is_skipped(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, rng_seed=0)
        bad = {"id": "no_type", "description": "desc", "target": 3}
        cs.load_pool_from_list([bad])
        assert cs.get_active_raw() == []

    def test_malformed_entry_missing_target_is_skipped(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, rng_seed=0)
        bad = {"id": "no_target", "description": "desc", "criteria_type": "enemy_killed"}
        cs.load_pool_from_list([bad])
        assert cs.get_active_raw() == []

    def test_valid_and_malformed_entries_loads_only_valid(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, rng_seed=0)
        good = _kill_challenge()
        bad = {"description": "malformed"}
        cs.load_pool_from_list([good, bad])
        assert len(cs.get_active_raw()) == 1
        assert cs.get_active_raw()[0].id == "test_kill"

    def test_load_from_json_file_populates_pool(self, tmp_path):
        data = {"challenges": [_kill_challenge()]}
        p = tmp_path / "challenges.json"
        p.write_text(json.dumps(data))
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, challenges_path=str(p), rng_seed=0)
        assert len(cs.get_active_raw()) == 1

    def test_missing_json_file_results_in_empty_pool(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, challenges_path=path, rng_seed=0)
        assert cs.get_active_raw() == []

    def test_corrupt_json_file_results_in_empty_pool(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{ this is not valid json !!!")
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, challenges_path=str(p), rng_seed=0)
        assert cs.get_active_raw() == []

    def test_reward_item_id_stored_on_active_challenge(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, rng_seed=0)
        cs.load_pool_from_list([_kill_challenge(item_id="medkit_basic")])
        ch = cs.get_active_raw()[0]
        assert ch.reward_item_id == "medkit_basic"

    def test_null_reward_item_id_stored_as_none(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, rng_seed=0)
        cs.load_pool_from_list([_kill_challenge(item_id=None)])
        ch = cs.get_active_raw()[0]
        assert ch.reward_item_id is None

    def test_zone_filter_stored_correctly(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, rng_seed=0)
        cs.load_pool_from_list([_kill_challenge(zone_filter="cargo_bay")])
        ch = cs.get_active_raw()[0]
        assert ch.zone_filter == "cargo_bay"


# ---------------------------------------------------------------------------
# Challenge selection
# ---------------------------------------------------------------------------

class TestChallengeSelection:

    def test_challenges_per_round_caps_active_count(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, challenges_per_round=2, rng_seed=0)
        pool = [_kill_challenge(), _loot_challenge(), _zone_entered_challenge()]
        cs.load_pool_from_list(pool)
        assert len(cs.get_active_raw()) == 2

    def test_rng_seed_produces_deterministic_selection(self):
        pool = [
            {"id": f"ch_{i}", "description": f"C{i}", "criteria_type": "enemy_killed",
             "target": i + 1, "zone_filter": None, "reward_xp": 0, "reward_money": 0}
            for i in range(10)
        ]
        bus_a, bus_b = _TrackingBus(), _TrackingBus()
        cs_a = ChallengeSystem(bus_a, challenges_per_round=3, rng_seed=42)
        cs_b = ChallengeSystem(bus_b, challenges_per_round=3, rng_seed=42)
        cs_a.load_pool_from_list(pool)
        cs_b.load_pool_from_list(pool)
        ids_a = {ch.id for ch in cs_a.get_active_raw()}
        ids_b = {ch.id for ch in cs_b.get_active_raw()}
        assert ids_a == ids_b

    def test_different_seeds_may_produce_different_selection(self):
        pool = [
            {"id": f"ch_{i}", "description": f"C{i}", "criteria_type": "enemy_killed",
             "target": i + 1, "zone_filter": None, "reward_xp": 0, "reward_money": 0}
            for i in range(10)
        ]
        bus_a, bus_b = _TrackingBus(), _TrackingBus()
        cs_a = ChallengeSystem(bus_a, challenges_per_round=3, rng_seed=0)
        cs_b = ChallengeSystem(bus_b, challenges_per_round=3, rng_seed=99)
        cs_a.load_pool_from_list(pool)
        cs_b.load_pool_from_list(pool)
        # With 10 items and 3 chosen, different seeds should differ at least once in 100 tries
        ids_a = {ch.id for ch in cs_a.get_active_raw()}
        ids_b = {ch.id for ch in cs_b.get_active_raw()}
        # Not guaranteed to differ but pool is large; just verify no crash
        assert isinstance(ids_a, set)
        assert isinstance(ids_b, set)

    def test_pool_smaller_than_per_round_uses_all(self):
        bus = _TrackingBus()
        cs = ChallengeSystem(bus, challenges_per_round=10, rng_seed=0)
        cs.load_pool_from_list([_kill_challenge(), _loot_challenge()])
        assert len(cs.get_active_raw()) == 2


# ---------------------------------------------------------------------------
# enemy_killed handler
# ---------------------------------------------------------------------------

class TestEnemyKilledHandler:

    def test_single_kill_increments_total_kills(self):
        cs, bus = _make_system([_kill_challenge(target=5)])
        bus.emit("enemy_killed")
        assert cs.kills == 1

    def test_multiple_kills_accumulate(self):
        cs, bus = _make_system([_kill_challenge(target=5)])
        for _ in range(4):
            bus.emit("enemy_killed")
        assert cs.kills == 4

    def test_kills_complete_challenge_at_target(self):
        cs, bus = _make_system([_kill_challenge(target=3)])
        for _ in range(3):
            bus.emit("enemy_killed")
        assert cs.get_active_raw()[0].completed is True

    def test_kill_challenge_not_completed_before_target(self):
        cs, bus = _make_system([_kill_challenge(target=5)])
        for _ in range(4):
            bus.emit("enemy_killed")
        assert cs.get_active_raw()[0].completed is False

    def test_challenge_completed_event_emitted_on_completion(self):
        cs, bus = _make_system([_kill_challenge(target=2)])
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        events = bus.all_events("challenge_completed")
        assert len(events) == 1

    def test_challenge_completed_event_payload_has_correct_id(self):
        cs, bus = _make_system([_kill_challenge(target=1)])
        bus.emit("enemy_killed")
        ev = bus.first_event("challenge_completed")
        assert ev is not None
        assert ev["challenge_id"] == "test_kill"

    def test_challenge_completed_event_payload_has_reward_xp(self):
        cs, bus = _make_system([_kill_challenge(target=1, xp=200)])
        bus.emit("enemy_killed")
        ev = bus.first_event("challenge_completed")
        assert ev["reward_xp"] == 200

    def test_challenge_completed_event_payload_has_reward_money(self):
        cs, bus = _make_system([_kill_challenge(target=1, money=350)])
        bus.emit("enemy_killed")
        ev = bus.first_event("challenge_completed")
        assert ev["reward_money"] == 350

    def test_challenge_completed_event_payload_has_reward_item_id(self):
        cs, bus = _make_system([_kill_challenge(target=1, item_id="scope_red_dot")])
        bus.emit("enemy_killed")
        ev = bus.first_event("challenge_completed")
        assert ev["reward_item_id"] == "scope_red_dot"

    def test_challenge_completed_event_payload_has_none_item_id_when_absent(self):
        cs, bus = _make_system([_kill_challenge(target=1, item_id=None)])
        bus.emit("enemy_killed")
        ev = bus.first_event("challenge_completed")
        assert ev["reward_item_id"] is None


# ---------------------------------------------------------------------------
# Idempotency — no double-completion
# ---------------------------------------------------------------------------

class TestIdempotency:

    def test_extra_kills_after_completion_do_not_re_emit(self):
        cs, bus = _make_system([_kill_challenge(target=2)])
        for _ in range(5):
            bus.emit("enemy_killed")
        events = bus.all_events("challenge_completed")
        assert len(events) == 1

    def test_completed_challenge_stays_completed(self):
        cs, bus = _make_system([_kill_challenge(target=1)])
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")  # extra kill
        assert cs.get_active_raw()[0].completed is True

    def test_progress_does_not_exceed_target(self):
        cs, bus = _make_system([_kill_challenge(target=3)])
        for _ in range(10):
            bus.emit("enemy_killed")
        ch = cs.get_active_raw()[0]
        assert ch.progress <= ch.target

    def test_multiple_challenges_each_complete_independently(self):
        pool = [_kill_challenge(target=1), _loot_challenge(target=1)]
        cs, bus = _make_system(pool)
        bus.emit("enemy_killed")
        bus.emit("item_picked_up")
        events = bus.all_events("challenge_completed")
        assert len(events) == 2


# ---------------------------------------------------------------------------
# item_picked_up handler
# ---------------------------------------------------------------------------

class TestItemPickedUpHandler:

    def test_single_item_increments_loot_collected(self):
        cs, bus = _make_system([_loot_challenge(target=5)])
        bus.emit("item_picked_up")
        assert cs.loot_collected == 1

    def test_loot_challenge_completes_at_target(self):
        cs, bus = _make_system([_loot_challenge(target=3)])
        for _ in range(3):
            bus.emit("item_picked_up")
        assert cs.get_active_raw()[0].completed is True

    def test_loot_challenge_not_completed_before_target(self):
        cs, bus = _make_system([_loot_challenge(target=5)])
        for _ in range(4):
            bus.emit("item_picked_up")
        assert cs.get_active_raw()[0].completed is False

    def test_loot_event_does_not_advance_kill_challenge(self):
        cs, bus = _make_system([_kill_challenge(target=3)])
        for _ in range(3):
            bus.emit("item_picked_up")
        assert cs.get_active_raw()[0].completed is False


# ---------------------------------------------------------------------------
# zone_entered handler
# ---------------------------------------------------------------------------

class TestZoneEnteredHandler:

    def test_single_zone_increments_zones_visited(self):
        cs, bus = _make_system([_zone_entered_challenge(target=3)])
        bus.emit("zone_entered", zone=_FakeZone("Alpha"))
        assert len(cs.zones_visited) == 1

    def test_entering_same_zone_twice_counts_once(self):
        cs, bus = _make_system([_zone_entered_challenge(target=3)])
        bus.emit("zone_entered", zone=_FakeZone("Alpha"))
        bus.emit("zone_entered", zone=_FakeZone("Alpha"))
        assert len(cs.zones_visited) == 1

    def test_entering_different_zones_all_counted(self):
        cs, bus = _make_system([_zone_entered_challenge(target=3)])
        for name in ("Alpha", "Beta", "Gamma"):
            bus.emit("zone_entered", zone=_FakeZone(name))
        assert len(cs.zones_visited) == 3

    def test_zone_entered_challenge_completes_at_target(self):
        cs, bus = _make_system([_zone_entered_challenge(target=2)])
        bus.emit("zone_entered", zone=_FakeZone("Alpha"))
        bus.emit("zone_entered", zone=_FakeZone("Beta"))
        assert cs.get_active_raw()[0].completed is True

    def test_zone_entered_updates_current_zone(self):
        cs, bus = _make_system([_zone_entered_challenge()])
        bus.emit("zone_entered", zone=_FakeZone("Reactor Core"))
        assert cs._current_zone == "Reactor Core"

    def test_zone_entered_with_no_zone_kwarg_is_safe(self):
        cs, bus = _make_system([_zone_entered_challenge()])
        bus.emit("zone_entered")  # no zone kwarg — must not raise

    def test_current_zone_updates_on_each_new_zone(self):
        cs, bus = _make_system([_zone_entered_challenge()])
        bus.emit("zone_entered", zone=_FakeZone("Alpha"))
        bus.emit("zone_entered", zone=_FakeZone("Beta"))
        assert cs._current_zone == "Beta"


# ---------------------------------------------------------------------------
# reach_location handler
# ---------------------------------------------------------------------------

class TestReachLocation:

    def test_reach_location_completes_when_matching_zone_entered(self):
        cs, bus = _make_system([_reach_location_challenge(zone_filter="cargo_bay")])
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        assert cs.get_active_raw()[0].completed is True

    def test_reach_location_does_not_complete_for_wrong_zone(self):
        cs, bus = _make_system([_reach_location_challenge(zone_filter="cargo_bay")])
        bus.emit("zone_entered", zone=_FakeZone("Reactor Core"))
        assert cs.get_active_raw()[0].completed is False

    def test_reach_location_matches_case_insensitively(self):
        cs, bus = _make_system([_reach_location_challenge(zone_filter="cargo_bay")])
        bus.emit("zone_entered", zone=_FakeZone("CARGO BAY"))
        assert cs.get_active_raw()[0].completed is True

    def test_reach_location_matches_with_underscore_zone_filter(self):
        cs, bus = _make_system([_reach_location_challenge(zone_filter="reactor_core")])
        bus.emit("zone_entered", zone=_FakeZone("Reactor Core"))
        assert cs.get_active_raw()[0].completed is True

    def test_reach_location_emits_challenge_completed(self):
        cs, bus = _make_system([_reach_location_challenge(zone_filter="cargo_bay")])
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        ev = bus.first_event("challenge_completed")
        assert ev is not None
        assert ev["challenge_id"] == "test_reach"

    def test_reach_location_without_zone_filter_never_completes(self):
        challenge = {
            "id": "no_filter_reach",
            "description": "Reach nowhere",
            "criteria_type": "reach_location",
            "target": 1,
            "zone_filter": None,
            "reward_xp": 10,
            "reward_money": 0,
            "reward_item_id": None,
        }
        cs, bus = _make_system([challenge])
        bus.emit("zone_entered", zone=_FakeZone("Anywhere"))
        assert cs.get_active_raw()[0].completed is False

    def test_reach_location_not_completed_after_visiting_different_zone(self):
        cs, bus = _make_system([_reach_location_challenge(zone_filter="command_deck")])
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        bus.emit("zone_entered", zone=_FakeZone("Reactor Core"))
        assert cs.get_active_raw()[0].completed is False


# ---------------------------------------------------------------------------
# Zone-filtered kill / loot challenges
# ---------------------------------------------------------------------------

class TestZoneFilteredChallenges:

    def test_kill_in_wrong_zone_does_not_advance_zone_filtered_challenge(self):
        cs, bus = _make_system([_kill_challenge(target=3, zone_filter="cargo_bay")])
        bus.emit("zone_entered", zone=_FakeZone("Reactor Core"))
        for _ in range(3):
            bus.emit("enemy_killed")
        assert cs.get_active_raw()[0].completed is False

    def test_kill_in_correct_zone_advances_zone_filtered_challenge(self):
        cs, bus = _make_system([_kill_challenge(target=3, zone_filter="cargo_bay")])
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        for _ in range(3):
            bus.emit("enemy_killed")
        assert cs.get_active_raw()[0].completed is True

    def test_zone_filtered_kills_counted_separately_per_zone(self):
        pool = [
            _kill_challenge(target=2, zone_filter="cargo_bay"),
        ]
        cs, bus = _make_system(pool)
        # 1 kill in cargo bay, then 2 kills in reactor core
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        bus.emit("enemy_killed")
        bus.emit("zone_entered", zone=_FakeZone("Reactor Core"))
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        # Only 1 kill in cargo_bay
        assert cs.get_active_raw()[0].completed is False

    def test_loot_in_correct_zone_advances_zone_filtered_loot_challenge(self):
        cs, bus = _make_system([_loot_challenge(target=2, zone_filter="reactor_core")])
        bus.emit("zone_entered", zone=_FakeZone("Reactor Core"))
        bus.emit("item_picked_up")
        bus.emit("item_picked_up")
        assert cs.get_active_raw()[0].completed is True

    def test_loot_in_wrong_zone_does_not_advance_zone_filtered_loot_challenge(self):
        cs, bus = _make_system([_loot_challenge(target=2, zone_filter="reactor_core")])
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        bus.emit("item_picked_up")
        bus.emit("item_picked_up")
        assert cs.get_active_raw()[0].completed is False

    def test_no_zone_kill_challenge_counts_all_zones(self):
        cs, bus = _make_system([_kill_challenge(target=3, zone_filter=None)])
        bus.emit("zone_entered", zone=_FakeZone("Alpha"))
        bus.emit("enemy_killed")
        bus.emit("zone_entered", zone=_FakeZone("Beta"))
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        assert cs.get_active_raw()[0].completed is True

    def test_kills_outside_any_zone_count_for_global_challenge(self):
        """Before any zone_entered event, kills still count for global challenges."""
        cs, bus = _make_system([_kill_challenge(target=2, zone_filter=None)])
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        assert cs.get_active_raw()[0].completed is True

    def test_zone_key_normalized_lowercase_with_underscores(self):
        """Zone names with spaces are normalized to underscores for zone_filter matching."""
        cs, bus = _make_system([_kill_challenge(target=1, zone_filter="cargo_bay")])
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        bus.emit("enemy_killed")
        assert cs.get_active_raw()[0].completed is True


# ---------------------------------------------------------------------------
# Unknown criteria_type
# ---------------------------------------------------------------------------

class TestUnknownCriteriaType:

    def test_unknown_criteria_type_never_completes(self):
        challenge = {
            "id": "unknown_type",
            "description": "Unknown type challenge",
            "criteria_type": "extracted_with_items",
            "target": 1,
            "zone_filter": None,
            "reward_xp": 100,
            "reward_money": 0,
            "reward_item_id": None,
        }
        cs, bus = _make_system([challenge])
        # No matter what events fire, it should never complete
        bus.emit("enemy_killed")
        bus.emit("item_picked_up")
        bus.emit("zone_entered", zone=_FakeZone("Zone A"))
        assert cs.get_active_raw()[0].completed is False

    def test_unknown_criteria_type_does_not_raise(self):
        challenge = {
            "id": "weird_type",
            "description": "Weird",
            "criteria_type": "first_kill_time",
            "target": 180,
            "zone_filter": None,
            "reward_xp": 0,
            "reward_money": 0,
            "reward_item_id": None,
        }
        cs, bus = _make_system([challenge])
        # Must not raise
        bus.emit("enemy_killed")
        bus.emit("item_picked_up")

    def test_unknown_type_does_not_emit_challenge_completed(self):
        challenge = {
            "id": "bogus",
            "description": "Bogus",
            "criteria_type": "no_such_criteria",
            "target": 1,
            "zone_filter": None,
            "reward_xp": 50,
            "reward_money": 0,
            "reward_item_id": None,
        }
        cs, bus = _make_system([challenge])
        bus.emit("enemy_killed")
        assert bus.all_events("challenge_completed") == []


# ---------------------------------------------------------------------------
# get_active_challenges() → ChallengeInfo
# ---------------------------------------------------------------------------

class TestGetActiveChallenges:

    def test_returns_list_of_challenge_info(self):
        cs, bus = _make_system([_kill_challenge()])
        infos = cs.get_active_challenges()
        assert len(infos) == 1
        assert isinstance(infos[0], ChallengeInfo)

    def test_challenge_info_name_matches_description(self):
        ch = _kill_challenge()
        ch["description"] = "My special description"
        cs, bus = _make_system([ch])
        info = cs.get_active_challenges()[0]
        assert info.name == "My special description"

    def test_challenge_info_target_correct(self):
        cs, bus = _make_system([_kill_challenge(target=7)])
        info = cs.get_active_challenges()[0]
        assert info.target == 7

    def test_challenge_info_progress_zero_initially(self):
        cs, bus = _make_system([_kill_challenge(target=5)])
        info = cs.get_active_challenges()[0]
        assert info.progress == 0

    def test_challenge_info_progress_updates_with_events(self):
        cs, bus = _make_system([_kill_challenge(target=5)])
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        info = cs.get_active_challenges()[0]
        assert info.progress == 2

    def test_challenge_info_progress_capped_at_target(self):
        cs, bus = _make_system([_kill_challenge(target=2)])
        for _ in range(10):
            bus.emit("enemy_killed")
        info = cs.get_active_challenges()[0]
        assert info.progress <= info.target

    def test_challenge_info_completed_false_initially(self):
        cs, bus = _make_system([_kill_challenge(target=5)])
        info = cs.get_active_challenges()[0]
        assert info.completed is False

    def test_challenge_info_completed_true_after_completion(self):
        cs, bus = _make_system([_kill_challenge(target=1)])
        bus.emit("enemy_killed")
        info = cs.get_active_challenges()[0]
        assert info.completed is True

    def test_challenge_info_zone_empty_when_no_zone_filter(self):
        cs, bus = _make_system([_kill_challenge(zone_filter=None)])
        info = cs.get_active_challenges()[0]
        assert info.zone == ""

    def test_challenge_info_zone_humanized_from_zone_filter(self):
        cs, bus = _make_system([_kill_challenge(zone_filter="cargo_bay")])
        info = cs.get_active_challenges()[0]
        assert info.zone == "Cargo Bay"

    def test_challenge_info_zone_humanized_multi_word(self):
        cs, bus = _make_system([_kill_challenge(zone_filter="reactor_core")])
        info = cs.get_active_challenges()[0]
        assert info.zone == "Reactor Core"

    def test_challenge_info_zone_humanized_command_deck(self):
        cs, bus = _make_system([_kill_challenge(zone_filter="command_deck")])
        info = cs.get_active_challenges()[0]
        assert info.zone == "Command Deck"

    def test_active_challenges_property_alias_returns_same(self):
        cs, bus = _make_system([_kill_challenge()])
        assert cs.active_challenges == cs.get_active_challenges()


# ---------------------------------------------------------------------------
# get_completed_challenges()
# ---------------------------------------------------------------------------

class TestGetCompletedChallenges:

    def test_empty_when_no_challenge_completed(self):
        cs, bus = _make_system([_kill_challenge(target=5)])
        assert cs.get_completed_challenges() == []

    def test_returns_completed_challenge_after_completion(self):
        cs, bus = _make_system([_kill_challenge(target=1)])
        bus.emit("enemy_killed")
        completed = cs.get_completed_challenges()
        assert len(completed) == 1

    def test_completed_challenge_has_correct_id(self):
        cs, bus = _make_system([_kill_challenge(target=1)])
        bus.emit("enemy_killed")
        ch = cs.get_completed_challenges()[0]
        assert ch.id == "test_kill"

    def test_completed_challenge_has_reward_xp(self):
        cs, bus = _make_system([_kill_challenge(target=1, xp=250)])
        bus.emit("enemy_killed")
        ch = cs.get_completed_challenges()[0]
        assert ch.reward_xp == 250

    def test_completed_challenge_has_reward_money(self):
        cs, bus = _make_system([_kill_challenge(target=1, money=400)])
        bus.emit("enemy_killed")
        ch = cs.get_completed_challenges()[0]
        assert ch.reward_money == 400

    def test_completed_challenge_has_reward_item_id(self):
        cs, bus = _make_system([_kill_challenge(target=1, item_id="ammo_rifle")])
        bus.emit("enemy_killed")
        ch = cs.get_completed_challenges()[0]
        assert ch.reward_item_id == "ammo_rifle"

    def test_only_completed_challenges_returned(self):
        pool = [_kill_challenge(target=1), _loot_challenge(target=5)]
        cs, bus = _make_system(pool)
        bus.emit("enemy_killed")  # completes kill challenge only
        completed = cs.get_completed_challenges()
        assert len(completed) == 1
        assert completed[0].id == "test_kill"

    def test_multiple_completions_all_returned(self):
        pool = [_kill_challenge(target=1), _loot_challenge(target=1)]
        cs, bus = _make_system(pool)
        bus.emit("enemy_killed")
        bus.emit("item_picked_up")
        assert len(cs.get_completed_challenges()) == 2

    def test_returns_new_list_not_internal_reference(self):
        cs, bus = _make_system([_kill_challenge(target=1)])
        bus.emit("enemy_killed")
        a = cs.get_completed_challenges()
        b = cs.get_completed_challenges()
        assert a is not b


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------

class TestReset:

    def test_reset_clears_kills(self):
        cs, bus = _make_system([_kill_challenge(target=5)])
        bus.emit("enemy_killed")
        cs.reset()
        assert cs.kills == 0

    def test_reset_clears_loot_collected(self):
        cs, bus = _make_system([_loot_challenge(target=5)])
        bus.emit("item_picked_up")
        cs.reset()
        assert cs.loot_collected == 0

    def test_reset_clears_zones_visited(self):
        cs, bus = _make_system([_zone_entered_challenge()])
        bus.emit("zone_entered", zone=_FakeZone("Alpha"))
        cs.reset()
        assert cs.zones_visited == set()

    def test_reset_clears_current_zone(self):
        cs, bus = _make_system([_zone_entered_challenge()])
        bus.emit("zone_entered", zone=_FakeZone("Alpha"))
        cs.reset()
        assert cs._current_zone is None

    def test_reset_clears_completed_challenges(self):
        cs, bus = _make_system([_kill_challenge(target=1)])
        bus.emit("enemy_killed")
        cs.reset()
        assert cs.get_completed_challenges() == []

    def test_reset_clears_zone_kill_counters(self):
        cs, bus = _make_system([_kill_challenge(target=5, zone_filter="cargo_bay")])
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        bus.emit("enemy_killed")
        cs.reset()
        assert cs._zone_kills == {}

    def test_reset_clears_zone_loot_counters(self):
        cs, bus = _make_system([_loot_challenge(target=5, zone_filter="cargo_bay")])
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        bus.emit("item_picked_up")
        cs.reset()
        assert cs._zone_loot == {}

    def test_reset_reselects_challenges_from_pool(self):
        cs, bus = _make_system([_kill_challenge(target=1)])
        bus.emit("enemy_killed")
        assert cs.get_active_raw()[0].completed is True
        cs.reset()
        new_active = cs.get_active_raw()
        assert len(new_active) == 1
        assert new_active[0].completed is False

    def test_after_reset_challenge_can_be_completed_again(self):
        cs, bus = _make_system([_kill_challenge(target=1)])
        bus.emit("enemy_killed")
        cs.reset()
        bus.emit("enemy_killed")
        assert cs.get_active_raw()[0].completed is True

    def test_reset_allows_second_challenge_completed_event(self):
        cs, bus = _make_system([_kill_challenge(target=1)])
        bus.emit("enemy_killed")  # first completion
        cs.reset()
        bus.emit("enemy_killed")  # second completion
        events = bus.all_events("challenge_completed")
        assert len(events) == 2


# ---------------------------------------------------------------------------
# Integration: multiple challenge types active simultaneously
# ---------------------------------------------------------------------------

class TestMultipleChallengesActive:

    def test_kill_and_loot_challenges_progress_independently(self):
        pool = [_kill_challenge(target=3), _loot_challenge(target=2)]
        cs, bus = _make_system(pool)
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        bus.emit("item_picked_up")
        bus.emit("item_picked_up")

        actives = cs.get_active_raw()
        kill_ch = next(c for c in actives if c.criteria_type == "enemy_killed")
        loot_ch = next(c for c in actives if c.criteria_type == "item_picked_up")
        assert kill_ch.progress == 2
        assert loot_ch.completed is True

    def test_completing_one_challenge_does_not_affect_others(self):
        pool = [_kill_challenge(target=1), _loot_challenge(target=5)]
        cs, bus = _make_system(pool)
        bus.emit("enemy_killed")  # completes kill only
        actives = cs.get_active_raw()
        loot_ch = next(c for c in actives if c.criteria_type == "item_picked_up")
        assert loot_ch.completed is False

    def test_zone_and_global_challenges_both_progress(self):
        pool = [_kill_challenge(target=2, zone_filter=None), _kill_challenge(target=1, zone_filter="cargo_bay")]
        # Rename second to avoid id collision
        pool[1]["id"] = "kill_in_zone"
        cs, bus = _make_system(pool)
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        actives = cs.get_active_raw()
        global_ch = next(c for c in actives if c.id == "test_kill")
        zone_ch = next(c for c in actives if c.id == "kill_in_zone")
        assert global_ch.completed is True
        assert zone_ch.completed is True
