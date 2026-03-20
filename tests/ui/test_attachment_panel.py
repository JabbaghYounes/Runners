"""Unit and integration tests for the AttachmentPanel UI widget.

AttachmentPanel (src/ui/attachment_panel.py) is the self-contained widget
that renders a weapon's mod slots inside the InventoryScreen and handles
click-to-equip / click-to-remove interactions.

Expected public API:
    panel = AttachmentPanel(weapon, inventory, font)
    panel.render(surface)               -> None
    panel.handle_click(pos, selected)   -> bool  (True = action taken)
    panel.status                        -> str   (feedback message, "" if none)

Slot positions are exposed via:
    panel.slot_rects                    -> dict[str, pygame.Rect]

All logic tests are run without touching the rendering path.

# Run: pytest tests/ui/test_attachment_panel.py
"""
from __future__ import annotations

from typing import Any

import pygame
import pytest

# Skip the entire module if AttachmentPanel has not been implemented yet.
AttachmentPanel = pytest.importorskip(
    "src.ui.attachment_panel",
    reason="src/ui/attachment_panel.py not yet implemented",
).AttachmentPanel

from src.inventory.item import Attachment, Rarity, Weapon
from src.inventory.inventory import Inventory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weapon(
    wid: str = "rifle_01",
    mod_slots: list[str] | None = None,
    damage: int = 30,
) -> Weapon:
    return Weapon(
        id=wid,
        name="Test Rifle",
        rarity=Rarity.COMMON,
        weight=3.0,
        base_value=200,
        stats={"range": 450, "reload_time": 2.0},
        sprite_path="",
        damage=damage,
        fire_rate=4.0,
        magazine_size=20,
        mod_slots=mod_slots if mod_slots is not None else ["scope", "barrel"],
    )


def _attachment(
    aid: str = "scope_01",
    slot_type: str = "scope",
    stat_delta: dict | None = None,
    compatible_weapons: list[str] | None = None,
    weight: float = 0.3,
) -> Attachment:
    return Attachment(
        id=aid,
        name="Test Scope",
        rarity=Rarity.COMMON,
        weight=weight,
        base_value=80,
        stats={},
        sprite_path="",
        slot_type=slot_type,
        compatible_weapons=compatible_weapons or [],
        stat_delta=stat_delta or {"accuracy": 10},
    )


def _inventory(capacity: int = 10, max_weight: float = 50.0) -> Inventory:
    return Inventory(max_slots=capacity, max_weight=max_weight)


@pytest.fixture()
def font() -> pygame.font.Font | None:
    """Provide a font object (or None if the panel accepts None gracefully)."""
    pygame.font.init()
    try:
        return pygame.font.Font(None, 24)
    except Exception:
        return None


@pytest.fixture()
def surface() -> pygame.Surface:
    return pygame.Surface((800, 600))


# ---------------------------------------------------------------------------
# Construction and initialisation
# ---------------------------------------------------------------------------


class TestAttachmentPanelInit:
    def test_panel_instantiates_without_error(self, font: Any) -> None:
        w = _weapon()
        inv = _inventory()
        panel = AttachmentPanel(w, inv, font)
        assert panel is not None

    def test_panel_exposes_slot_rects_dict(self, font: Any) -> None:
        """Panel must expose slot_rects so tests can derive click positions."""
        w = _weapon(mod_slots=["scope", "barrel"])
        inv = _inventory()
        panel = AttachmentPanel(w, inv, font)
        assert hasattr(panel, "slot_rects"), (
            "AttachmentPanel must expose 'slot_rects: dict[str, pygame.Rect]'"
        )
        assert isinstance(panel.slot_rects, dict)

    def test_slot_rects_contains_all_weapon_mod_slots(self, font: Any) -> None:
        w = _weapon(mod_slots=["scope", "barrel", "grip"])
        inv = _inventory()
        panel = AttachmentPanel(w, inv, font)
        for slot in ("scope", "barrel", "grip"):
            assert slot in panel.slot_rects, (
                f"slot_rects is missing key {slot!r}"
            )

    def test_weapon_with_no_slots_shows_no_slot_rects(self, font: Any) -> None:
        w = _weapon(mod_slots=[])
        inv = _inventory()
        panel = AttachmentPanel(w, inv, font)
        assert panel.slot_rects == {}

    def test_status_is_empty_string_on_creation(self, font: Any) -> None:
        w = _weapon()
        inv = _inventory()
        panel = AttachmentPanel(w, inv, font)
        assert panel.status == ""

    def test_render_does_not_raise_on_surface(
        self, font: Any, surface: pygame.Surface
    ) -> None:
        w = _weapon()
        inv = _inventory()
        panel = AttachmentPanel(w, inv, font)
        panel.render(surface)  # must not raise


