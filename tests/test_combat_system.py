"""Tests for CombatSystem — projectile collision and damage pipeline.

Covers:
  - Projectile hits entity → take_damage called
  - Dead projectile skipped
  - Dead entity skipped
  - Owner is never hit by its own projectile
  - Entity without take_damage does not crash CombatSystem
  - Projectile dies after hitting a valid entity
  - Effective armor (get_effective_armor) reduces raw damage in CombatSystem
  - Effective damage is at minimum 1 even when armor exceeds raw damage
  - fire() creates a Projectile aimed at the target
"""
import pytest
import pygame

from src.systems.combat import CombatSystem
from src.entities.projectile import Projectile


# ---------------------------------------------------------------------------
# Mock entities
# ---------------------------------------------------------------------------

class _Entity:
    """Minimal entity that records calls to take_damage."""
    def __init__(self, x=100, y=100, alive=True, armor=0):
        self.rect = pygame.Rect(x, y, 28, 48)
        self.alive = alive
        self._armor = armor
        self.damage_log: list = []

    def take_damage(self, amount: int) -> int:
        self.damage_log.append(amount)
        return amount

    def get_effective_armor(self) -> float:
        return float(self._armor)

    @property
    def center(self):
        return float(self.rect.centerx), float(self.rect.centery)


class _EntityNoTakeDamage:
    """Entity that lacks take_damage — CombatSystem must handle it gracefully."""
    def __init__(self):
        self.rect = pygame.Rect(100, 100, 28, 48)
        self.alive = True

    @property
    def center(self):
        return float(self.rect.centerx), float(self.rect.centery)


def _overlapping_proj(target, damage=30, owner=None):
    """Return a live Projectile whose rect overlaps target.rect."""
    proj = Projectile(target.rect.x, target.rect.y, vx=0, vy=0,
                      damage=damage, owner=owner)
    return proj


@pytest.fixture()
def cs():
    return CombatSystem()


# ---------------------------------------------------------------------------
# Basic collision
# ---------------------------------------------------------------------------

class TestBasicCollision:
    def test_projectile_calls_take_damage(self, cs):
        entity = _Entity()
        proj = _overlapping_proj(entity, damage=20)
        cs.update([proj], [entity], dt=0.016)
        assert len(entity.damage_log) == 1

    def test_projectile_dies_after_hit(self, cs):
        entity = _Entity()
        proj = _overlapping_proj(entity, damage=20)
        cs.update([proj], [entity], dt=0.016)
        assert proj.alive is False

    def test_non_overlapping_projectile_does_not_hit(self, cs):
        entity = _Entity(x=100, y=100)
        proj = Projectile(x=900, y=900, vx=0, vy=0, damage=20, owner=None)
        cs.update([proj], [entity], dt=0.016)
        assert len(entity.damage_log) == 0
        assert proj.alive is True

    def test_dead_projectile_skipped(self, cs):
        entity = _Entity()
        proj = _overlapping_proj(entity, damage=20)
        proj.alive = False
        cs.update([proj], [entity], dt=0.016)
        assert len(entity.damage_log) == 0

    def test_dead_entity_skipped(self, cs):
        entity = _Entity(alive=False)
        proj = _overlapping_proj(entity, damage=20)
        cs.update([proj], [entity], dt=0.016)
        assert len(entity.damage_log) == 0

    def test_owner_not_hit_by_own_projectile(self, cs):
        owner = _Entity()
        proj = _overlapping_proj(owner, damage=20, owner=owner)
        cs.update([proj], [owner], dt=0.016)
        assert len(owner.damage_log) == 0
        assert proj.alive is True   # never consumed

    def test_entity_without_take_damage_does_not_crash(self, cs):
        entity = _EntityNoTakeDamage()
        proj = _overlapping_proj(entity, damage=20)
        cs.update([proj], [entity], dt=0.016)  # must not raise
        assert proj.alive is False  # projectile still consumed

    def test_empty_lists_do_not_crash(self, cs):
        cs.update([], [], dt=0.016)

    def test_multiple_projectiles_each_hit_once(self, cs):
        e1 = _Entity(x=50, y=50)
        e2 = _Entity(x=200, y=200)
        p1 = _overlapping_proj(e1, damage=10)
        p2 = _overlapping_proj(e2, damage=10)
        cs.update([p1, p2], [e1, e2], dt=0.016)
        assert len(e1.damage_log) == 1
        assert len(e2.damage_log) == 1


# ---------------------------------------------------------------------------
# Armor-aware damage pipeline
# ---------------------------------------------------------------------------

