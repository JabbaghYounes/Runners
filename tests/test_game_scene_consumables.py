"""Integration tests for GameScene's quick-slot key dispatch (K_1–K_4).

Verifies the three wired joints in the consumables feature:
1. K_1–K_4 triggers Inventory.use_consumable() for the matching quick slot
2. consumable_used EventBus event is emitted exactly once
3. Item is removed from inventory after use
4. HP is restored for heal consumables (clamped at max_health)
5. Buff is added to player.active_buffs for buff consumables
6. Dead player cannot consume items (player.alive guard)
7. Empty quick slot is a safe no-op (no event, no error)
8. _full_init=False stub mode prevents dispatch entirely
"""
from __future__ import annotations

import sys
import types

import pytest


# ---------------------------------------------------------------------------
# Minimal Pygame stub — installed before any src imports
# ---------------------------------------------------------------------------


def _install_pygame_stub() -> None:
    """Install a lightweight pygame stub suitable for headless test execution."""
    if "pygame" in sys.modules:
        return

    pg = types.ModuleType("pygame")

    # --- Key constants ---
    pg.K_1 = 49
    pg.K_2 = 50
    pg.K_3 = 51
    pg.K_4 = 52
    pg.K_m = 109
    pg.K_ESCAPE = 27
    pg.K_e = 101
    pg.K_a = 97
    pg.K_d = 100
    pg.K_SPACE = 32
    pg.K_LCTRL = 306
    pg.K_LSHIFT = 304
    pg.K_c = 99

    pg.KEYDOWN = 2
    pg.KEYUP = 3

    # --- Rect stub with attributes used by Entity and game_scene ---
    class _Rect:
        def __init__(self, *args, **kwargs):
            if len(args) == 4:
                self.x, self.y, self.width, self.height = (
                    int(args[0]), int(args[1]), int(args[2]), int(args[3])
                )
            else:
                self.x = self.y = self.width = self.height = 0
            self.w = self.width
            self.h = self.height
            self.centerx = self.x + self.width // 2
            self.centery = self.y + self.height // 2
            self.left = self.x
            self.right = self.x + self.width
            self.top = self.y
            self.bottom = self.y + self.height

        def contains(self, *a):
            return False

        def unionall(self, others):
            return self

    pg.Rect = _Rect

    # --- math.Vector2 stub ---
    class _Vector2:
        def __init__(self, x=0.0, y=0.0):
            self.x = float(x)
            self.y = float(y)

    math_mod = types.ModuleType("pygame.math")
    math_mod.Vector2 = _Vector2
    pg.math = math_mod

    # --- font sub-module ---
    font_mod = types.ModuleType("pygame.font")
    font_mod.SysFont = lambda *a, **kw: None
    pg.font = font_mod

    # --- draw sub-module ---
    draw_mod = types.ModuleType("pygame.draw")
    draw_mod.rect = lambda *a, **kw: None
    pg.draw = draw_mod

    # --- key sub-module (returns empty dict — handle_input uses .get()) ---
    key_mod = types.ModuleType("pygame.key")
    key_mod.get_pressed = lambda: {}
    pg.key = key_mod

    sys.modules["pygame"] = pg
    sys.modules["pygame.math"] = math_mod
    sys.modules["pygame.font"] = font_mod
    sys.modules["pygame.draw"] = draw_mod
    sys.modules["pygame.key"] = key_mod


_install_pygame_stub()


# ---------------------------------------------------------------------------
# Safe to import src modules now
# ---------------------------------------------------------------------------

from src.core.event_bus import event_bus    # noqa: E402
from src.inventory.inventory import Inventory  # noqa: E402
from src.inventory.item import Consumable      # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_heal_consumable() -> Consumable:
    return Consumable(
        id="medkit_small",
        name="Small Medkit",
        rarity="common",
        sprite_key="medkit_small",
        value=50,
        consumable_type="heal",
        heal_amount=30,
    )


def _make_speed_stim() -> Consumable:
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


def _make_keydown(key: int):
    """Return a minimal KEYDOWN event-like object."""
    import pygame
    return types.SimpleNamespace(type=pygame.KEYDOWN, key=key)


def _make_scene():
    """Create a GameScene in stub mode with _full_init patched to True.

    Using zones=[] prevents _default_zones() from calling pygame.Rect at
    module level, keeping this constructor fully headless.
    """
    from src.scenes.game_scene import GameScene
    scene = GameScene(zones=[])
    scene._full_init = True
    return scene


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
def scene():
    return _make_scene()


# ---------------------------------------------------------------------------
# Quick-slot key dispatch
# ---------------------------------------------------------------------------


