"""Unit tests for BotLoadoutBuilder and the _rarity_str helper.

Covers: return shape, weapon/armor selection, difficulty-based rarity
filtering, fallback when preferred rarity is absent, empty catalog edge case,
armour 50%-chance gate, and the _rarity_str normalisation helper.

# Run: pytest tests/test_bot_loadout.py
"""
from __future__ import annotations

from enum import Enum
from unittest.mock import MagicMock, patch

import pytest

from src.entities.bot_loadout import BotLoadoutBuilder, _rarity_str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(item_id: str = "pistol_01", rarity: str = "common") -> MagicMock:
    """Return a minimal item mock with id and rarity attributes."""
    m = MagicMock()
    m.id = item_id
    m.rarity = rarity
    return m


def _item_db(
    weapons: list | None = None,
    armors: list | None = None,
) -> MagicMock:
    """Return a mock ItemDatabase whose get_all_by_type() returns the given lists."""
    db = MagicMock()
    weapons = list(weapons or [])
    armors = list(armors or [])

    def _get_all(item_type: str) -> list:
        if item_type == "weapon":
            return weapons
        if item_type == "armor":
            return armors
        return []

    db.get_all_by_type.side_effect = _get_all
    return db


# ===========================================================================
# _rarity_str helper
# ===========================================================================

class TestRarityStr:
    """_rarity_str normalises rarity to a lower-case string."""

    def test_plain_string_returned_as_lowercase(self):
        m = MagicMock()
        m.rarity = "UNCOMMON"
        assert _rarity_str(m) == "uncommon"

    def test_already_lowercase_string_unchanged(self):
        m = MagicMock()
        m.rarity = "rare"
        assert _rarity_str(m) == "rare"

    def test_mixed_case_string_lowercased(self):
        m = MagicMock()
        m.rarity = "Legendary"
        assert _rarity_str(m) == "legendary"

    def test_enum_rarity_uses_value_attribute(self):
        class _Rarity(Enum):
            EPIC = "epic"

        m = MagicMock()
        m.rarity = _Rarity.EPIC
        assert _rarity_str(m) == "epic"

    def test_missing_rarity_attribute_defaults_to_common(self):
        # spec=[]: no auto-created attributes, so rarity is absent
        m = MagicMock(spec=[])
        assert _rarity_str(m) == "common"


# ===========================================================================
# Return shape
# ===========================================================================

class TestBotLoadoutBuilderReturnShape:
    """random_loadout always returns a dict with exactly 'weapon' and 'armor' keys."""

    def test_returns_dict(self):
        db = _item_db(weapons=[_item("pistol", "common")])
        result = BotLoadoutBuilder.random_loadout(db)
        assert isinstance(result, dict)

    def test_result_has_weapon_key(self):
        result = BotLoadoutBuilder.random_loadout(_item_db(weapons=[_item()]))
        assert "weapon" in result

    def test_result_has_armor_key(self):
        result = BotLoadoutBuilder.random_loadout(_item_db(weapons=[_item()]))
        assert "armor" in result

    def test_weapon_is_none_when_catalog_is_empty(self):
        result = BotLoadoutBuilder.random_loadout(_item_db(weapons=[], armors=[]))
        assert result["weapon"] is None

    def test_armor_is_none_when_armor_catalog_is_empty_and_random_triggers(self):
        db = _item_db(weapons=[_item()], armors=[])
        with patch("random.random", return_value=0.5):  # >= 0.5 → armor path
            result = BotLoadoutBuilder.random_loadout(db)
        assert result["armor"] is None

    def test_weapon_is_an_item_when_catalog_has_weapons(self):
        weapon = _item("rifle_01", "uncommon")
        db = _item_db(weapons=[weapon])
        with patch("random.choice", side_effect=lambda pool: pool[0]):
            result = BotLoadoutBuilder.random_loadout(db)
        assert result["weapon"] is weapon


# ===========================================================================
# Difficulty-based rarity filtering
# ===========================================================================

