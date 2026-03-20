"""Unit tests for PlayerAgent — the AI-controlled PvP bot entity.

Covers: faction assignment, initialization, center property, armor property,
take_damage (lethal / non-lethal / dead-guard), loadout application, intent
flags, and the Faction enum on all combatant types.

NOT covered here (already in test_pvp_mechanics.py):
  - is_player_controlled flag
  - CombatSystem lethal-hit detection and player_killed emission
  - Friendly-fire flag behaviour

# Run: pytest tests/test_player_agent.py
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from src.constants import Faction
from src.entities.player_agent import PlayerAgent, _BOT_WIDTH, _BOT_HEIGHT, _BOT_MAX_HEALTH
from src.entities.robot_enemy import AIState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_weapon_item(
    damage: float = 20.0,
    fire_rate: float = 5.0,
    magazine_size: int = 12,
    reload_time: float = 1.5,
    projectile_speed: float = 600.0,
) -> MagicMock:
    w = MagicMock()
    w.damage = damage
    w.fire_rate = fire_rate
    w.magazine_size = magazine_size
    w.reload_time = reload_time
    w.projectile_speed = projectile_speed
    w.stats = {}
    return w


def _make_armor_item(armor_value: int = 10) -> MagicMock:
    a = MagicMock()
    a.armor = armor_value
    a.armor_value = armor_value
    return a


def _make_agent(**kw) -> PlayerAgent:
    kw.setdefault("x", 100.0)
    kw.setdefault("y", 200.0)
    return PlayerAgent(**kw)


# ===========================================================================
# Faction enum — correctness and assignment
# ===========================================================================

class TestFactionEnum:
    """Faction enum is defined with correct values and assigned to all combatants."""

    def test_faction_player_value_is_player_string(self):
        assert Faction.PLAYER.value == "player"

    def test_faction_enemy_value_is_enemy_string(self):
        assert Faction.ENEMY.value == "enemy"

    def test_faction_player_and_enemy_are_distinct(self):
        assert Faction.PLAYER != Faction.ENEMY

    def test_player_entity_has_faction_player(self):
        from src.entities.player import Player
        p = Player(x=0, y=0)
        assert p.faction == Faction.PLAYER

    def test_robot_enemy_has_faction_enemy(self):
        from src.entities.robot_enemy import RobotEnemy
        r = RobotEnemy(x=0.0, y=0.0, hp=50)
        assert r.faction == Faction.ENEMY

    def test_player_agent_has_faction_player(self):
        agent = _make_agent()
        assert agent.faction == Faction.PLAYER

    def test_player_agent_faction_is_not_enemy(self):
        agent = _make_agent()
        assert agent.faction != Faction.ENEMY


# ===========================================================================
# Initialization
# ===========================================================================

class TestPlayerAgentInit:
    """PlayerAgent starts with the correct default field values."""

    def test_starts_alive(self):
        assert _make_agent().alive is True

    def test_starts_in_patrol_state(self):
        assert _make_agent().ai_state == AIState.PATROL

    def test_health_equals_max_health_at_spawn(self):
        agent = _make_agent()
        assert agent.health == agent.max_health

    def test_max_health_matches_constant(self):
        assert _make_agent().max_health == _BOT_MAX_HEALTH

    def test_health_is_positive(self):
        assert _make_agent().health > 0

    def test_target_vx_starts_at_zero(self):
        assert _make_agent().target_vx == 0.0

    def test_jump_intent_starts_false(self):
        assert _make_agent().jump_intent is False

    def test_on_ground_starts_false(self):
        assert _make_agent().on_ground is False

    def test_position_x_stored_correctly(self):
        assert _make_agent(x=150.0, y=250.0).x == pytest.approx(150.0)

    def test_position_y_stored_correctly(self):
        assert _make_agent(x=150.0, y=250.0).y == pytest.approx(250.0)

    def test_rect_width_matches_constant(self):
        assert _make_agent().rect.w == _BOT_WIDTH

    def test_rect_height_matches_constant(self):
        assert _make_agent().rect.h == _BOT_HEIGHT

    def test_waypoints_default_to_spawn_position(self):
        agent = _make_agent(x=50.0, y=75.0, patrol_waypoints=None)
        assert agent.patrol_waypoints == [(50.0, 75.0)]

    def test_custom_waypoints_are_stored(self):
        wps = [(10.0, 20.0), (30.0, 40.0)]
        agent = _make_agent(patrol_waypoints=wps)
        assert agent.patrol_waypoints == wps

    def test_inventory_is_not_none(self):
        assert _make_agent().inventory is not None

    def test_no_weapon_in_empty_loadout(self):
        agent = _make_agent(loadout={"weapon": None, "armor": None})
        assert agent.weapon_state is None

    def test_killer_reference_starts_none(self):
        assert _make_agent()._killer is None

    def test_death_event_not_emitted_at_spawn(self):
        assert _make_agent()._death_event_emitted is False

    def test_difficulty_stored_correctly(self):
        assert _make_agent(difficulty="hard").difficulty == "hard"

    def test_difficulty_defaults_to_medium(self):
        assert _make_agent().difficulty == "medium"


# ===========================================================================
# center property
# ===========================================================================

class TestPlayerAgentCenter:
    """center property returns the world-space centre of the bot's rect."""

    def test_center_is_tuple_of_two_floats(self):
        cx, cy = _make_agent().center
        assert isinstance(cx, float)
        assert isinstance(cy, float)

    def test_center_x_equals_rect_centerx(self):
        agent = _make_agent(x=100.0, y=200.0)
        assert agent.center[0] == float(agent.rect.centerx)

    def test_center_y_equals_rect_centery(self):
        agent = _make_agent(x=100.0, y=200.0)
        assert agent.center[1] == float(agent.rect.centery)

    def test_center_accounts_for_bot_width(self):
        agent = _make_agent(x=0.0, y=0.0)
        assert agent.center[0] == pytest.approx(_BOT_WIDTH / 2.0)

    def test_center_accounts_for_bot_height(self):
        agent = _make_agent(x=0.0, y=0.0)
        assert agent.center[1] == pytest.approx(_BOT_HEIGHT / 2.0)

    def test_center_updates_when_position_changes(self):
        agent = _make_agent(x=0.0, y=0.0)
        cx_before, _ = agent.center
        agent.x = 100.0
        cx_after, _ = agent.center
        assert cx_after != cx_before


