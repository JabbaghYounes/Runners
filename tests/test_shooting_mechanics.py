# Run: pytest tests/test_shooting_mechanics.py
"""Tests for the shooting mechanics feature.

Covers:
  - WeaponState: initialization, stats, can_fire, needs_reload
  - WeaponSystem: fire cooldown, reload timer, try_fire, start_reload, events
  - ShootingSystem: mouse aim tracking, crosshair rendering, fire/reload dispatch
  - Projectile travel direction toward aimed position
  - Hit detection reduces target health (end-to-end with CombatSystem)
  - Configurable weapon stats via Weapon item
  - Magazine depletion triggers auto-reload
  - Reload on R key press
  - Crosshair rendered at mouse position
"""
from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock

import pygame
import pytest

from src.constants import DEFAULT_WEAPON_STATS
from src.systems.weapon_system import WeaponState, WeaponSystem
from src.systems.shooting_system import ShootingSystem
from src.entities.projectile import Projectile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeEntity:
    """Minimal entity with center and alive attributes."""

    def __init__(self, x: float = 100.0, y: float = 100.0, alive: bool = True):
        self.rect = pygame.Rect(int(x), int(y), 28, 48)
        self.alive = alive
        self.health = 100
        self.damage_log: list[int] = []

    @property
    def center(self):
        return (float(self.rect.centerx), float(self.rect.centery))

    def take_damage(self, amount: int) -> int:
        self.damage_log.append(amount)
        self.health -= amount
        if self.health <= 0:
            self.alive = False
        return amount


class _TrackingBus:
    """Minimal event bus that records emitted events."""

    def __init__(self):
        self.emitted: list[tuple[str, dict]] = []

    def emit(self, event: str, **kwargs):
        self.emitted.append((event, kwargs))

    def subscribe(self, event: str, callback):
        pass

    def unsubscribe(self, event: str, callback):
        pass

    def all_events(self, name: str) -> list[dict]:
        return [payload for ename, payload in self.emitted if ename == name]


def _make_mouse_event(event_type, pos=(400, 300), button=1):
    """Create a fake pygame event."""
    evt = pygame.event.Event(event_type)
    if event_type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        evt = pygame.event.Event(event_type, pos=pos, button=button)
    elif event_type == pygame.MOUSEMOTION:
        evt = pygame.event.Event(event_type, pos=pos, rel=(0, 0), buttons=(0, 0, 0))
    elif event_type == pygame.KEYDOWN:
        evt = pygame.event.Event(event_type, key=pos, mod=0)
    return evt


# ===========================================================================
# 1. WeaponState
# ===========================================================================

class TestWeaponState:
    """WeaponState initialization and property behavior."""

    def test_default_stats_match_constants(self):
        ws = WeaponState()
        assert ws.fire_rate == DEFAULT_WEAPON_STATS["fire_rate"]
        assert ws.damage == DEFAULT_WEAPON_STATS["damage"]
        assert ws.magazine_size == int(DEFAULT_WEAPON_STATS["magazine_size"])
        assert ws.reload_time == DEFAULT_WEAPON_STATS["reload_time"]

    def test_ammo_starts_at_magazine_size(self):
        ws = WeaponState(magazine_size=30)
        assert ws.ammo == 30

    def test_can_fire_when_ammo_and_no_cooldown(self):
        ws = WeaponState()
        assert ws.can_fire is True

    def test_cannot_fire_when_reloading(self):
        ws = WeaponState()
        ws.reloading = True
        assert ws.can_fire is False

    def test_cannot_fire_when_on_cooldown(self):
        ws = WeaponState()
        ws.fire_cooldown = 0.5
        assert ws.can_fire is False

    def test_cannot_fire_when_empty_magazine(self):
        ws = WeaponState()
        ws.ammo = 0
        assert ws.can_fire is False

    def test_needs_reload_when_empty_and_not_reloading(self):
        ws = WeaponState()
        ws.ammo = 0
        assert ws.needs_reload is True

    def test_does_not_need_reload_when_reloading(self):
        ws = WeaponState()
        ws.ammo = 0
        ws.reloading = True
        assert ws.needs_reload is False

    def test_does_not_need_reload_when_has_ammo(self):
        ws = WeaponState()
        assert ws.needs_reload is False

    def test_fire_interval_calculation(self):
        ws = WeaponState(fire_rate=10.0)
        assert ws.fire_interval == pytest.approx(0.1)

    def test_fire_interval_zero_fire_rate(self):
        ws = WeaponState(fire_rate=0.0)
        assert ws.fire_interval == 1.0

    def test_custom_stats(self):
        ws = WeaponState(
            fire_rate=8.0,
            damage=25.0,
            magazine_size=20,
            reload_time=2.0,
            projectile_speed=800.0,
        )
        assert ws.fire_rate == 8.0
        assert ws.damage == 25.0
        assert ws.magazine_size == 20
        assert ws.reload_time == 2.0
        assert ws.projectile_speed == 800.0
        assert ws.ammo == 20

    def test_load_from_weapon_item(self):
        """WeaponState.load_from_weapon copies stats from a Weapon item."""
        from src.inventory.item import Weapon
        weapon = Weapon(
            item_id="rifle_01",
            name="Test Rifle",
            rarity="common",
            damage=30,
            fire_rate=6.0,
            magazine_size=25,
            stats={"reload_time": 2.5, "projectile_speed": 700.0},
        )
        ws = WeaponState()
        ws.load_from_weapon(weapon)
        assert ws.damage == 30.0
        assert ws.fire_rate == 6.0
        assert ws.magazine_size == 25
        assert ws.reload_time == 2.5
        assert ws.ammo == 25


