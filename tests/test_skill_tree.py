"""Unit tests for the SkillTree progression system.

Tests cover:
- Loading skill tree data from JSON
- Branch and node query methods
- Prerequisite enforcement (can_unlock)
- Unlock with and without an XPSystem (skill-point gating)
- Skill-point deduction on unlock
- Stat bonus aggregation from unlocked nodes
- Save/load round-trip (serialisation)
- Display helpers
- Integration with SaveManager (including skill_points persistence)
- Integration with GameScene._apply_skill_tree_bonuses
"""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from src.progression.skill_tree import SkillTree
from src.progression.xp_system import XPSystem
from src.progression.currency import Currency


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def skill_data() -> dict:
    """Return a minimal skill tree definition with two branches."""
    return {
        "branches": ["combat", "mobility"],
        "nodes": [
            {
                "id": "combat_1",
                "name": "Steady Aim",
                "branch": "combat",
                "description": "+10% weapon damage",
                "cost_sp": 1,
                "requires": [],
                "stat_bonus": {"damage_mult": 0.10},
            },
            {
                "id": "combat_2",
                "name": "Armored Up",
                "branch": "combat",
                "description": "+15 starting armor",
                "cost_sp": 1,
                "requires": ["combat_1"],
                "stat_bonus": {"extra_armor": 15},
            },
            {
                "id": "combat_3",
                "name": "Lethal Precision",
                "branch": "combat",
                "description": "+20% weapon damage",
                "cost_sp": 1,
                "requires": ["combat_2"],
                "stat_bonus": {"damage_mult": 0.20},
            },
            {
                "id": "mobility_1",
                "name": "Light Feet",
                "branch": "mobility",
                "description": "+10% movement speed",
                "cost_sp": 1,
                "requires": [],
                "stat_bonus": {"speed_mult": 0.10},
            },
            {
                "id": "mobility_2",
                "name": "Quick Recovery",
                "branch": "mobility",
                "description": "+15 max HP",
                "cost_sp": 1,
                "requires": ["mobility_1"],
                "stat_bonus": {"extra_hp": 15},
            },
            {
                "id": "mobility_3",
                "name": "Sprint Master",
                "branch": "mobility",
                "description": "+20% movement speed",
                "cost_sp": 1,
                "requires": ["mobility_2"],
                "stat_bonus": {"speed_mult": 0.20},
            },
        ],
    }


@pytest.fixture
def skill_path(tmp_path, skill_data) -> str:
    """Write skill tree JSON to a temp file and return its path."""
    p = tmp_path / "skill_tree.json"
    p.write_text(json.dumps(skill_data))
    return str(p)


@pytest.fixture
def tree(skill_path) -> SkillTree:
    """A SkillTree loaded from the test data."""
    st = SkillTree()
    st.load(skill_path)
    return st


@pytest.fixture
def xp_with_sp() -> XPSystem:
    """An XPSystem with 10 skill points — enough to unlock any chain."""
    xp = XPSystem()
    xp.skill_points = 10
    return xp


@pytest.fixture
def xp_broke() -> XPSystem:
    """An XPSystem with 0 skill points."""
    return XPSystem()


# ---------------------------------------------------------------------------
# TestLoad -- loading skill tree data
# ---------------------------------------------------------------------------

class TestLoad:
    def test_load_populates_nodes(self, tree):
        assert len(tree.node_ids) == 6

    def test_load_populates_branches(self, tree):
        assert tree.branches == ["combat", "mobility"]

    def test_get_node_returns_dict(self, tree):
        node = tree.get_node("combat_1")
        assert node is not None
        assert node["name"] == "Steady Aim"

    def test_get_node_returns_none_for_unknown(self, tree):
        assert tree.get_node("nonexistent") is None

    def test_get_branch_nodes_returns_correct_count(self, tree):
        assert len(tree.get_branch_nodes("combat")) == 3
        assert len(tree.get_branch_nodes("mobility")) == 3

    def test_get_branch_nodes_returns_empty_for_unknown(self, tree):
        assert tree.get_branch_nodes("unknown") == []

    def test_node_ids_property_returns_all_ids(self, tree):
        ids = tree.node_ids
        assert "combat_1" in ids
        assert "combat_2" in ids
        assert "combat_3" in ids
        assert "mobility_1" in ids
        assert "mobility_2" in ids
        assert "mobility_3" in ids

    def test_load_raises_on_missing_id(self, tmp_path):
        bad = {"branches": ["x"], "nodes": [{"branch": "x"}]}
        p = tmp_path / "bad.json"
        p.write_text(json.dumps(bad))
        st = SkillTree()
        with pytest.raises(ValueError, match="'id'"):
            st.load(str(p))

    def test_load_raises_on_missing_branch(self, tmp_path):
        bad = {"branches": [], "nodes": [{"id": "x_1"}]}
        p = tmp_path / "bad2.json"
        p.write_text(json.dumps(bad))
        st = SkillTree()
        with pytest.raises(ValueError, match="'branch'"):
            st.load(str(p))


