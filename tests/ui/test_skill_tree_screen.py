# Run: pytest tests/ui/test_skill_tree_screen.py
"""Unit and integration tests for SkillTreeScreen widget and _format_bonus helper.

Tests cover:
- _format_bonus(): every key category and the generic fallback
- SkillTreeScreen init: attribute setup
- _node_state(): UNLOCKED / AVAILABLE / LOCKED state transitions
- handle_event(): mouse hover tracking and click-to-unlock flow
- render(): card_rect population, idempotency, and crash-safety
"""
from __future__ import annotations

import json
import types

import pytest
import pygame

from src.ui.skill_tree_screen import SkillTreeScreen, _format_bonus
from src.progression.skill_tree import SkillTree
from src.progression.xp_system import XPSystem


# ---------------------------------------------------------------------------
# Session-scoped pygame init — headless, no display window required
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def pygame_headless():
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.quit()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def skill_data() -> dict:
    """Minimal two-branch, three-node tree: combat chain + one mobility root."""
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
                "id": "mobility_1",
                "name": "Light Feet",
                "branch": "mobility",
                "description": "+10% movement speed",
                "cost_sp": 1,
                "requires": [],
                "stat_bonus": {"speed_mult": 0.10},
            },
        ],
    }


@pytest.fixture
def tree(skill_data, tmp_path) -> SkillTree:
    """SkillTree loaded from the test fixture data."""
    p = tmp_path / "skill_tree.json"
    p.write_text(json.dumps(skill_data))
    st = SkillTree()
    st.load(str(p))
    return st


@pytest.fixture
def xp_rich() -> XPSystem:
    """XPSystem with 10 skill points — enough to unlock any chain."""
    xp = XPSystem()
    xp.skill_points = 10
    return xp


@pytest.fixture
def xp_broke() -> XPSystem:
    """XPSystem with 0 skill points — cannot unlock anything."""
    return XPSystem()


@pytest.fixture
def widget(tree, xp_rich) -> SkillTreeScreen:
    """Default widget: rich XP system, nothing unlocked yet."""
    return SkillTreeScreen(tree, xp_rich)


@pytest.fixture
def surface() -> pygame.Surface:
    """800×600 offscreen surface for render tests."""
    return pygame.Surface((800, 600))


@pytest.fixture
def area() -> pygame.Rect:
    """Content area rect passed to render() and handle_event()."""
    return pygame.Rect(10, 10, 780, 580)


# ---------------------------------------------------------------------------
# Helpers for fabricating synthetic events without the pygame event queue
# ---------------------------------------------------------------------------

def _motion(pos) -> types.SimpleNamespace:
    """Synthesise a MOUSEMOTION event."""
    return types.SimpleNamespace(type=pygame.MOUSEMOTION, pos=pos)


def _click(pos, button: int = 1) -> types.SimpleNamespace:
    """Synthesise a MOUSEBUTTONDOWN event."""
    return types.SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def _keydown() -> types.SimpleNamespace:
    """Synthesise an irrelevant KEYDOWN event."""
    return types.SimpleNamespace(type=pygame.KEYDOWN)


# ---------------------------------------------------------------------------
# TestFormatBonus — pure-function unit tests
# ---------------------------------------------------------------------------

class TestFormatBonus:
    """_format_bonus() converts stat_bonus key/value pairs to human-readable strings."""

    # ── Named percentage keys ────────────────────────────────────────────────

    def test_damage_mult_formats_as_percentage(self):
        assert _format_bonus("damage_mult", 0.10) == "+10% weapon damage"

    def test_damage_mult_zero_percent(self):
        assert _format_bonus("damage_mult", 0.0) == "+0% weapon damage"

    def test_damage_mult_large_value(self):
        assert _format_bonus("damage_mult", 0.25) == "+25% weapon damage"

    def test_speed_mult_formats_as_percentage(self):
        assert _format_bonus("speed_mult", 0.15) == "+15% move speed"

    def test_crit_chance_formats_as_percentage(self):
        assert _format_bonus("crit_chance", 0.10) == "+10% crit chance"

    def test_dodge_chance_formats_as_percentage(self):
        assert _format_bonus("dodge_chance", 0.05) == "+5% dodge chance"

    # ── Named flat keys ──────────────────────────────────────────────────────

    def test_extra_hp_formats_as_flat(self):
        assert _format_bonus("extra_hp", 15) == "+15 max HP"

    def test_extra_armor_formats_as_flat(self):
        assert _format_bonus("extra_armor", 10) == "+10 starting armor"

    def test_extra_hp_truncates_float_value(self):
        # int(15.9) == 15
        assert _format_bonus("extra_hp", 15.9) == "+15 max HP"

    # ── Generic fallback keys ────────────────────────────────────────────────

    def test_unknown_float_below_one_uses_pct_fallback(self):
        result = _format_bonus("sprint_speed", 0.20)
        assert result == "+20% sprint speed"

    def test_unknown_int_uses_flat_fallback(self):
        result = _format_bonus("jump_count", 1)
        assert result == "+1 jump count"

    def test_unknown_float_above_one_uses_flat_fallback(self):
        result = _format_bonus("armor_regen", 1.5)
        assert result == "+1.5 armor regen"

    def test_underscore_in_key_replaced_by_space(self):
        result = _format_bonus("special_power", 0.10)
        assert "special power" in result

    def test_returns_string(self):
        assert isinstance(_format_bonus("damage_mult", 0.10), str)


