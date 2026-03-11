"""Unit tests for the consumables feature.

Covers:
- heal() HP restoration and max-health clamping
- player_healed event emission
- Buff application via apply_buff() and Player.active_buffs
- buff_applied / buff_expired EventBus events
- BuffSystem.update() decrement and expiry
- get_stat() base + modifier stacking
- Inventory add / remove / use_consumable flow
- Quick-slot assignment and lookup
- Graceful no-op on empty or unassigned quick-slots

Tests are pure Python and do NOT require Pygame or a display.
The pygame stub below satisfies any top-level ``import pygame`` in
source modules without actually initialising SDL.
"""

from __future__ import annotations

import sys
import types

import pytest


# ---------------------------------------------------------------------------
# Minimal Pygame stub — must be installed before importing src modules
# ---------------------------------------------------------------------------


def _install_pygame_stub() -> None:
    """Replace the real pygame with a lightweight stub for headless testing."""
    if "pygame" in sys.modules:
        return  # Already present (either real or stub)

    pg = types.ModuleType("pygame")

    # Key constants used in game_scene.py
    pg.K_1 = 49
    pg.K_2 = 50
    pg.K_3 = 51
    pg.K_4 = 52
    pg.K_e = 101
    pg.KEYDOWN = 2

    # Stub font sub-module
    font_mod = types.ModuleType("pygame.font")
    font_mod.SysFont = lambda *a, **kw: None  # type: ignore[assignment]
    pg.font = font_mod  # type: ignore[attr-defined]

    # Stub draw sub-module
    draw_mod = types.ModuleType("pygame.draw")
    draw_mod.rect = lambda *a, **kw: None  # type: ignore[attr-defined]
    pg.draw = draw_mod  # type: ignore[attr-defined]

    # Stub Rect
    pg.Rect = lambda *a, **kw: None  # type: ignore[attr-defined]

    sys.modules["pygame"] = pg
    sys.modules["pygame.font"] = font_mod
    sys.modules["pygame.draw"] = draw_mod


_install_pygame_stub()

# ---------------------------------------------------------------------------
# Now it is safe to import src modules
# ---------------------------------------------------------------------------

from src.core.event_bus import EventBus, event_bus  # noqa: E402
from src.inventory.inventory import Inventory       # noqa: E402
from src.inventory.item import Consumable           # noqa: E402
from src.systems.buff_system import ActiveBuff, BuffSystem  # noqa: E402
from src.entities.player import Player              # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Wipe all subscriptions between tests to prevent cross-test pollution."""
    event_bus.clear()
    yield
    event_bus.clear()


@pytest.fixture
def buff_system() -> BuffSystem:
    return BuffSystem()


@pytest.fixture
def player(buff_system: BuffSystem) -> Player:
    return Player(max_health=100, buff_system=buff_system)


@pytest.fixture
def inventory() -> Inventory:
    return Inventory()


@pytest.fixture
def medkit_small() -> Consumable:
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
def medkit_large() -> Consumable:
    return Consumable(
        id="medkit_large",
        name="Large Medkit",
        rarity="uncommon",
        sprite_key="medkit_large",
        value=120,
        consumable_type="heal",
        heal_amount=80,
    )


@pytest.fixture
def stim_speed() -> Consumable:
    return Consumable(
        id="stim_speed",
        name="Speed Stim",
        rarity="uncommon",
        sprite_key="stim_speed",
        value=200,
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
        value=350,
        consumable_type="buff",
        buff_type="damage",
        buff_value=25.0,
        buff_duration=12.0,
    )


# ---------------------------------------------------------------------------
# heal() tests
# ---------------------------------------------------------------------------


class TestHeal:
    def test_heal_restores_hp(self, player: Player) -> None:
        player.health = 50
        player.heal(30)
        assert player.health == 80

    def test_heal_clamps_at_max_health(self, player: Player) -> None:
        player.health = 90
        player.heal(50)  # Would bring to 140 — must clamp to 100
        assert player.health == player.max_health == 100

    def test_heal_at_full_hp_returns_zero(self, player: Player) -> None:
        player.health = 100
        gained = player.heal(20)
        assert gained == 0
        assert player.health == 100

    def test_heal_returns_actual_gain(self, player: Player) -> None:
        player.health = 80
        gained = player.heal(30)
        assert gained == 20  # Only 20 HP of headroom

    def test_heal_emits_player_healed_event(self, player: Player) -> None:
        received: list[dict] = []
        event_bus.subscribe("player_healed", received.append)
        player.health = 60
        player.heal(25)
        assert len(received) == 1
        assert received[0]["amount"] == 25
        assert received[0]["player"] is player

    def test_heal_does_not_emit_when_already_full(self, player: Player) -> None:
        received: list[dict] = []
        event_bus.subscribe("player_healed", received.append)
        player.heal(10)
        assert received == []

    def test_zero_heal_amount_is_noop(self, player: Player) -> None:
        player.health = 50
        gained = player.heal(0)
        assert gained == 0
        assert player.health == 50

    def test_negative_heal_amount_is_noop(self, player: Player) -> None:
        player.health = 50
        gained = player.heal(-10)
        assert gained == 0
        assert player.health == 50


