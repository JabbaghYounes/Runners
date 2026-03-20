"""Integration tests for weapon attachment stat propagation through the combat pipeline.

Tests the integration layer between:
  - Weapon.effective_stat() and WeaponState.load_from_weapon() (critical fix)
  - attach_to_weapon() / detach_from_weapon() event emission
  - ShootingSystem subscription to 'weapon_attachment_changed'

This file does NOT duplicate the domain-layer tests already in
test_weapon_attachments.py. It focuses on the pipeline between components.

# Run: pytest tests/test_weapon_mod_integration.py
"""
from __future__ import annotations

from typing import Any

import pygame
import pytest

from src.inventory.item import Attachment, Rarity, Weapon
from src.inventory.inventory import Inventory
from src.inventory.weapon_attachments import attach_to_weapon, detach_from_weapon
from src.systems.weapon_system import WeaponState, WeaponSystem
from src.systems.shooting_system import ShootingSystem
from src.constants import DEFAULT_WEAPON_STATS


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _weapon(
    wid: str = "rifle_01",
    mod_slots: list[str] | None = None,
    damage: int = 30,
    fire_rate: float = 4.0,
    magazine_size: int = 20,
    stats: dict | None = None,
) -> Weapon:
    return Weapon(
        id=wid,
        name="Test Rifle",
        rarity=Rarity.COMMON,
        weight=3.0,
        base_value=200,
        stats=stats or {"range": 450, "reload_time": 2.0, "accuracy": 70},
        sprite_path="",
        damage=damage,
        fire_rate=fire_rate,
        magazine_size=magazine_size,
        mod_slots=mod_slots if mod_slots is not None else ["scope", "barrel", "grip"],
    )


def _attachment(
    aid: str = "scope_01",
    slot_type: str = "scope",
    stat_delta: dict | None = None,
    compatible_weapons: list[str] | None = None,
) -> Attachment:
    return Attachment(
        id=aid,
        name="Test Scope",
        rarity=Rarity.COMMON,
        weight=0.3,
        base_value=80,
        stats={},
        sprite_path="",
        slot_type=slot_type,
        compatible_weapons=compatible_weapons or [],
        stat_delta=stat_delta or {"accuracy": 10},
    )


class _FakePlayer:
    """Minimal player stub for ShootingSystem update/sync tests."""

    def __init__(self, weapon: Weapon | None = None) -> None:
        self.inventory = Inventory(max_slots=10, max_weight=50.0)
        if weapon is not None:
            self.inventory.add(weapon)
            self.inventory.equipped_weapon = weapon
        self.rect = pygame.Rect(100, 100, 28, 48)
        self.alive = True

    @property
    def center(self) -> tuple[float, float]:
        return (float(self.rect.centerx), float(self.rect.centery))


# ---------------------------------------------------------------------------
# WeaponState.load_from_weapon() must use effective_stat()
# ---------------------------------------------------------------------------


class TestWeaponStateLoadsEffectiveStats:
    """WeaponState must read Weapon.effective_stat() so attachment bonuses are
    reflected, not the raw base-stat properties.

    These tests fail against the current implementation (which reads
    getattr(weapon, 'damage', ...)) and pass after the fix.
    """

    def test_damage_without_attachments_matches_base_value(self):
        w = _weapon(damage=30)
        state = WeaponState()
        state.load_from_weapon(w)
        assert state.damage == pytest.approx(30.0)

    def test_damage_with_scope_attachment_is_boosted(self):
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        state = WeaponState()
        state.load_from_weapon(w)
        assert state.damage == pytest.approx(40.0)

    def test_damage_with_suppressor_attachment_is_reduced(self):
        w = _weapon(damage=30, mod_slots=["barrel"])
        att = _attachment(slot_type="barrel", stat_delta={"damage": -5})
        w.attach(att)
        state = WeaponState()
        state.load_from_weapon(w)
        assert state.damage == pytest.approx(25.0)

    def test_fire_rate_with_barrel_attachment_is_boosted(self):
        w = _weapon(fire_rate=4.0, mod_slots=["barrel"])
        att = _attachment(slot_type="barrel", stat_delta={"fire_rate": 1.5})
        w.attach(att)
        state = WeaponState()
        state.load_from_weapon(w)
        assert state.fire_rate == pytest.approx(5.5)

    def test_cumulative_damage_from_two_attachments(self):
        w = _weapon(damage=30, mod_slots=["scope", "barrel"])
        w.attach(_attachment(aid="s", slot_type="scope", stat_delta={"damage": 5}))
        w.attach(_attachment(aid="b", slot_type="barrel", stat_delta={"damage": 3}))
        state = WeaponState()
        state.load_from_weapon(w)
        assert state.damage == pytest.approx(38.0)

    def test_reload_time_attachment_delta_applied(self):
        """A stock with negative reload_time delta should shorten WeaponState.reload_time."""
        w = _weapon(mod_slots=["stock"], stats={"range": 450, "reload_time": 2.0})
        att = _attachment(slot_type="stock", stat_delta={"reload_time": -0.5})
        w.attach(att)
        state = WeaponState()
        state.load_from_weapon(w)
        # effective reload_time = 2.0 + (-0.5) = 1.5
        assert state.reload_time == pytest.approx(1.5)

    def test_stats_revert_to_base_after_detach_and_reload(self):
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        state = WeaponState()
        state.load_from_weapon(w)
        assert state.damage == pytest.approx(40.0)

        w.detach("scope")
        state.load_from_weapon(w)
        assert state.damage == pytest.approx(30.0)

    def test_weapon_base_damage_property_unchanged_by_load(self):
        """Weapon.damage (the base property) must remain at the original value."""
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        state = WeaponState()
        state.load_from_weapon(w)
        assert state.damage == pytest.approx(40.0)
        assert w.damage == 30  # base property is unchanged


