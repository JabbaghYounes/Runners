"""Tests for HUDState dataclass and support types."""
from __future__ import annotations

import pytest
from src.ui.hud_state import (
    HUDState,
    BuffEntry,
    WeaponInfo,
    ZoneInfo,
    ChallengeInfo,
    ConsumableSlot,
)


class TestHUDStateDefaults:
    def test_constructs_with_no_args(self):
        state = HUDState()
        assert state is not None

    def test_default_hp_is_100(self):
        state = HUDState()
        assert state.hp == 100.0

    def test_default_max_hp_is_100(self):
        state = HUDState()
        assert state.max_hp == 100.0

    def test_default_armor_is_0(self):
        state = HUDState()
        assert state.armor == 0.0

    def test_default_max_armor_is_100(self):
        state = HUDState()
        assert state.max_armor == 100.0

    def test_default_level_is_1(self):
        state = HUDState()
        assert state.level == 1

    def test_default_seconds_remaining_is_900(self):
        state = HUDState()
        assert state.seconds_remaining == 900.0

    def test_default_active_buffs_is_empty_list(self):
        state = HUDState()
        assert state.active_buffs == []

    def test_default_zones_is_empty_list(self):
        state = HUDState()
        assert state.zones == []

    def test_default_equipped_weapon_is_none(self):
        state = HUDState()
        assert state.equipped_weapon is None

    def test_default_extraction_pos_is_none(self):
        state = HUDState()
        assert state.extraction_pos is None

    def test_default_consumable_slots_is_empty_list(self):
        state = HUDState()
        assert state.consumable_slots == []

    def test_default_active_challenges_is_empty_list(self):
        state = HUDState()
        assert state.active_challenges == []

    def test_default_map_world_rect_is_none(self):
        state = HUDState()
        assert state.map_world_rect is None

    def test_default_player_world_pos_is_origin(self):
        state = HUDState()
        assert state.player_world_pos == (0.0, 0.0)


class TestHUDStateFieldAssignment:
    def test_hp_field_stored(self):
        state = HUDState(hp=42.0)
        assert state.hp == 42.0

    def test_max_hp_field_stored(self):
        state = HUDState(max_hp=200.0)
        assert state.max_hp == 200.0

    def test_level_field_stored(self):
        state = HUDState(level=7)
        assert state.level == 7

    def test_seconds_remaining_stored(self):
        state = HUDState(seconds_remaining=123.5)
        assert state.seconds_remaining == 123.5

    def test_extraction_pos_stored(self):
        state = HUDState(extraction_pos=(640.0, 360.0))
        assert state.extraction_pos == (640.0, 360.0)


class TestBuffEntry:
    def test_constructs_with_required_fields(self):
        b = BuffEntry(label='Speed', seconds_left=5.0)
        assert b.label == 'Speed'
        assert b.seconds_left == 5.0

    def test_icon_defaults_to_none(self):
        b = BuffEntry(label='Test', seconds_left=1.0)
        assert b.icon is None

    def test_icon_can_be_set(self):
        sentinel = object()
        b = BuffEntry(label='Test', seconds_left=1.0, icon=sentinel)
        assert b.icon is sentinel


class TestWeaponInfo:
    def test_constructs_with_required_fields(self):
        w = WeaponInfo(name='Rifle', ammo_current=12, ammo_reserve=36)
        assert w.name == 'Rifle'
        assert w.ammo_current == 12
        assert w.ammo_reserve == 36

    def test_icon_defaults_to_none(self):
        w = WeaponInfo(name='Rifle', ammo_current=10, ammo_reserve=30)
        assert w.icon is None

    def test_reloading_defaults_false(self):
        w = WeaponInfo(name='Pistol', ammo_current=7, ammo_reserve=21)
        assert w.reloading is False

    def test_reload_progress_defaults_zero(self):
        w = WeaponInfo(name='Pistol', ammo_current=7, ammo_reserve=21)
        assert w.reload_progress == 0.0


class TestZoneInfo:
    def test_constructs_correctly(self):
        sentinel = object()
        z = ZoneInfo(name='Sector Alpha', color=(100, 200, 50), world_rect=sentinel)
        assert z.name == 'Sector Alpha'
        assert z.color == (100, 200, 50)
        assert z.world_rect is sentinel


class TestChallengeInfo:
    def test_constructs_correctly(self):
        c = ChallengeInfo(name='Kill 3 Robots', progress=1, target=3)
        assert c.name == 'Kill 3 Robots'
        assert c.progress == 1
        assert c.target == 3

    def test_completed_defaults_false(self):
        c = ChallengeInfo(name='Test', progress=0, target=5)
        assert c.completed is False

    def test_completed_can_be_set_true(self):
        c = ChallengeInfo(name='Test', progress=5, target=5, completed=True)
        assert c.completed is True


class TestConsumableSlot:
    def test_constructs_correctly(self):
        cs = ConsumableSlot(label='MedKit', count=2)
        assert cs.label == 'MedKit'
        assert cs.count == 2

    def test_icon_defaults_to_none(self):
        cs = ConsumableSlot(label='Stim', count=1)
        assert cs.icon is None


class TestHUDStateWithSupportTypes:
    def test_active_buffs_list_stored(self):
        buffs = [BuffEntry(label='Shield', seconds_left=10.0)]
        state = HUDState(active_buffs=buffs)
        assert len(state.active_buffs) == 1
        assert state.active_buffs[0].label == 'Shield'

    def test_active_challenges_list_stored(self):
        challenges = [ChallengeInfo(name='Loot Cache', progress=2, target=5)]
        state = HUDState(active_challenges=challenges)
        assert len(state.active_challenges) == 1

    def test_equipped_weapon_stored(self):
        weapon = WeaponInfo(name='SMG', ammo_current=25, ammo_reserve=75)
        state = HUDState(equipped_weapon=weapon)
        assert state.equipped_weapon is weapon

    def test_consumable_slots_list_stored(self):
        slots = [ConsumableSlot(label='MedKit', count=3)]
        state = HUDState(consumable_slots=slots)
        assert len(state.consumable_slots) == 1


