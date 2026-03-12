"""Tests for the data-driven vendor challenge system.

Covers:
- JSON pool loading and challenge selection
- Progress tracking via EventBus events (kills, loot, zones)
- Zone-filtered challenge tracking
- Completion detection and reward emission
- HUD integration via ChallengeInfo snapshots
- Reset for new rounds
"""
from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.core.event_bus import EventBus
from src.systems.challenge_system import ChallengeSystem, DEFAULT_CHALLENGES_PER_ROUND
from src.ui.hud_state import ChallengeInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool() -> list[dict[str, Any]]:
    """Return a minimal challenge pool for testing."""
    return [
        {
            "id": "kill_5",
            "description": "Eliminate 5 enemies",
            "criteria_type": "enemy_killed",
            "target": 5,
            "zone_filter": None,
            "reward_xp": 100,
            "reward_money": 200,
        },
        {
            "id": "loot_3",
            "description": "Pick up 3 items",
            "criteria_type": "item_picked_up",
            "target": 3,
            "zone_filter": None,
            "reward_xp": 50,
            "reward_money": 75,
        },
        {
            "id": "explore_2",
            "description": "Visit 2 zones",
            "criteria_type": "zone_entered",
            "target": 2,
            "zone_filter": None,
            "reward_xp": 80,
            "reward_money": 100,
        },
        {
            "id": "zone_alpha_kill_3",
            "description": "Kill 3 enemies in zone_alpha",
            "criteria_type": "enemy_killed",
            "target": 3,
            "zone_filter": "zone_alpha",
            "reward_xp": 120,
            "reward_money": 175,
        },
        {
            "id": "loot_zone_beta",
            "description": "Collect 2 items in zone_beta",
            "criteria_type": "item_picked_up",
            "target": 2,
            "zone_filter": "zone_beta",
            "reward_xp": 60,
            "reward_money": 90,
        },
    ]


def _make_zone(name: str) -> MagicMock:
    """Create a mock zone with a .name attribute."""
    zone = MagicMock()
    zone.name = name
    return zone


def _write_challenges_json(tmp_path, pool: list[dict]) -> str:
    """Write a challenges.json file and return its path."""
    path = tmp_path / "challenges.json"
    path.write_text(json.dumps({"challenges": pool}))
    return str(path)


# ---------------------------------------------------------------------------
# Pool Loading
# ---------------------------------------------------------------------------

class TestPoolLoading:
    def test_load_from_json_file(self, tmp_path):
        pool = _make_pool()
        path = _write_challenges_json(tmp_path, pool)
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path=path, rng_seed=42)
        assert len(cs._pool) == len(pool)

    def test_load_from_nonexistent_file(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        assert cs._pool == []
        assert cs.get_active_challenges() == []

    def test_load_from_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json{{{")
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path=str(path))
        assert cs._pool == []

    def test_load_pool_from_list(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        pool = _make_pool()
        cs.load_pool_from_list(pool)
        assert len(cs._pool) == len(pool)
        assert len(cs.get_active_challenges()) == DEFAULT_CHALLENGES_PER_ROUND


# ---------------------------------------------------------------------------
# Challenge Selection
# ---------------------------------------------------------------------------

class TestChallengeSelection:
    def test_selects_correct_number(self, tmp_path):
        pool = _make_pool()
        path = _write_challenges_json(tmp_path, pool)
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path=path, challenges_per_round=3, rng_seed=1)
        assert len(cs.get_active_challenges()) == 3

    def test_selects_fewer_when_pool_is_small(self, tmp_path):
        pool = _make_pool()[:2]
        path = _write_challenges_json(tmp_path, pool)
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path=path, challenges_per_round=5, rng_seed=1)
        assert len(cs.get_active_challenges()) == 2

    def test_deterministic_with_seed(self, tmp_path):
        pool = _make_pool()
        path = _write_challenges_json(tmp_path, pool)
        bus1 = EventBus()
        bus2 = EventBus()
        cs1 = ChallengeSystem(bus1, challenges_path=path, rng_seed=42)
        cs2 = ChallengeSystem(bus2, challenges_path=path, rng_seed=42)
        ids1 = [ch.id for ch in cs1.get_active_raw()]
        ids2 = [ch.id for ch in cs2.get_active_raw()]
        assert ids1 == ids2

    def test_empty_pool_yields_no_challenges(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        assert cs.get_active_challenges() == []

    def test_at_least_three_active_from_default_pool(self):
        """The default data/challenges.json must have >= 3 entries."""
        bus = EventBus()
        cs = ChallengeSystem(bus, rng_seed=99)
        assert len(cs.get_active_challenges()) >= 3


# ---------------------------------------------------------------------------
# Progress Tracking — Kills
# ---------------------------------------------------------------------------

class TestKillTracking:
    def test_global_kill_progress(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "kill_3", "description": "Kill 3",
            "criteria_type": "enemy_killed", "target": 3,
            "zone_filter": None, "reward_xp": 50, "reward_money": 100,
        }])
        bus.emit("enemy_killed", enemy_type="grunt")
        bus.emit("enemy_killed", enemy_type="grunt")
        infos = cs.get_active_challenges()
        assert len(infos) == 1
        assert infos[0].progress == 2
        assert infos[0].completed is False

    def test_kill_completion(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "kill_2", "description": "Kill 2",
            "criteria_type": "enemy_killed", "target": 2,
            "zone_filter": None, "reward_xp": 50, "reward_money": 100,
        }])
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        infos = cs.get_active_challenges()
        assert infos[0].completed is True
        assert infos[0].progress == 2


