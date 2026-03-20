"""Tests for AISystem projectile-based ATTACK.

Covers:
- _do_attack() calls combat_system.fire() with correct owner and damage
- _do_attack() returns a Projectile when combat_system is provided
- _do_attack() falls back to player.take_damage() when combat_system=None
- Dead player is skipped by both paths
- fire() raising an exception is swallowed; no crash, no projectile added
- update() collects and returns the list of fired projectiles
"""
from __future__ import annotations

import pytest

from src.entities.robot_enemy import AIState, RobotEnemy
from src.entities.projectile import Projectile
from src.systems.ai_system import AISystem


# ---------------------------------------------------------------------------
# Stubs / spies
# ---------------------------------------------------------------------------

class _Player:
    def __init__(self, x: float = 100.0, y: float = 100.0) -> None:
        self.x = x
        self.y = y
        self.width = 32
        self.height = 48
        self.alive = True
        self.damage_received: list[int] = []

    def take_damage(self, amount: int) -> None:
        self.damage_received.append(amount)


class _MockCombat:
    """Spy for CombatSystem.fire()."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def fire(
        self,
        owner: object,
        target_x: float,
        target_y: float,
        damage: int = 15,
        speed: float = 600.0,
    ) -> Projectile:
        self.calls.append({"owner": owner, "target_x": target_x,
                           "target_y": target_y, "damage": damage})
        cx = owner.rect.centerx  # type: ignore[attr-defined]
        cy = owner.rect.centery  # type: ignore[attr-defined]
        return Projectile(cx, cy, 0.0, 0.0, damage, owner=owner)


class _ExplodingCombat:
    """CombatSystem stub that always raises."""

    def fire(self, *args, **kwargs) -> None:  # type: ignore[override]
        raise RuntimeError("intentional test failure")


class _Bus:
    def emit(self, *a, **kw) -> None:
        pass


def _robot(**overrides) -> RobotEnemy:
    defaults = dict(
        x=100.0, y=100.0, hp=50,
        attack_range=200.0, attack_damage=10, attack_cooldown=0.5,
        type_id="grunt",
    )
    defaults.update(overrides)
    r = RobotEnemy(**defaults)
    r.state = AIState.ATTACK
    return r


# ---------------------------------------------------------------------------
# _do_attack with combat_system provided
# ---------------------------------------------------------------------------

class TestDoAttackWithCombatSystem:

    def test_fire_called_once_after_cooldown(self) -> None:
        ai = AISystem()
        robot = _robot(attack_cooldown=0.5)
        robot.attack_timer = 0.6          # already past cooldown
        combat = _MockCombat()
        ai._do_attack(robot, _Player(), dt=0.0, bus=_Bus(), combat_system=combat)
        assert len(combat.calls) == 1

    def test_fire_called_with_correct_owner(self) -> None:
        ai = AISystem()
        robot = _robot()
        robot.attack_timer = 0.6
        combat = _MockCombat()
        ai._do_attack(robot, _Player(), dt=0.0, bus=_Bus(), combat_system=combat)
        assert combat.calls[0]["owner"] is robot

    def test_fire_called_with_enemy_attack_damage(self) -> None:
        ai = AISystem()
        robot = _robot(attack_damage=35)
        robot.attack_timer = 0.6
        combat = _MockCombat()
        ai._do_attack(robot, _Player(), dt=0.0, bus=_Bus(), combat_system=combat)
        assert combat.calls[0]["damage"] == 35

    def test_fire_not_called_before_cooldown(self) -> None:
        ai = AISystem()
        robot = _robot(attack_cooldown=1.2)
        robot.attack_timer = 0.0          # nowhere near cooldown
        combat = _MockCombat()
        ai._do_attack(robot, _Player(), dt=0.016, bus=_Bus(), combat_system=combat)
        assert len(combat.calls) == 0

    def test_returns_projectile_instance(self) -> None:
        ai = AISystem()
        robot = _robot()
        robot.attack_timer = 0.6
        combat = _MockCombat()
        proj = ai._do_attack(robot, _Player(), dt=0.0, bus=_Bus(), combat_system=combat)
        assert isinstance(proj, Projectile)

    def test_returns_none_before_cooldown(self) -> None:
        ai = AISystem()
        robot = _robot(attack_cooldown=1.2)
        robot.attack_timer = 0.0
        combat = _MockCombat()
        result = ai._do_attack(robot, _Player(), dt=0.016, bus=_Bus(), combat_system=combat)
        assert result is None

    def test_dead_player_skips_fire(self) -> None:
        ai = AISystem()
        robot = _robot()
        robot.attack_timer = 0.6
        player = _Player()
        player.alive = False
        combat = _MockCombat()
        proj = ai._do_attack(robot, player, dt=0.0, bus=_Bus(), combat_system=combat)
        assert len(combat.calls) == 0
        assert proj is None

    def test_projectile_owner_is_robot(self) -> None:
        ai = AISystem()
        robot = _robot()
        robot.attack_timer = 0.6
        combat = _MockCombat()
        proj = ai._do_attack(robot, _Player(), dt=0.0, bus=_Bus(), combat_system=combat)
        assert proj is not None
        assert proj.owner is robot


# ---------------------------------------------------------------------------
# _do_attack without combat_system (legacy fallback)
# ---------------------------------------------------------------------------

class TestDoAttackFallback:

    def test_fallback_calls_take_damage(self) -> None:
        ai = AISystem()
        robot = _robot(attack_damage=10)
        robot.attack_timer = 0.6
        player = _Player()
        ai._do_attack(robot, player, dt=0.0, bus=_Bus(), combat_system=None)
        assert 10 in player.damage_received

    def test_fallback_returns_none(self) -> None:
        ai = AISystem()
        robot = _robot()
        robot.attack_timer = 0.6
        player = _Player()
        result = ai._do_attack(robot, player, dt=0.0, bus=_Bus(), combat_system=None)
        assert result is None

    def test_fallback_dead_player_not_damaged(self) -> None:
        ai = AISystem()
        robot = _robot()
        robot.attack_timer = 0.6
        player = _Player()
        player.alive = False
        ai._do_attack(robot, player, dt=0.0, bus=_Bus(), combat_system=None)
        assert player.damage_received == []


# ---------------------------------------------------------------------------
# Exception safety
# ---------------------------------------------------------------------------

class TestFireExceptionSafety:

    def test_fire_exception_swallowed_returns_none(self) -> None:
        ai = AISystem()
        robot = _robot()
        robot.attack_timer = 0.6
        result = ai._do_attack(
            robot, _Player(), dt=0.0, bus=_Bus(),
            combat_system=_ExplodingCombat(),
        )
        assert result is None

    def test_fire_exception_does_not_crash_update(self) -> None:
        ai = AISystem()
        robot = _robot(attack_cooldown=0.5)
        robot.attack_timer = 0.6

        projs = ai.update(
            [robot], _Player(), None, dt=0.0,
            event_bus=_Bus(), combat_system=_ExplodingCombat(),
        )
        assert projs == []


# ---------------------------------------------------------------------------
# update() return value
# ---------------------------------------------------------------------------

class TestUpdateReturnValue:

    def test_update_returns_list(self) -> None:
        ai = AISystem()
        robot = _robot()
        robot.attack_timer = 0.6
        result = ai.update(
            [robot], _Player(), None, dt=0.0,
            event_bus=_Bus(), combat_system=_MockCombat(),
        )
        assert isinstance(result, list)

    def test_update_contains_projectile_from_attack(self) -> None:
        ai = AISystem()
        robot = _robot(attack_cooldown=0.5)
        robot.attack_timer = 0.6
        combat = _MockCombat()
        result = ai.update(
            [robot], _Player(), None, dt=0.0,
            event_bus=_Bus(), combat_system=combat,
        )
        assert len(result) == 1
        assert isinstance(result[0], Projectile)

    def test_update_returns_empty_when_no_attack_fires(self) -> None:
        ai = AISystem()
        robot = _robot(attack_cooldown=1.2)
        robot.attack_timer = 0.0          # nowhere near cooldown
        result = ai.update(
            [robot], _Player(), None, dt=0.016,
            event_bus=_Bus(), combat_system=_MockCombat(),
        )
        assert result == []

    def test_update_returns_empty_for_patrol_state(self) -> None:
        ai = AISystem()
        robot = RobotEnemy(x=0.0, y=0.0, aggro_range=10.0)
        player = _Player(x=5000.0, y=5000.0)
        result = ai.update(
            [robot], player, None, dt=0.016,
            event_bus=_Bus(), combat_system=_MockCombat(),
        )
        assert result == []

    def test_update_multiple_attackers_returns_multiple_projectiles(self) -> None:
        ai = AISystem()
        combat = _MockCombat()
        player = _Player(x=100.0, y=100.0)

        robots = []
        for _ in range(3):
            r = _robot(attack_cooldown=0.5, attack_range=2000.0)
            r.attack_timer = 0.6
            robots.append(r)

        result = ai.update(
            robots, player, None, dt=0.0,
            event_bus=_Bus(), combat_system=combat,
        )
        assert len(result) == 3
        assert all(isinstance(p, Projectile) for p in result)
