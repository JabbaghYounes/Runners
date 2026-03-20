"""Unit/integration tests for SpawnSystem.spawn_bots().

Covers: empty map data, correct count, position, waypoints, difficulty,
missing-pos validation, malformed-pos skipping, partial success, and warning
emission for invalid entries.

# Run: pytest tests/test_spawn_bots.py
"""
from __future__ import annotations

import warnings
from unittest.mock import MagicMock

import pytest

from src.entities.player_agent import PlayerAgent
from src.entities.robot_enemy import AIState
from src.systems.spawn_system import SpawnSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item_db(weapons: list | None = None) -> MagicMock:
    """Return a mock ItemDatabase that serves the given weapon list."""
    db = MagicMock()
    weapons = list(weapons or [])

    def _get_all(item_type: str) -> list:
        if item_type == "weapon":
            return weapons
        return []

    db.get_all_by_type.side_effect = _get_all
    return db


def _entry(
    pos: tuple = (100.0, 200.0),
    waypoints: list | None = None,
    difficulty: str | None = None,
) -> dict:
    """Build a valid bot_spawns entry dict."""
    e: dict = {"pos": list(pos)}
    if waypoints is not None:
        e["patrol_waypoints"] = [list(wp) for wp in waypoints]
    if difficulty is not None:
        e["difficulty"] = difficulty
    return e


# ===========================================================================
# Count
# ===========================================================================

class TestSpawnBotsCount:
    """spawn_bots returns the correct number of bots."""

    def test_empty_bot_spawns_key_returns_empty_list(self):
        result = SpawnSystem().spawn_bots({"bot_spawns": []}, _item_db())
        assert result == []

    def test_missing_bot_spawns_key_returns_empty_list(self):
        result = SpawnSystem().spawn_bots({}, _item_db())
        assert result == []

    def test_single_valid_entry_returns_one_bot(self):
        data = {"bot_spawns": [_entry()]}
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert len(result) == 1

    def test_three_valid_entries_return_three_bots(self):
        data = {"bot_spawns": [_entry((x * 200.0, 100.0)) for x in range(3)]}
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert len(result) == 3

    def test_result_is_a_plain_list(self):
        result = SpawnSystem().spawn_bots({}, _item_db())
        assert isinstance(result, list)


# ===========================================================================
# Type and initial state
# ===========================================================================

