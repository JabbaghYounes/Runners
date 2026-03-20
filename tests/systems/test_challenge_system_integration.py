"""Integration tests for ChallengeSystem + EventBus + PostRound end-to-end flows.

Covers:
- Full round flow: events → challenge completion → PostRound rewards applied
- Per-zone challenge flow: enter zone → kill enemies → reward at extraction
- reach_location flow: enter zone → reward at extraction
- Multiple simultaneous challenges, each completing independently
- ChallengeSystem.reset() + new round flow

Run: pytest tests/systems/test_challenge_system_integration.py
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from src.core.event_bus import EventBus
from src.core.round_summary import RoundSummary
from src.scenes.post_round import PostRound
from src.systems.challenge_system import ChallengeSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TrackingBus(EventBus):
    def __init__(self) -> None:
        super().__init__()
        self.emitted: list[dict] = []

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        self.emitted.append({"event": event, **kwargs})
        super().emit(event, *args, **kwargs)

    def all_events(self, name: str) -> list[dict]:
        return [e for e in self.emitted if e["event"] == name]


class _FakeZone:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_cs(pool: list[dict], *, seed: int = 0) -> tuple[ChallengeSystem, _TrackingBus]:
    bus = _TrackingBus()
    cs = ChallengeSystem(bus, challenges_per_round=99, rng_seed=seed)
    cs.load_pool_from_list(pool)
    return cs, bus


def _summary(cs: ChallengeSystem, status: str = "success") -> RoundSummary:
    completed = len(cs.get_completed_challenges())
    total = len(cs.get_active_raw())
    return RoundSummary(
        extraction_status=status,
        extracted_items=[],
        xp_earned=0,
        money_earned=0,
        kills=0,
        challenges_completed=completed,
        challenges_total=total,
        level_before=1,
    )


def _post_round(cs: ChallengeSystem, summary: RoundSummary) -> tuple[PostRound, MagicMock, MagicMock]:
    xs = MagicMock()
    xs.level = 2
    cur = MagicMock()
    pr = PostRound(
        summary=summary,
        xp_system=xs,
        currency=cur,
        save_manager=MagicMock(),
        scene_manager=MagicMock(),
        audio_system=MagicMock(),
        challenge_system=cs,
    )
    return pr, xs, cur


# ---------------------------------------------------------------------------
# Full flow: emit events → challenge completes → PostRound applies rewards
# ---------------------------------------------------------------------------

class TestKillChallengeFullFlow:

    def test_kill_challenge_reward_xp_applied_at_post_round(self):
        pool = [{
            "id": "kill_5",
            "description": "Kill 5 enemies",
            "criteria_type": "enemy_killed",
            "target": 5,
            "zone_filter": None,
            "reward_xp": 200,
            "reward_money": 0,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)

        for _ in range(5):
            bus.emit("enemy_killed")

        assert cs.get_completed_challenges()[0].id == "kill_5"
        summary = _summary(cs)
        _, xs, _ = _post_round(cs, summary)

        assert call(200) in xs.award.call_args_list

    def test_kill_challenge_reward_money_applied_at_post_round(self):
        pool = [{
            "id": "kill_3",
            "description": "Kill 3 enemies",
            "criteria_type": "enemy_killed",
            "target": 3,
            "zone_filter": None,
            "reward_xp": 0,
            "reward_money": 300,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)
        for _ in range(3):
            bus.emit("enemy_killed")

        summary = _summary(cs)
        _, _, cur = _post_round(cs, summary)

        assert call(300) in cur.add.call_args_list

    def test_incomplete_kill_challenge_earns_no_bonus(self):
        pool = [{
            "id": "kill_10",
            "description": "Kill 10 enemies",
            "criteria_type": "enemy_killed",
            "target": 10,
            "zone_filter": None,
            "reward_xp": 500,
            "reward_money": 800,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)
        for _ in range(5):  # only 5 of 10 required
            bus.emit("enemy_killed")

        summary = _summary(cs)
        pr, xs, cur = _post_round(cs, summary)

        assert summary.challenge_bonus_xp == 0
        assert summary.challenge_bonus_money == 0


# ---------------------------------------------------------------------------
# Per-zone kill challenge full flow
# ---------------------------------------------------------------------------

class TestZoneKillChallengeFullFlow:

    def test_zone_kill_challenge_complete_in_correct_zone(self):
        pool = [{
            "id": "cargo_killer_3",
            "description": "Kill 3 in Cargo Bay",
            "criteria_type": "enemy_killed",
            "target": 3,
            "zone_filter": "cargo_bay",
            "reward_xp": 120,
            "reward_money": 200,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)

        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        for _ in range(3):
            bus.emit("enemy_killed")

        assert cs.get_active_raw()[0].completed is True
        summary = _summary(cs)
        _, xs, cur = _post_round(cs, summary)

        assert summary.challenge_bonus_xp == 120
        assert summary.challenge_bonus_money == 200

    def test_zone_kill_challenge_not_complete_if_kills_in_wrong_zone(self):
        pool = [{
            "id": "cargo_killer_3",
            "description": "Kill 3 in Cargo Bay",
            "criteria_type": "enemy_killed",
            "target": 3,
            "zone_filter": "cargo_bay",
            "reward_xp": 120,
            "reward_money": 200,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)

        # kills in reactor core — should not count
        bus.emit("zone_entered", zone=_FakeZone("Reactor Core"))
        for _ in range(3):
            bus.emit("enemy_killed")

        assert cs.get_active_raw()[0].completed is False

    def test_partial_kills_across_zones_completes_when_correct_zone_reached(self):
        pool = [{
            "id": "cargo_killer_2",
            "description": "Kill 2 in Cargo Bay",
            "criteria_type": "enemy_killed",
            "target": 2,
            "zone_filter": "cargo_bay",
            "reward_xp": 100,
            "reward_money": 150,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)

        # First kill outside zone
        bus.emit("zone_entered", zone=_FakeZone("Reactor Core"))
        bus.emit("enemy_killed")

        # Enter target zone and kill
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        bus.emit("enemy_killed")
        bus.emit("enemy_killed")

        assert cs.get_active_raw()[0].completed is True


# ---------------------------------------------------------------------------
# Loot challenge full flow
# ---------------------------------------------------------------------------

class TestLootChallengeFullFlow:

    def test_loot_challenge_reward_applied_after_collection(self):
        pool = [{
            "id": "loot_3_cargo",
            "description": "Collect 3 in Cargo Bay",
            "criteria_type": "item_picked_up",
            "target": 3,
            "zone_filter": "cargo_bay",
            "reward_xp": 100,
            "reward_money": 150,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)

        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        for _ in range(3):
            bus.emit("item_picked_up")

        summary = _summary(cs)
        pr, xs, cur = _post_round(cs, summary)

        assert summary.challenge_bonus_xp == 100
        assert summary.challenge_bonus_money == 150


# ---------------------------------------------------------------------------
# reach_location challenge full flow
# ---------------------------------------------------------------------------

class TestReachLocationChallengeFullFlow:

    def test_reach_location_rewards_applied_at_post_round(self):
        pool = [{
            "id": "cargo_visitor",
            "description": "Reach the Cargo Bay",
            "criteria_type": "reach_location",
            "target": 1,
            "zone_filter": "cargo_bay",
            "reward_xp": 50,
            "reward_money": 100,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)

        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))

        summary = _summary(cs)
        pr, xs, cur = _post_round(cs, summary)

        assert summary.challenge_bonus_xp == 50
        assert summary.challenge_bonus_money == 100

    def test_reach_location_not_rewarded_if_zone_never_visited(self):
        pool = [{
            "id": "reactor_visitor",
            "description": "Reach the Reactor Core",
            "criteria_type": "reach_location",
            "target": 1,
            "zone_filter": "reactor_core",
            "reward_xp": 75,
            "reward_money": 125,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)

        # visit Cargo Bay but not Reactor Core
        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))

        summary = _summary(cs)
        pr, xs, _ = _post_round(cs, summary)

        assert summary.challenge_bonus_xp == 0


# ---------------------------------------------------------------------------
# Item reward full flow
# ---------------------------------------------------------------------------

class TestItemRewardFullFlow:

    def test_item_reward_appended_when_challenge_completed(self):
        pool = [{
            "id": "cargo_looter_3",
            "description": "Collect 3 items in Cargo Bay",
            "criteria_type": "item_picked_up",
            "target": 3,
            "zone_filter": "cargo_bay",
            "reward_xp": 100,
            "reward_money": 150,
            "reward_item_id": "medkit_basic",
        }]
        cs, bus = _make_cs(pool)

        bus.emit("zone_entered", zone=_FakeZone("Cargo Bay"))
        for _ in range(3):
            bus.emit("item_picked_up")

        fake_item = MagicMock()
        fake_item.item_id = "medkit_basic"
        fake_item.monetary_value = 0

        mock_db = MagicMock()
        mock_db.create.return_value = fake_item

        summary = _summary(cs)
        with patch("src.inventory.item_database.ItemDatabase") as MockDB:
            MockDB.instance.return_value = mock_db
            pr, _, _ = _post_round(cs, summary)

        assert "medkit_basic" in summary.challenge_bonus_items
        assert fake_item in summary.extracted_items


# ---------------------------------------------------------------------------
# Multiple challenges, simultaneous completion
# ---------------------------------------------------------------------------

class TestMultipleChallengesSimultaneous:

    def test_two_challenges_both_apply_rewards(self):
        pool = [
            {
                "id": "kill_3",
                "description": "Kill 3",
                "criteria_type": "enemy_killed",
                "target": 3,
                "zone_filter": None,
                "reward_xp": 100,
                "reward_money": 150,
                "reward_item_id": None,
            },
            {
                "id": "loot_2",
                "description": "Loot 2",
                "criteria_type": "item_picked_up",
                "target": 2,
                "zone_filter": None,
                "reward_xp": 80,
                "reward_money": 120,
                "reward_item_id": None,
            },
        ]
        cs, bus = _make_cs(pool)

        for _ in range(3):
            bus.emit("enemy_killed")
        for _ in range(2):
            bus.emit("item_picked_up")

        summary = _summary(cs)
        pr, xs, cur = _post_round(cs, summary)

        assert summary.challenge_bonus_xp == 180  # 100 + 80
        assert summary.challenge_bonus_money == 270  # 150 + 120

    def test_only_completed_challenges_reward_applied(self):
        pool = [
            {
                "id": "kill_2",
                "description": "Kill 2",
                "criteria_type": "enemy_killed",
                "target": 2,
                "zone_filter": None,
                "reward_xp": 100,
                "reward_money": 0,
                "reward_item_id": None,
            },
            {
                "id": "loot_10",
                "description": "Loot 10",
                "criteria_type": "item_picked_up",
                "target": 10,
                "zone_filter": None,
                "reward_xp": 500,
                "reward_money": 0,
                "reward_item_id": None,
            },
        ]
        cs, bus = _make_cs(pool)

        for _ in range(2):
            bus.emit("enemy_killed")  # completes kill_2
        for _ in range(3):
            bus.emit("item_picked_up")  # only 3 of 10 for loot_10

        summary = _summary(cs)
        pr, xs, _ = _post_round(cs, summary)

        # Only kill_2 rewards should apply
        assert summary.challenge_bonus_xp == 100


# ---------------------------------------------------------------------------
# Reset + new round
# ---------------------------------------------------------------------------

class TestResetNewRound:

    def test_after_reset_previous_completion_not_rewarded_again(self):
        pool = [{
            "id": "kill_1",
            "description": "Kill 1",
            "criteria_type": "enemy_killed",
            "target": 1,
            "zone_filter": None,
            "reward_xp": 200,
            "reward_money": 300,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)

        # Round 1: complete the challenge
        bus.emit("enemy_killed")
        summary1 = _summary(cs)
        pr1, xs1, cur1 = _post_round(cs, summary1)
        assert summary1.challenge_bonus_xp == 200

        # Reset for round 2
        cs.reset()
        assert cs.get_completed_challenges() == []

        # Round 2: challenge not yet completed
        summary2 = _summary(cs)
        pr2, xs2, cur2 = _post_round(cs, summary2)
        assert summary2.challenge_bonus_xp == 0

    def test_completing_challenge_in_new_round_grants_reward_again(self):
        pool = [{
            "id": "kill_1",
            "description": "Kill 1",
            "criteria_type": "enemy_killed",
            "target": 1,
            "zone_filter": None,
            "reward_xp": 150,
            "reward_money": 0,
            "reward_item_id": None,
        }]
        cs, bus = _make_cs(pool)

        # Round 1
        bus.emit("enemy_killed")
        summary1 = _summary(cs)
        pr1, xs1, _ = _post_round(cs, summary1)
        assert summary1.challenge_bonus_xp == 150

        # Reset and complete again in round 2
        cs.reset()
        bus.emit("enemy_killed")
        summary2 = _summary(cs)
        pr2, xs2, _ = _post_round(cs, summary2)
        assert summary2.challenge_bonus_xp == 150