# ---------------------------------------------------------------------------
# Buff application
# ---------------------------------------------------------------------------


class TestBuffApplication:
    def test_apply_buff_adds_to_active_buffs(self, player: Player) -> None:
        buff = ActiveBuff("speed", value=30.0, duration=15.0, time_remaining=15.0)
        player.apply_buff(buff)
        assert buff in player.active_buffs

    def test_apply_buff_emits_buff_applied(self, player: Player) -> None:
        received: list[dict] = []
        event_bus.subscribe("buff_applied", received.append)
        buff = ActiveBuff("damage", value=25.0, duration=12.0, time_remaining=12.0)
        player.apply_buff(buff)
        assert len(received) == 1
        assert received[0]["buff_type"] == "damage"

    def test_multiple_buffs_of_same_type_stack(self, player: Player) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 15.0, 15.0))
        player.apply_buff(ActiveBuff("speed", 10.0, 10.0, 10.0))
        assert len(player.active_buffs) == 2

    def test_different_buff_types_coexist(self, player: Player) -> None:
        player.apply_buff(ActiveBuff("speed",  30.0, 15.0, 15.0))
        player.apply_buff(ActiveBuff("damage", 25.0, 12.0, 12.0))
        assert len(player.active_buffs) == 2


# ---------------------------------------------------------------------------
# BuffSystem tick / expiry
# ---------------------------------------------------------------------------


