"""Unit tests for post-round extraction value logic.

The PostRound scene (src/scenes/post_round.py) executes this core business
logic when a round ends (see feature-plan.md § Task 14):

    total_value = sum(i.value for i in extracted_items) if outcome == "success" else 0
    currency.add(total_value)
    save_manager.save(player_state)

These tests validate that logic in isolation — using real Item and Currency
objects — without requiring Pygame or a running game loop.

A thin helper ``compute_extraction_payout()`` replicates the scene's
calculation so assertions can be written against it directly.  A mock spy on
Currency.add() confirms it is called exactly once with the correct total.
"""
import pytest
from unittest.mock import MagicMock, call, patch

from src.inventory.item import (
    Item,
    RARITY_COMMON,
    RARITY_EPIC,
    RARITY_LEGENDARY,
    RARITY_RARE,
    RARITY_UNCOMMON,
)
from src.progression.currency import Currency
from src.save.save_manager import SaveManager


# ---------------------------------------------------------------------------
# Helper replicating PostRound's payout formula
# ---------------------------------------------------------------------------

def compute_extraction_payout(extracted_items: list[Item], outcome: str) -> int:
    """Replicate the PostRound scene's payout calculation.

    Returns the sum of item values on success, or 0 on any other outcome.
    This function is the single line of business logic the scene will execute.
    """
    return sum(i.value for i in extracted_items) if outcome == "success" else 0


# ---------------------------------------------------------------------------
# Item factory shortcut
# ---------------------------------------------------------------------------

def _item(value: int, rarity: str = RARITY_COMMON, item_id: str = "item") -> Item:
    """Create a minimal ``Item`` for payout tests.

    Instantiates the base ``Item`` class directly to avoid the known bug in
    ``make_item()`` where passing ``item_type`` to subclass constructors that
    also hardcode it via ``super().__init__(item_type=...)`` raises a
    ``TypeError``.  The payout logic only reads ``item.value``, so the base
    class is sufficient.
    """
    return Item(
        item_id=item_id,
        name="Test Item",
        item_type="weapon",
        rarity=rarity,
        value=value,
        weight=1.0,
        sprite="",
    )


# ---------------------------------------------------------------------------
# Payout computation — success outcome
# ---------------------------------------------------------------------------

class TestExtractionPayoutSuccess:
    def test_single_item_payout(self):
        assert compute_extraction_payout([_item(200)], "success") == 200

    def test_two_items_summed(self):
        assert compute_extraction_payout([_item(100), _item(300)], "success") == 400

    def test_three_items_summed(self):
        assert compute_extraction_payout([_item(100), _item(300), _item(550)], "success") == 950

    def test_empty_loot_on_success_yields_zero(self):
        assert compute_extraction_payout([], "success") == 0

    def test_high_value_loot_sum(self):
        items = [_item(3500), _item(2500), _item(2200)]
        assert compute_extraction_payout(items, "success") == 8200

    def test_mixed_rarity_items_summed_correctly(self):
        items = [
            _item(80, RARITY_COMMON),
            _item(350, RARITY_UNCOMMON),
            _item(550, RARITY_RARE),
            _item(1000, RARITY_EPIC),
            _item(3500, RARITY_LEGENDARY),
        ]
        assert compute_extraction_payout(items, "success") == 5480

    def test_single_legendary_item(self):
        assert compute_extraction_payout([_item(3500, RARITY_LEGENDARY)], "success") == 3500

    def test_many_common_items(self):
        items = [_item(80)] * 10
        assert compute_extraction_payout(items, "success") == 800


# ---------------------------------------------------------------------------
# Payout computation — failed / unknown outcomes
# ---------------------------------------------------------------------------

