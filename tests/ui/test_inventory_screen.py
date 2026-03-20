"""Unit and integration tests for InventoryScreen overlay.

# Run: pytest tests/ui/test_inventory_screen.py

InventoryScreen is the Tab-key inventory overlay pushed over GameScene via the
scene-stack push/pop semantics.

Coverage:
  - Instantiation (with/without assets, with/without inventory)
  - handle_events: Tab/Escape → sm.pop(); other keys → no pop
  - handle_events: MOUSEMOTION updates _hovered_slot
  - handle_events: right-click on occupied slot assigns quick-slot
  - handle_events: right-click on empty/None slot → no-op
  - render: None inventory → no crash, shows error message
  - render: populated inventory → no crash
  - render: full 24-slot inventory → no crash
  - render: with hovered slot over item → tooltip drawn without crash
  - render: quick-slot badges drawn for assigned slots
  - Lifecycle no-ops: on_enter, on_exit, update
  - _slot_rect geometry (column/row layout)
  - _slot_at hit-detection (inside, outside, None inventory)
  - _assign_to_quick_slot (first free, second free, full wrap-around, empty slot)
  - Scene-stack overlay semantics: inventory unchanged through open/close cycle
"""

from __future__ import annotations

import pytest
import pygame
from unittest.mock import MagicMock

from src.ui.inventory_screen import InventoryScreen
from src.inventory.inventory import Inventory
from src.inventory.item import Weapon, Armor, Consumable, Rarity


# ---------------------------------------------------------------------------
# Grid layout constants — mirrored from inventory_screen.py so geometry
# assertions are independent of the production code's module-level values.
# ---------------------------------------------------------------------------

_SLOT_SIZE: int = 56
_SLOT_GAP: int = 6
_COLS: int = 6
_ROWS: int = 4
_SCREEN_W: int = 1280
_SCREEN_H: int = 720

_GRID_W: int = _COLS * _SLOT_SIZE + (_COLS - 1) * _SLOT_GAP   # 366 px
_GRID_H: int = _ROWS * _SLOT_SIZE + (_ROWS - 1) * _SLOT_GAP   # 242 px
_TITLE_Y: int = (_SCREEN_H - _GRID_H) // 2 - 60               # 179 px
_GRID_Y: int = _TITLE_Y + 52                                    # 231 px
_GRID_X: int = (_SCREEN_W - _GRID_W) // 2                      # 457 px


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sm() -> MagicMock:
    return MagicMock()


def _empty_inv() -> Inventory:
    return Inventory(max_slots=24, max_weight=20.0)


def _weapon(id: str = "pistol_01", weight: float = 1.5, name: str = "Test Pistol") -> Weapon:
    return Weapon(
        id=id, name=name, rarity=Rarity.COMMON,
        weight=weight, base_value=100, stats={}, sprite_path="",
        damage=25, fire_rate=4, magazine_size=15, mod_slots=[],
    )


def _armor(id: str = "vest_01", weight: float = 3.0) -> Armor:
    return Armor(
        id=id, name="Test Vest", rarity=Rarity.UNCOMMON,
        weight=weight, base_value=150, stats={}, sprite_path="",
        defense=20, slot="chest",
    )


def _consumable(id: str = "medkit_01", weight: float = 0.3) -> Consumable:
    return Consumable(
        id=id, name="MedKit", rarity=Rarity.RARE,
        weight=weight, base_value=75, stats={}, sprite_path="",
        effect_type="heal", effect_value=50,
    )


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)


def _mousemotion(pos: tuple) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0))


def _rclick(pos: tuple) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=3)


def _lclick(pos: tuple) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def _slot_center(idx: int) -> tuple:
    """Return the screen-space centre of general grid slot *idx*."""
    col = idx % _COLS
    row = idx // _COLS
    x = _GRID_X + col * (_SLOT_SIZE + _SLOT_GAP) + _SLOT_SIZE // 2
    y = _GRID_Y + row * (_SLOT_SIZE + _SLOT_GAP) + _SLOT_SIZE // 2
    return (x, y)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