# ===========================================================================
# 2. WeaponSystem — cooldowns and firing
# ===========================================================================

class TestWeaponSystem:
    """WeaponSystem tick, fire, and reload logic."""

    def test_cooldown_decreases_over_time(self):
        bus = _TrackingBus()
        ws_sys = WeaponSystem(event_bus=bus)
        state = WeaponState()
        state.fire_cooldown = 0.5

        ws_sys.update(state, dt=0.2)
        assert state.fire_cooldown == pytest.approx(0.3, abs=1e-6)

    def test_cooldown_clamps_to_zero(self):
        ws_sys = WeaponSystem()
        state = WeaponState()
        state.fire_cooldown = 0.01

        ws_sys.update(state, dt=1.0)
        assert state.fire_cooldown == 0.0

    def test_reload_timer_counts_down(self):
        bus = _TrackingBus()
        ws_sys = WeaponSystem(event_bus=bus)
        state = WeaponState(reload_time=1.5)
        state.reloading = True
        state.reload_timer = 1.5

        ws_sys.update(state, dt=0.5)
        assert state.reloading is True
        assert state.reload_timer == pytest.approx(1.0, abs=1e-6)

    def test_reload_completes_and_refills_ammo(self):
        bus = _TrackingBus()
        ws_sys = WeaponSystem(event_bus=bus)
        state = WeaponState(magazine_size=12, reload_time=1.0)
        state.ammo = 0
        state.reloading = True
        state.reload_timer = 0.5

        ws_sys.update(state, dt=1.0)
        assert state.reloading is False
        assert state.ammo == 12

    def test_reload_complete_event_emitted(self):
        bus = _TrackingBus()
        ws_sys = WeaponSystem(event_bus=bus)
        state = WeaponState(reload_time=1.0)
        state.reloading = True
        state.reload_timer = 0.01

        ws_sys.update(state, dt=0.1)
        events = bus.all_events("reload_complete")
        assert len(events) == 1

    def test_try_fire_returns_projectile(self):
        bus = _TrackingBus()
        ws_sys = WeaponSystem(event_bus=bus)
        state = WeaponState()
        owner = _FakeEntity(x=0, y=0)

        proj = ws_sys.try_fire(state, owner, target_x=200.0, target_y=0.0)
        assert proj is not None
        assert isinstance(proj, Projectile)

    def test_try_fire_decrements_ammo(self):
        ws_sys = WeaponSystem()
        state = WeaponState(magazine_size=5)
        owner = _FakeEntity()

        ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert state.ammo == 4

    def test_try_fire_sets_cooldown(self):
        ws_sys = WeaponSystem()
        state = WeaponState(fire_rate=10.0)
        owner = _FakeEntity()

        ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert state.fire_cooldown == pytest.approx(0.1)

    def test_try_fire_emits_weapon_fired_event(self):
        bus = _TrackingBus()
        ws_sys = WeaponSystem(event_bus=bus)
        state = WeaponState()
        owner = _FakeEntity()

        ws_sys.try_fire(state, owner, 200.0, 200.0)
        events = bus.all_events("weapon_fired")
        assert len(events) == 1
        assert events[0]["owner"] is owner

    def test_try_fire_returns_none_when_reloading(self):
        ws_sys = WeaponSystem()
        state = WeaponState()
        state.reloading = True
        owner = _FakeEntity()

        proj = ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert proj is None

    def test_try_fire_returns_none_on_cooldown(self):
        ws_sys = WeaponSystem()
        state = WeaponState()
        state.fire_cooldown = 1.0
        owner = _FakeEntity()

        proj = ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert proj is None

    def test_try_fire_returns_none_empty_mag(self):
        ws_sys = WeaponSystem()
        state = WeaponState()
        state.ammo = 0
        owner = _FakeEntity()

        proj = ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert proj is None

    def test_auto_reload_on_empty_magazine(self):
        bus = _TrackingBus()
        ws_sys = WeaponSystem(event_bus=bus)
        state = WeaponState(magazine_size=1, reload_time=1.5)
        owner = _FakeEntity()

        ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert state.ammo == 0
        assert state.reloading is True

    def test_start_reload_sets_timer(self):
        bus = _TrackingBus()
        ws_sys = WeaponSystem(event_bus=bus)
        state = WeaponState(reload_time=2.0, magazine_size=10)
        state.ammo = 5

        result = ws_sys.start_reload(state)
        assert result is True
        assert state.reloading is True
        assert state.reload_timer == 2.0

    def test_start_reload_emits_event(self):
        bus = _TrackingBus()
        ws_sys = WeaponSystem(event_bus=bus)
        state = WeaponState(reload_time=2.0, magazine_size=10)
        state.ammo = 5

        ws_sys.start_reload(state)
        events = bus.all_events("reload_start")
        assert len(events) == 1
        assert events[0]["reload_time"] == 2.0

    def test_start_reload_noop_when_already_reloading(self):
        ws_sys = WeaponSystem()
        state = WeaponState()
        state.reloading = True

        result = ws_sys.start_reload(state)
        assert result is False

    def test_start_reload_noop_when_full(self):
        ws_sys = WeaponSystem()
        state = WeaponState(magazine_size=12)

        result = ws_sys.start_reload(state)
        assert result is False

    def test_projectile_velocity_toward_target(self):
        ws_sys = WeaponSystem()
        state = WeaponState(projectile_speed=600.0)
        # Entity centered at roughly (14, 24)
        owner = _FakeEntity(x=0, y=0)
        cx, cy = owner.center

        # Target directly to the right
        proj = ws_sys.try_fire(state, owner, target_x=cx + 500, target_y=cy)
        assert proj.vx > 0
        assert abs(proj.vy) < 1.0

    def test_projectile_velocity_toward_target_diagonal(self):
        ws_sys = WeaponSystem()
        state = WeaponState(projectile_speed=600.0)
        owner = _FakeEntity(x=0, y=0)
        cx, cy = owner.center

        # Target to the bottom-right
        proj = ws_sys.try_fire(state, owner, target_x=cx + 100, target_y=cy + 100)
        assert proj.vx > 0
        assert proj.vy > 0

    def test_projectile_damage_matches_weapon_state(self):
        ws_sys = WeaponSystem()
        state = WeaponState(damage=42.0)
        owner = _FakeEntity()

        proj = ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert proj.damage == 42

    def test_projectile_owner_is_set(self):
        ws_sys = WeaponSystem()
        state = WeaponState()
        owner = _FakeEntity()

        proj = ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert proj.owner is owner

    def test_rapid_fire_respects_cooldown(self):
        ws_sys = WeaponSystem()
        state = WeaponState(fire_rate=2.0)  # 0.5s between shots
        owner = _FakeEntity()

        # First shot succeeds
        p1 = ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert p1 is not None

        # Immediate second shot fails (cooldown)
        p2 = ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert p2 is None

        # After cooldown expires
        ws_sys.update(state, dt=0.5)
        p3 = ws_sys.try_fire(state, owner, 200.0, 200.0)
        assert p3 is not None