# ---------------------------------------------------------------------------
# Progress Tracking — Loot
# ---------------------------------------------------------------------------

class TestLootTracking:
    def test_global_loot_progress(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "loot_3", "description": "Collect 3",
            "criteria_type": "item_picked_up", "target": 3,
            "zone_filter": None, "reward_xp": 50, "reward_money": 75,
        }])
        bus.emit("item_picked_up")
        bus.emit("item_picked_up")
        infos = cs.get_active_challenges()
        assert infos[0].progress == 2

    def test_loot_completion(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "loot_1", "description": "Collect 1",
            "criteria_type": "item_picked_up", "target": 1,
            "zone_filter": None, "reward_xp": 10, "reward_money": 10,
        }])
        bus.emit("item_picked_up")
        assert cs.get_active_challenges()[0].completed is True


# ---------------------------------------------------------------------------
# Progress Tracking — Zone Exploration
# ---------------------------------------------------------------------------

class TestZoneTracking:
    def test_zone_entered_progress(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "explore_2", "description": "Visit 2 zones",
            "criteria_type": "zone_entered", "target": 2,
            "zone_filter": None, "reward_xp": 80, "reward_money": 100,
        }])
        bus.emit("zone_entered", zone=_make_zone("Zone A"))
        infos = cs.get_active_challenges()
        assert infos[0].progress == 1
        assert infos[0].completed is False

    def test_same_zone_counted_once(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "explore_2", "description": "Visit 2 zones",
            "criteria_type": "zone_entered", "target": 2,
            "zone_filter": None, "reward_xp": 80, "reward_money": 100,
        }])
        zone_a = _make_zone("Zone A")
        bus.emit("zone_entered", zone=zone_a)
        bus.emit("zone_entered", zone=zone_a)
        assert cs.get_active_challenges()[0].progress == 1

    def test_zone_exploration_completion(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "explore_2", "description": "Visit 2 zones",
            "criteria_type": "zone_entered", "target": 2,
            "zone_filter": None, "reward_xp": 80, "reward_money": 100,
        }])
        bus.emit("zone_entered", zone=_make_zone("Zone A"))
        bus.emit("zone_entered", zone=_make_zone("Zone B"))
        assert cs.get_active_challenges()[0].completed is True


# ---------------------------------------------------------------------------
# Zone-Filtered Challenges
# ---------------------------------------------------------------------------