# ---------------------------------------------------------------------------
# Clicking an empty slot while holding a matching attachment — equip path
# ---------------------------------------------------------------------------


class TestAttachmentPanelEquip:
    def test_handle_click_on_empty_slot_with_matching_attachment_equips_it(
        self, font: Any
    ) -> None:
        w = _weapon(mod_slots=["scope"])
        inv = _inventory()
        att = _attachment(slot_type="scope", stat_delta={"damage": 5})
        inv.add(att)
        panel = AttachmentPanel(w, inv, font)

        slot_center = panel.slot_rects["scope"].center
        panel.handle_click(slot_center, selected_item=att)

        assert w.get_attachment("scope") is att

    def test_equipping_removes_attachment_from_inventory(self, font: Any) -> None:
        w = _weapon(mod_slots=["scope"])
        inv = _inventory()
        att = _attachment(slot_type="scope")
        inv.add(att)
        panel = AttachmentPanel(w, inv, font)

        slot_center = panel.slot_rects["scope"].center
        panel.handle_click(slot_center, selected_item=att)

        assert att not in inv.get_items()

    def test_handle_click_returns_true_on_successful_equip(
        self, font: Any
    ) -> None:
        w = _weapon(mod_slots=["scope"])
        inv = _inventory()
        att = _attachment(slot_type="scope")
        inv.add(att)
        panel = AttachmentPanel(w, inv, font)

        result = panel.handle_click(
            panel.slot_rects["scope"].center, selected_item=att
        )
        assert result is True

    def test_equipping_incompatible_attachment_is_rejected(
        self, font: Any
    ) -> None:
        """An attachment whose slot_type doesn't match the target slot must be rejected."""
        w = _weapon(mod_slots=["scope"])
        inv = _inventory()
        barrel_att = _attachment(slot_type="barrel", stat_delta={"damage": 4})
        inv.add(barrel_att)
        panel = AttachmentPanel(w, inv, font)

        # Click the scope slot while holding a barrel attachment
        result = panel.handle_click(
            panel.slot_rects["scope"].center, selected_item=barrel_att
        )
        assert result is False
        assert w.get_attachment("scope") is None

    def test_equipping_incompatible_attachment_sets_status_message(
        self, font: Any
    ) -> None:
        w = _weapon(mod_slots=["scope"])
        inv = _inventory()
        barrel_att = _attachment(slot_type="barrel")
        inv.add(barrel_att)
        panel = AttachmentPanel(w, inv, font)

        panel.handle_click(panel.slot_rects["scope"].center, selected_item=barrel_att)
        assert panel.status != "", (
            "Panel must set a non-empty status message when an incompatible "
            "attachment is attempted"
        )

    def test_handle_click_with_no_selected_item_on_empty_slot_does_nothing(
        self, font: Any
    ) -> None:
        w = _weapon(mod_slots=["scope"])
        inv = _inventory()
        panel = AttachmentPanel(w, inv, font)

        result = panel.handle_click(
            panel.slot_rects["scope"].center, selected_item=None
        )
        assert result is False
        assert w.get_attachment("scope") is None

    def test_equipping_weapon_incompatible_attachment_is_rejected(
        self, font: Any
    ) -> None:
        """An attachment whose compatible_weapons list excludes this weapon is blocked."""
        w = _weapon(wid="rifle_01", mod_slots=["scope"])
        inv = _inventory()
        att = _attachment(
            slot_type="scope",
            compatible_weapons=["pistol_01"],  # rifle not in the list
        )
        inv.add(att)
        panel = AttachmentPanel(w, inv, font)

        result = panel.handle_click(
            panel.slot_rects["scope"].center, selected_item=att
        )
        assert result is False