# ===========================================================================
# 3. ShootingSystem — input, aim, crosshair
# ===========================================================================

class TestShootingSystem:
    """ShootingSystem input handling and crosshair."""

    def test_mouse_motion_updates_aim(self):
        ss = ShootingSystem()
        evt = _make_mouse_event(pygame.MOUSEMOTION, pos=(500, 400))
        ss.handle_events([evt])
        assert ss.aim_screen_pos == (500.0, 400.0)

    def test_aim_world_pos_accounts_for_camera_offset(self):
        ss = ShootingSystem()
        evt = _make_mouse_event(pygame.MOUSEMOTION, pos=(100, 200))
        ss.handle_events([evt])

        player = _FakeEntity()
        ss.update(player, dt=0.016, camera_offset=(50.0, 30.0))
        assert ss.aim_world_pos == (150.0, 230.0)

    def test_left_click_fires_projectile(self):
        ss = ShootingSystem()
        # Move mouse, then click
        move_evt = _make_mouse_event(pygame.MOUSEMOTION, pos=(300, 300))
        click_evt = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(300, 300), button=1)
        ss.handle_events([move_evt, click_evt])

        player = _FakeEntity(x=0, y=0)
        new_projs = ss.update(player, dt=0.016)
        assert len(new_projs) == 1
        assert isinstance(new_projs[0], Projectile)

    def test_right_click_does_not_fire(self):
        ss = ShootingSystem()
        click_evt = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(300, 300), button=3)
        ss.handle_events([click_evt])

        player = _FakeEntity()
        new_projs = ss.update(player, dt=0.016)
        assert len(new_projs) == 0

    def test_mouse_up_stops_firing(self):
        ss = ShootingSystem()
        down = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(300, 300), button=1)
        up = _make_mouse_event(pygame.MOUSEBUTTONUP, pos=(300, 300), button=1)
        ss.handle_events([down])

        player = _FakeEntity()
        projs1 = ss.update(player, dt=0.016)
        assert len(projs1) == 1

        # Release and advance past cooldown
        ss.handle_events([up])
        ss.update(player, dt=1.0)  # advance past cooldown
        projs2 = ss.update(player, dt=0.016)
        assert len(projs2) == 0

    def test_r_key_triggers_reload(self):
        bus = _TrackingBus()
        ss = ShootingSystem(event_bus=bus)
        # Deplete some ammo first
        ss._weapon_state.ammo = 5

        r_evt = _make_mouse_event(pygame.KEYDOWN, pos=pygame.K_r)
        ss.handle_events([r_evt])

        player = _FakeEntity()
        ss.update(player, dt=0.016)

        events = bus.all_events("reload_start")
        assert len(events) == 1

    def test_crosshair_renders_without_error(self):
        ss = ShootingSystem()
        move_evt = _make_mouse_event(pygame.MOUSEMOTION, pos=(640, 360))
        ss.handle_events([move_evt])

        screen = pygame.Surface((1280, 720))
        ss.render_crosshair(screen)  # Should not raise

    def test_dead_player_cannot_fire(self):
        ss = ShootingSystem()
        click = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(300, 300), button=1)
        ss.handle_events([click])

        player = _FakeEntity(alive=False)
        projs = ss.update(player, dt=0.016)
        assert len(projs) == 0

    def test_equip_weapon_updates_stats(self):
        from src.inventory.item import Weapon
        weapon = Weapon(
            item_id="smg_01",
            name="Test SMG",
            rarity="uncommon",
            damage=12,
            fire_rate=10.0,
            magazine_size=30,
            stats={"reload_time": 1.8},
        )
        ss = ShootingSystem()
        ss.equip_weapon(weapon)

        assert ss.weapon_state.damage == 12.0
        assert ss.weapon_state.fire_rate == 10.0
        assert ss.weapon_state.magazine_size == 30
        assert ss.weapon_state.reload_time == 1.8

    def test_equip_none_resets_to_defaults(self):
        ss = ShootingSystem()
        ss._weapon_state.damage = 999
        ss.equip_weapon(None)
        assert ss.weapon_state.damage == DEFAULT_WEAPON_STATS["damage"]

    def test_held_fire_produces_projectiles_at_fire_rate(self):
        """Holding LMB should produce projectiles at the weapon's fire rate."""
        ss = ShootingSystem()
        ss._weapon_state.fire_rate = 5.0  # 5 rounds/sec = 0.2s interval

        click = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(300, 300), button=1)
        ss.handle_events([click])

        player = _FakeEntity()
        total_projs = 0

        # Simulate 1 second of updates at 60fps
        for _ in range(60):
            projs = ss.update(player, dt=1.0 / 60)
            total_projs += len(projs)

        # At 5 rounds/sec over 1 second, expect 5 shots (+/- 1 for timing)
        assert 4 <= total_projs <= 6


