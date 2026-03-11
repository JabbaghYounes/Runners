"""Unit tests for HomeBase upgrade logic and bonus computation."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.progression.home_base import HomeBase
from src.progression.currency import Currency


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def defs_path(tmp_path) -> str:
    """Write a minimal home_base.json to a temp directory and return its path."""
    data = {
        "facilities": [
            {
                "id": "armory",
                "name": "ARMORY",
                "description": "Test armory",
                "max_level": 5,
                "levels": [
                    {"cost": 300, "bonus_type": "loot_value_bonus", "bonus_value": 0.10, "description": "+10%"},
                    {"cost": 500, "bonus_type": "loot_value_bonus", "bonus_value": 0.20, "description": "+20%"},
                    {"cost": 800, "bonus_type": "loot_value_bonus", "bonus_value": 0.30, "description": "+30%"},
                    {"cost": 1200, "bonus_type": "loot_value_bonus", "bonus_value": 0.40, "description": "+40%"},
                    {"cost": 2000, "bonus_type": "loot_value_bonus", "bonus_value": 0.50, "description": "+50%"},
                ],
            },
            {
                "id": "med_bay",
                "name": "MED BAY",
                "description": "Test med bay",
                "max_level": 5,
                "levels": [
                    {"cost": 250, "bonus_type": "extra_hp", "bonus_value": 25,  "description": "+25 HP"},
                    {"cost": 450, "bonus_type": "extra_hp", "bonus_value": 50,  "description": "+50 HP"},
                    {"cost": 700, "bonus_type": "extra_hp", "bonus_value": 75,  "description": "+75 HP"},
                    {"cost": 1100, "bonus_type": "extra_hp", "bonus_value": 100, "description": "+100 HP"},
                    {"cost": 1800, "bonus_type": "extra_hp", "bonus_value": 125, "description": "+125 HP"},
                ],
            },
            {
                "id": "storage",
                "name": "STORAGE",
                "description": "Test storage",
                "max_level": 5,
                "levels": [
                    {"cost": 200, "bonus_type": "extra_slots", "bonus_value": 2,  "description": "+2 slots"},
                    {"cost": 400, "bonus_type": "extra_slots", "bonus_value": 4,  "description": "+4 slots"},
                    {"cost": 650, "bonus_type": "extra_slots", "bonus_value": 6,  "description": "+6 slots"},
                    {"cost": 1000, "bonus_type": "extra_slots", "bonus_value": 8,  "description": "+8 slots"},
                    {"cost": 1600, "bonus_type": "extra_slots", "bonus_value": 10, "description": "+10 slots"},
                ],
            },
        ]
    }
    p = tmp_path / "home_base.json"
    p.write_text(json.dumps(data))
    return str(p)


@pytest.fixture
def hb(defs_path) -> HomeBase:
    return HomeBase(defs_path)


@pytest.fixture
def rich_currency() -> Currency:
    c = Currency()
    c.add(10_000)
    return c


@pytest.fixture
def broke_currency() -> Currency:
    return Currency(balance=0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUpgrade:
    def test_upgrade_increments_level(self, hb, rich_currency):
        assert hb.current_level("med_bay") == 0
        result = hb.upgrade("med_bay", rich_currency)
        assert result is True
        assert hb.current_level("med_bay") == 1

    def test_upgrade_deducts_currency(self, hb, rich_currency):
        initial_balance = rich_currency.balance
        cost = hb.upgrade_cost("med_bay")
        hb.upgrade("med_bay", rich_currency)
        assert rich_currency.balance == initial_balance - cost

    def test_upgrade_fails_when_insufficient_funds(self, hb, broke_currency):
        result = hb.upgrade("med_bay", broke_currency)
        assert result is False
        assert hb.current_level("med_bay") == 0
        assert broke_currency.balance == 0  # no deduction

    def test_upgrade_fails_at_max_level(self, hb, rich_currency):
        # Upgrade to max
        for _ in range(5):
            hb.upgrade("armory", rich_currency)
        assert hb.is_maxed("armory")
        result = hb.upgrade("armory", rich_currency)
        assert result is False
        assert hb.current_level("armory") == 5

    def test_upgrade_cost_is_none_when_maxed(self, hb, rich_currency):
        for _ in range(5):
            hb.upgrade("storage", rich_currency)
        assert hb.upgrade_cost("storage") is None

    def test_can_upgrade_returns_false_when_maxed(self, hb, rich_currency):
        for _ in range(5):
            hb.upgrade("armory", rich_currency)
        assert hb.can_upgrade("armory", rich_currency) is False

    def test_can_upgrade_returns_false_when_broke(self, hb, broke_currency):
        assert hb.can_upgrade("med_bay", broke_currency) is False

    def test_can_upgrade_returns_true_when_affordable(self, hb, rich_currency):
        assert hb.can_upgrade("med_bay", rich_currency) is True


class TestGetRoundBonuses:
    def test_all_zero_when_no_upgrades(self, hb):
        bonuses = hb.get_round_bonuses()
        assert bonuses["extra_hp"] == 0
        assert bonuses["extra_slots"] == 0
        assert bonuses["loot_value_bonus"] == 0.0

    def test_sums_hp_correctly_at_level_1(self, hb, rich_currency):
        hb.upgrade("med_bay", rich_currency)
        bonuses = hb.get_round_bonuses()
        assert bonuses["extra_hp"] == 25

    def test_sums_hp_correctly_at_level_3(self, hb, rich_currency):
        for _ in range(3):
            hb.upgrade("med_bay", rich_currency)
        bonuses = hb.get_round_bonuses()
        assert bonuses["extra_hp"] == 75

    def test_sums_slots_correctly(self, hb, rich_currency):
        hb.upgrade("storage", rich_currency)
        bonuses = hb.get_round_bonuses()
        assert bonuses["extra_slots"] == 2

    def test_sums_slots_at_level_2(self, hb, rich_currency):
        hb.upgrade("storage", rich_currency)
        hb.upgrade("storage", rich_currency)
        bonuses = hb.get_round_bonuses()
        assert bonuses["extra_slots"] == 4

    def test_loot_value_bonus_uses_max_not_additive(self, hb, rich_currency):
        # Armory level 1 = 0.10
        hb.upgrade("armory", rich_currency)
        bonuses = hb.get_round_bonuses()
        assert abs(bonuses["loot_value_bonus"] - 0.10) < 1e-9

    def test_loot_value_bonus_increases_with_level(self, hb, rich_currency):
        hb.upgrade("armory", rich_currency)
        hb.upgrade("armory", rich_currency)
        bonuses = hb.get_round_bonuses()
        assert abs(bonuses["loot_value_bonus"] - 0.20) < 1e-9

    def test_mixed_bonuses_all_facilities(self, hb, rich_currency):
        hb.upgrade("armory", rich_currency)   # loot +0.10
        hb.upgrade("med_bay", rich_currency)  # hp +25
        hb.upgrade("storage", rich_currency)  # slots +2
        bonuses = hb.get_round_bonuses()
        assert bonuses["extra_hp"] == 25
        assert bonuses["extra_slots"] == 2
        assert abs(bonuses["loot_value_bonus"] - 0.10) < 1e-9


class TestPersistence:
    def test_to_save_dict_roundtrip(self, hb, rich_currency):
        hb.upgrade("armory", rich_currency)
        hb.upgrade("armory", rich_currency)
        hb.upgrade("med_bay", rich_currency)
        saved = hb.to_save_dict()
        assert saved["armory"] == 2
        assert saved["med_bay"] == 1
        assert saved["storage"] == 0

    def test_from_save_dict_restores_levels(self, defs_path):
        hb = HomeBase(defs_path)
        hb.from_save_dict({"armory": 3, "med_bay": 2, "storage": 1})
        assert hb.current_level("armory") == 3
        assert hb.current_level("med_bay") == 2
        assert hb.current_level("storage") == 1

    def test_from_save_dict_clamps_to_max_level(self, defs_path):
        hb = HomeBase(defs_path)
        hb.from_save_dict({"armory": 99, "med_bay": 0, "storage": -5})
        assert hb.current_level("armory") == 5   # clamped to max_level
        assert hb.current_level("med_bay") == 0
        assert hb.current_level("storage") == 0  # clamped to 0

    def test_from_save_dict_ignores_unknown_facility_keys(self, defs_path):
        hb = HomeBase(defs_path)
        # Should not raise; unknown key silently ignored
        hb.from_save_dict({"armory": 1, "unknown_facility": 5})
        assert hb.current_level("armory") == 1
        assert "unknown_facility" not in hb.facility_ids

    def test_full_roundtrip_via_save_dict(self, defs_path, rich_currency):
        hb1 = HomeBase(defs_path)
        for _ in range(3):
            hb1.upgrade("armory", rich_currency)
        hb1.upgrade("med_bay", rich_currency)

        save = hb1.to_save_dict()

        hb2 = HomeBase(defs_path)
        hb2.from_save_dict(save)
        assert hb2.current_level("armory") == hb1.current_level("armory")
        assert hb2.current_level("med_bay") == hb1.current_level("med_bay")
        assert hb2.get_round_bonuses() == hb1.get_round_bonuses()


class TestSaveManager:
    def test_save_and_load_home_base(self, defs_path, tmp_path, rich_currency):
        """SaveManager.save() + load() round-trip preserves home_base levels."""
        from src.save.save_manager import SaveManager
        from src.progression.xp_system import XPSystem

        save_path = tmp_path / "saves" / "test_save.json"
        manager = SaveManager(save_path)

        hb = HomeBase(defs_path)
        hb.upgrade("armory", rich_currency)
        hb.upgrade("med_bay", rich_currency)

        xp = XPSystem()
        currency = Currency(500)

        manager.save(home_base=hb, currency=currency, xp_system=xp)

        loaded = manager.load()
        assert loaded["home_base"]["armory"] == 1
        assert loaded["home_base"]["med_bay"] == 1
        assert loaded["home_base"]["storage"] == 0
        assert loaded["player"]["money"] == 500


# ---------------------------------------------------------------------------
# TestFacilityDisplay — get_facility_display() output at various levels
# ---------------------------------------------------------------------------

class TestFacilityDisplay:
    def test_display_at_level_0_shows_not_built(self, hb):
        disp = hb.get_facility_display("med_bay")
        assert disp["current_bonus_description"] == "Not built"

    def test_display_at_level_0_shows_next_level_description(self, hb):
        disp = hb.get_facility_display("med_bay")
        # Next level (level 1) description is the first levels entry
        assert disp["bonus_description"] == "+25 HP"

    def test_display_at_level_1_shows_current_bonus_description(self, hb, rich_currency):
        hb.upgrade("med_bay", rich_currency)
        disp = hb.get_facility_display("med_bay")
        # current = the level 1 description (+25 HP)
        assert disp["current_bonus_description"] == "+25 HP"
        # next = the level 2 description (+50 HP)
        assert disp["bonus_description"] == "+50 HP"

    def test_display_at_max_level_shows_MAX(self, hb, rich_currency):
        for _ in range(5):
            hb.upgrade("armory", rich_currency)
        disp = hb.get_facility_display("armory")
        assert disp["bonus_description"] == "MAX"
        assert disp["cost"] is None

    def test_display_contains_all_required_keys(self, hb):
        disp = hb.get_facility_display("storage")
        expected_keys = {"id", "name", "level", "max_level", "cost",
                         "bonus_description", "current_bonus_description"}
        assert expected_keys == set(disp.keys())

    def test_display_level_matches_current_level(self, hb, rich_currency):
        hb.upgrade("storage", rich_currency)
        hb.upgrade("storage", rich_currency)
        disp = hb.get_facility_display("storage")
        assert disp["level"] == 2

    def test_display_max_level_field(self, hb):
        disp = hb.get_facility_display("armory")
        assert disp["max_level"] == 5

    def test_display_name_matches_json(self, hb):
        assert hb.get_facility_display("armory")["name"] == "ARMORY"
        assert hb.get_facility_display("med_bay")["name"] == "MED BAY"
        assert hb.get_facility_display("storage")["name"] == "STORAGE"

    def test_display_cost_is_correct_at_level_0(self, hb):
        # level 0 → next upgrade is level 1, cost is 250 for med_bay
        disp = hb.get_facility_display("med_bay")
        assert disp["cost"] == 250

    def test_display_cost_advances_with_level(self, hb, rich_currency):
        hb.upgrade("storage", rich_currency)   # now level 1
        disp = hb.get_facility_display("storage")
        # cost for level 2 is 400
        assert disp["cost"] == 400


# ---------------------------------------------------------------------------
# TestFacilityIds — facility_ids property
# ---------------------------------------------------------------------------

class TestFacilityIds:
    def test_facility_ids_returns_list(self, hb):
        assert isinstance(hb.facility_ids, list)

    def test_facility_ids_length_is_three(self, hb):
        assert len(hb.facility_ids) == 3

    def test_facility_ids_contains_armory(self, hb):
        assert "armory" in hb.facility_ids

    def test_facility_ids_contains_med_bay(self, hb):
        assert "med_bay" in hb.facility_ids

    def test_facility_ids_contains_storage(self, hb):
        assert "storage" in hb.facility_ids

    def test_facility_ids_order_matches_json(self, hb):
        # JSON defines: armory, med_bay, storage — order must be preserved
        assert hb.facility_ids == ["armory", "med_bay", "storage"]


# ---------------------------------------------------------------------------
# TestEdgeCases — guards on unusual inputs and boundary conditions
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_unknown_facility_raises_key_error(self, hb):
        # current_level() uses dict.get() and silently returns 0; methods that
        # look up the definition dict (_def) raise KeyError for unknown ids.
        with pytest.raises(KeyError):
            hb.max_level("unknown")

    def test_unknown_facility_upgrade_cost_raises(self, hb):
        with pytest.raises(KeyError):
            hb.upgrade_cost("unknown_facility")

    def test_is_maxed_false_at_level_zero(self, hb):
        assert hb.is_maxed("armory") is False

    def test_is_maxed_false_mid_level(self, hb, rich_currency):
        for _ in range(3):
            hb.upgrade("armory", rich_currency)
        assert hb.is_maxed("armory") is False

    def test_to_save_dict_always_contains_all_facilities(self, hb):
        saved = hb.to_save_dict()
        assert "armory" in saved
        assert "med_bay" in saved
        assert "storage" in saved

    def test_from_save_dict_empty_dict_leaves_all_zero(self, defs_path):
        hb = HomeBase(defs_path)
        hb.from_save_dict({})
        for fid in hb.facility_ids:
            assert hb.current_level(fid) == 0

    def test_from_save_dict_partial_dict_only_updates_specified(self, defs_path):
        hb = HomeBase(defs_path)
        hb.from_save_dict({"armory": 3})
        assert hb.current_level("armory") == 3
        assert hb.current_level("med_bay") == 0
        assert hb.current_level("storage") == 0

    def test_from_save_dict_float_values_are_casted_to_int(self, defs_path):
        hb = HomeBase(defs_path)
        hb.from_save_dict({"armory": 2.9})
        # int(2.9) == 2
        assert hb.current_level("armory") == 2

    def test_upgrade_sequence_costs_match_json(self, hb, rich_currency):
        """Each upgrade level deducts the exact cost defined in the JSON."""
        expected_costs = [200, 400, 650, 1000, 1600]  # storage level costs
        for expected_cost in expected_costs:
            assert hb.upgrade_cost("storage") == expected_cost
            hb.upgrade("storage", rich_currency)

    def test_upgrading_one_facility_does_not_affect_others(self, hb, rich_currency):
        hb.upgrade("armory", rich_currency)
        hb.upgrade("armory", rich_currency)
        assert hb.current_level("med_bay") == 0
        assert hb.current_level("storage") == 0

    def test_get_round_bonuses_returns_all_required_keys(self, hb):
        bonuses = hb.get_round_bonuses()
        assert "extra_hp" in bonuses
        assert "extra_slots" in bonuses
        assert "loot_value_bonus" in bonuses

    def test_get_round_bonuses_defaults_are_zero(self, hb):
        bonuses = hb.get_round_bonuses()
        assert bonuses["extra_hp"] == 0
        assert bonuses["extra_slots"] == 0
        assert bonuses["loot_value_bonus"] == 0.0

    def test_max_level_value_is_five_for_all_facilities(self, hb):
        for fid in hb.facility_ids:
            assert hb.max_level(fid) == 5

    def test_upgrade_cost_after_partial_upgrades_is_correct(self, hb, rich_currency):
        # Med bay: costs 250, 450, 700, 1100, 1800
        hb.upgrade("med_bay", rich_currency)  # now level 1, next cost = 450
        assert hb.upgrade_cost("med_bay") == 450
        hb.upgrade("med_bay", rich_currency)  # now level 2, next cost = 700
        assert hb.upgrade_cost("med_bay") == 700
