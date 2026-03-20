"""Integration and E2E tests: AI system + CombatSystem + RobotEnemy pipeline.

These tests exercise multiple components working together without a full
GameScene:
  - AISystem fires real Projectile objects via CombatSystem.fire()
  - CombatSystem resolves enemy-fired projectiles against a player stub
  - CombatSystem resolves player-fired projectiles against robots
  - Full robot kill flow: player fires → robot HP → 0 → DEAD → enemy_killed
  - Self-hit prevention: enemy projectile owner check prevents friendly damage

Run: pytest tests/test_robot_ai_integration.py
"""
from __future__ import annotations

import pytest
import pygame

from src.entities.robot_enemy import AIState, RobotEnemy
from src.entities.projectile import Projectile
from src.systems.ai_system import AISystem, _DEATH_ANIM_DURATION
from src.systems.combat import CombatSystem


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _Player:
    """Minimal player stub: has rect, center, take_damage, and alive flag."""

    def __init__(self, x: float = 300.0, y: float = 100.0) -> None:
        self.x = x
        self.y = y
        self.width = 32
        self.height = 48
        self.alive = True
        self.rect = pygame.Rect(int(x), int(y), 32, 48)
        self.damage_received: list[int] = []

    def take_damage(self, amount: int) -> None:
        self.damage_received.append(amount)

    @property
    def center(self) -> tuple[float, float]:
        return float(self.rect.centerx), float(self.rect.centery)


class _Bus:
    """Minimal event bus that records all emissions for assertions."""

    def __init__(self) -> None:
        self.emitted: list[tuple[str, dict]] = []

    def emit(self, event: str, **kwargs) -> None:
        self.emitted.append((event, kwargs))

    def all_events(self, name: str) -> list[dict]:
        return [payload for ev, payload in self.emitted if ev == name]

    def first_event(self, name: str) -> dict:
        for ev, payload in self.emitted:
            if ev == name:
                return payload
        raise KeyError(f"No event {name!r} emitted")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_robot(**overrides) -> RobotEnemy:
    defaults = dict(
        x=100.0, y=100.0, hp=50,
        move_speed=80.0, attack_range=2000.0,
        attack_damage=10, attack_cooldown=0.5,
        aggro_range=2000.0, type_id="grunt",
    )
    defaults.update(overrides)
    return RobotEnemy(**defaults)


def _overlapping_proj(target, damage: int = 20, owner=None) -> Projectile:
    """Return a stationary Projectile whose rect overlaps *target*.rect."""
    return Projectile(target.rect.x, target.rect.y, 0.0, 0.0, damage, owner=owner)


# ===========================================================================
# Integration: AISystem + CombatSystem fire pipeline
# ===========================================================================

class TestAISystemCombatSystemIntegration:
    """AISystem.update() with a real CombatSystem returns live Projectile objects."""

    def test_update_returns_real_projectile_instance(self) -> None:
        ai = AISystem()
        combat = CombatSystem()
        robot = _make_robot()
        robot.state = AIState.ATTACK
        robot.attack_timer = 0.6     # past cooldown
        player = _Player()
        bus = _Bus()

        projs = ai.update([robot], player, None, dt=0.0, event_bus=bus,
                          combat_system=combat)

        assert len(projs) == 1
        assert isinstance(projs[0], Projectile)

    def test_projectile_owner_is_the_firing_robot(self) -> None:
        ai = AISystem()
        combat = CombatSystem()
        robot = _make_robot()
        robot.state = AIState.ATTACK
        robot.attack_timer = 0.6
        player = _Player()
        bus = _Bus()

        projs = ai.update([robot], player, None, dt=0.0, event_bus=bus,
                          combat_system=combat)

        assert projs[0].owner is robot

    def test_projectile_damage_equals_enemy_attack_damage(self) -> None:
        ai = AISystem()
        combat = CombatSystem()
        robot = _make_robot(attack_damage=25)
        robot.state = AIState.ATTACK
        robot.attack_timer = 0.6
        player = _Player()
        bus = _Bus()

        projs = ai.update([robot], player, None, dt=0.0, event_bus=bus,
                          combat_system=combat)

        assert projs[0].damage == 25

    def test_enemy_projectile_deals_damage_to_player_on_collision(self) -> None:
        """Projectile created by the enemy, when placed on the player, registers a hit."""
        combat = CombatSystem()
        player = _Player(x=200.0, y=200.0)
        # Stationary projectile placed exactly at player's rect — guaranteed overlap
        proj = _overlapping_proj(player, damage=15, owner=object())

        combat.update([proj], [player], dt=0.016)

        assert len(player.damage_received) == 1
        assert player.damage_received[0] == 15

    def test_enemy_projectile_does_not_hit_its_own_owner(self) -> None:
        """CombatSystem skips self-hits via the owner check."""
        combat = CombatSystem()
        robot = _make_robot(hp=50)
        proj = _overlapping_proj(robot, damage=99, owner=robot)

        combat.update([proj], [robot], dt=0.016)

        # HP unchanged — owner skipped
        assert robot.hp == 50

    def test_player_projectile_reduces_robot_hp(self) -> None:
        """Player fires at robot → CombatSystem.update resolves the hit."""
        combat = CombatSystem()
        player = _Player(x=0.0, y=0.0)
        robot = _make_robot(x=300.0, y=300.0, hp=50)

        # fire() creates a Projectile; move it onto the robot for a guaranteed hit
        proj = combat.fire(player, float(robot.rect.centerx),
                           float(robot.rect.centery), damage=20)
        proj.rect.x = robot.rect.x
        proj.rect.y = robot.rect.y

        combat.update([proj], [robot], dt=0.016)

        assert robot.hp == 30

    def test_multiple_enemies_attacking_return_one_projectile_each(self) -> None:
        ai = AISystem()
        combat = CombatSystem()
        player = _Player()
        bus = _Bus()

        robots = []
        for _ in range(3):
            r = _make_robot(attack_cooldown=0.5, attack_range=2000.0)
            r.state = AIState.ATTACK
            r.attack_timer = 0.6
            robots.append(r)

        projs = ai.update(robots, player, None, dt=0.0, event_bus=bus,
                          combat_system=combat)

        assert len(projs) == 3
        assert all(isinstance(p, Projectile) for p in projs)

    def test_dead_robot_fires_no_projectile(self) -> None:
        """A robot with alive=False must be skipped; update() returns empty list."""
        ai = AISystem()
        combat = CombatSystem()
        robot = _make_robot()
        robot.alive = False
        bus = _Bus()

        projs = ai.update([robot], _Player(), None, dt=0.016,
                          event_bus=bus, combat_system=combat)

        assert projs == []