# ---------------------------------------------------------------------------
# TestCanUnlock -- prerequisite enforcement
# ---------------------------------------------------------------------------

class TestCanUnlock:
    def test_root_node_can_be_unlocked(self, tree):
        assert tree.can_unlock("combat_1") is True

    def test_child_node_cannot_be_unlocked_without_parent(self, tree):
        assert tree.can_unlock("combat_2") is False

    def test_child_node_can_be_unlocked_after_parent(self, tree):
        tree.unlock("combat_1")
        assert tree.can_unlock("combat_2") is True

    def test_grandchild_cannot_be_unlocked_without_full_chain(self, tree):
        tree.unlock("combat_1")
        assert tree.can_unlock("combat_3") is False

    def test_grandchild_can_be_unlocked_after_full_chain(self, tree):
        tree.unlock("combat_1")
        tree.unlock("combat_2")
        assert tree.can_unlock("combat_3") is True

    def test_unknown_node_cannot_be_unlocked(self, tree):
        assert tree.can_unlock("nonexistent") is False

    def test_already_unlocked_node_returns_false(self, tree):
        tree.unlock("combat_1")
        assert tree.can_unlock("combat_1") is False

    def test_can_unlock_with_sufficient_sp(self, tree, xp_with_sp):
        assert tree.can_unlock("combat_1", xp_with_sp) is True

    def test_can_unlock_with_zero_sp(self, tree, xp_broke):
        assert tree.can_unlock("combat_1", xp_broke) is False

    def test_can_unlock_with_exact_sp(self, tree):
        xp = XPSystem()
        xp.skill_points = 1  # cost_sp is 1
        assert tree.can_unlock("combat_1", xp) is True

    def test_can_unlock_with_one_less_than_cost(self, tree):
        xp = XPSystem()
        xp.skill_points = 0  # cost_sp is 1
        assert tree.can_unlock("combat_1", xp) is False

    def test_can_unlock_without_xp_system_ignores_sp(self, tree):
        """No xp_system → SP check is skipped (free-unlock mode for tests)."""
        assert tree.can_unlock("combat_1") is True


# ---------------------------------------------------------------------------
# TestUnlock -- unlock logic and SP deduction
# ---------------------------------------------------------------------------

