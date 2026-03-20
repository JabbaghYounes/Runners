"""Integration tests: GameScene._build_hud_state() — consumable fields.

Verifies the wiring between live player state and the HUDState snapshot:
- player.active_buffs  →  HUDState.active_buffs  (list[BuffEntry])
- player.inventory quick-slots  →  HUDState.consumable_slots  (list[ConsumableSlot])

Also covers two near-E2E scenarios:
  1. K_1 applies a buff → buff appears in next HUDState
  2. Buff ticks to expiry → subsequent HUDState shows empty active_buffs

Run: pytest tests/test_hud_consumable_wiring.py
"""
from __future__ import annotations

import types

import pytest
import pygame
from unittest.mock import MagicMock

from src.core.event_bus import EventBus, event_bus as global_event_bus
from src.systems.buff_system import ActiveBuff, BuffSystem
from src.inventory.item import Consumable
from src.inventory.inventory import Inventory
from src.ui.hud_state import BuffEntry, ConsumableSlot


# ---------------------------------------------------------------------------
# Session-scoped Pygame initialisation (headless)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _pygame_headless():
    pygame.display.init()
    pygame.font.init()
    yield


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_event_bus():
    global_event_bus.clear()
    yield
    global_event_bus.clear()


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def scene(bus):
    """Stub-mode GameScene (no tile map, _full_init=False)."""
    from src.scenes.game_scene import GameScene
    return GameScene(event_bus=bus, audio=MagicMock(), settings=MagicMock())


@pytest.fixture
def patched_scene():
    """Stub GameScene with _full_init patched True and a real BuffSystem wired in."""
    from src.scenes.game_scene import GameScene
    s = GameScene(zones=[])
    s._full_init = True
    bs = BuffSystem()
    s.player.set_buff_system(bs)
    s._buff = bs
    return s


@pytest.fixture
def medkit() -> Consumable:
    return Consumable(
        id="medkit_small",
        name="Small Medkit",
        rarity="common",
        sprite_key="medkit_small",
        value=50,
        consumable_type="heal",
        heal_amount=30,
    )


@pytest.fixture
def stim_speed() -> Consumable:
    return Consumable(
        id="stim_speed",
        name="Speed Stim",
        rarity="rare",
        sprite_key="stim_speed",
        value=400,
        consumable_type="buff",
        buff_type="speed",
        buff_value=30.0,
        buff_duration=15.0,
    )


@pytest.fixture
def stim_damage() -> Consumable:
    return Consumable(
        id="stim_damage",
        name="Damage Stim",
        rarity="rare",
        sprite_key="stim_damage",
        value=450,
        consumable_type="buff",
        buff_type="damage",
        buff_value=25.0,
        buff_duration=12.0,
    )


def _keydown(key: int):
    """Minimal KEYDOWN event-like namespace."""
    return types.SimpleNamespace(type=pygame.KEYDOWN, key=key)


# ---------------------------------------------------------------------------
# _build_hud_state() — active_buffs field
# ---------------------------------------------------------------------------

class TestBuildHUDStateActiveBuffs:
    """HUDState.active_buffs mirrors player.active_buffs."""

    def test_no_active_buffs_returns_empty_list(self, scene) -> None:
        state = scene._build_hud_state()
        assert state.active_buffs == []

    def test_one_active_buff_returns_one_entry(self, scene) -> None:
        buff = ActiveBuff("speed", value=30.0, duration=15.0, time_remaining=15.0)
        scene.player.active_buffs.append(buff)
        state = scene._build_hud_state()
        assert len(state.active_buffs) == 1

    def test_buff_entry_label_matches_buff_type(self, scene) -> None:
        buff = ActiveBuff("speed", value=30.0, duration=15.0, time_remaining=15.0)
        scene.player.active_buffs.append(buff)
        state = scene._build_hud_state()
        assert state.active_buffs[0].label == "speed"

    def test_buff_entry_label_for_damage_type(self, scene) -> None:
        buff = ActiveBuff("damage", value=25.0, duration=12.0, time_remaining=12.0)
        scene.player.active_buffs.append(buff)
        state = scene._build_hud_state()
        assert state.active_buffs[0].label == "damage"

    def test_buff_entry_seconds_left_matches_time_remaining(self, scene) -> None:
        buff = ActiveBuff("damage", value=25.0, duration=12.0, time_remaining=7.5)
        scene.player.active_buffs.append(buff)
        state = scene._build_hud_state()
        assert state.active_buffs[0].seconds_left == pytest.approx(7.5)

    def test_partially_elapsed_time_remaining_reflected(self, scene) -> None:
        """After a simulated partial tick, time_remaining change is visible in HUDState."""
        buff = ActiveBuff("speed", value=30.0, duration=10.0, time_remaining=10.0)
        scene.player.active_buffs.append(buff)
        buff.time_remaining = 3.5  # Simulate external tick
        state = scene._build_hud_state()
        assert state.active_buffs[0].seconds_left == pytest.approx(3.5)

    def test_two_active_buffs_return_two_entries(self, scene) -> None:
        scene.player.active_buffs.append(ActiveBuff("speed", 30.0, 15.0, 15.0))
        scene.player.active_buffs.append(ActiveBuff("damage", 25.0, 12.0, 12.0))
        state = scene._build_hud_state()
        assert len(state.active_buffs) == 2

    def test_entries_are_buff_entry_instances(self, scene) -> None:
        scene.player.active_buffs.append(ActiveBuff("speed", 30.0, 15.0, 15.0))
        state = scene._build_hud_state()
        assert isinstance(state.active_buffs[0], BuffEntry)

    def test_buff_entry_icon_is_none_when_assets_is_none(self, scene) -> None:
        scene._assets = None
        scene.player.active_buffs.append(ActiveBuff("speed", 30.0, 15.0, 15.0))
        state = scene._build_hud_state()
        assert state.active_buffs[0].icon is None

    def test_clearing_active_buffs_returns_empty_on_next_call(self, scene) -> None:
        scene.player.active_buffs.append(ActiveBuff("speed", 30.0, 15.0, 15.0))
        assert len(scene._build_hud_state().active_buffs) == 1
        scene.player.active_buffs.clear()
        assert scene._build_hud_state().active_buffs == []

    def test_buff_entries_label_order_matches_active_buffs_order(
        self, scene
    ) -> None:
        """Entry ordering in HUDState matches the order in player.active_buffs."""
        scene.player.active_buffs.append(ActiveBuff("speed", 30.0, 15.0, 15.0))
        scene.player.active_buffs.append(ActiveBuff("damage", 25.0, 12.0, 12.0))
        state = scene._build_hud_state()
        labels = [e.label for e in state.active_buffs]
        assert labels == ["speed", "damage"]