# ===========================================================================
# E2E: complete robot kill flow
# ===========================================================================

class TestRobotKillFlowE2E:
    """Happy-path end-to-end: player fires → robot dies → enemy_killed emitted."""

    def test_player_shot_kills_robot_then_emits_enemy_killed(self) -> None:
        """Full kill sequence: fire → collision → DEAD state → event emitted."""
        combat = CombatSystem()
        ai = AISystem()
        bus = _Bus()

        robot = _make_robot(hp=10, xp_reward=25)
        robot.state = AIState.PATROL
        player = _Player(x=5000.0, y=5000.0)  # far away: no aggro this frame

        # Place a killing blow on the robot
        proj = _overlapping_proj(robot, damage=20, owner=player)
        combat.update([proj], [robot], dt=0.016)

        # Robot should now be DEAD
        assert robot.state == AIState.DEAD

        # Let the death animation run to completion
        ai.update([robot], player, None,
                  dt=_DEATH_ANIM_DURATION + 0.1, event_bus=bus)

        assert any(ev == "enemy_killed" for ev, _ in bus.emitted)

    def test_enemy_killed_payload_contains_correct_xp_reward(self) -> None:
        combat = CombatSystem()
        ai = AISystem()
        bus = _Bus()

        robot = _make_robot(hp=10, xp_reward=42)
        robot.state = AIState.PATROL
        player = _Player(x=5000.0, y=5000.0)

        proj = _overlapping_proj(robot, damage=50, owner=player)
        combat.update([proj], [robot], dt=0.016)
        ai.update([robot], player, None,
                  dt=_DEATH_ANIM_DURATION + 0.1, event_bus=bus)

        payload = bus.first_event("enemy_killed")
        assert payload["xp_reward"] == 42

    def test_robot_alive_false_after_full_death_animation(self) -> None:
        combat = CombatSystem()
        ai = AISystem()
        bus = _Bus()

        robot = _make_robot(hp=10)
        robot.state = AIState.PATROL
        player = _Player(x=5000.0, y=5000.0)

        proj = _overlapping_proj(robot, damage=50, owner=player)
        combat.update([proj], [robot], dt=0.016)
        ai.update([robot], player, None,
                  dt=_DEATH_ANIM_DURATION + 0.1, event_bus=bus)

        assert robot.alive is False

    def test_enemy_killed_emitted_exactly_once_across_multiple_ai_updates(self) -> None:
        """Death event must fire exactly once even if AI.update() called again."""
        combat = CombatSystem()
        ai = AISystem()
        bus = _Bus()

        robot = _make_robot(hp=10)
        player = _Player(x=5000.0, y=5000.0)

        proj = _overlapping_proj(robot, damage=50, owner=player)
        combat.update([proj], [robot], dt=0.016)

        # First call: animation completes, event fires, alive → False
        ai.update([robot], player, None,
                  dt=_DEATH_ANIM_DURATION + 0.1, event_bus=bus)
        # Second call: robot.alive is False → skipped entirely
        ai.update([robot], player, None, dt=1.0, event_bus=bus)

        assert len(bus.all_events("enemy_killed")) == 1

    def test_enemy_fires_at_player_and_projectile_resolves_hit(self) -> None:
        """Full loop: enemy attacks → projectile collected → resolved against player."""
        ai = AISystem()
        combat = CombatSystem()
        bus = _Bus()

        # Put enemy and player close enough to be in ATTACK range
        robot = _make_robot(x=100.0, y=100.0,
                            attack_damage=10, attack_cooldown=0.5,
                            attack_range=2000.0)
        robot.state = AIState.ATTACK
        robot.attack_timer = 0.6      # past cooldown
        player = _Player(x=200.0, y=100.0)

        # AISystem fires a projectile via CombatSystem
        projs = ai.update([robot], player, None, dt=0.0,
                          event_bus=bus, combat_system=combat)
        assert len(projs) == 1

        # Manually place the projectile on the player to guarantee a hit
        proj = projs[0]
        proj.rect.x = player.rect.x
        proj.rect.y = player.rect.y

        combat.update(projs, [player], dt=0.016)

        assert len(player.damage_received) == 1
        assert player.damage_received[0] == 10