class TestZoneFilter:
    def test_zone_filtered_kills(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "zone_alpha_kill",
            "description": "Kill 2 in zone_alpha",
            "criteria_type": "enemy_killed", "target": 2,
            "zone_filter": "zone_alpha",
            "reward_xp": 100, "reward_money": 150,
        }])
        # Enter zone_alpha and kill
        bus.emit("zone_entered", zone=_make_zone("zone_alpha"))
        bus.emit("enemy_killed")
        assert cs.get_active_challenges()[0].progress == 1

    def test_kills_in_wrong_zone_dont_count(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "zone_alpha_kill",
            "description": "Kill 2 in zone_alpha",
            "criteria_type": "enemy_killed", "target": 2,
            "zone_filter": "zone_alpha",
            "reward_xp": 100, "reward_money": 150,
        }])
        # Enter zone_beta and kill -- should NOT count for zone_alpha
        bus.emit("zone_entered", zone=_make_zone("zone_beta"))
        bus.emit("enemy_killed")
        assert cs.get_active_challenges()[0].progress == 0

    def test_zone_filtered_loot(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "loot_zone_beta",
            "description": "Collect 2 in zone_beta",
            "criteria_type": "item_picked_up", "target": 2,
            "zone_filter": "zone_beta",
            "reward_xp": 60, "reward_money": 90,
        }])
        bus.emit("zone_entered", zone=_make_zone("zone_beta"))
        bus.emit("item_picked_up")
        bus.emit("item_picked_up")
        assert cs.get_active_challenges()[0].completed is True

    def test_zone_filtered_completion_emits_reward(self):
        bus = EventBus()
        completed_events = []
        bus.subscribe("challenge_completed", lambda **kw: completed_events.append(kw))

        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "zone_alpha_kill_2",
            "description": "Kill 2 in zone_alpha",
            "criteria_type": "enemy_killed", "target": 2,
            "zone_filter": "zone_alpha",
            "reward_xp": 120, "reward_money": 175,
        }])
        bus.emit("zone_entered", zone=_make_zone("zone_alpha"))
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        assert len(completed_events) == 1
        assert completed_events[0]["challenge_id"] == "zone_alpha_kill_2"


# ---------------------------------------------------------------------------
# Reward Emission
# ---------------------------------------------------------------------------

class TestRewardEmission:
    def test_completion_emits_challenge_completed(self):
        bus = EventBus()
        completed_events = []
        bus.subscribe("challenge_completed", lambda **kw: completed_events.append(kw))

        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "kill_1", "description": "Kill 1",
            "criteria_type": "enemy_killed", "target": 1,
            "zone_filter": None, "reward_xp": 100, "reward_money": 200,
        }])
        bus.emit("enemy_killed")
        assert len(completed_events) == 1
        assert completed_events[0]["challenge_id"] == "kill_1"
        assert completed_events[0]["reward_xp"] == 100
        assert completed_events[0]["reward_money"] == 200

    def test_no_double_reward_on_extra_progress(self):
        bus = EventBus()
        completed_events = []
        bus.subscribe("challenge_completed", lambda **kw: completed_events.append(kw))

        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "kill_1", "description": "Kill 1",
            "criteria_type": "enemy_killed", "target": 1,
            "zone_filter": None, "reward_xp": 100, "reward_money": 200,
        }])
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        assert len(completed_events) == 1

    def test_multiple_challenges_can_complete_independently(self):
        bus = EventBus()
        completed_ids = []
        bus.subscribe("challenge_completed", lambda **kw: completed_ids.append(kw["challenge_id"]))

        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([
            {
                "id": "kill_1", "description": "Kill 1",
                "criteria_type": "enemy_killed", "target": 1,
                "zone_filter": None, "reward_xp": 50, "reward_money": 50,
            },
            {
                "id": "loot_1", "description": "Collect 1",
                "criteria_type": "item_picked_up", "target": 1,
                "zone_filter": None, "reward_xp": 50, "reward_money": 50,
            },
        ])
        bus.emit("enemy_killed")
        assert "kill_1" in completed_ids
        assert "loot_1" not in completed_ids

        bus.emit("item_picked_up")
        assert "loot_1" in completed_ids


# ---------------------------------------------------------------------------
# HUD Integration — ChallengeInfo Snapshots
# ---------------------------------------------------------------------------