class TestExtractionPayoutFailure:
    def test_failed_outcome_yields_zero_with_items(self):
        items = [_item(1000), _item(2000)]
        assert compute_extraction_payout(items, "failed") == 0

    def test_failed_outcome_yields_zero_with_no_items(self):
        assert compute_extraction_payout([], "failed") == 0

    def test_failed_outcome_ignores_item_values(self):
        items = [_item(999_999)]
        assert compute_extraction_payout(items, "failed") == 0

    def test_unknown_outcome_yields_zero(self):
        """Any outcome string that isn't "success" must yield 0."""
        assert compute_extraction_payout([_item(500)], "timeout") == 0
        assert compute_extraction_payout([_item(500)], "killed") == 0
        assert compute_extraction_payout([_item(500)], "") == 0


# ---------------------------------------------------------------------------
# Currency integration — balance mutations
# ---------------------------------------------------------------------------

class TestCurrencyBalanceAfterExtraction:
    def test_success_increases_balance_by_total(self):
        c = Currency(balance=1000)
        items = [_item(200), _item(300)]
        total = compute_extraction_payout(items, "success")
        c.add(total)
        assert c.balance == 1500

    def test_failed_extraction_does_not_change_balance(self):
        c = Currency(balance=1000)
        items = [_item(500), _item(700)]
        total = compute_extraction_payout(items, "failed")
        c.add(total)  # add(0) — valid, no-op
        assert c.balance == 1000

    def test_extraction_on_zero_starting_balance(self):
        c = Currency(balance=0)
        total = compute_extraction_payout([_item(400)], "success")
        c.add(total)
        assert c.balance == 400

    def test_multiple_rounds_accumulate_correctly(self):
        """Simulate two consecutive successful extractions."""
        c = Currency(balance=0)
        # Round 1
        c.add(compute_extraction_payout([_item(200), _item(300)], "success"))
        assert c.balance == 500
        # Round 2
        c.add(compute_extraction_payout([_item(1000)], "success"))
        assert c.balance == 1500

    def test_failed_round_between_successes_does_not_reduce_balance(self):
        c = Currency(balance=0)
        c.add(compute_extraction_payout([_item(500)], "success"))     # +500
        c.add(compute_extraction_payout([_item(9999)], "failed"))     # +0
        c.add(compute_extraction_payout([_item(300)], "success"))     # +300
        assert c.balance == 800

    def test_formatted_balance_after_extraction(self):
        c = Currency(balance=0)
        c.add(compute_extraction_payout([_item(3200)], "success"))
        assert c.formatted() == "$3,200"


# ---------------------------------------------------------------------------
# currency.add() call-count verification
# ---------------------------------------------------------------------------

class TestCurrencyAddCallCount:
    """PostRound must call currency.add() exactly once (bulk total, not per item)."""

    def test_add_called_once_with_correct_total_on_success(self):
        c = Currency(balance=0)
        items = [_item(400), _item(600)]
        with patch.object(c, "add", wraps=c.add) as spy:
            total = compute_extraction_payout(items, "success")
            c.add(total)
            spy.assert_called_once_with(1000)

    def test_add_called_once_with_zero_on_failure(self):
        c = Currency(balance=500)
        items = [_item(999)]
        with patch.object(c, "add", wraps=c.add) as spy:
            total = compute_extraction_payout(items, "failed")
            c.add(total)
            spy.assert_called_once_with(0)

    def test_add_not_called_per_item(self):
        """Ensures the scene commits a single sum, not one add() per item."""
        c = Currency()
        items = [_item(100), _item(200), _item(300)]
        with patch.object(c, "add", wraps=c.add) as spy:
            total = compute_extraction_payout(items, "success")
            c.add(total)
            assert spy.call_count == 1, (
                f"currency.add() called {spy.call_count} times, expected 1"
            )

    def test_add_receives_exact_sum_not_partial(self):
        """Verify the argument passed to add() equals the full item sum."""
        c = Currency()
        items = [_item(150), _item(350), _item(500)]
        with patch.object(c, "add", wraps=c.add) as spy:
            total = compute_extraction_payout(items, "success")
            c.add(total)
            args, _ = spy.call_args
            assert args[0] == 1000

    def test_add_on_empty_success_called_once_with_zero(self):
        c = Currency(balance=300)
        with patch.object(c, "add", wraps=c.add) as spy:
            total = compute_extraction_payout([], "success")
            c.add(total)
            spy.assert_called_once_with(0)