# ---------------------------------------------------------------------------
# attach_to_weapon() / detach_from_weapon() event emission
# ---------------------------------------------------------------------------


class TestAttachmentEventEmission:
    """The helper functions in weapon_attachments.py must emit
    'weapon_attachment_changed' on the global EventBus after successful
    attach/detach operations.
    """

    def test_attach_emits_weapon_attachment_changed_event(self):
        from src.core.event_bus import event_bus as global_bus

        received: list[dict] = []

        def handler(**kwargs: Any) -> None:
            received.append(kwargs)

        global_bus.subscribe("weapon_attachment_changed", handler)
        try:
            w = _weapon(mod_slots=["scope"])
            att = _attachment(slot_type="scope")
            attach_to_weapon(w, att)
            assert len(received) == 1
            assert received[0].get("weapon") is w
        finally:
            global_bus.unsubscribe("weapon_attachment_changed", handler)

    def test_attach_event_carries_slot_type(self):
        from src.core.event_bus import event_bus as global_bus

        received: list[dict] = []

        def handler(**kwargs: Any) -> None:
            received.append(kwargs)

        global_bus.subscribe("weapon_attachment_changed", handler)
        try:
            w = _weapon(mod_slots=["barrel"])
            att = _attachment(slot_type="barrel", stat_delta={"damage": 4})
            attach_to_weapon(w, att)
            assert len(received) == 1, (
                "attach_to_weapon() did not emit 'weapon_attachment_changed' — "
                "add event_bus.emit() to the helper"
            )
            assert received[0].get("slot_type") == "barrel"
        finally:
            global_bus.unsubscribe("weapon_attachment_changed", handler)

    def test_failed_attach_does_not_emit_event(self):
        """A failed attach (wrong slot type) must not emit the event."""
        from src.core.event_bus import event_bus as global_bus

        received: list[dict] = []

        def handler(**kwargs: Any) -> None:
            received.append(kwargs)

        global_bus.subscribe("weapon_attachment_changed", handler)
        try:
            w = _weapon(mod_slots=["scope"])
            att = _attachment(slot_type="barrel")  # barrel att, scope-only weapon
            result = attach_to_weapon(w, att)
            assert result is False
            assert len(received) == 0
        finally:
            global_bus.unsubscribe("weapon_attachment_changed", handler)

    def test_detach_emits_weapon_attachment_changed_event(self):
        from src.core.event_bus import event_bus as global_bus

        received: list[dict] = []

        def handler(**kwargs: Any) -> None:
            received.append(kwargs)

        w = _weapon(mod_slots=["scope"])
        att = _attachment(slot_type="scope")
        w.attach(att)  # attach directly (no event subscription yet)

        global_bus.subscribe("weapon_attachment_changed", handler)
        try:
            detach_from_weapon(w, "scope")
            assert len(received) == 1
            assert received[0].get("weapon") is w
        finally:
            global_bus.unsubscribe("weapon_attachment_changed", handler)

    def test_detach_from_empty_slot_does_not_emit_event(self):
        """Detaching from an unoccupied slot returns None and must not emit."""
        from src.core.event_bus import event_bus as global_bus

        received: list[dict] = []

        def handler(**kwargs: Any) -> None:
            received.append(kwargs)

        global_bus.subscribe("weapon_attachment_changed", handler)
        try:
            w = _weapon(mod_slots=["scope"])
            result = detach_from_weapon(w, "scope")  # slot is empty
            assert result is None
            assert len(received) == 0
        finally:
            global_bus.unsubscribe("weapon_attachment_changed", handler)


# ---------------------------------------------------------------------------
# ShootingSystem subscribes to 'weapon_attachment_changed'
# ---------------------------------------------------------------------------