class TestUnlock:
    def test_unlock_root_node_succeeds(self, tree):
        assert tree.unlock("combat_1") is True
        assert tree.is_unlocked("combat_1") is True

    def test_unlock_marks_node_as_unlocked(self, tree):
        tree.unlock("combat_1")
        assert "combat_1" in tree.unlocked_ids

    def test_unlock_fails_for_locked_prerequisite(self, tree):
        assert tree.unlock("combat_2") is False
        assert tree.is_unlocked("combat_2") is False

    def test_unlock_fails_for_already_unlocked(self, tree):
        tree.unlock("combat_1")
        assert tree.unlock("combat_1") is False

    def test_unlock_unknown_node_fails(self, tree):
        assert tree.unlock("nonexistent") is False

    def test_unlock_with_sp_deducts_cost(self, tree, xp_with_sp):
        initial = xp_with_sp.skill_points
        tree.unlock("combat_1", xp_with_sp)
        assert xp_with_sp.skill_points == initial - 1

    def test_unlock_with_zero_sp_fails(self, tree, xp_broke):
        assert tree.unlock("combat_1", xp_broke) is False
        assert tree.is_unlocked("combat_1") is False
        assert xp_broke.skill_points == 0

    def test_unlock_chain_with_sp(self, tree, xp_with_sp):
        initial = xp_with_sp.skill_points
        tree.unlock("combat_1", xp_with_sp)
        tree.unlock("combat_2", xp_with_sp)
        assert xp_with_sp.skill_points == initial - 2

    def test_unlock_without_xp_system_does_not_check_sp(self, tree):
        """Without xp_system arg, unlock should succeed (free unlock mode)."""
        assert tree.unlock("combat_1") is True

    def test_unlock_full_branch(self, tree, xp_with_sp):
        tree.unlock("combat_1", xp_with_sp)
        tree.unlock("combat_2", xp_with_sp)
        tree.unlock("combat_3", xp_with_sp)
        assert tree.is_unlocked("combat_1")
        assert tree.is_unlocked("combat_2")
        assert tree.is_unlocked("combat_3")

    def test_unlock_across_branches(self, tree, xp_with_sp):
        tree.unlock("combat_1", xp_with_sp)
        tree.unlock("mobility_1", xp_with_sp)
        assert tree.is_unlocked("combat_1")
        assert tree.is_unlocked("mobility_1")

    def test_get_cost_sp_returns_correct_value(self, tree):
        assert tree.get_cost_sp("combat_1") == 1
        assert tree.get_cost_sp("combat_2") == 1
        assert tree.get_cost_sp("combat_3") == 1

    def test_get_cost_sp_unknown_returns_zero(self, tree):
        assert tree.get_cost_sp("nonexistent") == 0

    def test_sp_not_deducted_on_failed_unlock(self, tree, xp_with_sp):
        initial = xp_with_sp.skill_points
        # combat_2 requires combat_1 — unlock will fail
        result = tree.unlock("combat_2", xp_with_sp)
        assert result is False
        assert xp_with_sp.skill_points == initial


# ---------------------------------------------------------------------------
# TestStatBonuses -- bonus aggregation
# ---------------------------------------------------------------------------

class TestStatBonuses:
    def test_no_bonuses_when_nothing_unlocked(self, tree):
        bonuses = tree.get_stat_bonuses()
        assert bonuses == {}

    def test_single_node_bonus(self, tree):
        tree.unlock("combat_1")
        bonuses = tree.get_stat_bonuses()
        assert abs(bonuses["damage_mult"] - 0.10) < 1e-9

    def test_chain_bonuses_accumulate(self, tree):
        tree.unlock("combat_1")
        tree.unlock("combat_2")
        tree.unlock("combat_3")
        bonuses = tree.get_stat_bonuses()
        # damage_mult: 0.10 + 0.20 = 0.30
        assert abs(bonuses["damage_mult"] - 0.30) < 1e-9
        # extra_armor: 15
        assert bonuses["extra_armor"] == 15

    def test_cross_branch_bonuses(self, tree):
        tree.unlock("combat_1")
        tree.unlock("mobility_1")
        bonuses = tree.get_stat_bonuses()
        assert abs(bonuses["damage_mult"] - 0.10) < 1e-9
        assert abs(bonuses["speed_mult"] - 0.10) < 1e-9

    def test_full_mobility_branch_bonuses(self, tree):
        tree.unlock("mobility_1")
        tree.unlock("mobility_2")
        tree.unlock("mobility_3")
        bonuses = tree.get_stat_bonuses()
        # speed_mult: 0.10 + 0.20 = 0.30
        assert abs(bonuses["speed_mult"] - 0.30) < 1e-9
        # extra_hp: 15
        assert bonuses["extra_hp"] == 15

    def test_all_nodes_unlocked_bonuses(self, tree):
        for nid in tree.node_ids:
            # Unlock in order to satisfy prerequisites
            tree.unlock(nid)
        bonuses = tree.get_stat_bonuses()
        assert abs(bonuses["damage_mult"] - 0.30) < 1e-9
        assert bonuses["extra_armor"] == 15
        assert abs(bonuses["speed_mult"] - 0.30) < 1e-9
        assert bonuses["extra_hp"] == 15