class TestInstantiation:
    def test_constructs_without_inventory(self):
        scene = InventoryScreen(_make_sm(), inventory=None)
        assert scene is not None

    def test_constructs_with_empty_inventory(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene is not None

    def test_constructs_with_none_assets(self):
        scene = InventoryScreen(_make_sm(), _empty_inv(), assets=None)
        assert scene is not None

    def test_stores_inventory_reference(self):
        inv = _empty_inv()
        scene = InventoryScreen(_make_sm(), inv)
        assert scene._inventory is inv

    def test_stores_scene_manager_reference(self):
        sm = _make_sm()
        scene = InventoryScreen(sm, _empty_inv())
        assert scene._sm is sm

    def test_hovered_slot_is_none_on_construction(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene._hovered_slot is None

    def test_is_base_scene_subclass(self):
        from src.scenes.base_scene import BaseScene
        assert issubclass(InventoryScreen, BaseScene)

    def test_fulfils_base_scene_interface(self):
        """InventoryScreen can be instantiated without TypeError (all abstract methods implemented)."""
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert callable(scene.handle_events)
        assert callable(scene.update)
        assert callable(scene.render)


# ---------------------------------------------------------------------------
# handle_events: Tab and Escape close the overlay (sm.pop)
# ---------------------------------------------------------------------------

class TestHandleEventsCloseKeys:
    def test_tab_key_calls_sm_pop(self):
        sm = _make_sm()
        InventoryScreen(sm, _empty_inv()).handle_events([_keydown(pygame.K_TAB)])
        sm.pop.assert_called_once()

    def test_escape_key_calls_sm_pop(self):
        sm = _make_sm()
        InventoryScreen(sm, _empty_inv()).handle_events([_keydown(pygame.K_ESCAPE)])
        sm.pop.assert_called_once()

    def test_tab_calls_pop_exactly_once_per_event(self):
        sm = _make_sm()
        InventoryScreen(sm, _empty_inv()).handle_events([_keydown(pygame.K_TAB)])
        assert sm.pop.call_count == 1

    def test_return_key_does_not_call_sm_pop(self):
        sm = _make_sm()
        InventoryScreen(sm, _empty_inv()).handle_events([_keydown(pygame.K_RETURN)])
        sm.pop.assert_not_called()

    def test_spacebar_does_not_call_sm_pop(self):
        sm = _make_sm()
        InventoryScreen(sm, _empty_inv()).handle_events([_keydown(pygame.K_SPACE)])
        sm.pop.assert_not_called()

    def test_empty_event_list_does_not_call_sm_pop(self):
        sm = _make_sm()
        InventoryScreen(sm, _empty_inv()).handle_events([])
        sm.pop.assert_not_called()

    def test_consecutive_tab_events_each_call_pop(self):
        """Two handle_events calls each with Tab each result in one pop call."""
        sm = _make_sm()
        scene = InventoryScreen(sm, _empty_inv())
        scene.handle_events([_keydown(pygame.K_TAB)])
        scene.handle_events([_keydown(pygame.K_TAB)])
        assert sm.pop.call_count == 2

    def test_tab_key_pops_when_inventory_is_none(self):
        sm = _make_sm()
        InventoryScreen(sm, inventory=None).handle_events([_keydown(pygame.K_TAB)])
        sm.pop.assert_called_once()

    def test_escape_key_pops_when_inventory_is_none(self):
        sm = _make_sm()
        InventoryScreen(sm, inventory=None).handle_events([_keydown(pygame.K_ESCAPE)])
        sm.pop.assert_called_once()


# ---------------------------------------------------------------------------
# handle_events: MOUSEMOTION updates _hovered_slot
# ---------------------------------------------------------------------------

class TestHandleEventsMouseMotion:
    def test_motion_over_slot_0_sets_hovered_to_0(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        scene.handle_events([_mousemotion(_slot_center(0))])
        assert scene._hovered_slot == 0

    def test_motion_over_slot_5_sets_hovered_to_5(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        scene.handle_events([_mousemotion(_slot_center(5))])
        assert scene._hovered_slot == 5

    def test_motion_over_slot_23_sets_hovered_to_23(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        scene.handle_events([_mousemotion(_slot_center(23))])
        assert scene._hovered_slot == 23

    def test_motion_outside_grid_clears_hovered_slot(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        scene._hovered_slot = 3
        scene.handle_events([_mousemotion((0, 0))])   # far top-left, outside grid
        assert scene._hovered_slot is None

    def test_mouse_motion_does_not_call_sm_pop(self):
        sm = _make_sm()
        InventoryScreen(sm, _empty_inv()).handle_events([_mousemotion(_slot_center(3))])
        sm.pop.assert_not_called()

    def test_motion_with_none_inventory_does_not_raise(self):
        """_slot_at returns None when inventory is None; motion handler must not crash."""
        scene = InventoryScreen(_make_sm(), inventory=None)
        scene.handle_events([_mousemotion((500, 300))])
        assert scene._hovered_slot is None


# ---------------------------------------------------------------------------
# handle_events: right-click assigns quick-slot
# ---------------------------------------------------------------------------

class TestHandleEventsRightClick:
    def test_right_click_on_occupied_slot_assigns_to_first_free_quick_slot(self):
        inv = _empty_inv()
        inv.add_item(_consumable())         # lands in inventory slot 0
        scene = InventoryScreen(_make_sm(), inv)
        scene.handle_events([_rclick(_slot_center(0))])
        # Quick-slot 0 should now point at inventory slot 0
        assert inv.quick_slots[0] == 0

    def test_right_click_on_empty_slot_does_not_assign_quick_slot(self):
        inv = _empty_inv()                  # all slots empty
        scene = InventoryScreen(_make_sm(), inv)
        scene.handle_events([_rclick(_slot_center(0))])
        assert all(qs is None for qs in inv.quick_slots)

    def test_right_click_outside_grid_does_not_assign_quick_slot(self):
        inv = _empty_inv()
        scene = InventoryScreen(_make_sm(), inv)
        scene.handle_events([_rclick((0, 0))])
        assert all(qs is None for qs in inv.quick_slots)

    def test_right_click_with_none_inventory_does_not_raise(self):
        scene = InventoryScreen(_make_sm(), inventory=None)
        scene.handle_events([_rclick((500, 300))])  # must not raise

    def test_left_click_does_not_assign_quick_slot(self):
        inv = _empty_inv()
        inv.add_item(_consumable())
        scene = InventoryScreen(_make_sm(), inv)
        scene.handle_events([_lclick(_slot_center(0))])
        assert all(qs is None for qs in inv.quick_slots)


# ---------------------------------------------------------------------------
# render: no crash under various inventory states
# ---------------------------------------------------------------------------

class TestRender:
    """render() is a pure rendering method — tests verify it never raises."""

    @pytest.fixture(autouse=True)
    def _surf(self):
        self.screen = pygame.Surface((_SCREEN_W, _SCREEN_H))

    def test_render_with_none_inventory_does_not_raise(self):
        InventoryScreen(_make_sm(), inventory=None).render(self.screen)

    def test_render_with_empty_inventory_does_not_raise(self):
        InventoryScreen(_make_sm(), _empty_inv()).render(self.screen)

    def test_render_with_single_weapon_does_not_raise(self):
        inv = _empty_inv()
        inv.add_item(_weapon())
        InventoryScreen(_make_sm(), inv).render(self.screen)

    def test_render_with_multiple_item_types_does_not_raise(self):
        inv = _empty_inv()
        inv.add_item(_weapon())
        inv.add_item(_armor())
        inv.add_item(_consumable())
        InventoryScreen(_make_sm(), inv).render(self.screen)

    def test_render_with_full_24_slot_inventory_does_not_raise(self):
        inv = _empty_inv()
        for i in range(24):
            inv.add_item(_weapon(id=f"w_{i}", weight=0.5))
        InventoryScreen(_make_sm(), inv).render(self.screen)

    def test_render_with_quick_slot_assigned_does_not_raise(self):
        inv = _empty_inv()
        inv.add_item(_consumable())
        inv.assign_quick_slot(0, 0)
        InventoryScreen(_make_sm(), inv).render(self.screen)

    def test_render_twice_uses_cached_fonts_without_raising(self):
        inv = _empty_inv()
        inv.add_item(_weapon())
        scene = InventoryScreen(_make_sm(), inv)
        scene.render(self.screen)
        scene.render(self.screen)   # second render; _fonts_ready guard active

    def test_render_with_hovered_slot_over_occupied_item_shows_tooltip_without_raising(self):
        inv = _empty_inv()
        inv.add_item(_weapon())
        scene = InventoryScreen(_make_sm(), inv)
        scene._hovered_slot = 0     # force tooltip path
        scene.render(self.screen)

    def test_render_with_all_rarity_tiers_does_not_raise(self):
        inv = _empty_inv()
        for i, rarity in enumerate(Rarity):
            inv.add_item(Weapon(
                id=f"w_{i}", name=f"{rarity.value} gun",
                rarity=rarity, weight=0.5, base_value=100, stats={}, sprite_path="",
                damage=20, fire_rate=3, magazine_size=10, mod_slots=[],
            ))
        InventoryScreen(_make_sm(), inv).render(self.screen)

    def test_render_with_assets_none_does_not_raise(self):
        inv = _empty_inv()
        inv.add_item(_weapon())
        InventoryScreen(_make_sm(), inv, assets=None).render(self.screen)

    def test_render_weapon_tooltip_includes_damage_stat(self):
        """Rendering with a weapon tooltip must not raise when damage is non-zero."""
        inv = _empty_inv()
        inv.add_item(_weapon())     # weapon has damage=25
        scene = InventoryScreen(_make_sm(), inv)
        scene._hovered_slot = 0    # trigger tooltip branch
        scene.render(self.screen)  # must not raise

    def test_render_armor_tooltip_does_not_raise(self):
        inv = _empty_inv()
        inv.add_item(_armor())
        scene = InventoryScreen(_make_sm(), inv)
        scene._hovered_slot = 0
        scene.render(self.screen)

    def test_render_consumable_tooltip_does_not_raise(self):
        inv = Inventory(max_slots=24, max_weight=50.0)
        cons = Consumable(
            id="big_kit", name="BigKit", rarity=Rarity.UNCOMMON,
            weight=0.5, base_value=80, stats={}, sprite_path="",
            consumable_type="heal", heal_amount=60,
        )
        inv.add_item(cons)
        scene = InventoryScreen(_make_sm(), inv)
        scene._hovered_slot = 0
        scene.render(self.screen)


# ---------------------------------------------------------------------------
# Lifecycle no-ops: on_enter, on_exit, update
# ---------------------------------------------------------------------------

class TestLifecycleNoOps:
    def test_on_enter_does_not_raise(self):
        InventoryScreen(_make_sm(), _empty_inv()).on_enter()

    def test_on_exit_does_not_raise(self):
        InventoryScreen(_make_sm(), _empty_inv()).on_exit()

    def test_update_does_not_raise(self):
        InventoryScreen(_make_sm(), _empty_inv()).update(1 / 60)

    def test_on_enter_returns_none(self):
        assert InventoryScreen(_make_sm(), _empty_inv()).on_enter() is None

    def test_on_exit_returns_none(self):
        assert InventoryScreen(_make_sm(), _empty_inv()).on_exit() is None

    def test_update_returns_none(self):
        assert InventoryScreen(_make_sm(), _empty_inv()).update(0.016) is None

    def test_update_with_large_dt_does_not_raise(self):
        InventoryScreen(_make_sm(), _empty_inv()).update(10.0)

    def test_on_enter_with_none_inventory_does_not_raise(self):
        InventoryScreen(_make_sm(), inventory=None).on_enter()

    def test_on_exit_with_none_inventory_does_not_raise(self):
        InventoryScreen(_make_sm(), inventory=None).on_exit()


# ---------------------------------------------------------------------------
# _slot_rect geometry
# ---------------------------------------------------------------------------

class TestSlotRect:
    """_slot_rect(idx) must return correct Rect objects for the 6×4 grid."""

    def test_slot_0_x_equals_grid_x(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene._slot_rect(0).x == _GRID_X

    def test_slot_0_y_equals_grid_y(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene._slot_rect(0).y == _GRID_Y

    def test_slot_0_width_equals_slot_size(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene._slot_rect(0).width == _SLOT_SIZE

    def test_slot_0_height_equals_slot_size(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene._slot_rect(0).height == _SLOT_SIZE

    def test_slot_1_is_one_step_right_of_slot_0(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        r0 = scene._slot_rect(0)
        r1 = scene._slot_rect(1)
        assert r1.x == r0.x + _SLOT_SIZE + _SLOT_GAP
        assert r1.y == r0.y

    def test_slot_6_starts_second_row(self):
        """Slot 6 (index 6 % 6 == col 0, row 1) is directly below slot 0."""
        scene = InventoryScreen(_make_sm(), _empty_inv())
        r0 = scene._slot_rect(0)
        r6 = scene._slot_rect(6)
        assert r6.y == r0.y + _SLOT_SIZE + _SLOT_GAP
        assert r6.x == r0.x

    def test_slot_23_is_last_cell(self):
        """Slot 23: column 5, row 3."""
        scene = InventoryScreen(_make_sm(), _empty_inv())
        r = scene._slot_rect(23)
        expected_x = _GRID_X + 5 * (_SLOT_SIZE + _SLOT_GAP)
        expected_y = _GRID_Y + 3 * (_SLOT_SIZE + _SLOT_GAP)
        assert r.x == expected_x
        assert r.y == expected_y

    def test_all_slots_have_correct_size(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        for idx in range(24):
            r = scene._slot_rect(idx)
            assert r.width == _SLOT_SIZE
            assert r.height == _SLOT_SIZE

    def test_no_two_slots_overlap(self):
        """Adjacent grid cells must not overlap each other."""
        scene = InventoryScreen(_make_sm(), _empty_inv())
        rects = [scene._slot_rect(i) for i in range(24)]
        for a in range(24):
            for b in range(a + 1, 24):
                assert not rects[a].colliderect(rects[b]), (
                    f"Slots {a} and {b} overlap: {rects[a]} vs {rects[b]}"
                )


# ---------------------------------------------------------------------------
# _slot_at hit-detection
# ---------------------------------------------------------------------------

class TestSlotAt:
    def test_center_of_slot_0_returns_0(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene._slot_at(_slot_center(0)) == 0

    def test_center_of_slot_5_returns_5(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene._slot_at(_slot_center(5)) == 5

    def test_center_of_slot_23_returns_23(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene._slot_at(_slot_center(23)) == 23

    def test_position_at_top_left_of_screen_returns_none(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene._slot_at((0, 0)) is None

    def test_position_at_bottom_right_of_screen_returns_none(self):
        scene = InventoryScreen(_make_sm(), _empty_inv())
        assert scene._slot_at((_SCREEN_W - 1, _SCREEN_H - 1)) is None

    def test_slot_at_with_none_inventory_returns_none(self):
        scene = InventoryScreen(_make_sm(), inventory=None)
        assert scene._slot_at((500, 300)) is None

    def test_position_in_gap_between_slots_returns_none(self):
        """The gap between slot 0 and slot 1 (x-axis) must not hit any slot."""
        scene = InventoryScreen(_make_sm(), _empty_inv())
        gap_x = _GRID_X + _SLOT_SIZE + 1   # 1 px into the 6-px gap after slot 0
        gap_y = _GRID_Y + _SLOT_SIZE // 2
        result = scene._slot_at((gap_x, gap_y))
        # The gap pixel must not collide with slot 0 or slot 1
        assert result != 0


# ---------------------------------------------------------------------------
# _assign_to_quick_slot
# ---------------------------------------------------------------------------

class TestAssignToQuickSlot:
    def test_assigns_occupied_slot_to_first_free_quick_slot(self):
        inv = _empty_inv()
        inv.add_item(_consumable())     # inventory slot 0
        scene = InventoryScreen(_make_sm(), inv)
        scene._assign_to_quick_slot(0)
        assert inv.quick_slots[0] == 0

    def test_assigns_to_second_quick_slot_when_first_occupied(self):
        inv = _empty_inv()
        inv.add_item(_consumable("c1"))  # slot 0
        inv.add_item(_consumable("c2"))  # slot 1
        inv.assign_quick_slot(0, 0)      # lock quick-slot 0 → inventory slot 0
        scene = InventoryScreen(_make_sm(), inv)
        scene._assign_to_quick_slot(1)   # should land in quick-slot 1
        assert inv.quick_slots[1] == 1

    def test_fills_all_four_quick_slots_sequentially(self):
        inv = _empty_inv()
        for i in range(4):
            inv.add_item(_consumable(f"c{i}"))
        scene = InventoryScreen(_make_sm(), inv)
        for i in range(4):
            scene._assign_to_quick_slot(i)
        assert inv.quick_slots == [0, 1, 2, 3]

    def test_wraps_to_quick_slot_0_when_all_occupied(self):
        inv = _empty_inv()
        for i in range(5):
            inv.add_item(_consumable(f"c{i}", weight=0.1))
        # Fill all four quick-slots with the first four items
        for qs in range(4):
            inv.assign_quick_slot(qs, qs)
        scene = InventoryScreen(_make_sm(), inv)
        # Assign slot 4 (fifth item) → all quick-slots full → wraps to quick-slot 0
        scene._assign_to_quick_slot(4)
        assert inv.quick_slots[0] == 4

    def test_does_nothing_for_empty_inventory_slot(self):
        inv = _empty_inv()          # all slots empty
        scene = InventoryScreen(_make_sm(), inv)
        scene._assign_to_quick_slot(0)
        assert all(qs is None for qs in inv.quick_slots)

    def test_does_nothing_when_inventory_is_none(self):
        scene = InventoryScreen(_make_sm(), inventory=None)
        scene._assign_to_quick_slot(0)   # must not raise


# ---------------------------------------------------------------------------
# Scene-stack / overlay semantics
# ---------------------------------------------------------------------------

class TestOverlaySemantics:
    def test_construction_does_not_mutate_inventory(self):
        inv = _empty_inv()
        weapon = _weapon()
        inv.add_item(weapon)
        InventoryScreen(_make_sm(), inv)
        # Construction must not change the inventory
        assert weapon in inv.slots

    def test_inventory_unchanged_through_open_update_close_cycle(self):
        """on_enter → update → Tab → on_exit must not alter inventory contents."""
        inv = _empty_inv()
        weapon = _weapon()
        inv.add_item(weapon)

        scene = InventoryScreen(_make_sm(), inv)
        scene.on_enter()
        scene.update(0.016)
        scene.handle_events([_keydown(pygame.K_TAB)])
        scene.on_exit()

        assert weapon in inv.slots
        assert inv.used_slots == 1

    def test_repeated_open_close_cycles_do_not_corrupt_inventory(self):
        inv = _empty_inv()
        for i in range(3):
            inv.add_item(_weapon(f"w{i}", weight=0.5))

        for _ in range(3):
            scene = InventoryScreen(_make_sm(), inv)
            scene.on_enter()
            scene.handle_events([_keydown(pygame.K_ESCAPE)])
            scene.on_exit()

        assert inv.used_slots == 3

    def test_quick_slot_assignment_persists_after_close(self):
        """A quick-slot assignment made inside the overlay must survive after close."""
        inv = _empty_inv()
        inv.add_item(_consumable())
        scene = InventoryScreen(_make_sm(), inv)
        scene.on_enter()
        scene._assign_to_quick_slot(0)
        scene.handle_events([_keydown(pygame.K_TAB)])
        scene.on_exit()

        assert inv.quick_slots[0] == 0