class TestBuffSystemTick:
    def test_update_decrements_time_remaining(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        buff = ActiveBuff("speed", value=30.0, duration=15.0, time_remaining=15.0)
        player.apply_buff(buff)
        buff_system.update(5.0)
        assert buff.time_remaining == pytest.approx(10.0)

    def test_buff_removed_after_full_duration(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        buff = ActiveBuff("speed", value=30.0, duration=5.0, time_remaining=5.0)
        player.apply_buff(buff)
        buff_system.update(5.0)
        assert buff not in player.active_buffs

    def test_buff_removed_when_time_hits_exactly_zero(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        buff = ActiveBuff("damage", 25.0, 3.0, 3.0)
        player.apply_buff(buff)
        buff_system.update(3.0)
        assert player.active_buffs == []

    def test_buff_expired_event_emitted(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        received: list[dict] = []
        event_bus.subscribe("buff_expired", received.append)
        buff = ActiveBuff("damage", 25.0, 2.0, 2.0)
        player.apply_buff(buff)
        buff_system.update(2.0)
        assert len(received) == 1
        assert received[0]["buff_type"] == "damage"

    def test_unexpired_buff_remains(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        buff = ActiveBuff("speed", 30.0, 15.0, 15.0)
        player.apply_buff(buff)
        buff_system.update(5.0)
        assert buff in player.active_buffs

    def test_partial_tick_leaves_correct_remainder(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        buff = ActiveBuff("speed", 30.0, 10.0, 10.0)
        player.apply_buff(buff)
        buff_system.update(3.0)
        buff_system.update(3.0)
        assert buff.time_remaining == pytest.approx(4.0)

    def test_only_expired_buffs_are_removed(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        short = ActiveBuff("damage", 25.0, 2.0, 2.0)
        long_ = ActiveBuff("speed",  30.0, 15.0, 15.0)
        player.apply_buff(short)
        player.apply_buff(long_)
        buff_system.update(2.0)
        assert short not in player.active_buffs
        assert long_ in player.active_buffs


# ---------------------------------------------------------------------------
# get_stat() — base + modifier stacking
# ---------------------------------------------------------------------------


class TestGetStat:
    def test_get_stat_returns_base_without_buffs(self, player: Player) -> None:
        assert player.get_stat("speed") == pytest.approx(200.0)
        assert player.get_stat("damage") == pytest.approx(25.0)

    def test_get_stat_adds_single_buff_modifier(self, player: Player) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 15.0, 15.0))
        assert player.get_stat("speed") == pytest.approx(230.0)

    def test_get_stat_stacks_multiple_same_type_buffs(self, player: Player) -> None:
        player.apply_buff(ActiveBuff("damage", 25.0, 12.0, 12.0))
        player.apply_buff(ActiveBuff("damage", 10.0,  8.0,  8.0))
        assert player.get_stat("damage") == pytest.approx(60.0)  # 25 base + 35

    def test_get_stat_ignores_unrelated_buff_types(self, player: Player) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 15.0, 15.0))
        assert player.get_stat("damage") == pytest.approx(25.0)  # base only

    def test_get_stat_after_buff_expires_returns_base(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 3.0, 3.0))
        buff_system.update(3.0)
        assert player.get_stat("speed") == pytest.approx(200.0)

    def test_get_stat_unknown_stat_returns_zero_base(self, player: Player) -> None:
        assert player.get_stat("luck") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Inventory — add / remove / quick-slot
# ---------------------------------------------------------------------------


class TestInventory:
    def test_add_item_fills_first_empty_slot(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        assert slot == 0
        assert inventory.item_at(0) is medkit_small

    def test_add_multiple_items_fills_sequentially(
        self,
        inventory: Inventory,
        medkit_small: Consumable,
        medkit_large: Consumable,
    ) -> None:
        slot0 = inventory.add_item(medkit_small)
        slot1 = inventory.add_item(medkit_large)
        assert slot0 == 0
        assert slot1 == 1

    def test_add_item_returns_none_when_full(
        self, medkit_small: Consumable
    ) -> None:
        inv = Inventory(capacity=1)
        inv.add_item(medkit_small)
        result = inv.add_item(medkit_small)
        assert result is None

    def test_remove_item_clears_slot(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        inventory.remove_item(slot)
        assert inventory.item_at(slot) is None

    def test_remove_item_returns_the_item(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        removed = inventory.remove_item(slot)
        assert removed is medkit_small

    def test_remove_item_clears_linked_quick_slot(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        inventory.assign_quick_slot(slot, 2)
        inventory.remove_item(slot)
        assert inventory.quick_slots[2] is None

    def test_assign_quick_slot(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        inventory.assign_quick_slot(slot, 0)
        assert inventory.quick_slots[0] == slot

    def test_quick_slot_item_returns_item(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        inventory.assign_quick_slot(slot, 1)
        assert inventory.quick_slot_item(1) is medkit_small

    def test_quick_slot_item_returns_none_for_unassigned(
        self, inventory: Inventory
    ) -> None:
        assert inventory.quick_slot_item(0) is None


# ---------------------------------------------------------------------------
# use_consumable() — the main feature integration path
# ---------------------------------------------------------------------------


class TestUseConsumable:
    def test_use_consumable_removes_item_from_inventory(
        self,
        player: Player,
        inventory: Inventory,
        medkit_small: Consumable,
    ) -> None:
        player.inventory = inventory
        player.health = 50
        slot = inventory.add_item(medkit_small)
        inventory.assign_quick_slot(slot, 0)
        inventory.use_consumable(0, player)
        assert inventory.item_at(slot) is None

    def test_use_consumable_heal_applies_hp(
        self,
        player: Player,
        inventory: Inventory,
        medkit_small: Consumable,
    ) -> None:
        player.inventory = inventory
        player.health = 60
        slot = inventory.add_item(medkit_small)
        inventory.assign_quick_slot(slot, 0)
        inventory.use_consumable(0, player)
        assert player.health == 90  # 60 + 30

    def test_use_consumable_buff_adds_active_buff(
        self,
        player: Player,
        inventory: Inventory,
        stim_speed: Consumable,
    ) -> None:
        player.inventory = inventory
        slot = inventory.add_item(stim_speed)
        inventory.assign_quick_slot(slot, 1)
        inventory.use_consumable(1, player)
        assert len(player.active_buffs) == 1
        assert player.active_buffs[0].buff_type == "speed"

    def test_use_consumable_emits_consumable_used(
        self,
        player: Player,
        inventory: Inventory,
        medkit_small: Consumable,
    ) -> None:
        player.inventory = inventory
        received: list[dict] = []
        event_bus.subscribe("consumable_used", received.append)
        slot = inventory.add_item(medkit_small)
        inventory.assign_quick_slot(slot, 0)
        inventory.use_consumable(0, player)
        assert len(received) == 1

    def test_use_consumable_returns_true_on_success(
        self,
        player: Player,
        inventory: Inventory,
        medkit_small: Consumable,
    ) -> None:
        player.inventory = inventory
        slot = inventory.add_item(medkit_small)
        inventory.assign_quick_slot(slot, 0)
        result = inventory.use_consumable(0, player)
        assert result is True

    def test_use_empty_quick_slot_returns_false_no_exception(
        self, player: Player, inventory: Inventory
    ) -> None:
        player.inventory = inventory
        result = inventory.use_consumable(0, player)
        assert result is False

    def test_use_unassigned_quick_slot_returns_false(
        self,
        player: Player,
        inventory: Inventory,
        medkit_small: Consumable,
    ) -> None:
        player.inventory = inventory
        inventory.add_item(medkit_small)  # In slot, but no quick-slot link
        result = inventory.use_consumable(0, player)
        assert result is False

    def test_use_consumable_out_of_range_slot_returns_false(
        self, player: Player, inventory: Inventory
    ) -> None:
        player.inventory = inventory
        result = inventory.use_consumable(99, player)
        assert result is False

    def test_use_consumable_quick_slot_unlinked_after_use(
        self,
        player: Player,
        inventory: Inventory,
        medkit_small: Consumable,
    ) -> None:
        player.inventory = inventory
        player.health = 50
        slot = inventory.add_item(medkit_small)
        inventory.assign_quick_slot(slot, 0)
        inventory.use_consumable(0, player)
        # Quick-slot should be cleared because the inventory slot was removed
        assert inventory.quick_slots[0] is None

    def test_use_large_medkit_clamps_hp(
        self,
        player: Player,
        inventory: Inventory,
        medkit_large: Consumable,
    ) -> None:
        player.inventory = inventory
        player.health = 60  # +80 would exceed max_health=100
        slot = inventory.add_item(medkit_large)
        inventory.assign_quick_slot(slot, 0)
        inventory.use_consumable(0, player)
        assert player.health == 100


# ---------------------------------------------------------------------------
# ItemDatabase integration (reads from data/items.json)
# ---------------------------------------------------------------------------


class TestItemDatabase:
    def test_create_medkit_small(self) -> None:
        from src.inventory.item_database import item_database

        item = item_database.create("medkit_small")
        assert isinstance(item, Consumable)
        assert item.consumable_type == "heal"
        assert item.heal_amount == 30

    def test_create_medkit_large(self) -> None:
        from src.inventory.item_database import item_database

        item = item_database.create("medkit_large")
        assert isinstance(item, Consumable)
        assert item.heal_amount == 80

    def test_create_stim_speed(self) -> None:
        from src.inventory.item_database import item_database

        item = item_database.create("stim_speed")
        assert isinstance(item, Consumable)
        assert item.buff_type == "speed"
        assert item.buff_value == 30.0
        assert item.buff_duration == 15.0

    def test_create_stim_damage(self) -> None:
        from src.inventory.item_database import item_database

        item = item_database.create("stim_damage")
        assert isinstance(item, Consumable)
        assert item.buff_type == "damage"
        assert item.buff_value == 25.0

    def test_create_unknown_id_raises_key_error(self) -> None:
        from src.inventory.item_database import item_database

        with pytest.raises(KeyError):
            item_database.create("nonexistent_item_xyz")

    def test_create_returns_fresh_instances(self) -> None:
        from src.inventory.item_database import item_database

        a = item_database.create("medkit_small")
        b = item_database.create("medkit_small")
        assert a is not b   # Distinct instances, not the same object

    def test_all_ids_returns_all_four_known_items(self) -> None:
        from src.inventory.item_database import item_database

        ids = item_database.all_ids()
        for expected in ("medkit_small", "medkit_large", "stim_speed", "stim_damage"):
            assert expected in ids

    def test_reload_still_returns_correct_items(self) -> None:
        from src.inventory.item_database import item_database

        item_database.reload()
        item = item_database.create("stim_speed")
        assert item.id == "stim_speed"


# ---------------------------------------------------------------------------
# Consumable.use() — direct unit tests
# ---------------------------------------------------------------------------


class TestConsumableUseDirect:
    def test_use_heal_consumable_restores_health(
        self, player: Player, medkit_small: Consumable
    ) -> None:
        player.health = 60
        medkit_small.use(player)
        assert player.health == 90  # 60 + 30

    def test_use_heal_consumable_clamps_at_max_health(
        self, player: Player, medkit_small: Consumable
    ) -> None:
        player.health = 90
        medkit_small.use(player)
        assert player.health == 100

    def test_use_buff_consumable_adds_to_active_buffs(
        self, player: Player, stim_speed: Consumable
    ) -> None:
        stim_speed.use(player)
        assert len(player.active_buffs) == 1

    def test_use_buff_consumable_has_correct_buff_type(
        self, player: Player, stim_speed: Consumable
    ) -> None:
        stim_speed.use(player)
        assert player.active_buffs[0].buff_type == "speed"

    def test_use_buff_consumable_has_correct_value(
        self, player: Player, stim_speed: Consumable
    ) -> None:
        stim_speed.use(player)
        assert player.active_buffs[0].value == pytest.approx(30.0)

    def test_use_buff_consumable_sets_duration_and_time_remaining(
        self, player: Player, stim_speed: Consumable
    ) -> None:
        stim_speed.use(player)
        buff = player.active_buffs[0]
        assert buff.duration == pytest.approx(15.0)
        assert buff.time_remaining == pytest.approx(15.0)

    def test_use_buff_icon_key_falls_back_to_sprite_key_when_unset(
        self, player: Player
    ) -> None:
        consumable = Consumable(
            id="test_buff",
            name="Test",
            rarity="common",
            sprite_key="my_sprite",
            value=10,
            consumable_type="buff",
            buff_type="speed",
            buff_value=10.0,
            buff_duration=5.0,
            buff_icon_key="",  # Empty → falls back to sprite_key
        )
        consumable.use(player)
        assert player.active_buffs[0].icon_key == "my_sprite"

    def test_use_buff_icon_key_uses_explicit_buff_icon_key(
        self, player: Player
    ) -> None:
        consumable = Consumable(
            id="test_buff",
            name="Test",
            rarity="common",
            sprite_key="my_sprite",
            value=10,
            consumable_type="buff",
            buff_type="speed",
            buff_value=10.0,
            buff_duration=5.0,
            buff_icon_key="custom_icon",
        )
        consumable.use(player)
        assert player.active_buffs[0].icon_key == "custom_icon"

    def test_use_damage_buff_consumable_correct_type(
        self, player: Player, stim_damage: Consumable
    ) -> None:
        stim_damage.use(player)
        assert player.active_buffs[0].buff_type == "damage"
        assert player.active_buffs[0].value == pytest.approx(25.0)
        assert player.active_buffs[0].duration == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# Player.take_damage()
# ---------------------------------------------------------------------------


class TestPlayerDamage:
    def test_take_damage_reduces_health(self, player: Player) -> None:
        player.take_damage(20)
        assert player.health == 80

    def test_take_damage_returns_effective_damage(self, player: Player) -> None:
        result = player.take_damage(30)
        assert result == 30

    def test_take_damage_respects_armor_reduction(self, player: Player) -> None:
        player.armor = 5
        result = player.take_damage(20)
        assert result == 15
        assert player.health == 85

    def test_take_damage_armor_absorbs_all_damage(self, player: Player) -> None:
        """Armor >= damage: effective damage is 0 and health is unchanged."""
        player.armor = 50
        result = player.take_damage(20)
        assert result == 0
        assert player.health == 100

    def test_take_damage_clamps_health_at_zero(self, player: Player) -> None:
        player.take_damage(999)
        assert player.health == 0

    def test_take_damage_emits_player_killed_when_health_hits_zero(
        self, player: Player
    ) -> None:
        received: list[dict] = []
        event_bus.subscribe("player_killed", received.append)
        player.take_damage(100)
        assert len(received) == 1
        assert received[0]["victim"] is player

    def test_take_damage_does_not_emit_player_killed_when_player_survives(
        self, player: Player
    ) -> None:
        received: list[dict] = []
        event_bus.subscribe("player_killed", received.append)
        player.take_damage(50)
        assert received == []

    def test_take_damage_sets_alive_false_on_death(self, player: Player) -> None:
        player.take_damage(100)
        assert player.alive is False

    def test_take_damage_does_not_re_emit_player_killed_when_already_dead(
        self, player: Player
    ) -> None:
        """player_killed must be emitted exactly once even after repeated lethal hits."""
        received: list[dict] = []
        event_bus.subscribe("player_killed", received.append)
        player.take_damage(100)  # Kills player
        player.take_damage(100)  # Player already dead — no second event
        assert len(received) == 1

    def test_take_damage_partial_damage_leaves_player_alive(
        self, player: Player
    ) -> None:
        player.take_damage(99)
        assert player.health == 1
        assert player.alive is True


# ---------------------------------------------------------------------------
# BuffSystem.remove_entity()
# ---------------------------------------------------------------------------


class TestBuffSystemRemoveEntity:
    def test_remove_entity_clears_all_active_buffs(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 15.0, 15.0))
        player.apply_buff(ActiveBuff("damage", 25.0, 12.0, 12.0))
        assert len(player.active_buffs) == 2
        buff_system.remove_entity(player)
        assert player.active_buffs == []

    def test_remove_entity_deregisters_so_update_is_noop(
        self, player: Player, buff_system: BuffSystem
    ) -> None:
        player.apply_buff(ActiveBuff("speed", 30.0, 5.0, 5.0))
        buff_system.remove_entity(player)
        # Ticking past the original duration must not crash or re-populate buffs
        buff_system.update(10.0)
        assert player.active_buffs == []

    def test_remove_entity_on_unregistered_entity_is_noop(
        self, buff_system: BuffSystem
    ) -> None:
        """Calling remove_entity for an entity never added must not raise."""
        orphan = Player(max_health=100)
        buff_system.remove_entity(orphan)  # Must not raise
        assert orphan.active_buffs == []

    def test_remove_entity_does_not_affect_other_entities(
        self, buff_system: BuffSystem
    ) -> None:
        p1 = Player(max_health=100, buff_system=buff_system)
        p2 = Player(max_health=100, buff_system=buff_system)
        p1.apply_buff(ActiveBuff("speed", 30.0, 10.0, 10.0))
        p2.apply_buff(ActiveBuff("damage", 25.0, 10.0, 10.0))
        buff_system.remove_entity(p1)
        assert p1.active_buffs == []
        assert len(p2.active_buffs) == 1


# ---------------------------------------------------------------------------
# Inventory — edge cases not covered by TestInventory
# ---------------------------------------------------------------------------


class TestInventoryEdgeCases:
    def test_slots_returns_a_copy_not_live_reference(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        inventory.add_item(medkit_small)
        snapshot = inventory.slots()
        snapshot[0] = None  # Mutate the copy
        assert inventory.item_at(0) is medkit_small  # Original is unaffected

    def test_item_at_returns_none_for_negative_index(
        self, inventory: Inventory
    ) -> None:
        assert inventory.item_at(-1) is None

    def test_item_at_returns_none_for_index_at_capacity(
        self, inventory: Inventory
    ) -> None:
        assert inventory.item_at(inventory.capacity) is None

    def test_item_at_returns_none_for_index_well_beyond_capacity(
        self, inventory: Inventory
    ) -> None:
        assert inventory.item_at(9999) is None

    def test_remove_item_on_empty_slot_returns_none(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        inventory.remove_item(slot)         # First removal — slot now empty
        result = inventory.remove_item(slot)  # Second removal — already empty
        assert result is None

    def test_remove_item_negative_index_returns_none(
        self, inventory: Inventory
    ) -> None:
        assert inventory.remove_item(-1) is None

    def test_remove_item_beyond_capacity_returns_none(
        self, inventory: Inventory
    ) -> None:
        assert inventory.remove_item(9999) is None

    def test_assign_quick_slot_ignores_out_of_range_qs_idx(
        self, inventory: Inventory, medkit_small: Consumable
    ) -> None:
        slot = inventory.add_item(medkit_small)
        inventory.assign_quick_slot(slot, 99)  # Must not raise
        # All quick-slots should remain unassigned
        assert all(qs is None for qs in inventory.quick_slots)

    def test_quick_slot_item_returns_none_for_negative_index(
        self, inventory: Inventory
    ) -> None:
        assert inventory.quick_slot_item(-1) is None

    def test_quick_slot_item_returns_none_for_out_of_range_index(
        self, inventory: Inventory
    ) -> None:
        assert inventory.quick_slot_item(99) is None

    def test_full_inventory_capacity_respected(
        self, medkit_small: Consumable
    ) -> None:
        inv = Inventory(capacity=2)
        inv.add_item(medkit_small)
        inv.add_item(medkit_small)
        result = inv.add_item(medkit_small)  # Third item — inventory is full
        assert result is None