# ---------------------------------------------------------------------------
# TestSaveLoad -- serialisation round-trip
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_empty_tree_saves_empty_list(self, tree):
        data = tree.to_save_dict()
        assert data["unlocked"] == []

    def test_save_contains_unlocked_nodes(self, tree):
        tree.unlock("combat_1")
        tree.unlock("mobility_1")
        data = tree.to_save_dict()
        assert "combat_1" in data["unlocked"]
        assert "mobility_1" in data["unlocked"]

    def test_save_dict_is_sorted(self, tree):
        tree.unlock("mobility_1")
        tree.unlock("combat_1")
        data = tree.to_save_dict()
        assert data["unlocked"] == sorted(data["unlocked"])

    def test_load_state_restores_unlocked(self, tree):
        tree.load_state({"unlocked": ["combat_1", "combat_2"]})
        assert tree.is_unlocked("combat_1")
        assert tree.is_unlocked("combat_2")
        assert not tree.is_unlocked("combat_3")

    def test_load_state_with_unlocked_nodes_key(self, tree):
        """SaveManager uses 'unlocked_nodes'; SkillTree should accept both."""
        tree.load_state({"unlocked_nodes": ["mobility_1"]})
        assert tree.is_unlocked("mobility_1")

    def test_load_state_empty_dict(self, tree):
        tree.unlock("combat_1")
        tree.load_state({})
        assert not tree.is_unlocked("combat_1")

    def test_full_round_trip(self, skill_path):
        st1 = SkillTree()
        st1.load(skill_path)
        st1.unlock("combat_1")
        st1.unlock("combat_2")
        st1.unlock("mobility_1")
        saved = st1.to_save_dict()

        st2 = SkillTree()
        st2.load(skill_path)
        st2.load_state(saved)
        assert st2.is_unlocked("combat_1")
        assert st2.is_unlocked("combat_2")
        assert st2.is_unlocked("mobility_1")
        assert not st2.is_unlocked("combat_3")
        assert st2.get_stat_bonuses() == st1.get_stat_bonuses()


# ---------------------------------------------------------------------------
# TestNodeDisplay -- display helper
# ---------------------------------------------------------------------------

class TestNodeDisplay:
    def test_display_returns_dict_for_valid_node(self, tree):
        disp = tree.get_node_display("combat_1")
        assert disp is not None
        assert disp["id"] == "combat_1"
        assert disp["name"] == "Steady Aim"
        assert disp["branch"] == "combat"

    def test_display_returns_none_for_unknown_node(self, tree):
        assert tree.get_node_display("nonexistent") is None

    def test_display_shows_unlocked_true_after_unlock(self, tree):
        tree.unlock("combat_1")
        disp = tree.get_node_display("combat_1")
        assert disp["unlocked"] is True

    def test_display_shows_available_true_for_root(self, tree):
        disp = tree.get_node_display("combat_1")
        assert disp["available"] is True

    def test_display_shows_available_false_for_locked_child(self, tree):
        disp = tree.get_node_display("combat_2")
        assert disp["available"] is False

    def test_display_contains_cost_sp(self, tree):
        disp = tree.get_node_display("combat_1")
        assert disp["cost_sp"] == 1

    def test_display_contains_description(self, tree):
        disp = tree.get_node_display("combat_1")
        assert disp["description"] == "+10% weapon damage"

    def test_display_contains_requires(self, tree):
        disp = tree.get_node_display("combat_2")
        assert disp["requires"] == ["combat_1"]

    def test_display_available_respects_xp_system_sp(self, tree):
        """available=True only when xp_system has enough SP."""
        xp = XPSystem()
        xp.skill_points = 0
        disp = tree.get_node_display("combat_1", xp_system=xp)
        assert disp["available"] is False

        xp.skill_points = 1
        disp = tree.get_node_display("combat_1", xp_system=xp)
        assert disp["available"] is True


# ---------------------------------------------------------------------------
# TestXPSystemSkillPoints -- XPSystem SP mechanics
# ---------------------------------------------------------------------------