class TestArmorDamagePipeline:
    """These tests validate the refactored pipeline where CombatSystem calls
    target.get_effective_armor() to compute effective damage before passing
    it to take_damage.  Tests will fail until task 9 of the feature plan is
    implemented."""

    def test_armor_reduces_damage_received(self, cs):
        # Entity with 20 armor, hit for 30 raw → effective ≤ 29
        entity = _Entity(armor=20)
        proj = _overlapping_proj(entity, damage=30)
        cs.update([proj], [entity], dt=0.016)
        assert len(entity.damage_log) == 1
        assert entity.damage_log[0] < 30

    def test_armor_equals_raw_damage_results_in_min_one(self, cs):
        # armor ≥ damage → effective = max(1, 0) = 1
        entity = _Entity(armor=50)
        proj = _overlapping_proj(entity, damage=30)
        cs.update([proj], [entity], dt=0.016)
        assert entity.damage_log[0] >= 1

    def test_higher_armor_means_lower_damage(self, cs):
        low_armor = _Entity(x=100, y=100, armor=5)
        high_armor = _Entity(x=400, y=400, armor=25)
        p1 = _overlapping_proj(low_armor,  damage=30)
        p2 = _overlapping_proj(high_armor, damage=30)
        cs.update([p1, p2], [low_armor, high_armor], dt=0.016)
        assert low_armor.damage_log[0] > high_armor.damage_log[0]

    def test_zero_armor_takes_full_raw_damage(self, cs):
        entity = _Entity(armor=0)
        proj = _overlapping_proj(entity, damage=25)
        cs.update([proj], [entity], dt=0.016)
        assert entity.damage_log[0] == 25

    def test_entity_without_get_effective_armor_still_receives_full_damage(self, cs):
        """Entities that don't expose get_effective_armor get hit for full damage."""
        class _SimpleEntity:
            rect = pygame.Rect(100, 100, 28, 48)
            alive = True
            damage_log: list = []

            def take_damage(self, amount):
                self.damage_log.append(amount)
                return amount

        entity = _SimpleEntity()
        entity.damage_log = []
        proj = Projectile(100, 100, 0, 0, damage=20, owner=None)
        cs.update([proj], [entity], dt=0.016)
        assert entity.damage_log[0] == 20


# ---------------------------------------------------------------------------
# fire() factory
# ---------------------------------------------------------------------------

class TestCombatFire:
    def test_fire_returns_projectile(self, cs):
        owner = _Entity(x=0, y=0)
        proj = cs.fire(owner, target_x=200, target_y=0, damage=15, speed=600)
        assert isinstance(proj, Projectile)

    def test_fire_sets_damage(self, cs):
        owner = _Entity(x=0, y=0)
        proj = cs.fire(owner, target_x=200, target_y=0, damage=25)
        assert proj.damage == 25

    def test_fire_sets_owner(self, cs):
        owner = _Entity(x=0, y=0)
        proj = cs.fire(owner, target_x=200, target_y=0)
        assert proj.owner is owner

    def test_fire_projectile_starts_alive(self, cs):
        owner = _Entity(x=0, y=0)
        proj = cs.fire(owner, target_x=200, target_y=0)
        assert proj.alive is True

    def test_fire_velocity_points_toward_target(self, cs):
        owner = _Entity(x=0, y=0)
        # Target is directly to the right → vx > 0, vy ≈ 0
        proj = cs.fire(owner, target_x=500, target_y=owner.rect.centery, damage=10)
        assert proj.vx > 0
        assert abs(proj.vy) < 1.0


# ---------------------------------------------------------------------------
# End-to-end: Player hit via CombatSystem with armor
# ---------------------------------------------------------------------------

class TestCombatPlayerEndToEnd:
    def test_player_health_decreases_after_combat_hit(self, cs):
        from src.entities.player import Player
        player = Player(x=100, y=100)
        player.armor = 0

        hp_before = getattr(player, 'current_health', player.health)
        proj = _overlapping_proj(player, damage=20)
        cs.update([proj], [player], dt=0.016)
        hp_after = getattr(player, 'current_health', player.health)

        assert hp_after < hp_before

    def test_player_with_armor_takes_less_damage_than_raw(self, cs):
        from src.entities.player import Player
        player = Player(x=100, y=100)
        player.armor = 20

        hp_before = getattr(player, 'current_health', player.health)
        proj = _overlapping_proj(player, damage=30)
        cs.update([proj], [player], dt=0.016)
        net_loss = hp_before - getattr(player, 'current_health', player.health)

        assert net_loss < 30   # armor absorbed some

    def test_player_dies_when_damage_exhausts_health(self, cs):
        from src.entities.player import Player
        player = Player(x=100, y=100)
        player.armor = 0

        proj = _overlapping_proj(player, damage=99999)
        cs.update([proj], [player], dt=0.016)

        hp = getattr(player, 'current_health', player.health)
        assert hp == 0
        assert player.alive is False
