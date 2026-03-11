"""Tests for GameScene._apply_home_base_bonuses().

Strategy: call the private method as an unbound function, passing a minimal
stub "self" (SimpleNamespace) and a stub player. This avoids pygame
initialisation and lets us test the pure bonus-application logic in isolation.
"""
from __future__ import annotations

import json
import types

import pytest

from src.scenes.game_scene import GameScene
from src.progression.home_base import HomeBase
from src.progression.currency import Currency


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def defs_path(tmp_path) -> str:
    """Write a minimal home_base.json and return its path."""
    data = {
        "facilities": [
            {
                "id": "armory",
                "name": "ARMORY",
                "description": "Loot value facility",
                "max_level": 5,
                "levels": [
                    {"cost": 300,  "bonus_type": "loot_value_bonus", "bonus_value": 0.10, "description": "+10%"},
                    {"cost": 500,  "bonus_type": "loot_value_bonus", "bonus_value": 0.20, "description": "+20%"},
                    {"cost": 800,  "bonus_type": "loot_value_bonus", "bonus_value": 0.30, "description": "+30%"},
                    {"cost": 1200, "bonus_type": "loot_value_bonus", "bonus_value": 0.40, "description": "+40%"},
                    {"cost": 2000, "bonus_type": "loot_value_bonus", "bonus_value": 0.50, "description": "+50%"},
                ],
            },
            {
                "id": "med_bay",
                "name": "MED BAY",
                "description": "HP facility",
                "max_level": 5,
                "levels": [
                    {"cost": 250,  "bonus_type": "extra_hp", "bonus_value": 25,  "description": "+25 HP"},
                    {"cost": 450,  "bonus_type": "extra_hp", "bonus_value": 50,  "description": "+50 HP"},
                    {"cost": 700,  "bonus_type": "extra_hp", "bonus_value": 75,  "description": "+75 HP"},
                    {"cost": 1100, "bonus_type": "extra_hp", "bonus_value": 100, "description": "+100 HP"},
                    {"cost": 1800, "bonus_type": "extra_hp", "bonus_value": 125, "description": "+125 HP"},
                ],
            },
            {
                "id": "storage",
                "name": "STORAGE",
                "description": "Inventory facility",
                "max_level": 5,
                "levels": [
                    {"cost": 200,  "bonus_type": "extra_slots", "bonus_value": 2,  "description": "+2 slots"},
                    {"cost": 400,  "bonus_type": "extra_slots", "bonus_value": 4,  "description": "+4 slots"},
                    {"cost": 650,  "bonus_type": "extra_slots", "bonus_value": 6,  "description": "+6 slots"},
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
def rich() -> Currency:
    # Max-levelling all three facilities costs $12,950 total; use 15,000
    # so any single test that max-levels everything has headroom.
    c = Currency()
    c.add(15_000)
    return c


class _StubInventory:
    """Minimal inventory stand-in: tracks capacity changes only."""

    def __init__(self, capacity: int = 24) -> None:
        self._capacity = capacity

    def expand_capacity(self, n: int) -> None:
        if n > 0:
            self._capacity += n


class _StubPlayer:
    """Minimal player stand-in for bonus-application tests."""

    def __init__(self, health: int = 100) -> None:
        self.health = health
        self.max_health = health
        self.inventory = _StubInventory()


def _apply(scene_stub, player, home_base) -> None:
    """Call the unbound method with a fake self."""
    GameScene._apply_home_base_bonuses(scene_stub, player, home_base)


def _scene() -> types.SimpleNamespace:
    """Create a minimal stub that provides the attributes the method writes."""
    return types.SimpleNamespace(loot_value_bonus=0.0)


# ---------------------------------------------------------------------------
# TestApplyHomeBaseBonuses
# ---------------------------------------------------------------------------

class TestApplyHomeBaseBonuses:

    # ----- None home_base (no-op) -------------------------------------------

    def test_none_home_base_leaves_health_unchanged(self):
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, None)
        assert player.health == 100

    def test_none_home_base_leaves_max_health_unchanged(self):
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, None)
        assert player.max_health == 100

    def test_none_home_base_leaves_inventory_unchanged(self):
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, None)
        assert player.inventory._capacity == 24

    def test_none_home_base_leaves_loot_bonus_zero(self):
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, None)
        assert scene.loot_value_bonus == 0.0

    # ----- All facilities at level 0 ----------------------------------------

    def test_all_level_zero_no_hp_change(self, hb):
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert player.health == 100
        assert player.max_health == 100

    def test_all_level_zero_no_inventory_change(self, hb):
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert player.inventory._capacity == 24

    def test_all_level_zero_loot_bonus_is_zero(self, hb):
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert scene.loot_value_bonus == 0.0

    # ----- Med Bay (extra_hp) -----------------------------------------------

    def test_med_bay_level_1_adds_25_hp(self, hb, rich):
        hb.upgrade("med_bay", rich)
        scene = _scene()
        player = _StubPlayer(health=100)
        _apply(scene, player, hb)
        assert player.health == 125

    def test_med_bay_level_1_raises_max_health(self, hb, rich):
        hb.upgrade("med_bay", rich)
        scene = _scene()
        player = _StubPlayer(health=100)
        _apply(scene, player, hb)
        assert player.max_health == 125

    def test_med_bay_health_and_max_health_stay_equal(self, hb, rich):
        hb.upgrade("med_bay", rich)
        scene = _scene()
        player = _StubPlayer(health=100)
        _apply(scene, player, hb)
        assert player.health == player.max_health

    def test_med_bay_level_3_adds_75_hp(self, hb, rich):
        for _ in range(3):
            hb.upgrade("med_bay", rich)
        scene = _scene()
        player = _StubPlayer(health=100)
        _apply(scene, player, hb)
        assert player.health == 175
        assert player.max_health == 175

    def test_med_bay_max_level_adds_125_hp(self, hb, rich):
        for _ in range(5):
            hb.upgrade("med_bay", rich)
        scene = _scene()
        player = _StubPlayer(health=100)
        _apply(scene, player, hb)
        assert player.health == 225
        assert player.max_health == 225

    def test_med_bay_does_not_change_inventory(self, hb, rich):
        hb.upgrade("med_bay", rich)
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert player.inventory._capacity == 24

    def test_med_bay_does_not_change_loot_bonus(self, hb, rich):
        hb.upgrade("med_bay", rich)
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert scene.loot_value_bonus == 0.0

    # ----- Storage (extra_slots) --------------------------------------------

    def test_storage_level_1_adds_2_slots(self, hb, rich):
        hb.upgrade("storage", rich)
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert player.inventory._capacity == 26

    def test_storage_level_2_adds_4_slots(self, hb, rich):
        hb.upgrade("storage", rich)
        hb.upgrade("storage", rich)
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert player.inventory._capacity == 28

    def test_storage_max_level_adds_10_slots(self, hb, rich):
        for _ in range(5):
            hb.upgrade("storage", rich)
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert player.inventory._capacity == 34

    def test_storage_does_not_change_player_health(self, hb, rich):
        hb.upgrade("storage", rich)
        scene = _scene()
        player = _StubPlayer(health=100)
        _apply(scene, player, hb)
        assert player.health == 100
        assert player.max_health == 100

    def test_storage_does_not_change_loot_bonus(self, hb, rich):
        hb.upgrade("storage", rich)
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert scene.loot_value_bonus == 0.0

    # ----- Armory (loot_value_bonus) ----------------------------------------

    def test_armory_level_1_sets_loot_bonus_to_0_10(self, hb, rich):
        hb.upgrade("armory", rich)
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert abs(scene.loot_value_bonus - 0.10) < 1e-9

    def test_armory_level_3_sets_loot_bonus_to_0_30(self, hb, rich):
        for _ in range(3):
            hb.upgrade("armory", rich)
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert abs(scene.loot_value_bonus - 0.30) < 1e-9

    def test_armory_max_level_sets_loot_bonus_to_0_50(self, hb, rich):
        for _ in range(5):
            hb.upgrade("armory", rich)
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert abs(scene.loot_value_bonus - 0.50) < 1e-9

    def test_armory_does_not_change_health(self, hb, rich):
        hb.upgrade("armory", rich)
        scene = _scene()
        player = _StubPlayer(health=100)
        _apply(scene, player, hb)
        assert player.health == 100
        assert player.max_health == 100

    def test_armory_does_not_change_inventory(self, hb, rich):
        hb.upgrade("armory", rich)
        scene = _scene()
        player = _StubPlayer()
        _apply(scene, player, hb)
        assert player.inventory._capacity == 24

    # ----- All three facilities upgraded ------------------------------------

    def test_all_facilities_level_1_applies_all_bonuses(self, hb, rich):
        hb.upgrade("armory", rich)   # loot +0.10
        hb.upgrade("med_bay", rich)  # hp +25
        hb.upgrade("storage", rich)  # slots +2
        scene = _scene()
        player = _StubPlayer(health=100)
        _apply(scene, player, hb)
        assert player.health == 125
        assert player.max_health == 125
        assert player.inventory._capacity == 26
        assert abs(scene.loot_value_bonus - 0.10) < 1e-9

    def test_all_facilities_max_level_applies_all_bonuses(self, hb, rich):
        for fid in ("armory", "med_bay", "storage"):
            for _ in range(5):
                hb.upgrade(fid, rich)
        scene = _scene()
        player = _StubPlayer(health=100)
        _apply(scene, player, hb)
        assert player.health == 225        # +125 from med_bay max
        assert player.max_health == 225
        assert player.inventory._capacity == 34  # +10 from storage max
        assert abs(scene.loot_value_bonus - 0.50) < 1e-9

    def test_bonuses_applied_to_player_with_custom_base_health(self, hb, rich):
        """Bonus stacks on top of whatever the player's base health is."""
        hb.upgrade("med_bay", rich)   # +25 hp
        scene = _scene()
        player = _StubPlayer(health=150)  # non-default base
        _apply(scene, player, hb)
        assert player.health == 175
        assert player.max_health == 175

    def test_apply_is_idempotent_for_same_home_base_state(self, hb, rich):
        """Calling _apply_home_base_bonuses twice does NOT double-apply bonuses
        to the same player instance — a new player is assumed each round."""
        hb.upgrade("med_bay", rich)
        scene1 = _scene()
        scene2 = _scene()
        player1 = _StubPlayer(health=100)
        player2 = _StubPlayer(health=100)
        _apply(scene1, player1, hb)
        _apply(scene2, player2, hb)
        # Each player independently receives the bonus once
        assert player1.health == player2.health == 125