# ---------------------------------------------------------------------------
# TestInit — SkillTreeScreen initialisation
# ---------------------------------------------------------------------------

class TestInit:
    """Constructor stores references and initialises clean state."""

    def test_stores_skill_tree_reference(self, tree, xp_rich):
        w = SkillTreeScreen(tree, xp_rich)
        assert w._skill_tree is tree

    def test_stores_xp_system_reference(self, tree, xp_rich):
        w = SkillTreeScreen(tree, xp_rich)
        assert w._xp_system is xp_rich

    def test_card_rects_starts_empty(self, tree, xp_rich):
        w = SkillTreeScreen(tree, xp_rich)
        assert w._card_rects == {}

    def test_hovered_node_starts_as_none(self, tree, xp_rich):
        w = SkillTreeScreen(tree, xp_rich)
        assert w._hovered_node_id is None


# ---------------------------------------------------------------------------
# TestNodeState — _node_state() private helper
# ---------------------------------------------------------------------------

class TestNodeState:
    """_node_state() returns the correct sentinel for each node situation."""

    def test_unlocked_node_returns_unlocked(self, widget, tree):
        tree.unlock("combat_1")
        assert widget._node_state("combat_1") == "unlocked"

    def test_available_root_node_returns_available(self, widget):
        # combat_1: no prerequisites, xp_rich has 10 SP → available
        assert widget._node_state("combat_1") == "available"

    def test_locked_child_without_parent_returns_locked(self, widget):
        # combat_2 requires combat_1 which is not yet unlocked
        assert widget._node_state("combat_2") == "locked"

    def test_available_child_after_parent_unlocked(self, widget, tree):
        tree.unlock("combat_1")
        assert widget._node_state("combat_2") == "available"

    def test_locked_when_sp_is_zero(self, tree, xp_broke):
        w = SkillTreeScreen(tree, xp_broke)
        # combat_1 has no prerequisites, but SP == 0 → locked
        assert w._node_state("combat_1") == "locked"

    def test_already_unlocked_node_stays_unlocked_state(self, widget, tree):
        tree.unlock("combat_1")
        tree.unlock("combat_2")
        assert widget._node_state("combat_1") == "unlocked"
        assert widget._node_state("combat_2") == "unlocked"


# ---------------------------------------------------------------------------
# TestHandleEvent — mouse interaction
# ---------------------------------------------------------------------------