# ---------------------------------------------------------------------------
# _build_hud_state() — consumable_slots field
# ---------------------------------------------------------------------------

class TestBuildHUDStateConsumableSlots:
    """HUDState.consumable_slots mirrors player.inventory quick-slot state."""

    def test_empty_inventory_returns_four_slots(self, scene) -> None:
        """All four quick-slot cells should always be present."""
        state = scene._build_hud_state()
        assert len(state.consumable_slots) == 4

    def test_all_empty_slots_have_count_zero(self, scene) -> None:
        state = scene._build_hud_state()
        for slot in state.consumable_slots:
            assert slot.count == 0

    def test_all_empty_slots_have_blank_label(self, scene) -> None:
        state = scene._build_hud_state()
        for slot in state.consumable_slots:
            assert slot.label == ""

    def test_item_assigned_to_quick_slot_0_appears_at_index_0(
        self, scene, medkit: Consumable
    ) -> None:
        inv: Inventory = scene.player.inventory
        s = inv.add_item(medkit)
        inv.assign_quick_slot(s, 0)
        state = scene._build_hud_state()
        assert state.consumable_slots[0].label == medkit.name

    def test_item_assigned_to_quick_slot_2_appears_at_index_2(
        self, scene, stim_speed: Consumable
    ) -> None:
        inv: Inventory = scene.player.inventory
        s = inv.add_item(stim_speed)
        inv.assign_quick_slot(s, 2)
        state = scene._build_hud_state()
        assert state.consumable_slots[2].label == stim_speed.name

    def test_assigned_slot_has_count_one(self, scene, medkit: Consumable) -> None:
        inv: Inventory = scene.player.inventory
        s = inv.add_item(medkit)
        inv.assign_quick_slot(s, 0)
        state = scene._build_hud_state()
        assert state.consumable_slots[0].count == 1

    def test_unassigned_slots_remain_count_zero(
        self, scene, medkit: Consumable
    ) -> None:
        """Only slot 0 is assigned; slots 1-3 must stay empty."""
        inv: Inventory = scene.player.inventory
        s = inv.add_item(medkit)
        inv.assign_quick_slot(s, 0)
        state = scene._build_hud_state()
        for i in range(1, 4):
            assert state.consumable_slots[i].count == 0

    def test_slot_icon_is_none_when_assets_is_none(
        self, scene, medkit: Consumable
    ) -> None:
        scene._assets = None
        inv: Inventory = scene.player.inventory
        s = inv.add_item(medkit)
        inv.assign_quick_slot(s, 0)
        state = scene._build_hud_state()
        assert state.consumable_slots[0].icon is None

    def test_after_using_consumable_slot_shows_empty(
        self, scene, medkit: Consumable
    ) -> None:
        """Once an item is consumed (slot cleared), the next HUDState reflects that."""
        scene.player.health = 60
        inv: Inventory = scene.player.inventory
        s = inv.add_item(medkit)
        inv.assign_quick_slot(s, 0)

        inv.use_consumable(0, scene.player)  # Consumes and removes

        state = scene._build_hud_state()
        assert state.consumable_slots[0].count == 0
        assert state.consumable_slots[0].label == ""

    def test_all_four_slots_filled_returns_all_four_non_empty(
        self, scene
    ) -> None:
        """Assigning a consumable to each quick slot → all 4 entries have count 1."""
        inv: Inventory = scene.player.inventory
        for qs in range(4):
            item = Consumable(
                id=f"item_{qs}",
                name=f"Item {qs}",
                rarity="common",
                sprite_key=f"item_{qs}",
                value=10,
                consumable_type="heal",
                heal_amount=5,
            )
            s = inv.add_item(item)
            inv.assign_quick_slot(s, qs)
        state = scene._build_hud_state()
        assert all(c.count == 1 for c in state.consumable_slots)

    def test_entries_are_consumable_slot_instances(
        self, scene, medkit: Consumable
    ) -> None:
        inv: Inventory = scene.player.inventory
        s = inv.add_item(medkit)
        inv.assign_quick_slot(s, 1)
        state = scene._build_hud_state()
        for cs in state.consumable_slots:
            assert isinstance(cs, ConsumableSlot)

    def test_each_call_returns_fresh_snapshot(
        self, scene, medkit: Consumable
    ) -> None:
        """Two consecutive _build_hud_state() calls return independent objects."""
        inv: Inventory = scene.player.inventory
        s = inv.add_item(medkit)
        inv.assign_quick_slot(s, 0)
        first = scene._build_hud_state()
        second = scene._build_hud_state()
        assert first is not second
        assert first.consumable_slots is not second.consumable_slots