# ===========================================================================
# armor property
# ===========================================================================

class TestPlayerAgentArmor:
    """armor property derives the correct integer value from equipped armor."""

    def test_armor_is_zero_without_equipped_armor(self):
        agent = _make_agent(loadout={"weapon": None, "armor": None})
        assert agent.armor == 0

    def test_armor_reads_armor_attribute_from_item(self):
        armor_item = _make_armor_item(armor_value=15)
        agent = _make_agent(loadout={"weapon": None, "armor": armor_item})
        assert agent.armor == 15

    def test_armor_returns_int(self):
        armor_item = _make_armor_item(armor_value=8)
        agent = _make_agent(loadout={"weapon": None, "armor": armor_item})
        assert isinstance(agent.armor, int)

    def test_get_effective_armor_matches_armor_property(self):
        armor_item = _make_armor_item(armor_value=8)
        agent = _make_agent(loadout={"weapon": None, "armor": armor_item})
        assert agent.get_effective_armor() == agent.armor

    def test_get_effective_armor_is_zero_without_armor(self):
        agent = _make_agent(loadout={"weapon": None, "armor": None})
        assert agent.get_effective_armor() == 0


# ===========================================================================
# take_damage
# ===========================================================================

class TestPlayerAgentTakeDamage:
    """take_damage reduces health and correctly handles death conditions."""

    def test_take_damage_reduces_health(self):
        agent = _make_agent()
        before = agent.health
        agent.take_damage(10)
        assert agent.health == before - 10

    def test_take_damage_nonlethal_keeps_alive(self):
        agent = _make_agent()
        agent.take_damage(agent.health - 1)
        assert agent.alive is True

    def test_take_damage_nonlethal_keeps_patrol_state(self):
        agent = _make_agent()
        agent.take_damage(1)
        assert agent.ai_state == AIState.PATROL

    def test_take_damage_lethal_sets_alive_false(self):
        agent = _make_agent()
        agent.take_damage(agent.health)
        assert agent.alive is False

    def test_take_damage_lethal_sets_ai_state_to_dead(self):
        agent = _make_agent()
        agent.take_damage(agent.health + 1000)
        assert agent.ai_state == AIState.DEAD

    def test_take_damage_clamps_health_to_zero_on_overkill(self):
        agent = _make_agent()
        agent.take_damage(agent.health + 1000)
        assert agent.health == 0

    def test_dead_bot_ignores_additional_take_damage_calls(self):
        """Once dead, further take_damage must not change health."""
        agent = _make_agent()
        agent.take_damage(agent.health)  # lethal
        health_after_death = agent.health
        agent.take_damage(999)           # must be ignored
        assert agent.health == health_after_death

    def test_dead_bot_remains_dead_after_extra_damage(self):
        agent = _make_agent()
        agent.take_damage(agent.health)
        agent.take_damage(1)
        assert agent.alive is False

    def test_take_damage_exactly_to_zero_is_lethal(self):
        agent = _make_agent()
        agent.take_damage(agent.health)
        assert agent.alive is False
        assert agent.health == 0

    def test_take_damage_one_below_lethal_is_nonlethal(self):
        agent = _make_agent()
        agent.take_damage(agent.health - 1)
        assert agent.alive is True
        assert agent.health == 1