class TestHandleEvent:
    """handle_event() correctly routes MOUSEMOTION (hover) and MOUSEBUTTONDOWN
    (click-to-unlock) events, returning True only when a card was hit."""

    def _place_card(self, widget, node_id: str, rect_tuple) -> None:
        """Inject a card rect directly, bypassing render()."""
        widget._card_rects[node_id] = pygame.Rect(rect_tuple)

    # ── MOUSEMOTION ──────────────────────────────────────────────────────────

    def test_mousemotion_over_card_sets_hovered_node(self, widget, area):
        self._place_card(widget, "combat_1", (100, 100, 200, 90))
        widget.handle_event(_motion((150, 130)), area)
        assert widget._hovered_node_id == "combat_1"

    def test_mousemotion_off_all_cards_clears_hover(self, widget, area):
        self._place_card(widget, "combat_1", (100, 100, 200, 90))
        widget._hovered_node_id = "combat_1"
        widget.handle_event(_motion((500, 500)), area)
        assert widget._hovered_node_id is None

    def test_mousemotion_returns_false(self, widget, area):
        self._place_card(widget, "combat_1", (100, 100, 200, 90))
        result = widget.handle_event(_motion((150, 130)), area)
        assert result is False

    def test_mousemotion_selects_correct_card_when_multiple_present(self, widget, area):
        self._place_card(widget, "combat_1",   (100, 100, 200, 90))
        self._place_card(widget, "mobility_1", (400, 100, 200, 90))
        widget.handle_event(_motion((450, 130)), area)
        assert widget._hovered_node_id == "mobility_1"

    # ── MOUSEBUTTONDOWN: left click ──────────────────────────────────────────

    def test_left_click_available_card_unlocks_node(self, widget, tree, area):
        self._place_card(widget, "combat_1", (100, 100, 200, 90))
        widget.handle_event(_click((150, 130)), area)
        assert tree.is_unlocked("combat_1")

    def test_left_click_available_card_returns_true(self, widget, area):
        self._place_card(widget, "combat_1", (100, 100, 200, 90))
        result = widget.handle_event(_click((150, 130)), area)
        assert result is True

    def test_left_click_locked_card_does_not_unlock(self, widget, tree, area):
        # combat_2 requires combat_1 → locked
        self._place_card(widget, "combat_2", (100, 100, 200, 90))
        widget.handle_event(_click((150, 130)), area)
        assert not tree.is_unlocked("combat_2")

    def test_left_click_locked_card_returns_true(self, widget, area):
        self._place_card(widget, "combat_2", (100, 100, 200, 90))
        result = widget.handle_event(_click((150, 130)), area)
        assert result is True

    def test_left_click_already_unlocked_card_returns_true(self, widget, tree, area):
        tree.unlock("combat_1")
        self._place_card(widget, "combat_1", (100, 100, 200, 90))
        result = widget.handle_event(_click((150, 130)), area)
        assert result is True

    def test_left_click_deducts_sp_on_successful_unlock(self, widget, xp_rich, area):
        initial_sp = xp_rich.skill_points
        self._place_card(widget, "combat_1", (100, 100, 200, 90))
        widget.handle_event(_click((150, 130)), area)
        assert xp_rich.skill_points == initial_sp - 1

    def test_left_click_when_broke_does_not_unlock(self, tree, xp_broke, area):
        w = SkillTreeScreen(tree, xp_broke)
        w._card_rects["combat_1"] = pygame.Rect(100, 100, 200, 90)
        w.handle_event(_click((150, 130)), area)
        assert not tree.is_unlocked("combat_1")

    # ── MOUSEBUTTONDOWN: other buttons ───────────────────────────────────────

    def test_right_click_on_card_returns_false(self, widget, area):
        self._place_card(widget, "combat_1", (100, 100, 200, 90))
        result = widget.handle_event(_click((150, 130), button=3), area)
        assert result is False

    def test_right_click_does_not_unlock(self, widget, tree, area):
        self._place_card(widget, "combat_1", (100, 100, 200, 90))
        widget.handle_event(_click((150, 130), button=3), area)
        assert not tree.is_unlocked("combat_1")

    # ── Miss (click outside all cards) ──────────────────────────────────────

    def test_click_outside_all_cards_returns_false(self, widget, area):
        self._place_card(widget, "combat_1", (100, 100, 200, 90))
        result = widget.handle_event(_click((600, 500)), area)
        assert result is False

    # ── Irrelevant events ────────────────────────────────────────────────────

    def test_irrelevant_event_type_returns_false(self, widget, area):
        result = widget.handle_event(_keydown(), area)
        assert result is False


# ---------------------------------------------------------------------------
# TestRender — render() smoke tests and card_rect population
# ---------------------------------------------------------------------------

class TestRender:
    """render() must populate _card_rects and must not raise under any
    normal operating condition."""

    def test_render_populates_card_rects_for_all_nodes(self, widget, surface, area):
        widget.render(surface, area)
        assert len(widget._card_rects) == 3  # combat_1, combat_2, mobility_1

    def test_render_card_rects_contains_combat_1(self, widget, surface, area):
        widget.render(surface, area)
        assert "combat_1" in widget._card_rects

    def test_render_card_rects_contains_combat_2(self, widget, surface, area):
        widget.render(surface, area)
        assert "combat_2" in widget._card_rects

    def test_render_card_rects_contains_mobility_1(self, widget, surface, area):
        widget.render(surface, area)
        assert "mobility_1" in widget._card_rects

    def test_render_clears_stale_card_rects_from_previous_call(
        self, widget, surface, area
    ):
        widget._card_rects["stale_node"] = pygame.Rect(0, 0, 1, 1)
        widget.render(surface, area)
        assert "stale_node" not in widget._card_rects

    def test_render_does_not_crash_with_no_hover(self, widget, surface, area):
        widget._hovered_node_id = None
        widget.render(surface, area)  # must not raise

    def test_render_does_not_crash_with_unlocked_nodes(
        self, widget, tree, surface, area
    ):
        tree.unlock("combat_1")
        widget.render(surface, area)  # must not raise

    def test_render_empty_branches_produces_no_card_rects(
        self, tmp_path, xp_rich, surface, area
    ):
        empty_data = {"branches": [], "nodes": []}
        p = tmp_path / "empty.json"
        p.write_text(json.dumps(empty_data))
        st = SkillTree()
        st.load(str(p))
        w = SkillTreeScreen(st, xp_rich)
        w.render(surface, area)
        assert w._card_rects == {}

    def test_render_card_rects_are_pygame_rects(self, widget, surface, area):
        widget.render(surface, area)
        for rect in widget._card_rects.values():
            assert isinstance(rect, pygame.Rect)

    def test_render_second_call_produces_same_node_count(
        self, widget, surface, area
    ):
        widget.render(surface, area)
        first_count = len(widget._card_rects)
        widget.render(surface, area)
        second_count = len(widget._card_rects)
        assert first_count == second_count

    def test_render_card_rects_horizontally_within_area(
        self, widget, surface, area
    ):
        widget.render(surface, area)
        for node_id, rect in widget._card_rects.items():
            assert rect.left >= area.left,  f"{node_id}: card.left < area.left"
            assert rect.right <= area.right, f"{node_id}: card.right > area.right"