class TestXPSystemSkillPoints:
    def test_level_up_awards_one_sp(self):
        xp = XPSystem()
        assert xp.skill_points == 0
        xp.award(xp.xp_to_next_level())
        assert xp.level == 2
        assert xp.skill_points == 1

    def test_multiple_level_ups_award_correct_sp(self):
        xp = XPSystem()
        # Award enough XP to reach level 3
        needed = xp.xp_to_next_level()
        xp.award(needed)
        needed2 = xp.xp_to_next_level()
        xp.award(needed2)
        assert xp.level == 3
        assert xp.skill_points == 2

    def test_spend_skill_point_deducts(self):
        xp = XPSystem()
        xp.skill_points = 5
        result = xp.spend_skill_point()
        assert result is True
        assert xp.skill_points == 4

    def test_spend_skill_point_fails_when_broke(self):
        xp = XPSystem()
        result = xp.spend_skill_point()
        assert result is False
        assert xp.skill_points == 0

    def test_spend_skill_point_amount(self):
        xp = XPSystem()
        xp.skill_points = 3
        result = xp.spend_skill_point(2)
        assert result is True
        assert xp.skill_points == 1

    def test_sp_persists_through_save_dict(self):
        xp = XPSystem()
        xp.skill_points = 7
        data = xp.to_save_dict()
        assert data["skill_points"] == 7

    def test_sp_restored_through_load(self):
        xp = XPSystem()
        xp.load({"xp": 0, "level": 3, "skill_points": 4})
        assert xp.skill_points == 4

    def test_sp_load_defaults_to_zero(self):
        xp = XPSystem()
        xp.load({"xp": 0, "level": 3})
        assert xp.skill_points == 0


# ---------------------------------------------------------------------------
# TestSaveManagerIntegration -- save/load with SaveManager
# ---------------------------------------------------------------------------

class TestSaveManagerIntegration:
    def test_save_and_load_with_skill_tree(self, skill_path, tmp_path):
        from src.save.save_manager import SaveManager
        from src.progression.home_base import HomeBase

        save_path = tmp_path / "saves" / "test_save.json"
        manager = SaveManager(save_path)

        xp = XPSystem()
        xp.skill_points = 10

        st = SkillTree()
        st.load(skill_path)
        st.unlock("combat_1", xp)
        st.unlock("combat_2", xp)

        currency = Currency(500)

        # Use a dict-based save
        state = {
            "version": 1,
            "player": {
                "level": xp.level,
                "xp": xp.xp,
                "money": currency.balance,
                "skill_points": xp.skill_points,
            },
            "inventory": [],
            "skill_tree": st.to_save_dict(),
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        }
        manager.save(state)

        loaded = manager.load()
        assert "combat_1" in loaded["skill_tree"]["unlocked"]
        assert "combat_2" in loaded["skill_tree"]["unlocked"]
        assert loaded["player"]["skill_points"] == xp.skill_points

    def test_save_manager_kwarg_with_skill_tree(self, skill_path, tmp_path):
        """Test the keyword-argument save path with skill_tree."""
        from src.save.save_manager import SaveManager
        from src.progression.home_base import HomeBase

        # Create a minimal home_base.json
        hb_data = {
            "facilities": [{
                "id": "armory", "name": "ARMORY", "description": "",
                "max_level": 1,
                "levels": [{"cost": 100, "bonus_type": "loot_value_bonus",
                             "bonus_value": 0.1, "description": "+10%"}],
            }]
        }
        hb_path = tmp_path / "home_base.json"
        hb_path.write_text(json.dumps(hb_data))

        save_path = tmp_path / "saves" / "test_save.json"
        manager = SaveManager(save_path)

        hb = HomeBase(str(hb_path))
        xp = XPSystem()
        xp.skill_points = 10

        st = SkillTree()
        st.load(skill_path)
        st.unlock("mobility_1", xp)

        currency = Currency(500)

        manager.save(home_base=hb, currency=currency, xp_system=xp, skill_tree=st)

        loaded = manager.load()
        assert "mobility_1" in loaded["skill_tree"]["unlocked"]

    def test_skill_points_persisted_and_restored(self, tmp_path):
        """skill_points survive a full save/restore cycle via SaveManager."""
        from src.save.save_manager import SaveManager

        save_path = tmp_path / "saves" / "sp_test.json"
        manager   = SaveManager(save_path)

        xp = XPSystem()
        xp.skill_points = 5
        xp.level = 6

        manager.save(xp_system=xp)

        xp2 = XPSystem()
        manager.restore(xp_system=xp2)
        assert xp2.skill_points == 5
        assert xp2.level == 6

    def test_old_save_migrates_skill_points(self, tmp_path):
        """Saves without skill_points get a derived default on load."""
        from src.save.save_manager import SaveManager
        import json as _json

        save_path = tmp_path / "saves" / "old.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        old_state = {
            "version": 1,
            "player": {"level": 4, "xp": 0, "money": 0},
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        }
        save_path.write_text(_json.dumps(old_state))

        manager = SaveManager(save_path)
        loaded  = manager.load()
        # Derived default: level 4 → 3 unspent SP (level - 1)
        assert loaded["player"]["skill_points"] == 3