# ===========================================================================
# 4. End-to-end: fire projectile -> hit target -> reduce health
# ===========================================================================

class TestShootingEndToEnd:
    """Projectile fired via ShootingSystem hits a target via CombatSystem."""

    def test_fired_projectile_hits_target_and_reduces_health(self):
        from src.systems.combat import CombatSystem

        bus = _TrackingBus()
        ss = ShootingSystem(event_bus=bus)
        ss._weapon_state.damage = 25.0

        # Position mouse over target
        move = _make_mouse_event(pygame.MOUSEMOTION, pos=(200, 200))
        click = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(200, 200), button=1)
        ss.handle_events([move, click])

        player = _FakeEntity(x=0, y=0)
        target = _FakeEntity(x=200, y=200)
        initial_hp = target.health

        projs = ss.update(player, dt=0.016)
        assert len(projs) >= 1

        # Move projectile to overlap with target
        proj = projs[0]
        proj.rect.x = target.rect.x
        proj.rect.y = target.rect.y

        combat = CombatSystem()
        combat.update(projs, [target], dt=0.016)

        assert target.health < initial_hp
        assert len(target.damage_log) == 1
        assert target.damage_log[0] == 25

    def test_projectile_travels_toward_aim_direction(self):
        ss = ShootingSystem()
        # Aim to the right of the player
        move = _make_mouse_event(pygame.MOUSEMOTION, pos=(500, 124))
        click = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(500, 124), button=1)
        ss.handle_events([move, click])

        player = _FakeEntity(x=0, y=100)
        projs = ss.update(player, dt=0.016)
        assert len(projs) == 1

        proj = projs[0]
        # Projectile should be moving to the right
        assert proj.vx > 0

    def test_magazine_depletion_and_reload_cycle(self):
        """Fire until empty, auto-reload triggers, wait for reload, fire again."""
        bus = _TrackingBus()
        ss = ShootingSystem(event_bus=bus)
        ss._weapon_state.magazine_size = 3
        ss._weapon_state.ammo = 3
        ss._weapon_state.fire_rate = 100.0  # fast fire rate
        ss._weapon_state.reload_time = 0.5

        click = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(300, 300), button=1)
        ss.handle_events([click])

        player = _FakeEntity()
        all_projs = []

        # Fire 3 shots rapidly
        for _ in range(3):
            projs = ss.update(player, dt=0.1)
            all_projs.extend(projs)

        assert len(all_projs) == 3
        assert ss.weapon_state.ammo == 0
        assert ss.weapon_state.reloading is True

        # Cannot fire during reload
        projs = ss.update(player, dt=0.016)
        assert len(projs) == 0

        # Wait for reload to complete
        ss.update(player, dt=1.0)
        assert ss.weapon_state.reloading is False
        assert ss.weapon_state.ammo == 3

        # Can fire again
        projs = ss.update(player, dt=0.016)
        assert len(projs) == 1

    def test_hit_detection_kills_target_at_zero_hp(self):
        """Projectile with enough damage kills the target."""
        from src.systems.combat import CombatSystem

        ss = ShootingSystem()
        ss._weapon_state.damage = 200.0  # lethal

        move = _make_mouse_event(pygame.MOUSEMOTION, pos=(100, 100))
        click = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(100, 100), button=1)
        ss.handle_events([move, click])

        player = _FakeEntity(x=0, y=0)
        target = _FakeEntity(x=100, y=100)

        projs = ss.update(player, dt=0.016)
        proj = projs[0]
        proj.rect.x = target.rect.x
        proj.rect.y = target.rect.y

        combat = CombatSystem()
        combat.update(projs, [target], dt=0.016)

        assert target.health <= 0
        assert target.alive is False


