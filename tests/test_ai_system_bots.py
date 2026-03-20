"""Tests for AISystem.update_bots() — the PvP bot FSM driver.

These tests specify the full PATROL → AGGRO → ATTACK → DEAD lifecycle for
bot entities.  Where update_bots() is not yet present in AISystem the tests
skip rather than fail with an AttributeError, so the suite can run in a
partially-implemented state.

Coverage (per test pyramid):
  Unit   — state transitions, edge cases (dead bot skip, no-weapon guard,
            loot-pickup range boundary, reload guard)
  Integration — CombatSystem.fire() wiring in ATTACK state; EventBus
               player_killed emission in DEAD state; weapon-state tick

NOT covered here (already in test_pvp_mechanics.py):
  - CombatSystem lethal-hit detection and player_killed event payload
  - Friendly-fire flag and faction-based damage routing
  - XPSystem and LootSystem reactions to player_killed

# Run: pytest tests/test_ai_system_bots.py
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from src.entities.player_agent import PlayerAgent
from src.entities.robot_enemy import AIState
from src.systems.ai_system import AISystem, LOST_PLAYER_TIMEOUT, _DEATH_ANIM_DURATION


# ---------------------------------------------------------------------------
# Helpers and stubs
# ---------------------------------------------------------------------------

def _has_update_bots() -> bool:
    return callable(getattr(AISystem, "update_bots", None))


def _skip_if_not_impl():
    if not _has_update_bots():
        pytest.skip("AISystem.update_bots() not yet implemented")


class _Player:
    """Minimal player stub compatible with _centre_of() and AISystem."""
    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.width = 28
        self.height = 48
        self.alive = True


class _Tilemap:
    """Fully-walkable 20×20 grid for BFS pathfinding tests."""
    def __init__(self) -> None:
        self.tile_size = 32
        self.walkability_grid = [[0] * 20 for _ in range(20)]


class _Bus:
    """Simple recording event bus."""
    def __init__(self) -> None:
        self.emitted: list[tuple[str, dict]] = []

    def emit(self, event: str, **kwargs) -> None:
        self.emitted.append((event, kwargs))

    def subscribe(self, *a, **kw) -> None:
        pass

    def names(self) -> list[str]:
        return [e for e, _ in self.emitted]

    def payloads(self, event: str) -> list[dict]:
        return [kw for e, kw in self.emitted if e == event]


class _Combat:
    """Stub CombatSystem that records fire() calls."""
    def __init__(self) -> None:
        self.fired: list[tuple] = []

    def fire(self, owner, target_x: float, target_y: float, **kw):
        proj = MagicMock()
        proj.owner = owner
        self.fired.append((owner, target_x, target_y))
        return proj


def _make_weapon_item(
    damage: float = 20.0,
    fire_rate: float = 5.0,
    magazine_size: int = 12,
    reload_time: float = 1.5,
) -> MagicMock:
    w = MagicMock()
    w.damage = damage
    w.fire_rate = fire_rate
    w.magazine_size = magazine_size
    w.reload_time = reload_time
    w.projectile_speed = 600.0
    w.stats = {}
    return w


def _make_bot(
    x: float = 100.0,
    y: float = 100.0,
    ai_state: AIState = AIState.PATROL,
    aggro_range: float = 300.0,
    attack_range: float = 150.0,
    patrol_waypoints: list | None = None,
    with_weapon: bool = False,
    health: int = 100,
) -> PlayerAgent:
    """Build a PlayerAgent with minimal but valid configuration."""
    wps = patrol_waypoints or [(x, y), (x + 200.0, y)]
    weapon = _make_weapon_item() if with_weapon else None
    bot = PlayerAgent(
        x=x,
        y=y,
        patrol_waypoints=wps,
        loadout={"weapon": weapon, "armor": None},
    )
    bot.ai_state = ai_state
    bot.health = health
    bot.aggro_range = aggro_range
    bot.attack_range = attack_range
    return bot


# ===========================================================================
# Method existence
# ===========================================================================

class TestUpdateBotsMethodExists:
    """AISystem must expose a callable update_bots() method."""

    def test_update_bots_attribute_exists(self):
        assert hasattr(AISystem(), "update_bots"), (
            "AISystem.update_bots() is missing — required by the PvP bot feature."
        )

    def test_update_bots_is_callable(self):
        assert callable(getattr(AISystem(), "update_bots", None))


# ===========================================================================
# PATROL state
# ===========================================================================

class TestUpdateBotsPatrol:
    """Bots in PATROL state navigate waypoints and sense the player."""

    def test_empty_bot_list_is_a_no_op(self):
        _skip_if_not_impl()
        ai = AISystem()
        # Must not raise
        ai.update_bots([], _Player(), [], _Tilemap(), 0.016, _Bus(), _Combat())

    def test_patrol_bot_moves_toward_distant_waypoint(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=0.0, y=0.0, patrol_waypoints=[(0.0, 0.0), (300.0, 0.0)])
        player = _Player(x=5000.0, y=5000.0)  # far away — no aggro trigger
        ai.update_bots([bot], player, [], _Tilemap(), 1.0, _Bus(), _Combat())
        # Either target_vx is non-zero (intent flag set) or x has moved
        assert bot.target_vx != 0.0 or bot.x > 0.0, (
            "Bot in PATROL did not set movement intent toward its waypoint"
        )

    def test_patrol_transitions_to_aggro_when_player_enters_range(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.PATROL, aggro_range=300.0)
        player = _Player(x=130.0, y=100.0)  # ~30 px — inside aggro range
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), _Combat())
        assert bot.ai_state == AIState.AGGRO

    def test_patrol_stays_in_patrol_when_player_out_of_range(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.PATROL, aggro_range=100.0)
        player = _Player(x=5000.0, y=5000.0)
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), _Combat())
        assert bot.ai_state == AIState.PATROL

    def test_dead_bot_is_skipped_in_patrol(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0)
        bot.alive = False
        x_before = bot.x
        ai.update_bots([bot], _Player(), [], _Tilemap(), 1.0, _Bus(), _Combat())
        assert bot.x == x_before

    def test_patrol_bot_cycles_through_waypoints_on_arrival(self):
        """A bot that reaches its first waypoint advances to the next."""
        _skip_if_not_impl()
        ai = AISystem()
        # Place waypoint exactly at bot centre so arrival is immediate
        bot = _make_bot(
            x=0.0,
            y=0.0,
            ai_state=AIState.PATROL,
            patrol_waypoints=[(14.0, 24.0), (300.0, 0.0)],  # first wp at bot centre
            aggro_range=5.0,  # tiny — player never triggers aggro
        )
        player = _Player(x=5000.0, y=5000.0)
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), _Combat())
        assert bot._waypoint_idx == 1 or bot.patrol_waypoints[bot._waypoint_idx] != (14.0, 24.0), (
            "Waypoint index did not advance after arrival"
        )


# ===========================================================================
# Loot pickup during PATROL
# ===========================================================================

class TestUpdateBotsLootPickup:
    """Bots in PATROL state collect nearby loot items."""

    def _make_loot(self, x: float, y: float) -> MagicMock:
        loot = MagicMock()
        loot.alive = True
        loot.x = x
        loot.y = y
        # Provide a rect so distance calculations work
        loot.rect = MagicMock()
        loot.rect.centerx = x
        loot.rect.centery = y
        loot.item = MagicMock()
        loot.item.weight = 0.5
        return loot

    def test_patrol_bot_consumes_loot_within_pickup_range(self):
        _skip_if_not_impl()
        from src.constants import PVP_LOOT_DETECT_RANGE  # 96 px
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.PATROL)
        player = _Player(x=5000.0, y=5000.0)
        # Loot within 96 px of bot centre (~14+48/2 = 28, 100+48/2 = 124)
        loot = self._make_loot(x=110.0, y=100.0)  # ~10 px from bot x-centre
        bus = _Bus()
        ai.update_bots([bot], player, [loot], _Tilemap(), 0.016, bus, _Combat())
        # The loot must have been consumed (alive=False) OR item_picked_up emitted
        consumed = not loot.alive
        event_fired = "item_picked_up" in bus.names()
        assert consumed or event_fired, (
            "Bot in PATROL did not pick up loot that is within pickup range"
        )

    def test_patrol_bot_ignores_loot_beyond_pickup_range(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.PATROL)
        player = _Player(x=5000.0, y=5000.0)
        # Loot far away (> 96 px)
        loot = self._make_loot(x=5000.0, y=5000.0)
        ai.update_bots([bot], player, [loot], _Tilemap(), 0.016, _Bus(), _Combat())
        assert loot.alive is True

    def test_loot_pickup_emits_item_picked_up_event(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.PATROL)
        player = _Player(x=5000.0, y=5000.0)
        loot = self._make_loot(x=105.0, y=100.0)
        bus = _Bus()
        ai.update_bots([bot], player, [loot], _Tilemap(), 0.016, bus, _Combat())
        if not loot.alive:  # was consumed — check event
            assert "item_picked_up" in bus.names()


# ===========================================================================
# AGGRO state
# ===========================================================================

class TestUpdateBotsAggro:
    """Bots in AGGRO state chase the player and react to distance changes."""

    def test_aggro_bot_transitions_to_attack_when_in_attack_range(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.AGGRO, attack_range=150.0)
        player = _Player(x=130.0, y=100.0)  # ~30 px — inside attack range
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), _Combat())
        assert bot.ai_state == AIState.ATTACK

    def test_aggro_bot_returns_to_patrol_after_lost_player_timeout(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.AGGRO, aggro_range=200.0)
        bot.lost_timer = LOST_PLAYER_TIMEOUT - 0.01
        player = _Player(x=5000.0, y=5000.0)  # far outside aggro range
        ai.update_bots([bot], player, [], _Tilemap(), 0.05, _Bus(), _Combat())
        assert bot.ai_state == AIState.PATROL

    def test_aggro_bot_stays_aggro_before_lost_timeout(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.AGGRO, aggro_range=200.0)
        bot.lost_timer = 0.0
        player = _Player(x=5000.0, y=5000.0)
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), _Combat())
        assert bot.ai_state == AIState.AGGRO

    def test_aggro_bot_moves_toward_player(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(
            x=0.0, y=0.0,
            ai_state=AIState.AGGRO,
            aggro_range=1000.0,
            attack_range=10.0,
        )
        player = _Player(x=400.0, y=0.0)
        x_before = bot.x
        ai.update_bots([bot], player, [], _Tilemap(), 1.0, _Bus(), _Combat())
        assert bot.x > x_before or bot.target_vx > 0.0, (
            "AGGRO bot did not move toward player"
        )


# ===========================================================================
# ATTACK state
# ===========================================================================

class TestUpdateBotsAttack:
    """Bots in ATTACK state fire projectiles and manage weapon cooldowns."""

    def test_armed_bot_fires_when_weapon_is_ready(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.ATTACK, with_weapon=True)
        bot.weapon_state.fire_cooldown = 0.0  # immediately ready
        bot.weapon_state.ammo = bot.weapon_state.magazine_size
        player = _Player(x=130.0, y=100.0)
        combat = _Combat()
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), combat)
        assert len(combat.fired) >= 1, "Armed bot in ATTACK state did not fire"

    def test_fired_projectile_owner_is_the_bot(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.ATTACK, with_weapon=True)
        bot.weapon_state.fire_cooldown = 0.0
        bot.weapon_state.ammo = bot.weapon_state.magazine_size
        player = _Player(x=130.0, y=100.0)
        combat = _Combat()
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), combat)
        if combat.fired:
            owner, _, _ = combat.fired[0]
            assert owner is bot

    def test_unarmed_bot_does_not_call_fire(self):
        """A bot without a weapon must not crash and must not fire."""
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.ATTACK, with_weapon=False)
        player = _Player(x=130.0, y=100.0)
        combat = _Combat()
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), combat)
        assert len(combat.fired) == 0

    def test_unarmed_bot_stays_in_aggro_or_attack_without_crash(self):
        """No weapon → bot does not error out; state remains sane."""
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.ATTACK, with_weapon=False)
        player = _Player(x=130.0, y=100.0)
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), _Combat())
        assert bot.ai_state in (AIState.ATTACK, AIState.AGGRO)

    def test_bot_does_not_fire_before_cooldown_expires(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.ATTACK, with_weapon=True)
        bot.weapon_state.fire_cooldown = 9999.0  # never ready in one frame
        player = _Player(x=130.0, y=100.0)
        combat = _Combat()
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), combat)
        assert len(combat.fired) == 0

    def test_bot_initiates_reload_when_magazine_is_empty(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.ATTACK, with_weapon=True)
        bot.weapon_state.ammo = 0
        bot.weapon_state.reloading = False
        player = _Player(x=130.0, y=100.0)
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), _Combat())
        assert bot.weapon_state.reloading is True, (
            "Bot did not start reloading after magazine ran empty"
        )

    def test_bot_stays_in_attack_during_reload(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.ATTACK, with_weapon=True)
        bot.weapon_state.ammo = 0
        bot.weapon_state.reloading = True
        bot.weapon_state.reload_timer = 1.0
        player = _Player(x=130.0, y=100.0)
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), _Combat())
        assert bot.ai_state == AIState.ATTACK

    def test_attack_reverts_to_aggro_when_player_leaves_range(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0, ai_state=AIState.ATTACK, attack_range=150.0)
        player = _Player(x=5000.0, y=5000.0)  # well beyond attack range
        ai.update_bots([bot], player, [], _Tilemap(), 0.016, _Bus(), _Combat())
        assert bot.ai_state == AIState.AGGRO


# ===========================================================================
# DEAD state
# ===========================================================================

class TestUpdateBotsDead:
    """Bots in DEAD state run the death animation and emit player_killed."""

    def test_dead_bot_emits_player_killed_after_animation_completes(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot()
        killer = MagicMock()
        killer.is_player_controlled = True
        bot.take_damage(bot.health + 1)  # lethal → ai_state = DEAD
        bot._killer = killer
        bus = _Bus()
        # Run for longer than _DEATH_ANIM_DURATION
        ai.update_bots([bot], _Player(), [], _Tilemap(), _DEATH_ANIM_DURATION + 0.1, bus, _Combat())
        assert "player_killed" in bus.names(), (
            "player_killed event was not emitted after bot death animation completed"
        )

    def test_player_killed_payload_has_victim(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot()
        bot.take_damage(bot.health + 1)
        bot._killer = MagicMock()
        bus = _Bus()
        ai.update_bots([bot], _Player(), [], _Tilemap(), _DEATH_ANIM_DURATION + 0.1, bus, _Combat())
        payloads = bus.payloads("player_killed")
        assert payloads, "No player_killed events emitted"
        assert payloads[0]["victim"] is bot

    def test_player_killed_payload_has_killer(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot()
        killer = MagicMock()
        killer.is_player_controlled = True
        bot.take_damage(bot.health + 1)
        bot._killer = killer
        bus = _Bus()
        ai.update_bots([bot], _Player(), [], _Tilemap(), _DEATH_ANIM_DURATION + 0.1, bus, _Combat())
        payloads = bus.payloads("player_killed")
        assert payloads, "No player_killed events emitted"
        assert payloads[0]["killer"] is killer

    def test_player_killed_not_emitted_before_animation_completes(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot()
        bot.take_damage(bot.health + 1)
        bot._killer = MagicMock()
        bus = _Bus()
        # Run for only half the animation duration
        ai.update_bots([bot], _Player(), [], _Tilemap(), _DEATH_ANIM_DURATION * 0.5, bus, _Combat())
        assert "player_killed" not in bus.names()

    def test_player_killed_emitted_exactly_once(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot()
        bot.take_damage(bot.health + 1)
        bot._killer = MagicMock()
        bus = _Bus()
        # First call completes the death animation
        ai.update_bots([bot], _Player(), [], _Tilemap(), _DEATH_ANIM_DURATION + 0.1, bus, _Combat())
        events_after_first = len(bus.payloads("player_killed"))
        # Second call — must not emit again
        ai.update_bots([bot], _Player(), [], _Tilemap(), _DEATH_ANIM_DURATION + 0.1, bus, _Combat())
        assert len(bus.payloads("player_killed")) == events_after_first, (
            "player_killed was emitted more than once for a single bot death"
        )

    def test_dead_bot_does_not_move(self):
        _skip_if_not_impl()
        ai = AISystem()
        bot = _make_bot(x=100.0, y=100.0)
        bot.take_damage(bot.health + 1)
        x_before = bot.x
        ai.update_bots([bot], _Player(x=105.0), [], _Tilemap(), 1.0, _Bus(), _Combat())
        assert bot.x == x_before


# ===========================================================================
# Multiple bots
# ===========================================================================

class TestUpdateBotsMultipleBots:
    """Each bot in the list is updated independently."""

    def test_each_bot_transitions_independently(self):
        """Bot A is near the player (→ AGGRO); bot B is far (→ stays PATROL)."""
        _skip_if_not_impl()
        ai = AISystem()
        bot_near = _make_bot(x=0.0, y=0.0, ai_state=AIState.PATROL, aggro_range=200.0)
        bot_far = _make_bot(x=5000.0, y=5000.0, ai_state=AIState.PATROL, aggro_range=50.0)
        player = _Player(x=10.0, y=0.0)
        ai.update_bots([bot_near, bot_far], player, [], _Tilemap(), 0.016, _Bus(), _Combat())
        assert bot_near.ai_state == AIState.AGGRO
        assert bot_far.ai_state == AIState.PATROL

    def test_already_dead_bots_are_completely_skipped(self):
        _skip_if_not_impl()
        ai = AISystem()
        dead = _make_bot(x=100.0, y=100.0)
        dead.alive = False
        x_before = dead.x
        ai.update_bots([dead], _Player(x=105.0), [], _Tilemap(), 1.0, _Bus(), _Combat())
        assert dead.x == x_before