# ---------------------------------------------------------------------------
# TestApplySkillTreeBonuses -- GameScene integration
# ---------------------------------------------------------------------------

class TestApplySkillTreeBonuses:
    """Test that GameScene._apply_skill_tree_bonuses correctly applies bonuses."""

    class _StubPlayer:
        def __init__(self, health=100):
            self.health     = health
            self.max_health = health
            self.armor      = 0
            self.max_armor  = 100
            self.walk_speed = 180.0
            self.damage_mult = 1.0

    def _apply(self, player, skill_tree):
        from src.scenes.game_scene import GameScene
        scene = types.SimpleNamespace(loot_value_bonus=0.0)
        GameScene._apply_skill_tree_bonuses(scene, player, skill_tree)

    def test_none_skill_tree_is_noop(self):
        player = self._StubPlayer()
        self._apply(player, None)
        assert player.health == 100

    def test_empty_skill_tree_no_bonuses(self, tree):
        player = self._StubPlayer()
        self._apply(player, tree)
        assert player.health == 100
        assert player.armor == 0

    def test_combat_1_adds_damage_mult(self, tree):
        tree.unlock("combat_1")
        player = self._StubPlayer()
        self._apply(player, tree)
        assert abs(player.damage_mult - 1.10) < 1e-9

    def test_combat_2_adds_armor(self, tree):
        tree.unlock("combat_1")
        tree.unlock("combat_2")
        player = self._StubPlayer()
        self._apply(player, tree)
        assert player.armor == 15

    def test_mobility_1_adds_speed(self, tree):
        tree.unlock("mobility_1")
        player = self._StubPlayer()
        self._apply(player, tree)
        expected = 180.0 * 1.10
        assert abs(player.walk_speed - expected) < 1e-6

    def test_mobility_2_adds_hp(self, tree):
        tree.unlock("mobility_1")
        tree.unlock("mobility_2")
        player = self._StubPlayer()
        self._apply(player, tree)
        assert player.health == 115
        assert player.max_health == 115

    def test_full_combat_branch(self, tree):
        tree.unlock("combat_1")
        tree.unlock("combat_2")
        tree.unlock("combat_3")
        player = self._StubPlayer()
        self._apply(player, tree)
        # damage_mult: 1.0 + 0.10 + 0.20 = 1.30
        assert abs(player.damage_mult - 1.30) < 1e-9
        # armor: 15
        assert player.armor == 15

    def test_full_mobility_branch(self, tree):
        tree.unlock("mobility_1")
        tree.unlock("mobility_2")
        tree.unlock("mobility_3")
        player = self._StubPlayer()
        self._apply(player, tree)
        # speed_mult: 0.10 + 0.20 = 0.30 => 180 * 1.30 = 234
        expected_speed = 180.0 * 1.30
        assert abs(player.walk_speed - expected_speed) < 1e-6
        # extra_hp: 15
        assert player.health == 115
        assert player.max_health == 115

    def test_all_branches_combined(self, tree):
        for nid in tree.node_ids:
            tree.unlock(nid)
        player = self._StubPlayer()
        self._apply(player, tree)
        assert abs(player.damage_mult - 1.30) < 1e-9
        assert player.armor == 15
        assert player.health == 115
        assert player.max_health == 115
        expected_speed = 180.0 * 1.30
        assert abs(player.walk_speed - expected_speed) < 1e-6