# ===========================================================================
# 5. Weapon stats from Weapon item
# ===========================================================================

class TestWeaponConfigurableStats:
    """Weapons from the inventory system provide configurable stats."""

    def test_different_weapons_have_different_fire_rates(self):
        from src.inventory.item import Weapon

        pistol = Weapon(
            item_id="pistol_01", name="Pistol", rarity="common",
            damage=15, fire_rate=3.0, magazine_size=12,
            stats={"reload_time": 1.5},
        )
        smg = Weapon(
            item_id="smg_01", name="SMG", rarity="uncommon",
            damage=10, fire_rate=10.0, magazine_size=30,
            stats={"reload_time": 2.0},
        )

        ws_pistol = WeaponState()
        ws_pistol.load_from_weapon(pistol)

        ws_smg = WeaponState()
        ws_smg.load_from_weapon(smg)

        assert ws_pistol.fire_rate == 3.0
        assert ws_smg.fire_rate == 10.0
        assert ws_pistol.damage == 15.0
        assert ws_smg.damage == 10.0
        assert ws_pistol.magazine_size == 12
        assert ws_smg.magazine_size == 30
        assert ws_pistol.reload_time == 1.5
        assert ws_smg.reload_time == 2.0

    def test_weapon_stats_via_stats_dict(self):
        from src.inventory.item import Weapon

        weapon = Weapon(
            item_id="custom_01", name="Custom Gun", rarity="rare",
            stats={
                "damage": 35,
                "fire_rate": 4.0,
                "magazine_size": 8,
                "reload_time": 3.0,
            },
        )
        ws = WeaponState()
        ws.load_from_weapon(weapon)
        assert ws.damage == 35.0
        assert ws.fire_rate == 4.0
        assert ws.magazine_size == 8
        assert ws.reload_time == 3.0