class TestShootingSystemAttachmentRefresh:
    """ShootingSystem must subscribe to 'weapon_attachment_changed' via its
    injected EventBus and refresh WeaponState when the currently-equipped
    weapon is the source of the event.
    """

    def test_shooting_system_registers_listener_on_attachment_changed(self):
        from src.core.event_bus import EventBus

        bus = EventBus()
        ShootingSystem(event_bus=bus)
        assert bus.listener_count("weapon_attachment_changed") >= 1

    def test_damage_updates_in_weapon_state_after_attachment_event(self):
        from src.core.event_bus import EventBus

        bus = EventBus()
        ss = ShootingSystem(event_bus=bus)
        w = _weapon(damage=30, mod_slots=["scope"])
        ss.equip_weapon(w)

        assert ss.weapon_state.damage == pytest.approx(30.0)

        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        bus.emit("weapon_attachment_changed", weapon=w, slot_type="scope")

        assert ss.weapon_state.damage == pytest.approx(40.0)

    def test_fire_rate_updates_in_weapon_state_after_attachment_event(self):
        from src.core.event_bus import EventBus

        bus = EventBus()
        ss = ShootingSystem(event_bus=bus)
        w = _weapon(fire_rate=4.0, mod_slots=["barrel"])
        ss.equip_weapon(w)

        att = _attachment(slot_type="barrel", stat_delta={"fire_rate": 2.0})
        w.attach(att)
        bus.emit("weapon_attachment_changed", weapon=w, slot_type="barrel")

        assert ss.weapon_state.fire_rate == pytest.approx(6.0)

    def test_event_for_different_weapon_does_not_change_state(self):
        """An event for a non-equipped weapon must leave WeaponState untouched."""
        from src.core.event_bus import EventBus

        bus = EventBus()
        ss = ShootingSystem(event_bus=bus)
        w_equipped = _weapon(wid="w1", damage=30, mod_slots=["scope"])
        w_other = _weapon(wid="w2", damage=50, mod_slots=["scope"])
        ss.equip_weapon(w_equipped)

        att = _attachment(slot_type="scope", stat_delta={"damage": 20})
        w_other.attach(att)
        bus.emit("weapon_attachment_changed", weapon=w_other, slot_type="scope")

        assert ss.weapon_state.damage == pytest.approx(30.0)

    def test_weapon_state_reverts_after_detach_event(self):
        """After detaching an attachment and emitting event, base stats are restored."""
        from src.core.event_bus import EventBus

        bus = EventBus()
        ss = ShootingSystem(event_bus=bus)
        w = _weapon(damage=30, mod_slots=["scope"])
        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        ss.equip_weapon(w)
        bus.emit("weapon_attachment_changed", weapon=w, slot_type="scope")
        assert ss.weapon_state.damage == pytest.approx(40.0)

        w.detach("scope")
        bus.emit("weapon_attachment_changed", weapon=w, slot_type="scope")
        assert ss.weapon_state.damage == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# E2E: attach → event → refresh → boosted projectile damage
# ---------------------------------------------------------------------------


class TestAttachFireCycle:
    """End-to-end: equip attachment → event fires → WeaponState refreshed →
    fired projectile carries the boosted damage value.
    """

    def test_projectile_has_base_damage_before_attachment(self):
        """Without any attachment the projectile carries the weapon's base damage."""
        from src.core.event_bus import EventBus

        bus = EventBus()
        ss = ShootingSystem(event_bus=bus)
        w = _weapon(damage=30, mod_slots=["scope"], magazine_size=5)
        ss.equip_weapon(w)

        player = _FakePlayer(w)
        ws = ss.weapon_state
        ws.fire_cooldown = 0.0
        ws.reloading = False

        proj = ss._weapon_system.try_fire(ws, player, 200.0, 100.0)
        assert proj is not None
        assert proj.damage == 30

    def test_projectile_carries_attachment_boosted_damage(self):
        """After equipping a damage attachment and receiving the event, the fired
        projectile must carry the boosted damage (base + attachment delta).
        """
        from src.core.event_bus import EventBus

        bus = EventBus()
        ss = ShootingSystem(event_bus=bus)
        w = _weapon(damage=30, mod_slots=["scope"], magazine_size=5)
        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        ss.equip_weapon(w)
        bus.emit("weapon_attachment_changed", weapon=w, slot_type="scope")

        # WeaponState should now report boosted damage
        assert ss.weapon_state.damage == pytest.approx(40.0)

        player = _FakePlayer(w)
        ws = ss.weapon_state
        ws.fire_cooldown = 0.0
        ws.reloading = False

        proj = ss._weapon_system.try_fire(ws, player, 200.0, 100.0)
        assert proj is not None
        assert proj.damage == 40

    def test_removing_attachment_restores_base_projectile_damage(self):
        """After removing an attachment, fired projectiles revert to base damage."""
        from src.core.event_bus import EventBus

        bus = EventBus()
        ss = ShootingSystem(event_bus=bus)
        w = _weapon(damage=30, mod_slots=["scope"], magazine_size=10)
        att = _attachment(slot_type="scope", stat_delta={"damage": 10})
        w.attach(att)
        ss.equip_weapon(w)
        bus.emit("weapon_attachment_changed", weapon=w, slot_type="scope")
        assert ss.weapon_state.damage == pytest.approx(40.0)

        # Detach and emit event
        w.detach("scope")
        bus.emit("weapon_attachment_changed", weapon=w, slot_type="scope")
        assert ss.weapon_state.damage == pytest.approx(30.0)

        player = _FakePlayer(w)
        ws = ss.weapon_state
        ws.fire_cooldown = 0.0
        ws.reloading = False

        proj = ss._weapon_system.try_fire(ws, player, 200.0, 100.0)
        assert proj is not None
        assert proj.damage == 30