# ---------------------------------------------------------------------------
# Clicking an occupied slot — detach path
# ---------------------------------------------------------------------------


class TestAttachmentPanelDetach:
    def test_handle_click_on_occupied_slot_detaches_attachment(
        self, font: Any
    ) -> None:
        w = _weapon(mod_slots=["scope"])
        inv = _inventory()
        att = _attachment(slot_type="scope")
        w.attach(att)
        panel = AttachmentPanel(w, inv, font)

        panel.handle_click(panel.slot_rects["scope"].center, selected_item=None)

        assert w.get_attachment("scope") is None

    def test_detached_attachment_added_to_inventory(self, font: Any) -> None:
        w = _weapon(mod_slots=["scope"])
        inv = _inventory()
        att = _attachment(slot_type="scope")
        w.attach(att)
        panel = AttachmentPanel(w, inv, font)

        panel.handle_click(panel.slot_rects["scope"].center, selected_item=None)

        assert att in inv.get_items()

    def test_handle_click_returns_true_on_successful_detach(
        self, font: Any
    ) -> None:
        w = _weapon(mod_slots=["scope"])
        inv = _inventory()
        att = _attachment(slot_type="scope")
        w.attach(att)
        panel = AttachmentPanel(w, inv, font)

        result = panel.handle_click(
            panel.slot_rects["scope"].center, selected_item=None
        )
        assert result is True

    def test_detach_blocked_when_inventory_is_full(self, font: Any) -> None:
        """If the inventory has no free slots, detaching must be aborted."""
        # Create a 1-slot inventory that is already full
        inv = _inventory(capacity=1)
        filler = _attachment(aid="filler", slot_type="barrel")
        inv.add(filler)
        assert inv.is_full

        w = _weapon(mod_slots=["scope"])
        att = _attachment(aid="scope_01", slot_type="scope")
        w.attach(att)

        panel = AttachmentPanel(w, inv, font)
        result = panel.handle_click(
            panel.slot_rects["scope"].center, selected_item=None
        )

        assert result is False
        assert w.get_attachment("scope") is att  # attachment NOT removed

    def test_full_inventory_block_sets_status_message(self, font: Any) -> None:
        inv = _inventory(capacity=1)
        inv.add(_attachment(aid="filler", slot_type="barrel"))
        w = _weapon(mod_slots=["scope"])
        w.attach(_attachment(slot_type="scope"))

        panel = AttachmentPanel(w, inv, font)
        panel.handle_click(panel.slot_rects["scope"].center, selected_item=None)

        assert panel.status != "", (
            "Panel must set a non-empty status message when detach is blocked "
            "by a full inventory"
        )


# ---------------------------------------------------------------------------
# Weapons with no mod slots
# ---------------------------------------------------------------------------


class TestAttachmentPanelNoSlots:
    def test_weapon_with_no_slots_produces_empty_slot_rects(
        self, font: Any
    ) -> None:
        w = _weapon(mod_slots=[])
        inv = _inventory()
        panel = AttachmentPanel(w, inv, font)
        assert panel.slot_rects == {}

    def test_handle_click_on_no_slot_weapon_returns_false(
        self, font: Any
    ) -> None:
        w = _weapon(mod_slots=[])
        inv = _inventory()
        att = _attachment(slot_type="scope")
        inv.add(att)
        panel = AttachmentPanel(w, inv, font)

        result = panel.handle_click((100, 100), selected_item=att)
        assert result is False

    def test_render_no_slots_weapon_does_not_raise(
        self, font: Any, surface: pygame.Surface
    ) -> None:
        w = _weapon(mod_slots=[])
        inv = _inventory()
        panel = AttachmentPanel(w, inv, font)
        panel.render(surface)  # must not raise