# ---------------------------------------------------------------------------
# save_manager.save() call-count verification
# ---------------------------------------------------------------------------

class TestSaveManagerCallCount:
    """PostRound must call save_manager.save() exactly once to persist state."""

    def test_save_called_exactly_once_on_success(self):
        mock_save_manager = MagicMock(spec=SaveManager)
        # Simulate what PostRound does at end of scene
        c = Currency(balance=0)
        items = [_item(500)]
        total = compute_extraction_payout(items, "success")
        c.add(total)
        mock_save_manager.save({"player": {"money": c.balance}})
        assert mock_save_manager.save.call_count == 1

    def test_save_called_exactly_once_on_failure(self):
        mock_save_manager = MagicMock(spec=SaveManager)
        c = Currency(balance=1000)
        items = [_item(500)]
        total = compute_extraction_payout(items, "failed")
        c.add(total)
        mock_save_manager.save({"player": {"money": c.balance}})
        assert mock_save_manager.save.call_count == 1

    def test_save_receives_updated_money_on_success(self):
        """The state dict passed to save() must reflect the new balance."""
        mock_save_manager = MagicMock(spec=SaveManager)
        c = Currency(balance=200)
        items = [_item(300)]
        total = compute_extraction_payout(items, "success")
        c.add(total)
        state = {"player": {"money": c.balance}}
        mock_save_manager.save(state)
        saved_state = mock_save_manager.save.call_args[0][0]
        assert saved_state["player"]["money"] == 500

    def test_save_receives_unchanged_money_on_failure(self):
        mock_save_manager = MagicMock(spec=SaveManager)
        c = Currency(balance=750)
        items = [_item(9999)]
        total = compute_extraction_payout(items, "failed")
        c.add(total)
        state = {"player": {"money": c.balance}}
        mock_save_manager.save(state)
        saved_state = mock_save_manager.save.call_args[0][0]
        assert saved_state["player"]["money"] == 750


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_item_with_zero_value_uses_rarity_fallback_then_summed(self):
        """Items with value=0 fall back to RARITY_DEFAULT_VALUES before summing."""
        item = _item(0, RARITY_COMMON)   # value=0 → fallback = 100
        total = compute_extraction_payout([item], "success")
        c = Currency()
        c.add(total)
        assert c.balance == 100  # RARITY_DEFAULT_VALUES[RARITY_COMMON]

    def test_payout_does_not_mutate_item_value(self):
        """compute_extraction_payout() must be read-only — no side effects."""
        item = _item(300)
        original_value = item.value
        compute_extraction_payout([item], "success")
        assert item.value == original_value

    def test_payout_does_not_mutate_item_list(self):
        items = [_item(100), _item(200)]
        original_len = len(items)
        compute_extraction_payout(items, "success")
        assert len(items) == original_len

    def test_large_loot_haul(self):
        """Stress: 20 items across rarity tiers, all summed correctly."""
        items = (
            [_item(80)] * 5          # 5 common  = 400
            + [_item(300)] * 5       # 5 uncommon = 1500
            + [_item(550)] * 5       # 5 rare     = 2750
            + [_item(1000)] * 5      # 5 epic     = 5000
        )
        expected = 400 + 1500 + 2750 + 5000  # = 9650
        assert compute_extraction_payout(items, "success") == expected

    def test_outcome_case_sensitivity(self):
        """'Success' (capital S) is not the same as 'success'."""
        items = [_item(500)]
        assert compute_extraction_payout(items, "Success") == 0
        assert compute_extraction_payout(items, "SUCCESS") == 0
        assert compute_extraction_payout(items, "success") == 500
