"""Tests for RoundSummary dataclass — src/core/round_summary.py"""
import pytest
from src.core.round_summary import RoundSummary


class _FakeItem:
    """Minimal Item stand-in for constructing test summaries."""

    def __init__(self, name: str, monetary_value: int, rarity: str = "common"):
        self.name = name
        self.monetary_value = monetary_value
        self.rarity = rarity


# ── Helper ─────────────────────────────────────────────────────────────────────

def _make(**overrides):
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


# ── Valid statuses ─────────────────────────────────────────────────────────────

def test_success_status_accepted():
    s = _make(extraction_status="success")
    assert s.extraction_status == "success"


def test_timeout_status_accepted():
    s = _make(extraction_status="timeout")
    assert s.extraction_status == "timeout"


def test_eliminated_status_accepted():
    s = _make(extraction_status="eliminated")
    assert s.extraction_status == "eliminated"


# ── Status validation ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_status", [
    "win", "fail", "dead", "SUCCESS", "TIMEOUT", "ELIMINATED",
    "victory", "", "extracted", "killed",
])
def test_invalid_status_raises_value_error(bad_status):
    with pytest.raises(ValueError):
        _make(extraction_status=bad_status)


def test_none_status_raises():
    with pytest.raises((ValueError, TypeError)):
        _make(extraction_status=None)


# ── Default field values ───────────────────────────────────────────────────────

def test_level_after_defaults_to_zero():
    s = _make()
    assert s.level_after == 0


def test_level_after_can_be_provided_explicitly():
    s = _make(level_after=5)
    assert s.level_after == 5


# ── Field storage ──────────────────────────────────────────────────────────────

def test_xp_earned_stored():
    s = _make(xp_earned=750)
    assert s.xp_earned == 750


def test_money_earned_stored():
    s = _make(money_earned=1200)
    assert s.money_earned == 1200


def test_kills_stored():
    s = _make(kills=7)
    assert s.kills == 7


def test_challenges_completed_stored():
    s = _make(challenges_completed=2, challenges_total=5)
    assert s.challenges_completed == 2


def test_challenges_total_stored():
    s = _make(challenges_completed=2, challenges_total=5)
    assert s.challenges_total == 5


def test_level_before_stored():
    s = _make(level_before=4)
    assert s.level_before == 4


def test_extracted_items_stored_by_identity():
    items = [_FakeItem("Rifle", 500), _FakeItem("Vest", 200)]
    s = _make(extracted_items=items)
    assert s.extracted_items is items


def test_extracted_items_length():
    items = [_FakeItem("Rifle", 500), _FakeItem("Vest", 200)]
    s = _make(extracted_items=items)
    assert len(s.extracted_items) == 2


# ── Edge cases ─────────────────────────────────────────────────────────────────

def test_empty_extracted_items_is_valid():
    s = _make(extraction_status="timeout", extracted_items=[])
    assert s.extracted_items == []


def test_zero_xp_is_valid():
    s = _make(xp_earned=0)
    assert s.xp_earned == 0


def test_zero_kills_is_valid():
    s = _make(kills=0)
    assert s.kills == 0


def test_zero_challenges_is_valid():
    s = _make(challenges_completed=0, challenges_total=0)
    assert s.challenges_completed == 0
    assert s.challenges_total == 0


def test_large_xp_value_stored():
    s = _make(xp_earned=999_999)
    assert s.xp_earned == 999_999


def test_ten_items_stored():
    items = [_FakeItem(f"item_{i}", i * 100) for i in range(10)]
    s = _make(extracted_items=items)
    assert len(s.extracted_items) == 10


def test_timeout_with_zero_money_and_empty_items():
    """A timeout round earns no money and delivers no loot."""
    s = _make(extraction_status="timeout", money_earned=0, extracted_items=[])
    assert s.money_earned == 0
    assert s.extracted_items == []


def test_eliminated_with_zero_money_and_empty_items():
    """An eliminated round earns no money and delivers no loot."""
    s = _make(extraction_status="eliminated", money_earned=0, extracted_items=[])
    assert s.money_earned == 0
    assert s.extracted_items == []


# ── total_loot_value property ──────────────────────────────────────────────────


class _FakeItemWithValue:
    """Stand-in that exposes both monetary_value and value attributes."""

    def __init__(self, monetary_value: int, value: int | None = None):
        self.monetary_value = monetary_value
        self.value = value if value is not None else monetary_value


class _FakeItemValueOnly:
    """Stand-in with only a .value attribute (no .monetary_value)."""

    def __init__(self, value: int):
        self.value = value


class TestTotalLootValue:
    """RoundSummary.total_loot_value computed property."""

    def test_empty_items_returns_zero(self):
        s = _make(extracted_items=[])
        assert s.total_loot_value == 0

    def test_single_item_returns_its_monetary_value(self):
        s = _make(extracted_items=[_FakeItemWithValue(500)])
        assert s.total_loot_value == 500

    def test_multiple_items_summed(self):
        items = [_FakeItemWithValue(300), _FakeItemWithValue(700)]
        s = _make(extracted_items=items)
        assert s.total_loot_value == 1000

    def test_three_items_of_different_values(self):
        items = [_FakeItemWithValue(100), _FakeItemWithValue(250), _FakeItemWithValue(650)]
        s = _make(extracted_items=items)
        assert s.total_loot_value == 1000

    def test_prefers_monetary_value_over_value(self):
        """monetary_value is read first; the fallback .value should be ignored."""
        item = _FakeItemWithValue(monetary_value=800, value=100)
        s = _make(extracted_items=[item])
        assert s.total_loot_value == 800

    def test_falls_back_to_value_when_no_monetary_value(self):
        """Items without monetary_value fall back to .value."""
        item = _FakeItemValueOnly(value=400)
        s = _make(extracted_items=[item])
        assert s.total_loot_value == 400

    def test_zero_value_item_contributes_zero(self):
        items = [_FakeItemWithValue(0), _FakeItemWithValue(500)]
        s = _make(extracted_items=items)
        assert s.total_loot_value == 500

    def test_total_loot_value_is_int(self):
        items = [_FakeItemWithValue(333), _FakeItemWithValue(334)]
        s = _make(extracted_items=items)
        assert isinstance(s.total_loot_value, int)

    def test_large_loot_haul_summed_correctly(self):
        items = [_FakeItemWithValue(v) for v in [80, 300, 550, 1150, 2500]]
        s = _make(extracted_items=items)
        assert s.total_loot_value == 4580

    def test_failed_round_with_empty_items_is_zero(self):
        s = _make(extraction_status="timeout", extracted_items=[])
        assert s.total_loot_value == 0

    def test_read_only_does_not_mutate_items(self):
        """Accessing total_loot_value must not alter the extracted_items list."""
        items = [_FakeItemWithValue(300), _FakeItemWithValue(200)]
        s = _make(extracted_items=items)
        _ = s.total_loot_value
        assert len(s.extracted_items) == 2
        assert s.extracted_items[0].monetary_value == 300