class TestQuickSlotDispatch:
    """K_1–K_4 dispatch through GameScene.handle_events → Inventory.use_consumable."""

    def test_k1_heal_consumable_restores_hp(self, scene) -> None:
        """K_1 on a heal consumable in quick slot 0 raises player HP."""
        import pygame

        medkit = _make_heal_consumable()
        scene.player.health = 60
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 0)

        scene.handle_events([_make_keydown(pygame.K_1)])

        assert scene.player.health == 90  # 60 + 30

    def test_k2_maps_to_quick_slot_1(self, scene) -> None:
        """K_2 dispatches to quick slot index 1."""
        import pygame

        medkit = _make_heal_consumable()
        scene.player.health = 50
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 1)

        scene.handle_events([_make_keydown(pygame.K_2)])

        assert scene.player.health == 80

    def test_k3_maps_to_quick_slot_2(self, scene) -> None:
        """K_3 dispatches to quick slot index 2."""
        import pygame

        medkit = _make_heal_consumable()
        scene.player.health = 70
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 2)

        scene.handle_events([_make_keydown(pygame.K_3)])

        assert scene.player.health == 100  # clamped at max

    def test_k4_maps_to_quick_slot_3(self, scene) -> None:
        """K_4 dispatches to quick slot index 3."""
        import pygame

        medkit = _make_heal_consumable()
        scene.player.health = 60
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 3)

        scene.handle_events([_make_keydown(pygame.K_4)])

        assert scene.player.health == 90

    def test_consumable_removed_from_inventory_after_use(self, scene) -> None:
        """The inventory slot is empty once the item is consumed."""
        import pygame

        medkit = _make_heal_consumable()
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 0)

        scene.handle_events([_make_keydown(pygame.K_1)])

        assert inv.item_at(slot) is None

    def test_quick_slot_unlinked_after_use(self, scene) -> None:
        """remove_item() clears the quick-slot reference automatically."""
        import pygame

        medkit = _make_heal_consumable()
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 0)

        scene.handle_events([_make_keydown(pygame.K_1)])

        assert inv.quick_slots[0] is None

    def test_consumable_used_event_emitted_once(self, scene) -> None:
        """consumable_used is emitted exactly once on successful use."""
        import pygame

        received: list[dict] = []
        event_bus.subscribe("consumable_used", received.append)

        medkit = _make_heal_consumable()
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 0)

        scene.handle_events([_make_keydown(pygame.K_1)])

        assert len(received) == 1

    def test_buff_consumable_adds_active_buff(self, scene) -> None:
        """K_1 on a buff consumable adds the buff to player.active_buffs."""
        import pygame

        stim = _make_speed_stim()
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(stim)
        inv.assign_quick_slot(slot, 0)

        scene.handle_events([_make_keydown(pygame.K_1)])

        assert len(scene.player.active_buffs) == 1
        assert scene.player.active_buffs[0].buff_type == "speed"

    def test_buff_consumable_has_correct_duration(self, scene) -> None:
        """The ActiveBuff created from a buff consumable carries the right duration."""
        import pygame

        stim = _make_speed_stim()
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(stim)
        inv.assign_quick_slot(slot, 0)

        scene.handle_events([_make_keydown(pygame.K_1)])

        buff = scene.player.active_buffs[0]
        assert buff.duration == pytest.approx(15.0)
        assert buff.time_remaining == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------


class TestDispatchGuards:
    """Verify the alive, _full_init, and empty-slot guards."""

    def test_empty_quick_slot_is_noop(self, scene) -> None:
        """K_1 on an unassigned quick slot emits nothing and does not raise."""
        import pygame

        received: list[dict] = []
        event_bus.subscribe("consumable_used", received.append)
        original_hp = scene.player.health

        scene.handle_events([_make_keydown(pygame.K_1)])

        assert received == []
        assert scene.player.health == original_hp

    def test_dead_player_cannot_consume(self, scene) -> None:
        """K_1 when player.alive is False is a complete no-op."""
        import pygame

        received: list[dict] = []
        event_bus.subscribe("consumable_used", received.append)

        medkit = _make_heal_consumable()
        scene.player.health = 0
        scene.player.alive = False
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 0)

        scene.handle_events([_make_keydown(pygame.K_1)])

        assert received == []
        assert inv.item_at(slot) is medkit  # Item is untouched

    def test_full_init_false_prevents_dispatch(self, scene) -> None:
        """If _full_init is False, the key handler must not fire."""
        import pygame

        received: list[dict] = []
        event_bus.subscribe("consumable_used", received.append)

        scene._full_init = False  # Revert to stub mode
        medkit = _make_heal_consumable()
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 0)

        scene.handle_events([_make_keydown(pygame.K_1)])

        assert received == []

    def test_heal_clamped_at_max_health(self, scene) -> None:
        """Healing a near-full player cannot exceed max_health."""
        import pygame

        medkit = _make_heal_consumable()  # heals 30
        scene.player.health = 90          # +30 → 120, must clamp to 100
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 0)

        scene.handle_events([_make_keydown(pygame.K_1)])

        assert scene.player.health == scene.player.max_health == 100

    def test_pressing_wrong_key_does_not_consume(self, scene) -> None:
        """Unrelated key presses do not trigger quick-slot use."""
        import pygame

        received: list[dict] = []
        event_bus.subscribe("consumable_used", received.append)

        medkit = _make_heal_consumable()
        inv: Inventory = scene.player.inventory
        slot = inv.add_item(medkit)
        inv.assign_quick_slot(slot, 0)

        # K_m should toggle the map overlay, not consume anything
        scene.handle_events([_make_keydown(pygame.K_m)])

        assert received == []
        assert inv.item_at(slot) is medkit