# ---------------------------------------------------------------------------
# TestDataFile -- verify the shipped data/skill_tree.json
# ---------------------------------------------------------------------------

class TestDataFile:
    """Verify the actual data/skill_tree.json file loads correctly."""

    def test_load_shipped_data(self):
        import os
        root      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(root, "data", "skill_tree.json")
        st = SkillTree()
        st.load(data_path)
        assert len(st.branches) == 2
        assert len(st.node_ids) == 8  # 4 combat + 4 mobility

    def test_shipped_data_has_combat_branch(self):
        import os
        root      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(root, "data", "skill_tree.json")
        st = SkillTree()
        st.load(data_path)
        combat = st.get_branch_nodes("combat")
        assert len(combat) == 4

    def test_shipped_data_has_mobility_branch(self):
        import os
        root      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(root, "data", "skill_tree.json")
        st = SkillTree()
        st.load(data_path)
        mobility = st.get_branch_nodes("mobility")
        assert len(mobility) == 4

    def test_shipped_data_prerequisite_chain_valid(self):
        import os
        root      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(root, "data", "skill_tree.json")
        st = SkillTree()
        st.load(data_path)
        # All prerequisites should reference existing nodes
        for nid in st.node_ids:
            node = st.get_node(nid)
            for req in node.get("requires", []):
                assert st.get_node(req) is not None, (
                    f"Node {nid} requires {req} which does not exist"
                )

    def test_shipped_data_has_cost_sp(self):
        """Every node in the shipped data must have a cost_sp field."""
        import os
        root      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(root, "data", "skill_tree.json")
        st = SkillTree()
        st.load(data_path)
        for nid in st.node_ids:
            node = st.get_node(nid)
            assert "cost_sp" in node, f"Node {nid} missing 'cost_sp'"
            assert node["cost_sp"] >= 1


# ---------------------------------------------------------------------------
# TestSkillUnlockedEvent -- event_bus integration
# ---------------------------------------------------------------------------

class _TrackingBus:
    """Minimal tracking bus for event-emission assertions."""

    def __init__(self):
        self.emitted: list[tuple[str, dict]] = []

    def emit(self, event: str, **kwargs) -> None:
        self.emitted.append((event, kwargs))

    def all_events(self, name: str) -> list[dict]:
        return [payload for ename, payload in self.emitted if ename == name]


class TestSkillUnlockedEvent:
    """SkillTree.unlock() emits 'skill_unlocked' through the optional event_bus."""

    def test_unlock_emits_skill_unlocked_event(self, tree):
        bus = _TrackingBus()
        st = SkillTree(event_bus=bus)
        st._nodes = tree._nodes          # share the loaded node definitions
        st._branches = tree._branches
        st.unlock("combat_1")
        events = bus.all_events("skill_unlocked")
        assert len(events) == 1

    def test_skill_unlocked_event_carries_node_id(self, tree):
        bus = _TrackingBus()
        st = SkillTree(event_bus=bus)
        st._nodes = tree._nodes
        st._branches = tree._branches
        st.unlock("combat_1")
        event = bus.all_events("skill_unlocked")[0]
        assert event["node_id"] == "combat_1"

    def test_no_event_without_event_bus(self, tree):
        """SkillTree without event_bus should unlock silently."""
        st = SkillTree()                 # no bus
        st._nodes = tree._nodes
        st._branches = tree._branches
        result = st.unlock("combat_1")
        assert result is True            # unlock still succeeds

    def test_failed_unlock_does_not_emit_event(self, tree):
        """A failed unlock (prereq not met) must not emit any event."""
        bus = _TrackingBus()
        st = SkillTree(event_bus=bus)
        st._nodes = tree._nodes
        st._branches = tree._branches
        result = st.unlock("combat_2")   # combat_1 not yet unlocked
        assert result is False
        assert bus.all_events("skill_unlocked") == []

    def test_event_bus_is_none_by_default(self):
        st = SkillTree()
        assert st._event_bus is None
