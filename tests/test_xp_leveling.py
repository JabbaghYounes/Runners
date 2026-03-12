"""Tests for XP gain, leveling, level-up notification, extraction XP,
enemy-kill XP, level-gated skill tree, and save/load persistence.

Covers the feature spec:
  - XP awarded for each enemy kill (configurable amount per enemy type)
  - XP awarded for successful extraction
  - XP bar and current level visible on HUD (via HUDState fields)
  - Reaching XP threshold increases player level and notifies the player
  - Level is persisted in save data across rounds
  - Skill tree nodes can require a minimum player level
"""
import json
import pytest

from src.progression.xp_system import XPSystem
from src.progression.skill_tree import SkillTree
from src.constants import EXTRACTION_XP, PVP_KILL_XP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TrackingBus:
    """Minimal event bus that records emitted events for assertions."""

    def __init__(self):
        from collections import defaultdict
        self._handlers = defaultdict(list)
        self.emitted = []

    def subscribe(self, event, callback):
        if callback not in self._handlers[event]:
            self._handlers[event].append(callback)

    def unsubscribe(self, event, callback):
        try:
            self._handlers[event].remove(callback)
        except ValueError:
            pass

    def emit(self, event, **kwargs):
        self.emitted.append((event, kwargs))
        for cb in list(self._handlers[event]):
            cb(**kwargs)

    def publish(self, event, **kwargs):
        self.emit(event, **kwargs)

    def clear(self, event=None):
        if event is None:
            self._handlers.clear()
        else:
            self._handlers.pop(event, None)

    def all_events(self, name):
        return [payload for ename, payload in self.emitted if ename == name]


@pytest.fixture
def bus():
    return _TrackingBus()


@pytest.fixture
def xp_system(bus):
    return XPSystem(event_bus=bus)


# ===========================================================================
# XPSystem — basic award and leveling
# ===========================================================================

class TestXPSystemBasics:
    def test_initial_state(self, xp_system):
        assert xp_system.xp == 0
        assert xp_system.level == 1

    def test_award_adds_xp(self, xp_system):
        xp_system.award(100)
        assert xp_system.xp == 100

    def test_award_accumulates(self, xp_system):
        xp_system.award(100)
        xp_system.award(200)
        assert xp_system.xp == 300

    def test_xp_to_next_level_at_level_1(self, xp_system):
        # BASE_XP=900, SCALE=1.4, level=1: 900 * 1.4^0 = 900
        assert xp_system.xp_to_next_level() == 900

    def test_level_up_when_xp_reaches_threshold(self, xp_system):
        xp_system.award(900)
        assert xp_system.level == 2
        assert xp_system.xp == 0  # remainder after leveling

    def test_level_up_with_excess_xp(self, xp_system):
        xp_system.award(950)
        assert xp_system.level == 2
        assert xp_system.xp == 50

    def test_multiple_level_ups_in_one_award(self, xp_system):
        # Level 1 requires 900, level 2 requires 1260 (900*1.4)
        xp_system.award(900 + 1260)
        assert xp_system.level == 3

    def test_pending_xp_tracks_uncommitted(self, xp_system):
        xp_system.award(200)
        assert xp_system._pending_xp == 200

    def test_commit_clears_pending_xp(self, xp_system):
        xp_system.award(200)
        xp_system.commit()
        assert xp_system._pending_xp == 0
        assert xp_system.xp == 200  # actual XP not affected


# ===========================================================================
# XPSystem — enemy kill XP via event bus
# ===========================================================================

class TestEnemyKillXP:
    def test_enemy_killed_event_awards_xp(self, xp_system, bus):
        bus.emit("enemy_killed", xp_reward=50, enemy=None, x=0, y=0, loot_table=[])
        assert xp_system.xp == 50

    def test_enemy_killed_different_xp_rewards(self, xp_system, bus):
        # Grunt: 25 XP
        bus.emit("enemy_killed", xp_reward=25, enemy=None, x=0, y=0, loot_table=[])
        # Heavy: 60 XP
        bus.emit("enemy_killed", xp_reward=60, enemy=None, x=0, y=0, loot_table=[])
        assert xp_system.xp == 85

    def test_enemy_killed_with_zero_xp_does_not_award(self, xp_system, bus):
        bus.emit("enemy_killed", xp_reward=0, enemy=None, x=0, y=0, loot_table=[])
        assert xp_system.xp == 0

    def test_enemy_killed_without_xp_reward_key(self, xp_system, bus):
        bus.emit("enemy_killed", enemy=None, x=0, y=0, loot_table=[])
        assert xp_system.xp == 0

    def test_enemy_killed_triggers_level_up(self, xp_system, bus):
        bus.emit("enemy_killed", xp_reward=900, enemy=None, x=0, y=0, loot_table=[])
        assert xp_system.level == 2

    def test_enemy_killed_level_up_emits_event(self, xp_system, bus):
        bus.emit("enemy_killed", xp_reward=900, enemy=None, x=0, y=0, loot_table=[])
        level_up_events = bus.all_events("level_up")
        assert len(level_up_events) >= 1
        assert level_up_events[0]["level"] == 2

    def test_configurable_xp_per_enemy_type(self, xp_system, bus):
        """Different enemy types award different XP amounts."""
        enemy_xp = {"grunt": 25, "heavy": 60, "sniper": 40}
        for etype, xp in enemy_xp.items():
            bus.emit("enemy_killed", xp_reward=xp, enemy=None, x=0, y=0, loot_table=[])
        assert xp_system.xp == sum(enemy_xp.values())