# ===========================================================================
# 6. Projectile basic behavior
# ===========================================================================

# ---------------------------------------------------------------------------
# Minimal tile-map stub used by tile-collision tests
# ---------------------------------------------------------------------------

class _MockTileMap:
    """Minimal tile map stub for tile-collision unit tests.

    Args:
        solid_cells: set of (col, row) tuples that are solid.
        cols:        optional int — the map width in tiles (to test positive edge).
        rows:        optional int — the map height in tiles (to test positive edge).
    """

    def __init__(self, solid_cells=None, cols=None, rows=None):
        self._solid = set(solid_cells or [])
        if cols is not None:
            self.cols = cols
        if rows is not None:
            self.rows = rows

    def is_solid(self, col: int, row: int) -> bool:
        return (col, row) in self._solid


class TestProjectileBasics:
    """Projectile entity update and TTL."""

    def test_projectile_moves_by_velocity(self):
        proj = Projectile(0, 0, vx=100, vy=0, damage=10)
        proj.update(dt=1.0)
        assert proj.rect.x == 100

    def test_projectile_dies_after_ttl(self):
        proj = Projectile(0, 0, vx=100, vy=0, damage=10)
        proj.update(dt=3.0)
        assert proj.alive is False

    def test_projectile_stays_alive_before_ttl(self):
        proj = Projectile(0, 0, vx=100, vy=0, damage=10)
        proj.update(dt=0.5)
        assert proj.alive is True

    def test_projectile_renders_without_error(self):
        proj = Projectile(50, 50, vx=100, vy=0, damage=10)
        screen = pygame.Surface((800, 600))
        proj.render(screen, (0, 0))  # Should not raise

    def test_dead_projectile_does_not_render(self):
        proj = Projectile(50, 50, vx=100, vy=0, damage=10)
        proj.alive = False
        screen = pygame.Surface((800, 600))
        proj.render(screen, (0, 0))  # Should not raise

    def test_projectile_collides_with_overlapping_entity(self):
        proj = Projectile(100, 100, vx=0, vy=0, damage=10)
        entity = _FakeEntity(x=100, y=100)
        assert proj.rect.colliderect(entity.rect)

    def test_projectile_does_not_collide_with_distant_entity(self):
        proj = Projectile(0, 0, vx=0, vy=0, damage=10)
        entity = _FakeEntity(x=500, y=500)
        assert not proj.rect.colliderect(entity.rect)

    # ------------------------------------------------------------------
    # Tile-collision despawn (Phase 1 Task 1 + Phase 2 Task 2)
    # ------------------------------------------------------------------

    def test_projectile_despawns_on_solid_tile_collision(self):
        """Projectile entering a solid tile is immediately despawned."""
        from src.constants import TILE_SIZE

        proj = Projectile(0, 0, vx=0, vy=0, damage=10)
        # center is at (rect.centerx, rect.centery) = (4, 2) → tile (0, 0)
        col = proj.rect.centerx // TILE_SIZE
        row = proj.rect.centery // TILE_SIZE
        tile_map = _MockTileMap(solid_cells={(col, row)})

        proj.update(dt=0.001, tile_map=tile_map)

        assert proj.alive is False

    def test_projectile_stays_alive_on_non_solid_tile(self):
        """Projectile in open air (non-solid tile) is not despawned."""
        proj = Projectile(0, 0, vx=0, vy=0, damage=10)
        tile_map = _MockTileMap(solid_cells=set())  # no solid tiles

        proj.update(dt=0.001, tile_map=tile_map)

        assert proj.alive is True

    def test_projectile_tile_map_none_does_not_crash(self):
        """Passing tile_map=None (no map) must not raise — backward compat."""
        proj = Projectile(0, 0, vx=100, vy=0, damage=10)

        proj.update(dt=0.016, tile_map=None)  # must not raise

        assert proj.alive is True  # TTL not exhausted

    def test_projectile_despawns_when_column_is_negative(self):
        """Projectile that exits the left edge of the world is despawned."""
        proj = Projectile(-200, 0, vx=0, vy=0, damage=10)
        # rect.centerx is negative → col < 0
        tile_map = _MockTileMap()

        proj.update(dt=0.001, tile_map=tile_map)

        assert proj.alive is False

    def test_projectile_despawns_when_row_is_negative(self):
        """Projectile that exits the top edge of the world is despawned."""
        proj = Projectile(0, -200, vx=0, vy=0, damage=10)
        # rect.centery is negative → row < 0
        tile_map = _MockTileMap()

        proj.update(dt=0.001, tile_map=tile_map)

        assert proj.alive is False

    def test_projectile_despawns_when_column_exceeds_map_width(self):
        """Projectile past the right edge (col >= cols) is despawned."""
        from src.constants import TILE_SIZE

        proj = Projectile(0, 0, vx=0, vy=0, damage=10)
        col = proj.rect.centerx // TILE_SIZE  # 0
        # Map has only col=0 width; col >= cols triggers despawn
        tile_map = _MockTileMap(solid_cells=set(), cols=0)

        proj.update(dt=0.001, tile_map=tile_map)

        assert proj.alive is False

    def test_projectile_despawns_when_row_exceeds_map_height(self):
        """Projectile past the bottom edge (row >= rows) is despawned."""
        from src.constants import TILE_SIZE

        proj = Projectile(0, 0, vx=0, vy=0, damage=10)
        row = proj.rect.centery // TILE_SIZE  # 0
        # Map has only row=0 height; row >= rows triggers despawn
        tile_map = _MockTileMap(solid_cells=set(), cols=999, rows=0)

        proj.update(dt=0.001, tile_map=tile_map)

        assert proj.alive is False

    def test_projectile_not_despawned_when_inside_map_without_size_attrs(self):
        """A map without cols/rows attributes skips positive-edge guard cleanly."""
        proj = Projectile(0, 0, vx=0, vy=0, damage=10)
        # _MockTileMap without cols/rows → no bounds attrs → rely on is_solid only
        tile_map = _MockTileMap(solid_cells=set())

        proj.update(dt=0.001, tile_map=tile_map)

        assert proj.alive is True  # open tile, no size guard → survives

    def test_solid_tile_check_uses_center_not_corner(self):
        """Tile lookup is based on projectile center, not top-left corner."""
        from src.constants import TILE_SIZE

        proj = Projectile(0, 0, vx=0, vy=0, damage=10)
        cx, cy = proj.rect.centerx, proj.rect.centery
        col = cx // TILE_SIZE
        row = cy // TILE_SIZE

        # Solid at (col+1, row) — a tile the center does NOT occupy
        tile_map = _MockTileMap(solid_cells={(col + 1, row)})
        proj.update(dt=0.001, tile_map=tile_map)

        assert proj.alive is True  # centre is not in a solid tile