# ---------------------------------------------------------------------------
# Near-E2E: K_1 dispatch → HUDState → buff expiry
# ---------------------------------------------------------------------------

class TestBuffLifecycleThroughScene:
    """Full buff lifecycle: K_1 press → HUDState reflects buff → tick to expiry → gone."""

    def test_buff_consumable_via_k1_appears_in_hud_state(
        self, patched_scene
    ) -> None:
        """After pressing K_1 to consume a speed stim, active_buffs has one entry."""
        stim = Consumable(
            id="stim_speed",
            name="Speed Stim",
            rarity="rare",
            sprite_key="stim_speed",
            value=400,
            consumable_type="buff",
            buff_type="speed",
            buff_value=30.0,
            buff_duration=15.0,
        )
        inv: Inventory = patched_scene.player.inventory
        slot = inv.add_item(stim)
        inv.assign_quick_slot(slot, 0)

        patched_scene.handle_events([_keydown(pygame.K_1)])

        state = patched_scene._build_hud_state()
        assert len(state.active_buffs) == 1
        assert state.active_buffs[0].label == "speed"

    def test_buff_expires_and_disappears_from_hud_state(
        self, patched_scene
    ) -> None:
        """After the buff's full duration elapses, HUDState.active_buffs is empty."""
        stim = Consumable(
            id="stim_speed",
            name="Speed Stim",
            rarity="rare",
            sprite_key="stim_speed",
            value=400,
            consumable_type="buff",
            buff_type="speed",
            buff_value=30.0,
            buff_duration=5.0,  # Short for testing
        )
        inv: Inventory = patched_scene.player.inventory
        slot = inv.add_item(stim)
        inv.assign_quick_slot(slot, 0)

        patched_scene.handle_events([_keydown(pygame.K_1)])

        # Tick the BuffSystem past the duration
        patched_scene._buff.update(5.0)

        state = patched_scene._build_hud_state()
        assert state.active_buffs == []

    def test_heal_consumable_via_k1_slot_shows_empty_in_hud_state(
        self, patched_scene
    ) -> None:
        """After a heal consumable is used, its quick-slot entry is empty in HUDState."""
        medkit = Consumable(
            id="medkit_small",
            name="Small Medkit",
            rarity="common",
            sprite_key="medkit_small",
            value=50,
            consumable_type="heal",
            heal_amount=30,
        )
        patched_scene.player.health = 60
        inv: Inventory = patched_scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 0)

        patched_scene.handle_events([_keydown(pygame.K_1)])

        state = patched_scene._build_hud_state()
        assert state.consumable_slots[0].count == 0

    def test_buff_seconds_left_decreases_after_partial_tick(
        self, patched_scene
    ) -> None:
        """seconds_left in HUDState decreases proportionally to BuffSystem.update(dt)."""
        stim = Consumable(
            id="stim_speed",
            name="Speed Stim",
            rarity="rare",
            sprite_key="stim_speed",
            value=400,
            consumable_type="buff",
            buff_type="speed",
            buff_value=30.0,
            buff_duration=10.0,
        )
        inv: Inventory = patched_scene.player.inventory
        slot = inv.add_item(stim)
        inv.assign_quick_slot(slot, 0)

        patched_scene.handle_events([_keydown(pygame.K_1)])

        # Tick 4 seconds
        patched_scene._buff.update(4.0)

        state = patched_scene._build_hud_state()
        assert state.active_buffs[0].seconds_left == pytest.approx(6.0)