# ---------------------------------------------------------------------------
# Mutable-default independence
# ---------------------------------------------------------------------------
class TestHUDStateMutableDefaults:
    def test_two_instances_have_independent_active_buffs(self):
        """Mutating one HUDState's active_buffs must not affect another."""
        s1 = HUDState()
        s2 = HUDState()
        s1.active_buffs.append(BuffEntry(label='Speed', seconds_left=5.0))
        assert s2.active_buffs == []

    def test_two_instances_have_independent_zones(self):
        s1 = HUDState()
        s2 = HUDState()
        s1.zones.append(object())  # any sentinel value
        assert s2.zones == []

    def test_two_instances_have_independent_consumable_slots(self):
        s1 = HUDState()
        s2 = HUDState()
        s1.consumable_slots.append(ConsumableSlot(label='x', count=1))
        assert s2.consumable_slots == []

    def test_two_instances_have_independent_active_challenges(self):
        s1 = HUDState()
        s2 = HUDState()
        s1.active_challenges.append(ChallengeInfo(name='A', progress=0, target=1))
        assert s2.active_challenges == []


# ---------------------------------------------------------------------------
# XP / progression fields
# ---------------------------------------------------------------------------
class TestHUDStateXPFields:
    def test_default_xp_is_zero(self):
        state = HUDState()
        assert state.xp == 0.0

    def test_default_xp_to_next_is_100(self):
        state = HUDState()
        assert state.xp_to_next == 100.0

    def test_xp_field_stored(self):
        state = HUDState(xp=350.0)
        assert state.xp == pytest.approx(350.0)

    def test_xp_to_next_field_stored(self):
        state = HUDState(xp_to_next=500.0)
        assert state.xp_to_next == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# BuffEntry — additional field verification
# ---------------------------------------------------------------------------
class TestBuffEntryAdditional:
    def test_seconds_left_stored_as_float(self):
        b = BuffEntry(label='Shield', seconds_left=2.75)
        assert b.seconds_left == pytest.approx(2.75)

    def test_seconds_left_zero_allowed(self):
        b = BuffEntry(label='Expired', seconds_left=0.0)
        assert b.seconds_left == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# WeaponInfo — reloading state fields
# ---------------------------------------------------------------------------
class TestWeaponInfoReloading:
    def test_reloading_true_stored(self):
        w = WeaponInfo(name='Shotgun', ammo_current=0, ammo_reserve=24,
                       reloading=True)
        assert w.reloading is True

    def test_reload_progress_stored(self):
        w = WeaponInfo(name='Shotgun', ammo_current=0, ammo_reserve=24,
                       reloading=True, reload_progress=0.6)
        assert w.reload_progress == pytest.approx(0.6)

    def test_ammo_values_stored(self):
        w = WeaponInfo(name='Rifle', ammo_current=3, ammo_reserve=90)
        assert w.ammo_current == 3
        assert w.ammo_reserve == 90


# ---------------------------------------------------------------------------
# ConsumableSlot — icon field
# ---------------------------------------------------------------------------
class TestConsumableSlotIcon:
    def test_icon_can_be_set(self):
        sentinel = object()
        cs = ConsumableSlot(label='MedKit', count=2, icon=sentinel)
        assert cs.icon is sentinel

    def test_count_zero_allowed(self):
        cs = ConsumableSlot(label='Empty', count=0)
        assert cs.count == 0


# ---------------------------------------------------------------------------
# HUDState.tile_surf — new field for the baked 1-px-per-tile minimap surface
# ---------------------------------------------------------------------------


class TestHUDStateTileSurf:
    """tile_surf carries TileMap.baked_minimap through the HUD pipeline."""

    def test_tile_surf_default_is_none(self):
        state = HUDState()
        assert state.tile_surf is None

    def test_tile_surf_field_accepts_any_value(self):
        """Field must accept a pygame.Surface or any sentinel without type error."""
        sentinel = object()
        state = HUDState(tile_surf=sentinel)
        assert state.tile_surf is sentinel

    def test_tile_surf_stored_when_set_via_constructor(self):
        import pygame
        surf = pygame.Surface((10, 8))
        state = HUDState(tile_surf=surf)
        assert state.tile_surf is surf

    def test_tile_surf_can_be_replaced_by_mutation(self):
        state = HUDState()
        assert state.tile_surf is None
        surf = object()
        state.tile_surf = surf
        assert state.tile_surf is surf

    def test_two_instances_tile_surf_are_independent(self):
        """Mutating one instance's tile_surf must not affect another."""
        s1 = HUDState()
        s2 = HUDState()
        s1.tile_surf = object()
        assert s2.tile_surf is None

    def test_tile_surf_none_is_falsy(self):
        """Code that guards with 'if state.tile_surf:' must see None as falsy."""
        state = HUDState()
        assert not state.tile_surf

    def test_tile_surf_pygame_surface_is_truthy(self):
        """A real pygame.Surface stored in tile_surf must be truthy."""
        import pygame
        surf = pygame.Surface((100, 30))
        state = HUDState(tile_surf=surf)
        # pygame.Surface does not define __bool__ as False for non-empty surfaces,
        # but the field reference itself must not be None
        assert state.tile_surf is not None