class TestBotLoadoutBuilderDifficultyFiltering:
    """Weapons are filtered to the preferred rarity tier for each difficulty."""

    def _first(self, pool: list):
        return pool[0]

    def test_easy_selects_from_common_weapons_only(self):
        common = _item("pistol", "common")
        rare = _item("sniper", "rare")
        db = _item_db(weapons=[common, rare])
        with patch("random.choice", side_effect=self._first):
            result = BotLoadoutBuilder.random_loadout(db, difficulty="easy")
        assert result["weapon"] is common

    def test_medium_selects_from_uncommon_weapons_only(self):
        uncommon = _item("rifle", "uncommon")
        common = _item("pistol", "common")
        db = _item_db(weapons=[common, uncommon])
        with patch("random.choice", side_effect=self._first):
            result = BotLoadoutBuilder.random_loadout(db, difficulty="medium")
        assert result["weapon"] is uncommon

    def test_hard_selects_from_rare_weapons_only(self):
        rare = _item("sniper", "rare")
        common = _item("pistol", "common")
        db = _item_db(weapons=[common, rare])
        with patch("random.choice", side_effect=self._first):
            result = BotLoadoutBuilder.random_loadout(db, difficulty="hard")
        assert result["weapon"] is rare

    def test_easy_filter_excludes_uncommon_weapons(self):
        """When easy is requested, only common weapons are in the pool."""
        uncommon = _item("rifle", "uncommon")
        db = _item_db(weapons=[uncommon])
        # No common weapons exist — fallback pool (all) is used instead
        with patch("random.choice", side_effect=self._first):
            result = BotLoadoutBuilder.random_loadout(db, difficulty="easy")
        # Must still return something (fallback to full pool)
        assert result["weapon"] is uncommon

    def test_medium_filter_excludes_non_uncommon_weapons(self):
        common = _item("pistol", "common")
        rare = _item("sniper", "rare")
        db = _item_db(weapons=[common, rare])
        # Neither is uncommon — fallback to all weapons
        with patch("random.choice", side_effect=self._first):
            result = BotLoadoutBuilder.random_loadout(db, difficulty="medium")
        # First in fallback pool is common
        assert result["weapon"] is common

    def test_unknown_difficulty_falls_back_gracefully(self):
        """An unrecognised difficulty string must not crash and must return a weapon."""
        weapon = _item("pistol", "common")
        db = _item_db(weapons=[weapon])
        with patch("random.choice", side_effect=self._first):
            result = BotLoadoutBuilder.random_loadout(db, difficulty="legendary")
        # Weapon may come from fallback pool — key assertion is no crash + non-None
        assert result["weapon"] is not None

    def test_default_difficulty_is_medium(self):
        """Calling without difficulty= uses 'medium' (uncommon preferred)."""
        uncommon = _item("rifle", "uncommon")
        common = _item("pistol", "common")
        db = _item_db(weapons=[common, uncommon])
        with patch("random.choice", side_effect=self._first):
            result = BotLoadoutBuilder.random_loadout(db)
        # medium → uncommon preferred, so uncommon rifle should be chosen
        assert result["weapon"] is uncommon


# ===========================================================================
# Fallback when preferred rarity is absent
# ===========================================================================

class TestBotLoadoutBuilderRarityFallback:
    """When no weapons match the preferred rarity, all weapons are used as fallback."""

    def test_fallback_pool_is_non_empty_when_alternatives_exist(self):
        rare_weapon = _item("sniper", "rare")
        db = _item_db(weapons=[rare_weapon])
        # difficulty="easy" wants common — none exist, so fallback to all
        with patch("random.choice", side_effect=lambda p: p[0]):
            result = BotLoadoutBuilder.random_loadout(db, difficulty="easy")
        assert result["weapon"] is rare_weapon

    def test_fallback_returns_none_only_when_catalog_is_truly_empty(self):
        db = _item_db(weapons=[])
        result = BotLoadoutBuilder.random_loadout(db, difficulty="easy")
        assert result["weapon"] is None


# ===========================================================================
# Armor 50% chance gate
# ===========================================================================

class TestBotLoadoutBuilderArmorChance:
    """The armor slot is filled with 50% probability controlled by random.random()."""

    def test_armor_not_selected_when_random_below_threshold(self):
        """random.random() < 0.5 → armor slot is skipped entirely."""
        armor = _item("vest_01", "common")
        db = _item_db(weapons=[_item()], armors=[armor])
        with patch("random.random", return_value=0.49):
            result = BotLoadoutBuilder.random_loadout(db)
        assert result["armor"] is None

    def test_armor_selected_when_random_at_threshold(self):
        """random.random() >= 0.5 → armor slot is populated from catalog."""
        armor = _item("vest_01", "common")
        db = _item_db(weapons=[_item()], armors=[armor])
        with patch("random.random", return_value=0.5):
            with patch("random.choice", side_effect=lambda p: p[0]):
                result = BotLoadoutBuilder.random_loadout(db)
        assert result["armor"] is armor

    def test_armor_selected_when_random_above_threshold(self):
        armor = _item("vest_01", "common")
        db = _item_db(weapons=[_item()], armors=[armor])
        with patch("random.random", return_value=0.99):
            with patch("random.choice", side_effect=lambda p: p[0]):
                result = BotLoadoutBuilder.random_loadout(db)
        assert result["armor"] is armor

    def test_armor_is_none_when_random_is_zero(self):
        """random.random() == 0.0 → below threshold, no armor."""
        armor = _item("vest_01", "common")
        db = _item_db(weapons=[_item()], armors=[armor])
        with patch("random.random", return_value=0.0):
            result = BotLoadoutBuilder.random_loadout(db)
        assert result["armor"] is None


# ===========================================================================
# Empty catalog edge cases
# ===========================================================================

class TestBotLoadoutBuilderEmptyCatalog:
    """BotLoadoutBuilder handles an empty ItemDatabase without crashing."""

    def test_fully_empty_db_returns_none_weapon(self):
        result = BotLoadoutBuilder.random_loadout(_item_db())
        assert result["weapon"] is None

    def test_fully_empty_db_returns_none_armor(self):
        with patch("random.random", return_value=0.5):  # trigger armor path
            result = BotLoadoutBuilder.random_loadout(_item_db())
        assert result["armor"] is None

    def test_fully_empty_db_still_returns_dict(self):
        result = BotLoadoutBuilder.random_loadout(_item_db())
        assert isinstance(result, dict)

    def test_get_all_by_type_called_for_weapon(self):
        db = _item_db()
        BotLoadoutBuilder.random_loadout(db)
        db.get_all_by_type.assert_any_call("weapon")
