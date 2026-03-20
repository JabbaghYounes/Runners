# Run: pytest tests/test_currency_system.py
"""Unit, integration, and E2E tests for the currency tracking feature.

Feature spec:
  - CurrencySystem subscribes to "player_extracted" and sums monetary value of
    all extracted items, crediting the persistent balance.
  - Challenge rewards (reward_money) are added via "challenge_completed".
  - Currency balance persists across rounds in save data.
  - Currency cannot go below zero.
  - Spending currency (home base upgrades) emits "currency_spent" and deducts
    the amount.

Source files under test:
  src/systems/currency_system.py
  src/progression/currency.py         (floor / load() contract)
  src/save/save_manager.py            (persistence round-trip)
  src/progression/home_base.py        (currency_spent event on upgrade)
  src/progression/skill_tree.py       (currency_spent event on unlock)
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from src.systems.currency_system import CurrencySystem
from src.progression.currency import Currency
from src.save.save_manager import SaveManager


# ---------------------------------------------------------------------------
# Loot item stubs
# ---------------------------------------------------------------------------

class _Item:
    """Minimal loot-item stub with a numeric monetary_value."""
    def __init__(self, monetary_value: int | float) -> None:
        self.monetary_value = monetary_value


class _BadItem:
    """Stub whose monetary_value cannot be cast to int."""
    monetary_value: str = "not-a-number"


class _NoValueItem:
    """Stub that has no monetary_value attribute at all."""
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def currency() -> Currency:
    """A fresh zero-balance Currency object."""
    return Currency(balance=0)


@pytest.fixture
def cs(currency, event_bus) -> CurrencySystem:
    """CurrencySystem wired to a zero-balance Currency and the tracking bus."""
    return CurrencySystem(currency=currency, event_bus=event_bus)


# ===========================================================================
# Initialization and event subscriptions
# ===========================================================================

class TestCurrencySystemInit:

    def test_round_earnings_starts_at_zero(self, currency, event_bus):
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        assert cs.round_earnings == 0

    def test_subscribes_to_player_extracted(self, currency, event_bus):
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        assert event_bus.listener_count("player_extracted") == 1

    def test_subscribes_to_challenge_completed(self, currency, event_bus):
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        assert event_bus.listener_count("challenge_completed") == 1

    def test_no_subscriptions_when_event_bus_is_none(self, currency):
        cs = CurrencySystem(currency=currency, event_bus=None)
        assert cs._event_bus is None

    def test_construction_without_event_bus_does_not_raise(self, currency):
        cs = CurrencySystem(currency=currency)
        assert cs.round_earnings == 0

    def test_construction_does_not_mutate_currency_balance(self, event_bus):
        c = Currency(balance=500)
        CurrencySystem(currency=c, event_bus=event_bus)
        assert c.balance == 500


# ===========================================================================
# _on_player_extracted — loot summation
# ===========================================================================

class TestPlayerExtracted:

    def test_single_item_credits_balance(self, cs, currency, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(300)])
        assert currency.balance == 300

    def test_single_item_increments_round_earnings(self, cs, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(300)])
        assert cs.round_earnings == 300

    def test_multiple_items_summed_into_balance(self, cs, currency, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(200), _Item(300), _Item(500)])
        assert currency.balance == 1_000

    def test_multiple_items_summed_into_round_earnings(self, cs, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(200), _Item(300), _Item(500)])
        assert cs.round_earnings == 1_000

    def test_empty_loot_list_does_not_credit_balance(self, cs, currency, event_bus):
        event_bus.emit("player_extracted", loot=[])
        assert currency.balance == 0

    def test_empty_loot_list_does_not_increment_round_earnings(self, cs, event_bus):
        event_bus.emit("player_extracted", loot=[])
        assert cs.round_earnings == 0

    def test_none_loot_treated_as_empty_list(self, cs, currency, event_bus):
        event_bus.emit("player_extracted", loot=None)
        assert currency.balance == 0
        assert cs.round_earnings == 0

    def test_missing_loot_kwarg_treated_as_empty_list(self, cs, currency, event_bus):
        event_bus.emit("player_extracted")    # no 'loot' key in payload
        assert currency.balance == 0
        assert cs.round_earnings == 0

    def test_item_with_zero_monetary_value_not_credited(self, cs, currency, event_bus):
        """$0-value items must not change the balance or round_earnings."""
        event_bus.emit("player_extracted", loot=[_Item(0)])
        assert currency.balance == 0
        assert cs.round_earnings == 0

    def test_item_with_uncastable_monetary_value_skipped_gracefully(
        self, cs, currency, event_bus
    ):
        """Items whose monetary_value cannot be cast to int are silently skipped."""
        event_bus.emit("player_extracted", loot=[_BadItem(), _Item(100)])
        assert currency.balance == 100

    def test_item_with_no_monetary_value_attribute_skipped(self, cs, currency, event_bus):
        """Items lacking the monetary_value attribute are silently skipped."""
        event_bus.emit("player_extracted", loot=[_NoValueItem(), _Item(50)])
        assert currency.balance == 50

    def test_mixed_valid_and_invalid_items_sums_valid_only(self, cs, currency, event_bus):
        loot = [_Item(100), _BadItem(), _NoValueItem(), _Item(200)]
        event_bus.emit("player_extracted", loot=loot)
        assert currency.balance == 300

    def test_float_monetary_value_truncated_to_int_before_credit(
        self, cs, currency, event_bus
    ):
        event_bus.emit("player_extracted", loot=[_Item(99.9)])
        assert currency.balance == 99

    def test_repeated_extractions_accumulate_balance(self, cs, currency, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(200)])
        event_bus.emit("player_extracted", loot=[_Item(300)])
        assert currency.balance == 500

    def test_repeated_extractions_accumulate_round_earnings(self, cs, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(200)])
        event_bus.emit("player_extracted", loot=[_Item(300)])
        assert cs.round_earnings == 500

    def test_large_loot_haul_summed_correctly(self, cs, currency, event_bus):
        loot = [_Item(80), _Item(350), _Item(550), _Item(1_000), _Item(3_500)]
        event_bus.emit("player_extracted", loot=loot)
        assert currency.balance == 5_480

    def test_extraction_keeps_balance_non_negative(self, event_bus):
        c = Currency(balance=0)
        cs = CurrencySystem(currency=c, event_bus=event_bus)
        event_bus.emit("player_extracted", loot=[_Item(100)])
        assert c.balance >= 0


# ===========================================================================
# _on_challenge_completed — reward_money crediting
# ===========================================================================

class TestChallengeCompleted:

    def test_reward_money_credits_balance(self, cs, currency, event_bus):
        event_bus.emit("challenge_completed", reward_money=500)
        assert currency.balance == 500

    def test_reward_money_increments_round_earnings(self, cs, event_bus):
        event_bus.emit("challenge_completed", reward_money=500)
        assert cs.round_earnings == 500

    def test_zero_reward_money_is_noop_for_balance(self, cs, currency, event_bus):
        event_bus.emit("challenge_completed", reward_money=0)
        assert currency.balance == 0

    def test_zero_reward_money_is_noop_for_round_earnings(self, cs, event_bus):
        event_bus.emit("challenge_completed", reward_money=0)
        assert cs.round_earnings == 0

    def test_negative_reward_money_clamped_to_zero(self, cs, currency, event_bus):
        """A misconfigured negative reward must never deduct from the balance."""
        event_bus.emit("challenge_completed", reward_money=-200)
        assert currency.balance == 0
        assert cs.round_earnings == 0

    def test_missing_reward_money_key_defaults_to_zero(self, cs, currency, event_bus):
        event_bus.emit("challenge_completed")    # no 'reward_money' in payload
        assert currency.balance == 0
        assert cs.round_earnings == 0

    def test_none_reward_money_treated_as_zero(self, cs, currency, event_bus):
        event_bus.emit("challenge_completed", reward_money=None)
        assert currency.balance == 0
        assert cs.round_earnings == 0

    def test_non_numeric_reward_money_silently_ignored(self, cs, currency, event_bus):
        event_bus.emit("challenge_completed", reward_money="big-money")
        assert currency.balance == 0
        assert cs.round_earnings == 0

    def test_float_reward_money_truncated_to_int(self, cs, currency, event_bus):
        event_bus.emit("challenge_completed", reward_money=99.9)
        assert currency.balance == 99

    def test_multiple_challenges_accumulate_balance(self, cs, currency, event_bus):
        event_bus.emit("challenge_completed", reward_money=200)
        event_bus.emit("challenge_completed", reward_money=300)
        assert currency.balance == 500

    def test_multiple_challenges_accumulate_round_earnings(self, cs, event_bus):
        event_bus.emit("challenge_completed", reward_money=200)
        event_bus.emit("challenge_completed", reward_money=300)
        assert cs.round_earnings == 500

    def test_large_reward_credited_correctly(self, cs, currency, event_bus):
        event_bus.emit("challenge_completed", reward_money=10_000)
        assert currency.balance == 10_000

    def test_negative_reward_keeps_balance_non_negative(self, event_bus):
        c = Currency(balance=0)
        cs = CurrencySystem(currency=c, event_bus=event_bus)
        event_bus.emit("challenge_completed", reward_money=-9_999)
        assert c.balance >= 0


# ===========================================================================
# round_earnings property and reset_round()
# ===========================================================================

class TestRoundEarningsAndReset:

    def test_round_earnings_zero_before_any_events(self, cs):
        assert cs.round_earnings == 0

    def test_round_earnings_sums_loot_and_challenge_rewards(self, cs, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(400)])
        event_bus.emit("challenge_completed", reward_money=100)
        assert cs.round_earnings == 500

    def test_reset_round_clears_round_earnings(self, cs, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(300)])
        event_bus.emit("challenge_completed", reward_money=200)
        cs.reset_round()
        assert cs.round_earnings == 0

    def test_reset_round_does_not_affect_currency_balance(self, cs, currency, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(500)])
        cs.reset_round()
        assert currency.balance == 500

    def test_reset_round_is_idempotent(self, cs):
        cs.reset_round()
        cs.reset_round()
        assert cs.round_earnings == 0

    def test_reset_round_safe_before_any_events(self, cs):
        cs.reset_round()
        assert cs.round_earnings == 0

    def test_events_after_reset_accumulate_fresh(self, cs, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(300)])
        cs.reset_round()
        event_bus.emit("challenge_completed", reward_money=150)
        assert cs.round_earnings == 150

    def test_currency_balance_accumulates_across_resets(self, cs, currency, event_bus):
        """Balance is persistent; round_earnings is per-round display only."""
        event_bus.emit("player_extracted", loot=[_Item(400)])
        cs.reset_round()
        event_bus.emit("player_extracted", loot=[_Item(600)])
        assert currency.balance == 1_000

    def test_round_earnings_reflects_only_current_round_after_reset(
        self, cs, event_bus
    ):
        event_bus.emit("player_extracted", loot=[_Item(400)])
        cs.reset_round()
        event_bus.emit("player_extracted", loot=[_Item(600)])
        assert cs.round_earnings == 600


# ===========================================================================
# teardown() — unsubscribes both event handlers
# ===========================================================================

class TestTeardown:

    def test_teardown_removes_player_extracted_listener(self, currency, event_bus):
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        cs.teardown()
        assert event_bus.listener_count("player_extracted") == 0

    def test_teardown_removes_challenge_completed_listener(self, currency, event_bus):
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        cs.teardown()
        assert event_bus.listener_count("challenge_completed") == 0

    def test_teardown_stops_player_extracted_from_crediting_balance(
        self, currency, event_bus
    ):
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        cs.teardown()
        event_bus.emit("player_extracted", loot=[_Item(500)])
        assert currency.balance == 0

    def test_teardown_stops_challenge_completed_from_crediting_balance(
        self, currency, event_bus
    ):
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        cs.teardown()
        event_bus.emit("challenge_completed", reward_money=300)
        assert currency.balance == 0

    def test_teardown_stops_round_earnings_from_accumulating(
        self, currency, event_bus
    ):
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        cs.teardown()
        event_bus.emit("player_extracted", loot=[_Item(100)])
        assert cs.round_earnings == 0

    def test_teardown_safe_when_event_bus_is_none(self, currency):
        cs = CurrencySystem(currency=currency, event_bus=None)
        cs.teardown()   # must not raise

    def test_teardown_is_idempotent(self, currency, event_bus):
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        cs.teardown()
        cs.teardown()   # second call must not raise

    def test_events_before_teardown_are_credited_normally(
        self, currency, event_bus
    ):
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        event_bus.emit("player_extracted", loot=[_Item(200)])
        cs.teardown()
        assert currency.balance == 200

    def test_teardown_does_not_remove_other_subscribers(self, currency, event_bus):
        """Unsubscribing CurrencySystem must leave unrelated listeners intact."""
        received: list[dict] = []
        event_bus.subscribe(
            "player_extracted", lambda **kw: received.append(kw)
        )
        cs = CurrencySystem(currency=currency, event_bus=event_bus)
        cs.teardown()
        event_bus.emit("player_extracted", loot=[])
        assert len(received) == 1


# ===========================================================================
# Currency floor — balance cannot go below zero
# ===========================================================================

class TestCurrencyFloor:

    def test_zero_value_loot_leaves_balance_at_zero(self, cs, currency, event_bus):
        event_bus.emit("player_extracted", loot=[_Item(0)])
        assert currency.balance == 0

    def test_negative_challenge_reward_cannot_deduct_from_zero_balance(
        self, event_bus
    ):
        c = Currency(balance=0)
        cs = CurrencySystem(currency=c, event_bus=event_bus)
        event_bus.emit("challenge_completed", reward_money=-1_000)
        assert c.balance == 0

    def test_currency_load_clamps_negative_persisted_value_to_zero(self):
        c = Currency()
        c.load({"balance": -500})
        assert c.balance == 0

    def test_currency_load_handles_missing_balance_key(self):
        """load() with no 'balance' key must default to 0, not raise."""
        c = Currency(balance=200)
        c.load({})
        assert c.balance == 0

    def test_currency_load_accepts_zero_balance(self):
        c = Currency(balance=100)
        c.load({"balance": 0})
        assert c.balance == 0

    def test_currency_spend_on_insufficient_funds_does_not_go_negative(self):
        c = Currency(balance=50)
        c.spend(100)       # refused — balance stays 50, not -50
        assert c.balance == 50

    def test_combined_bad_events_never_produce_negative_balance(self, event_bus):
        c = Currency(balance=0)
        cs = CurrencySystem(currency=c, event_bus=event_bus)
        event_bus.emit("challenge_completed", reward_money=-999)
        event_bus.emit("player_extracted", loot=[_Item(0), _BadItem(), _NoValueItem()])
        event_bus.emit("challenge_completed", reward_money=None)
        assert c.balance >= 0


# ===========================================================================
# Integration: SaveManager round-trip preserves currency balance
# ===========================================================================

class TestSaveManagerIntegration:

    def test_balance_persisted_under_player_money_key(self, tmp_path):
        mgr = SaveManager(tmp_path / "saves" / "s.json")
        mgr.save(currency=Currency(balance=1_500))
        assert mgr.load()["player"]["money"] == 1_500

    def test_zero_balance_persisted_correctly(self, tmp_path):
        mgr = SaveManager(tmp_path / "saves" / "s.json")
        mgr.save(currency=Currency(balance=0))
        assert mgr.load()["player"]["money"] == 0

    def test_restore_reads_money_into_balance(self, tmp_path):
        save_path = tmp_path / "saves" / "s.json"
        mgr = SaveManager(save_path)
        mgr.save({
            "version": 1,
            "player": {"level": 1, "xp": 0, "money": 2_500},
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {},
        })
        c = Currency()
        mgr.restore(currency=c)
        assert c.balance == 2_500

    def test_restore_clamps_negative_money_to_zero(self, tmp_path):
        """A corrupted save with negative money must not produce a negative balance."""
        save_path = tmp_path / "saves" / "s.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(
            json.dumps({
                "version": 1,
                "player": {"level": 1, "xp": 0, "money": -9_999},
                "inventory": [],
                "skill_tree": {"unlocked_nodes": []},
                "home_base": {},
            }),
            encoding="utf-8",
        )
        c = Currency()
        SaveManager(save_path).restore(currency=c)
        assert c.balance == 0

    def test_restore_defaults_to_zero_when_money_key_absent(self, tmp_path):
        """An old save without the 'money' key must restore to 0, not raise."""
        save_path = tmp_path / "saves" / "s.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(
            json.dumps({
                "version": 1,
                "player": {"level": 1, "xp": 0},   # no "money"
                "inventory": [],
                "skill_tree": {"unlocked_nodes": []},
                "home_base": {},
            }),
            encoding="utf-8",
        )
        c = Currency()
        SaveManager(save_path).restore(currency=c)
        assert c.balance == 0

    def test_full_earn_save_restore_cycle(self, tmp_path, event_bus):
        """Earn via CurrencySystem → save → restore → verify new-session balance."""
        mgr = SaveManager(tmp_path / "saves" / "s.json")
        c = Currency(balance=0)
        cs = CurrencySystem(currency=c, event_bus=event_bus)

        event_bus.emit("player_extracted", loot=[_Item(400)])
        event_bus.emit("challenge_completed", reward_money=100)

        mgr.save(currency=c)

        c2 = Currency()
        mgr.restore(currency=c2)
        assert c2.balance == 500

    def test_balance_accumulates_across_two_saved_rounds(self, tmp_path, event_bus):
        """Round 1 balance + round 2 earnings both survive separate saves."""
        mgr = SaveManager(tmp_path / "saves" / "s.json")

        # Round 1
        c = Currency(balance=0)
        cs1 = CurrencySystem(currency=c, event_bus=event_bus)
        event_bus.emit("challenge_completed", reward_money=300)
        mgr.save(currency=c)
        cs1.teardown()

        # Round 2: restore into fresh object, then earn more
        c2 = Currency()
        mgr.restore(currency=c2)
        cs2 = CurrencySystem(currency=c2, event_bus=event_bus)
        event_bus.emit("challenge_completed", reward_money=200)
        mgr.save(currency=c2)
        cs2.teardown()

        assert mgr.load()["player"]["money"] == 500


# ===========================================================================
# Integration: HomeBase.upgrade() deducts currency and emits currency_spent
# ===========================================================================

@pytest.fixture
def hb_defs_path(tmp_path) -> str:
    """Minimal home_base.json with one three-level facility for spending tests."""
    data = {
        "facilities": [
            {
                "id": "armory",
                "name": "ARMORY",
                "description": "",
                "max_level": 3,
                "levels": [
                    {
                        "cost": 300,
                        "bonus_type": "loot_value_bonus",
                        "bonus_value": 0.1,
                        "description": "+10%",
                    },
                    {
                        "cost": 600,
                        "bonus_type": "loot_value_bonus",
                        "bonus_value": 0.2,
                        "description": "+20%",
                    },
                    {
                        "cost": 1_000,
                        "bonus_type": "loot_value_bonus",
                        "bonus_value": 0.3,
                        "description": "+30%",
                    },
                ],
            }
        ]
    }
    p = tmp_path / "home_base.json"
    p.write_text(json.dumps(data))
    return str(p)


class TestHomeBaseSpending:

    def test_successful_upgrade_deducts_cost_from_balance(self, hb_defs_path):
        from src.progression.home_base import HomeBase
        c = Currency(balance=1_000)
        hb = HomeBase(hb_defs_path)
        hb.upgrade("armory", c)
        assert c.balance == 700     # 1000 - 300

    def test_failed_upgrade_leaves_balance_unchanged(self, hb_defs_path):
        from src.progression.home_base import HomeBase
        c = Currency(balance=50)    # less than the 300-cost
        hb = HomeBase(hb_defs_path)
        hb.upgrade("armory", c)
        assert c.balance == 50

    def test_balance_never_negative_after_failed_upgrade(self, hb_defs_path):
        from src.progression.home_base import HomeBase
        c = Currency(balance=0)
        hb = HomeBase(hb_defs_path)
        hb.upgrade("armory", c)
        assert c.balance >= 0

    def test_upgrade_emits_currency_spent_event(self, hb_defs_path, event_bus):
        """Successful upgrade must emit exactly one 'currency_spent' event."""
        from src.progression.home_base import HomeBase
        c = Currency(balance=1_000)
        hb = HomeBase(hb_defs_path)
        hb.upgrade("armory", c, event_bus=event_bus)
        assert len(event_bus.all_events("currency_spent")) == 1

    def test_currency_spent_event_carries_amount(self, hb_defs_path, event_bus):
        from src.progression.home_base import HomeBase
        c = Currency(balance=1_000)
        hb = HomeBase(hb_defs_path)
        hb.upgrade("armory", c, event_bus=event_bus)
        assert event_bus.first_event("currency_spent")["amount"] == 300

    def test_currency_spent_event_carries_new_balance(self, hb_defs_path, event_bus):
        from src.progression.home_base import HomeBase
        c = Currency(balance=1_000)
        hb = HomeBase(hb_defs_path)
        hb.upgrade("armory", c, event_bus=event_bus)
        assert event_bus.first_event("currency_spent")["new_balance"] == 700

    def test_currency_spent_not_emitted_on_failed_upgrade(
        self, hb_defs_path, event_bus
    ):
        """No 'currency_spent' when upgrade fails due to insufficient funds."""
        from src.progression.home_base import HomeBase
        c = Currency(balance=50)    # cannot afford 300
        hb = HomeBase(hb_defs_path)
        hb.upgrade("armory", c, event_bus=event_bus)
        assert len(event_bus.all_events("currency_spent")) == 0

    def test_upgrade_without_event_bus_still_deducts_balance(self, hb_defs_path):
        """upgrade() called without event_bus must succeed and deduct normally."""
        from src.progression.home_base import HomeBase
        c = Currency(balance=1_000)
        hb = HomeBase(hb_defs_path)
        result = hb.upgrade("armory", c)    # no event_bus argument
        assert result is True
        assert c.balance == 700


# ===========================================================================
# Integration: SkillTree.unlock() deducts currency and emits currency_spent
# ===========================================================================

@pytest.fixture
def skill_tree_path(tmp_path) -> str:
    """Minimal skill-tree JSON for currency-spending tests."""
    data = {
        "nodes": [
            {
                "id": "sprint_boost",
                "branch": "movement",
                "requires": [],
                "required_level": 0,
                "cost_money": 200,
                "stat_bonus": {"sprint_speed": 0.1},
            }
        ]
    }
    p = tmp_path / "skill_tree.json"
    p.write_text(json.dumps(data))
    return str(p)


class TestSkillTreeSpending:

    def test_unlock_deducts_cost_from_currency(self, skill_tree_path):
        from src.progression.skill_tree import SkillTree
        c = Currency(balance=500)
        st = SkillTree()
        st.load(skill_tree_path)
        st.unlock("sprint_boost", currency=c)
        assert c.balance == 300     # 500 - 200

    def test_unlock_blocked_when_insufficient_funds(self, skill_tree_path):
        from src.progression.skill_tree import SkillTree
        c = Currency(balance=50)
        st = SkillTree()
        st.load(skill_tree_path)
        result = st.unlock("sprint_boost", currency=c)
        assert result is False
        assert c.balance == 50

    def test_balance_never_negative_after_failed_unlock(self, skill_tree_path):
        from src.progression.skill_tree import SkillTree
        c = Currency(balance=0)
        st = SkillTree()
        st.load(skill_tree_path)
        st.unlock("sprint_boost", currency=c)
        assert c.balance >= 0

    def test_unlock_emits_currency_spent_event(self, skill_tree_path, event_bus):
        """Successful unlock must emit exactly one 'currency_spent' event."""
        from src.progression.skill_tree import SkillTree
        c = Currency(balance=500)
        st = SkillTree()
        st.load(skill_tree_path)
        st.unlock("sprint_boost", currency=c, event_bus=event_bus)
        assert len(event_bus.all_events("currency_spent")) == 1

    def test_currency_spent_carries_correct_amount(self, skill_tree_path, event_bus):
        from src.progression.skill_tree import SkillTree
        c = Currency(balance=500)
        st = SkillTree()
        st.load(skill_tree_path)
        st.unlock("sprint_boost", currency=c, event_bus=event_bus)
        assert event_bus.first_event("currency_spent")["amount"] == 200

    def test_currency_spent_not_emitted_on_failed_unlock(
        self, skill_tree_path, event_bus
    ):
        from src.progression.skill_tree import SkillTree
        c = Currency(balance=10)    # cannot afford 200
        st = SkillTree()
        st.load(skill_tree_path)
        st.unlock("sprint_boost", currency=c, event_bus=event_bus)
        assert len(event_bus.all_events("currency_spent")) == 0

    def test_unlock_still_works_without_event_bus(self, skill_tree_path):
        """unlock() called without event_bus must succeed and deduct normally."""
        from src.progression.skill_tree import SkillTree
        c = Currency(balance=500)
        st = SkillTree()
        st.load(skill_tree_path)
        result = st.unlock("sprint_boost", currency=c)
        assert result is True
        assert c.balance == 300


# ===========================================================================
# E2E: Full round — challenge + extraction → correct balance and round_earnings
# ===========================================================================

class TestFullRoundFlow:

    def test_challenge_and_extraction_together_update_balance(self, event_bus):
        c = Currency(balance=0)
        cs = CurrencySystem(currency=c, event_bus=event_bus)

        event_bus.emit("challenge_completed", reward_money=250)
        event_bus.emit("player_extracted", loot=[_Item(300), _Item(200)])

        assert c.balance == 750

    def test_challenge_and_extraction_together_set_round_earnings(self, event_bus):
        c = Currency(balance=0)
        cs = CurrencySystem(currency=c, event_bus=event_bus)

        event_bus.emit("challenge_completed", reward_money=250)
        event_bus.emit("player_extracted", loot=[_Item(300), _Item(200)])

        assert cs.round_earnings == 750

    def test_balance_persists_across_rounds_round_earnings_resets(self, event_bus):
        c = Currency(balance=0)
        cs = CurrencySystem(currency=c, event_bus=event_bus)

        # Round 1
        event_bus.emit("challenge_completed", reward_money=200)
        event_bus.emit("player_extracted", loot=[_Item(300)])
        assert cs.round_earnings == 500
        assert c.balance == 500

        cs.reset_round()

        # Round 2
        event_bus.emit("challenge_completed", reward_money=100)
        event_bus.emit("player_extracted", loot=[_Item(400)])
        assert cs.round_earnings == 500   # round 2 only
        assert c.balance == 1_000         # cumulative across both rounds

    def test_old_system_silent_after_teardown_new_system_takes_over(self, event_bus):
        """After teardown the old system must not double-count new events."""
        c = Currency(balance=0)
        cs1 = CurrencySystem(currency=c, event_bus=event_bus)
        event_bus.emit("player_extracted", loot=[_Item(200)])
        cs1.teardown()

        cs2 = CurrencySystem(currency=c, event_bus=event_bus)
        cs2.reset_round()
        event_bus.emit("player_extracted", loot=[_Item(150)])

        assert cs2.round_earnings == 150   # cs1 is silent
        assert c.balance == 350            # 200 (round 1) + 150 (round 2)

    def test_failed_extraction_earns_no_loot_money(self, event_bus):
        """When player_extracted is never emitted balance has only challenge rewards."""
        c = Currency(balance=0)
        cs = CurrencySystem(currency=c, event_bus=event_bus)

        event_bus.emit("challenge_completed", reward_money=300)
        event_bus.emit("extraction_failed")   # player did not extract

        assert c.balance == 300
        assert cs.round_earnings == 300

    def test_round_with_no_activity_does_not_change_balance(self, event_bus):
        c = Currency(balance=500)
        cs = CurrencySystem(currency=c, event_bus=event_bus)

        event_bus.emit("extraction_failed")   # no challenges, no loot

        assert c.balance == 500
        assert cs.round_earnings == 0

    def test_complete_save_restore_cycle_after_round(self, tmp_path, event_bus):
        """Earn in-round → save → restore into new session → balance correct."""
        mgr = SaveManager(tmp_path / "saves" / "s.json")
        c = Currency(balance=0)
        cs = CurrencySystem(currency=c, event_bus=event_bus)

        event_bus.emit("challenge_completed", reward_money=500)
        event_bus.emit("player_extracted", loot=[_Item(300), _Item(700)])

        assert c.balance == 1_500
        assert cs.round_earnings == 1_500

        mgr.save(currency=c)

        c_restored = Currency()
        mgr.restore(currency=c_restored)
        assert c_restored.balance == 1_500

    def test_all_failure_paths_keep_balance_non_negative(self, event_bus):
        """No combination of bad events must produce a negative balance."""
        c = Currency(balance=50)
        cs = CurrencySystem(currency=c, event_bus=event_bus)

        event_bus.emit("challenge_completed", reward_money=-1_000)
        event_bus.emit("player_extracted", loot=[_Item(0), _BadItem(), _NoValueItem()])
        event_bus.emit("challenge_completed", reward_money=None)

        assert c.balance >= 0