# ===========================================================================
# 8. Weapon-swap ammo reset
# ===========================================================================

class TestWeaponSwapSync:
    """Equipping a new weapon resets ammo, cooldown, and reload state."""

    def test_load_from_weapon_resets_ammo_to_new_magazine_size(self):
        """Switching to a weapon immediately fills its magazine."""
        from src.inventory.item import Weapon

        weapon = Weapon(
            item_id="rifle_01", name="Test Rifle", rarity="common",
            damage=30, fire_rate=6.0, magazine_size=20,
            stats={"reload_time": 2.0},
        )
        ws = WeaponState(magazine_size=5)
        ws.ammo = 2  # partially depleted before swap

        ws.load_from_weapon(weapon)

        assert ws.ammo == 20

    def test_load_from_weapon_resets_fire_cooldown_to_zero(self):
        """Mid-cooldown is cleared on weapon equip."""
        from src.inventory.item import Weapon

        weapon = Weapon(
            item_id="smg_01", name="SMG", rarity="uncommon",
            damage=12, fire_rate=10.0, magazine_size=30,
            stats={"reload_time": 1.8},
        )
        ws = WeaponState()
        ws.fire_cooldown = 0.5  # mid-shot cooldown

        ws.load_from_weapon(weapon)

        assert ws.fire_cooldown == 0.0

    def test_load_from_weapon_cancels_active_reload(self):
        """An in-progress reload is cancelled when a new weapon is equipped."""
        from src.inventory.item import Weapon

        weapon = Weapon(
            item_id="pistol_01", name="Pistol", rarity="common",
            damage=15, fire_rate=3.0, magazine_size=12,
            stats={"reload_time": 1.5},
        )
        ws = WeaponState()
        ws.reloading = True
        ws.reload_timer = 1.2  # mid-reload

        ws.load_from_weapon(weapon)

        assert ws.reloading is False
        assert ws.reload_timer == 0.0

    def test_shooting_system_ammo_resets_when_equipped_weapon_changes(self):
        """ShootingSystem._sync_weapon_from_player resets ammo on weapon swap."""
        from src.inventory.item import Weapon

        weapon_a = Weapon(
            item_id="rifle_a", name="Rifle A", rarity="common",
            damage=25, fire_rate=5.0, magazine_size=20,
            stats={"reload_time": 2.0},
        )
        weapon_b = Weapon(
            item_id="pistol_b", name="Pistol B", rarity="common",
            damage=15, fire_rate=3.0, magazine_size=12,
            stats={"reload_time": 1.5},
        )

        # Minimal player-alike with swappable equipped_weapon
        class _PlayerWithInventory:
            alive = True

            def __init__(self, weapon):
                self._weapon = weapon

            @property
            def center(self):
                return (0.0, 0.0)

            @property
            def inventory(self):
                return self

            @property
            def equipped_weapon(self):
                return self._weapon

            @equipped_weapon.setter
            def equipped_weapon(self, val):
                self._weapon = val

        ss = ShootingSystem()
        player = _PlayerWithInventory(weapon_a)

        # First update syncs weapon_a
        ss.update(player, dt=0.016)
        assert ss.weapon_state.magazine_size == 20

        # Deplete some ammo
        ss._weapon_state.ammo = 5

        # Swap to weapon_b
        player._weapon = weapon_b
        ss.update(player, dt=0.016)

        assert ss.weapon_state.magazine_size == 12
        assert ss.weapon_state.ammo == 12  # reset to weapon_b's magazine

    def test_equip_none_weapon_resets_to_default_stats(self):
        """equip_weapon(None) reverts all stats to DEFAULT_WEAPON_STATS."""
        ss = ShootingSystem()
        ss._weapon_state.damage = 999
        ss._weapon_state.fire_rate = 0.1

        ss.equip_weapon(None)

        assert ss.weapon_state.damage == DEFAULT_WEAPON_STATS["damage"]
        assert ss.weapon_state.fire_rate == DEFAULT_WEAPON_STATS["fire_rate"]
        assert ss.weapon_state.ammo == int(DEFAULT_WEAPON_STATS["magazine_size"])