class TestSpawnBotsType:
    """Every bot returned is a fully-initialised PlayerAgent."""

    def test_returns_player_agent_instances(self):
        data = {"bot_spawns": [_entry()]}
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert isinstance(result[0], PlayerAgent)

    def test_all_returned_items_are_player_agents(self):
        data = {"bot_spawns": [_entry((i * 100.0, 0.0)) for i in range(3)]}
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert all(isinstance(b, PlayerAgent) for b in result)

    def test_bots_start_alive(self):
        data = {"bot_spawns": [_entry()]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.alive is True

    def test_bots_start_in_patrol_state(self):
        data = {"bot_spawns": [_entry()]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.ai_state == AIState.PATROL


# ===========================================================================
# Position
# ===========================================================================

class TestSpawnBotsPosition:
    """Bots are placed at the world coordinates given in the map data."""

    def test_bot_placed_at_correct_x(self):
        data = {"bot_spawns": [_entry((123.0, 456.0))]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.x == pytest.approx(123.0)

    def test_bot_placed_at_correct_y(self):
        data = {"bot_spawns": [_entry((123.0, 456.0))]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.y == pytest.approx(456.0)

    def test_multiple_bots_placed_at_distinct_positions(self):
        positions = [(100.0, 50.0), (300.0, 50.0), (500.0, 50.0)]
        data = {"bot_spawns": [_entry(p) for p in positions]}
        result = SpawnSystem().spawn_bots(data, _item_db())
        xs = [b.x for b in result]
        assert xs == pytest.approx([p[0] for p in positions])

    def test_integer_pos_values_are_converted_to_float(self):
        data = {"bot_spawns": [{"pos": [64, 128]}]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.x == pytest.approx(64.0)
        assert bot.y == pytest.approx(128.0)


# ===========================================================================
# Waypoints
# ===========================================================================

class TestSpawnBotsWaypoints:
    """Bot patrol routes are parsed from the map data."""

    def test_explicit_waypoints_stored_on_bot(self):
        wps = [(10.0, 20.0), (30.0, 40.0)]
        data = {"bot_spawns": [_entry(waypoints=wps)]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.patrol_waypoints == wps

    def test_empty_waypoints_default_to_spawn_position(self):
        data = {"bot_spawns": [_entry((77.0, 88.0), waypoints=[])]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.patrol_waypoints == [(77.0, 88.0)]

    def test_missing_waypoints_key_defaults_to_spawn_position(self):
        data = {"bot_spawns": [{"pos": [55.0, 66.0]}]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.patrol_waypoints == [(55.0, 66.0)]

    def test_malformed_waypoint_entries_are_silently_dropped(self):
        """One valid waypoint + one broken one → only the valid one is kept."""
        data = {
            "bot_spawns": [{
                "pos": [100.0, 100.0],
                "patrol_waypoints": [[10.0, 20.0], "not_a_list"],
            }]
        }
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        # At minimum the valid waypoint should be present
        assert (10.0, 20.0) in bot.patrol_waypoints

    def test_all_waypoints_converted_to_float_tuples(self):
        wps = [(0, 0), (100, 50)]
        data = {"bot_spawns": [_entry(waypoints=wps)]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        for wp in bot.patrol_waypoints:
            assert isinstance(wp[0], float)
            assert isinstance(wp[1], float)


# ===========================================================================
# Difficulty
# ===========================================================================

class TestSpawnBotsDifficulty:
    """Difficulty tier is parsed and assigned to each bot."""

    def test_default_difficulty_is_medium(self):
        data = {"bot_spawns": [{"pos": [0.0, 0.0]}]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.difficulty == "medium"

    def test_easy_difficulty_stored_on_bot(self):
        data = {"bot_spawns": [_entry(difficulty="easy")]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.difficulty == "easy"

    def test_hard_difficulty_stored_on_bot(self):
        data = {"bot_spawns": [_entry(difficulty="hard")]}
        bot = SpawnSystem().spawn_bots(data, _item_db())[0]
        assert bot.difficulty == "hard"

    def test_different_difficulties_per_bot(self):
        data = {
            "bot_spawns": [
                _entry((0.0, 0.0), difficulty="easy"),
                _entry((200.0, 0.0), difficulty="hard"),
            ]
        }
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert result[0].difficulty == "easy"
        assert result[1].difficulty == "hard"


# ===========================================================================
# Validation — invalid entries are skipped with warnings
# ===========================================================================

class TestSpawnBotsValidation:
    """Invalid entries are skipped gracefully; valid entries still succeed."""

    def test_entry_missing_pos_key_is_skipped(self):
        data = {"bot_spawns": [{"patrol_waypoints": [[10.0, 20.0]]}]}
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert result == []

    def test_entry_missing_pos_emits_warning(self):
        data = {"bot_spawns": [{"patrol_waypoints": [[10.0, 20.0]]}]}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            SpawnSystem().spawn_bots(data, _item_db())
        assert len(caught) > 0, "Expected a warning for missing 'pos' key"

    def test_entry_with_non_numeric_pos_is_skipped(self):
        data = {"bot_spawns": [{"pos": ["bad", "values"]}]}
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert result == []

    def test_entry_with_non_numeric_pos_emits_warning(self):
        data = {"bot_spawns": [{"pos": ["not", "a", "number"]}]}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            SpawnSystem().spawn_bots(data, _item_db())
        assert len(caught) > 0

    def test_entry_with_empty_pos_list_is_skipped(self):
        data = {"bot_spawns": [{"pos": []}]}
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert result == []

    def test_partial_success_skips_bad_returns_good(self):
        """One invalid entry followed by one valid entry → only the valid bot returned."""
        data = {
            "bot_spawns": [
                {"patrol_waypoints": [[0.0, 0.0]]},   # missing pos — invalid
                _entry((200.0, 300.0)),                 # valid
            ]
        }
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert len(result) == 1
        assert result[0].x == pytest.approx(200.0)
        assert result[0].y == pytest.approx(300.0)

    def test_all_invalid_returns_empty_list(self):
        data = {
            "bot_spawns": [
                {"patrol_waypoints": [[0.0, 0.0]]},
                {"pos": ["x", "y"]},
            ]
        }
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert result == []

    def test_valid_entries_interspersed_with_invalid_all_counted(self):
        data = {
            "bot_spawns": [
                _entry((100.0, 100.0)),                 # valid
                {"patrol_waypoints": [[0.0, 0.0]]},   # invalid
                _entry((300.0, 100.0)),                 # valid
            ]
        }
        result = SpawnSystem().spawn_bots(data, _item_db())
        assert len(result) == 2