# ===========================================================================
# Loadout application
# ===========================================================================

class TestPlayerAgentLoadout:
    """_apply_loadout correctly configures weapon_state and inventory slots."""

    def test_weapon_item_creates_weapon_state(self):
        weapon = _make_weapon_item()
        agent = _make_agent(loadout={"weapon": weapon, "armor": None})
        assert agent.weapon_state is not None

    def test_weapon_item_stored_as_equipped_weapon(self):
        weapon = _make_weapon_item()
        agent = _make_agent(loadout={"weapon": weapon, "armor": None})
        assert agent.inventory.equipped_weapon is weapon

    def test_armor_item_stored_as_equipped_armor(self):
        armor = _make_armor_item()
        agent = _make_agent(loadout={"weapon": None, "armor": armor})
        assert agent.inventory.equipped_armor is armor

    def test_both_weapon_and_armor_in_loadout(self):
        weapon = _make_weapon_item()
        armor = _make_armor_item()
        agent = _make_agent(loadout={"weapon": weapon, "armor": armor})
        assert agent.inventory.equipped_weapon is weapon
        assert agent.inventory.equipped_armor is armor

    def test_empty_loadout_sets_weapon_state_none(self):
        agent = _make_agent(loadout={})
        assert agent.weapon_state is None

    def test_weapon_damage_loaded_into_weapon_state(self):
        weapon = _make_weapon_item(damage=35.0)
        agent = _make_agent(loadout={"weapon": weapon, "armor": None})
        assert agent.weapon_state.damage == pytest.approx(35.0)

    def test_weapon_fire_rate_loaded_into_weapon_state(self):
        weapon = _make_weapon_item(fire_rate=8.0)
        agent = _make_agent(loadout={"weapon": weapon, "armor": None})
        assert agent.weapon_state.fire_rate == pytest.approx(8.0)

    def test_weapon_magazine_size_loaded_into_weapon_state(self):
        weapon = _make_weapon_item(magazine_size=30)
        agent = _make_agent(loadout={"weapon": weapon, "armor": None})
        assert agent.weapon_state.magazine_size == 30