class TestHUDIntegration:
    def test_get_active_challenges_returns_challenge_infos(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "kill_5", "description": "Kill 5 enemies",
            "criteria_type": "enemy_killed", "target": 5,
            "zone_filter": None, "reward_xp": 100, "reward_money": 200,
        }])
        infos = cs.get_active_challenges()
        assert len(infos) == 1
        assert isinstance(infos[0], ChallengeInfo)
        assert infos[0].name == "Kill 5 enemies"
        assert infos[0].target == 5
        assert infos[0].progress == 0
        assert infos[0].completed is False

    def test_progress_reflected_in_hud_snapshot(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "kill_3", "description": "Kill 3",
            "criteria_type": "enemy_killed", "target": 3,
            "zone_filter": None, "reward_xp": 50, "reward_money": 100,
        }])
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        info = cs.get_active_challenges()[0]
        assert info.progress == 2
        assert info.completed is False

    def test_completed_reflected_in_hud_snapshot(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "kill_1", "description": "Kill 1",
            "criteria_type": "enemy_killed", "target": 1,
            "zone_filter": None, "reward_xp": 50, "reward_money": 100,
        }])
        bus.emit("enemy_killed")
        info = cs.get_active_challenges()[0]
        assert info.completed is True
        assert info.progress == 1

    def test_active_challenges_property_alias(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "kill_1", "description": "Kill 1",
            "criteria_type": "enemy_killed", "target": 1,
            "zone_filter": None, "reward_xp": 10, "reward_money": 10,
        }])
        # The property alias should work the same as the method
        assert cs.active_challenges == cs.get_active_challenges()

    def test_progress_clamped_to_target(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "kill_1", "description": "Kill 1",
            "criteria_type": "enemy_killed", "target": 1,
            "zone_filter": None, "reward_xp": 10, "reward_money": 10,
        }])
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        info = cs.get_active_challenges()[0]
        # Progress in the HUD snapshot should not exceed target
        assert info.progress <= info.target


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_progress(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "kill_3", "description": "Kill 3",
            "criteria_type": "enemy_killed", "target": 3,
            "zone_filter": None, "reward_xp": 50, "reward_money": 100,
        }])
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")
        assert cs.get_active_challenges()[0].progress == 2

        cs.reset()
        assert cs.kills == 0
        assert cs.loot_collected == 0
        assert len(cs.zones_visited) == 0

    def test_reset_reselects_challenges(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        pool = _make_pool()
        cs.load_pool_from_list(pool)
        old_ids = [ch.id for ch in cs.get_active_raw()]
        # Even after reset, challenges should be present (re-selected)
        cs.reset()
        assert len(cs.get_active_challenges()) == min(DEFAULT_CHALLENGES_PER_ROUND, len(pool))


# ---------------------------------------------------------------------------
# Default challenges.json Integration
# ---------------------------------------------------------------------------

class TestDefaultChallengesJSON:
    def test_default_pool_has_at_least_three_challenges(self):
        """The bundled data/challenges.json must contain >= 3 challenges."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "challenges.json",
        )
        with open(path) as f:
            data = json.load(f)
        assert len(data["challenges"]) >= 3

    def test_all_entries_have_required_fields(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "challenges.json",
        )
        with open(path) as f:
            data = json.load(f)
        required = {"id", "description", "criteria_type", "target", "reward_xp", "reward_money"}
        for ch in data["challenges"]:
            missing = required - set(ch.keys())
            assert not missing, f"Challenge {ch.get('id', '?')} missing: {missing}"

    def test_system_loads_default_pool(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, rng_seed=42)
        assert len(cs.get_active_challenges()) >= 3


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_unsupported_criteria_type(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "unknown", "description": "Unknown type",
            "criteria_type": "mysterious_event", "target": 1,
            "zone_filter": None, "reward_xp": 10, "reward_money": 10,
        }])
        # Should not crash, progress stays at 0
        bus.emit("enemy_killed")
        assert cs.get_active_challenges()[0].progress == 0

    def test_zone_entered_with_no_zone_kwarg(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "explore", "description": "Visit 1 zone",
            "criteria_type": "zone_entered", "target": 1,
            "zone_filter": None, "reward_xp": 10, "reward_money": 10,
        }])
        # Should not crash when zone kwarg is missing
        bus.emit("zone_entered")
        assert cs.get_active_challenges()[0].progress == 0

    def test_challenge_with_target_zero(self):
        bus = EventBus()
        cs = ChallengeSystem(bus, challenges_path="/nonexistent/path.json")
        cs.load_pool_from_list([{
            "id": "zero", "description": "Impossible",
            "criteria_type": "enemy_killed", "target": 0,
            "zone_filter": None, "reward_xp": 10, "reward_money": 10,
        }])
        # Target 0 is edge case; any kill should complete it
        # (progress 0 >= target 0 would trigger on load_pool_from_list -> _check_challenges)
        # Actually, after selection, _check_challenges is not called automatically
        # so it won't be completed until next event
        bus.emit("enemy_killed")
        info = cs.get_active_challenges()[0]
        assert info.completed is True