# ===========================================================================
# XPSystem — extraction XP via event bus
# ===========================================================================

class TestExtractionXP:
    def test_extraction_success_awards_xp(self, xp_system, bus):
        bus.emit("extraction_success", player=None)
        assert xp_system.xp == EXTRACTION_XP

    def test_extraction_xp_constant_is_positive(self):
        assert EXTRACTION_XP > 0

    def test_extraction_xp_added_to_existing(self, xp_system, bus):
        xp_system.award(100)
        bus.emit("extraction_success", player=None)
        assert xp_system.xp == 100 + EXTRACTION_XP

    def test_extraction_can_cause_level_up(self, bus):
        xp = XPSystem(event_bus=bus)
        # Fill up to just under the threshold
        xp.award(900 - EXTRACTION_XP)
        bus.emit("extraction_success", player=None)
        assert xp.level == 2


# ===========================================================================
# XPSystem — level-up notification
# ===========================================================================

class TestLevelUpNotification:
    def test_level_up_emits_level_up_event(self, xp_system, bus):
        xp_system.award(900)
        events = bus.all_events("level_up")
        assert len(events) == 1
        assert events[0]["level"] == 2

    def test_level_up_emits_level_dot_up_event(self, xp_system, bus):
        xp_system.award(900)
        events = bus.all_events("level.up")
        assert len(events) == 1
        assert events[0]["level"] == 2

    def test_no_level_up_event_when_xp_below_threshold(self, xp_system, bus):
        xp_system.award(100)
        events = bus.all_events("level_up")
        assert len(events) == 0

    def test_multiple_level_ups_emit_once_per_award(self, xp_system, bus):
        """A single award that crosses multiple levels emits one event
        with the final level."""
        xp_system.award(900 + 1260)  # crosses level 1 and 2 thresholds
        events = bus.all_events("level_up")
        assert len(events) == 1
        assert events[0]["level"] == 3

    def test_no_event_without_event_bus(self):
        """XPSystem without event_bus should not raise on level-up."""
        xp = XPSystem()
        xp.award(900)
        assert xp.level == 2


# ===========================================================================
# XPSystem — save / load persistence
# ===========================================================================

class TestXPPersistence:
    def test_to_save_dict_contains_xp_and_level(self, xp_system):
        xp_system.award(100)
        data = xp_system.to_save_dict()
        assert "xp" in data
        assert "level" in data
        assert data["xp"] == 100
        assert data["level"] == 1

    def test_load_restores_xp_and_level(self):
        xp = XPSystem()
        xp.load({"xp": 450, "level": 3})
        assert xp.xp == 450
        assert xp.level == 3

    def test_save_load_round_trip(self, xp_system):
        xp_system.award(500)
        data = xp_system.to_save_dict()

        restored = XPSystem()
        restored.load(data)
        assert restored.xp == xp_system.xp
        assert restored.level == xp_system.level

    def test_load_missing_keys_uses_defaults(self):
        xp = XPSystem()
        xp.load({})
        assert xp.xp == 0
        assert xp.level == 1

    def test_save_manager_round_trip(self, tmp_path):
        """Full SaveManager round-trip preserves XP and level."""
        from src.save.save_manager import SaveManager
        from src.progression.currency import Currency
        from src.progression.home_base import HomeBase

        save_path = tmp_path / "saves" / "test.json"
        mgr = SaveManager(save_path)

        xp = XPSystem()
        xp.award(500)
        currency = Currency(1000)
        hb = HomeBase()

        mgr.save(home_base=hb, currency=currency, xp_system=xp)
        loaded = mgr.load()

        assert loaded["player"]["xp"] == xp.xp
        assert loaded["player"]["level"] == xp.level


# ===========================================================================
# XPSystem — HUD state integration
# ===========================================================================

class TestHUDStateIntegration:
    def test_hud_state_carries_xp_fields(self):
        """HUDState must have level, xp, and xp_to_next fields."""
        from src.ui.hud_state import HUDState

        state = HUDState()
        assert hasattr(state, "level")
        assert hasattr(state, "xp")
        assert hasattr(state, "xp_to_next")

    def test_hud_state_defaults(self):
        from src.ui.hud_state import HUDState

        state = HUDState()
        assert state.level == 1
        assert state.xp == 0.0
        assert state.xp_to_next == 100.0

    def test_hud_state_reflects_xp_system_values(self):
        from src.ui.hud_state import HUDState

        xp = XPSystem()
        xp.award(300)

        state = HUDState(
            level=xp.level,
            xp=xp.xp,
            xp_to_next=xp.xp_to_next_level(),
        )
        assert state.level == 1
        assert state.xp == 300
        assert state.xp_to_next == 900