# ===========================================================================
# 7. Integration with Player entity
# ===========================================================================

class TestShootingWithPlayer:
    """Shooting system works with the real Player entity."""

    def test_player_can_fire_via_shooting_system(self):
        from src.entities.player import Player

        ss = ShootingSystem()
        player = Player(x=100, y=100)

        move = _make_mouse_event(pygame.MOUSEMOTION, pos=(400, 300))
        click = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(400, 300), button=1)
        ss.handle_events([move, click])

        projs = ss.update(player, dt=0.016)
        assert len(projs) == 1
        assert projs[0].owner is player

    def test_projectile_from_player_kills_robot_enemy(self):
        from src.entities.player import Player
        from src.entities.robot_enemy import RobotEnemy
        from src.systems.combat import CombatSystem

        ss = ShootingSystem()
        ss._weapon_state.damage = 200.0  # lethal

        player = Player(x=0, y=0)
        robot = RobotEnemy(x=200, y=100, hp=60)

        move = _make_mouse_event(pygame.MOUSEMOTION, pos=(200, 100))
        click = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(200, 100), button=1)
        ss.handle_events([move, click])

        projs = ss.update(player, dt=0.016)
        assert len(projs) == 1

        # Place projectile on top of robot
        projs[0].rect.x = robot.rect.x
        projs[0].rect.y = robot.rect.y

        combat = CombatSystem()
        combat.update(projs, [robot], dt=0.016)

        assert robot.hp <= 0
        assert robot.is_dead()

    def test_equipped_weapon_stats_used(self):
        from src.entities.player import Player
        from src.inventory.item import Weapon

        weapon = Weapon(
            item_id="rifle_01", name="Assault Rifle",
            rarity="rare", damage=30, fire_rate=8.0,
            magazine_size=25, stats={"reload_time": 2.0},
            weight=3.0,
        )

        ss = ShootingSystem()
        ss.equip_weapon(weapon)

        player = Player(x=0, y=0)

        move = _make_mouse_event(pygame.MOUSEMOTION, pos=(300, 300))
        click = _make_mouse_event(pygame.MOUSEBUTTONDOWN, pos=(300, 300), button=1)
        ss.handle_events([move, click])

        projs = ss.update(player, dt=0.016)
        assert len(projs) == 1
        assert projs[0].damage == 30
