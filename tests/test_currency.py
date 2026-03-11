"""Unit tests for src/progression/currency.py.

Tests cover:
- Initial balance construction (positive, zero, negative clamping)
- add(): increases balance, zero noop, negative raises ValueError
- spend(): sufficient funds deduct and return True, insufficient returns False
  without mutating balance, zero always succeeds, negative raises ValueError
- formatted(): dollar-string representation
- __repr__: sanity check
- Compound operation sequences
"""
import pytest

from src.progression.currency import Currency


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestCurrencyInit:
    def test_default_balance_is_zero(self):
        c = Currency()
        assert c.balance == 0

    def test_positive_starting_balance(self):
        c = Currency(balance=500)
        assert c.balance == 500

    def test_negative_starting_balance_clamped_to_zero(self):
        """Negative starting balance must be silently clamped, not raise."""
        c = Currency(balance=-100)
        assert c.balance == 0

    def test_float_balance_is_truncated_to_int(self):
        c = Currency(balance=99.9)  # type: ignore[arg-type]
        assert c.balance == 99

    def test_zero_starting_balance(self):
        c = Currency(balance=0)
        assert c.balance == 0


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------

class TestCurrencyAdd:
    def test_add_increases_balance(self):
        c = Currency(balance=100)
        c.add(50)
        assert c.balance == 150

    def test_add_zero_is_noop(self):
        c = Currency(balance=200)
        c.add(0)
        assert c.balance == 200

    def test_add_negative_raises_value_error(self):
        c = Currency()
        with pytest.raises(ValueError):
            c.add(-1)

    def test_add_large_amount(self):
        c = Currency()
        c.add(1_000_000)
        assert c.balance == 1_000_000

    def test_multiple_adds_accumulate(self):
        c = Currency()
        c.add(100)
        c.add(200)
        c.add(300)
        assert c.balance == 600

    def test_add_returns_none(self):
        c = Currency()
        result = c.add(10)
        assert result is None


# ---------------------------------------------------------------------------
# spend()
# ---------------------------------------------------------------------------

class TestCurrencySpend:
    def test_spend_sufficient_funds_returns_true(self):
        c = Currency(balance=500)
        assert c.spend(200) is True

    def test_spend_deducts_from_balance(self):
        c = Currency(balance=500)
        c.spend(200)
        assert c.balance == 300

    def test_spend_exact_balance_succeeds(self):
        """Spending exactly the remaining balance is valid (edge case)."""
        c = Currency(balance=100)
        assert c.spend(100) is True
        assert c.balance == 0

    def test_spend_insufficient_funds_returns_false(self):
        c = Currency(balance=50)
        assert c.spend(100) is False

    def test_spend_insufficient_funds_does_not_mutate_balance(self):
        """A failed spend must leave balance unchanged."""
        c = Currency(balance=50)
        c.spend(100)
        assert c.balance == 50

    def test_spend_zero_always_succeeds(self):
        c = Currency(balance=0)
        assert c.spend(0) is True
        assert c.balance == 0

    def test_spend_negative_raises_value_error(self):
        c = Currency(balance=1000)
        with pytest.raises(ValueError):
            c.spend(-10)

    def test_spend_all_then_cannot_spend_more(self):
        c = Currency(balance=100)
        c.spend(100)
        assert c.spend(1) is False

    def test_spend_on_empty_balance_returns_false(self):
        c = Currency(balance=0)
        assert c.spend(1) is False

    def test_spend_one_above_balance_returns_false(self):
        c = Currency(balance=99)
        assert c.spend(100) is False
        assert c.balance == 99


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestCurrencyHelpers:
    def test_formatted_zero(self):
        c = Currency()
        assert c.formatted() == "$0"

    def test_formatted_small_value(self):
        c = Currency(balance=500)
        assert c.formatted() == "$500"

    def test_formatted_large_value_with_comma(self):
        c = Currency(balance=3200)
        assert c.formatted() == "$3,200"

    def test_formatted_million(self):
        c = Currency(balance=1_000_000)
        assert c.formatted() == "$1,000,000"

    def test_repr_includes_class_name(self):
        c = Currency(balance=42)
        assert "Currency" in repr(c)

    def test_repr_includes_balance_value(self):
        c = Currency(balance=42)
        assert "42" in repr(c)


# ---------------------------------------------------------------------------
# Compound sequences
# ---------------------------------------------------------------------------

class TestCurrencyCompound:
    def test_add_then_spend_then_add(self):
        c = Currency()
        c.add(1000)
        c.spend(300)
        c.add(500)
        assert c.balance == 1200

    def test_spend_fails_then_add_then_spend_succeeds(self):
        c = Currency(balance=50)
        assert c.spend(200) is False  # not enough
        c.add(200)                    # top up
        assert c.spend(200) is True   # now succeeds
        assert c.balance == 50

    def test_sequential_small_spends(self):
        c = Currency(balance=300)
        for _ in range(10):
            c.spend(25)
        assert c.balance == 50

    def test_balance_never_goes_negative(self):
        c = Currency(balance=10)
        c.spend(20)  # returns False, balance stays 10
        c.spend(10)  # returns True, balance → 0
        c.spend(1)   # returns False, balance stays 0
        assert c.balance == 0