# ===========================================================================
# XPSystem — event bus subscription
# ===========================================================================

class TestEventBusSubscriptions:
    def test_subscribes_to_enemy_killed(self, bus):
        xp = XPSystem(event_bus=bus)
        assert any(cb == xp._on_enemy_killed for cb in bus._handlers.get("enemy_killed", []))

    def test_subscribes_to_extraction_success(self, bus):
        xp = XPSystem(event_bus=bus)
        assert any(cb == xp._on_extraction_success for cb in bus._handlers.get("extraction_success", []))

    def test_subscribes_to_player_killed(self, bus):
        xp = XPSystem(event_bus=bus)
        assert any(cb == xp._on_player_killed for cb in bus._handlers.get("player_killed", []))

    def test_no_subscriptions_without_event_bus(self):
        xp = XPSystem()
        assert xp._event_bus is None


# ===========================================================================
# SkillTree — level-gated progression
# ===========================================================================

class TestSkillTreeLevelGating:
    @pytest.fixture
    def skill_tree(self, tmp_path):
        tree_data = {
            "nodes": [
                {
                    "id": "sprint_boost",
                    "branch": "movement",
                    "requires": [],
                    "required_level": 0,
                    "stat_bonus": {"sprint_speed": 0.1},
                },
                {
                    "id": "double_jump",
                    "branch": "movement",
                    "requires": ["sprint_boost"],
                    "required_level": 3,
                    "stat_bonus": {"jump_count": 1},
                },
                {
                    "id": "armor_up",
                    "branch": "defense",
                    "requires": [],
                    "required_level": 5,
                    "stat_bonus": {"armor": 10},
                },
                {
                    "id": "basic_node",
                    "branch": "combat",
                    "requires": [],
                    "stat_bonus": {"damage": 0.05},
                },
            ]
        }
        path = tmp_path / "skill_tree.json"
        path.write_text(json.dumps(tree_data))
        tree = SkillTree()
        tree.load(str(path))
        return tree

    def test_can_unlock_no_level_requirement(self, skill_tree):
        """Node with required_level=0 can be unlocked at any level."""
        assert skill_tree.can_unlock("sprint_boost", player_level=1)

    def test_can_unlock_node_without_required_level_key(self, skill_tree):
        """Nodes without required_level field default to 0 (no restriction)."""
        assert skill_tree.can_unlock("basic_node", player_level=1)

    def test_cannot_unlock_level_gated_node_below_level(self, skill_tree):
        """Node requiring level 5 cannot be unlocked at level 3."""
        assert not skill_tree.can_unlock("armor_up", player_level=3)

    def test_can_unlock_level_gated_node_at_exact_level(self, skill_tree):
        """Node requiring level 5 can be unlocked at exactly level 5."""
        assert skill_tree.can_unlock("armor_up", player_level=5)

    def test_can_unlock_level_gated_node_above_level(self, skill_tree):
        """Node requiring level 5 can be unlocked at level 10."""
        assert skill_tree.can_unlock("armor_up", player_level=10)

    def test_prerequisite_and_level_both_required(self, skill_tree):
        """double_jump requires sprint_boost AND level 3."""
        # Missing prerequisite, sufficient level
        assert not skill_tree.can_unlock("double_jump", player_level=5)

        # Unlock prerequisite
        skill_tree.unlock("sprint_boost", player_level=1)

        # Has prerequisite but insufficient level
        assert not skill_tree.can_unlock("double_jump", player_level=2)

        # Has prerequisite AND sufficient level
        assert skill_tree.can_unlock("double_jump", player_level=3)

    def test_unlock_respects_level_gate(self, skill_tree):
        """unlock() returns False when level is insufficient."""
        assert not skill_tree.unlock("armor_up", player_level=2)
        assert "armor_up" not in skill_tree._unlocked

    def test_unlock_succeeds_when_level_met(self, skill_tree):
        """unlock() returns True and adds node when level is sufficient."""
        assert skill_tree.unlock("armor_up", player_level=5)
        assert "armor_up" in skill_tree._unlocked

    def test_backward_compatible_can_unlock_no_level_arg(self, skill_tree):
        """can_unlock without player_level arg defaults to 0, which passes
        for nodes without required_level."""
        assert skill_tree.can_unlock("sprint_boost")
        assert skill_tree.can_unlock("basic_node")

    def test_backward_compatible_cannot_unlock_gated_without_level(self, skill_tree):
        """Calling can_unlock without player_level defaults to 0,
        so level-gated nodes are blocked."""
        assert not skill_tree.can_unlock("armor_up")

    def test_stat_bonuses_after_unlock(self, skill_tree):
        skill_tree.unlock("sprint_boost", player_level=1)
        bonuses = skill_tree.get_stat_bonuses()
        assert bonuses["sprint_speed"] == pytest.approx(0.1)

    def test_save_load_preserves_unlocked(self, skill_tree):
        skill_tree.unlock("sprint_boost", player_level=1)
        data = skill_tree.to_save_dict()

        tree2 = SkillTree()
        # tree2 doesn't have nodes loaded, so just check state restore
        tree2.load_state(data)
        assert "sprint_boost" in tree2._unlocked
