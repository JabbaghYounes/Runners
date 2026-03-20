"""Unit tests for RoundSummary challenge bonus fields — src/core/round_summary.py

Run: pytest tests/core/test_round_summary_challenge_bonus.py
"""
from __future__ import annotations

import pytest

from src.core.round_summary import RoundSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make(**overrides) -> RoundSummary:
    defaults = dict(
        extraction_status="success",
        extracted_items=[],
        xp_earned=100,
        money_earned=500,
        kills=3,
        challenges_completed=1,
        challenges_total=3,
        level_before=2,
    )
    defaults.update(overrides)
    return RoundSummary(**defaults)


# ---------------------------------------------------------------------------
# challenge_bonus_xp field
# ---------------------------------------------------------------------------

class TestChallengeBonusXp:

    def test_defaults_to_zero(self):
        s = _make()
        assert s.challenge_bonus_xp == 0

    def test_can_be_set_at_construction(self):
        s = _make(challenge_bonus_xp=150)
        assert s.challenge_bonus_xp == 150

    def test_can_be_mutated(self):
        s = _make()
        s.challenge_bonus_xp += 200
        assert s.challenge_bonus_xp == 200

    def test_accumulation_via_multiple_increments(self):
        s = _make()
        s.challenge_bonus_xp += 100
        s.challenge_bonus_xp += 75
        assert s.challenge_bonus_xp == 175

    def test_large_value_stored_correctly(self):
        s = _make(challenge_bonus_xp=99_999)
        assert s.challenge_bonus_xp == 99_999

    def test_zero_value_is_valid(self):
        s = _make(challenge_bonus_xp=0)
        assert s.challenge_bonus_xp == 0


# ---------------------------------------------------------------------------
# challenge_bonus_money field
# ---------------------------------------------------------------------------

class TestChallengeBonusMoney:

    def test_defaults_to_zero(self):
        s = _make()
        assert s.challenge_bonus_money == 0

    def test_can_be_set_at_construction(self):
        s = _make(challenge_bonus_money=350)
        assert s.challenge_bonus_money == 350

    def test_can_be_mutated(self):
        s = _make()
        s.challenge_bonus_money += 500
        assert s.challenge_bonus_money == 500

    def test_accumulation_via_multiple_increments(self):
        s = _make()
        s.challenge_bonus_money += 100
        s.challenge_bonus_money += 250
        assert s.challenge_bonus_money == 350

    def test_large_value_stored_correctly(self):
        s = _make(challenge_bonus_money=50_000)
        assert s.challenge_bonus_money == 50_000


# ---------------------------------------------------------------------------
# challenge_bonus_items field
# ---------------------------------------------------------------------------

class TestChallengeBonusItems:

    def test_defaults_to_empty_list(self):
        s = _make()
        assert s.challenge_bonus_items == []

    def test_each_instance_has_independent_list(self):
        """Mutable default must not be shared between instances."""
        s1 = _make()
        s2 = _make()
        s1.challenge_bonus_items.append("medkit_basic")
        assert s2.challenge_bonus_items == []

    def test_can_be_set_at_construction(self):
        s = _make(challenge_bonus_items=["medkit_basic"])
        assert s.challenge_bonus_items == ["medkit_basic"]

    def test_items_can_be_appended(self):
        s = _make()
        s.challenge_bonus_items.append("scope_red_dot")
        assert s.challenge_bonus_items == ["scope_red_dot"]

    def test_multiple_items_appended(self):
        s = _make()
        s.challenge_bonus_items.append("medkit_basic")
        s.challenge_bonus_items.append("ammo_rifle")
        assert len(s.challenge_bonus_items) == 2
        assert "medkit_basic" in s.challenge_bonus_items
        assert "ammo_rifle" in s.challenge_bonus_items

    def test_item_ids_are_strings(self):
        s = _make()
        s.challenge_bonus_items.append("scope_red_dot")
        assert all(isinstance(x, str) for x in s.challenge_bonus_items)


# ---------------------------------------------------------------------------
# All three bonus fields coexist correctly
# ---------------------------------------------------------------------------

class TestBonusFieldsCoexist:

    def test_all_bonus_fields_default_to_zero_or_empty(self):
        s = _make()
        assert s.challenge_bonus_xp == 0
        assert s.challenge_bonus_money == 0
        assert s.challenge_bonus_items == []

    def test_mutating_xp_does_not_affect_money(self):
        s = _make()
        s.challenge_bonus_xp = 500
        assert s.challenge_bonus_money == 0

    def test_mutating_money_does_not_affect_xp(self):
        s = _make()
        s.challenge_bonus_money = 300
        assert s.challenge_bonus_xp == 0

    def test_mutating_items_does_not_affect_xp_or_money(self):
        s = _make()
        s.challenge_bonus_items.append("ammo_rifle")
        assert s.challenge_bonus_xp == 0
        assert s.challenge_bonus_money == 0

    def test_all_fields_set_together(self):
        s = _make(challenge_bonus_xp=100, challenge_bonus_money=250,
                  challenge_bonus_items=["medkit_basic"])
        assert s.challenge_bonus_xp == 100
        assert s.challenge_bonus_money == 250
        assert s.challenge_bonus_items == ["medkit_basic"]

    def test_bonus_fields_independent_of_base_fields(self):
        """Bonus fields must not interfere with core summary fields."""
        s = _make(xp_earned=200, money_earned=800,
                  challenge_bonus_xp=50, challenge_bonus_money=100)
        assert s.xp_earned == 200
        assert s.money_earned == 800
        assert s.challenge_bonus_xp == 50
        assert s.challenge_bonus_money == 100
