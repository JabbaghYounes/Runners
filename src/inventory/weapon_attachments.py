"""Weapon attachment management for the inventory system.

Provides helper functions to attach/detach mods from weapons that live
inside an :class:`Inventory`, and serialization helpers so equipped
attachments survive save/load round-trips.
"""
from __future__ import annotations

from typing import Any

from src.inventory.item import Attachment, Weapon


# ---------------------------------------------------------------------------
# Inventory-level attach / detach helpers
# ---------------------------------------------------------------------------


def attach_to_weapon(
    weapon: Weapon,
    attachment: Attachment,
    slot_type: str | None = None,
) -> bool:
    """Attach *attachment* to *weapon*.

    This is a thin wrapper around :meth:`Weapon.attach` that also
    validates types.

    Args:
        weapon:     The weapon to modify.
        attachment: The attachment to equip.
        slot_type:  Override the attachment's own ``slot_type``.

    Returns:
        ``True`` on success, ``False`` otherwise.
    """
    if not isinstance(weapon, Weapon):
        return False
    if not isinstance(attachment, Attachment):
        return False
    return weapon.attach(attachment, slot_type=slot_type)


def detach_from_weapon(
    weapon: Weapon,
    slot_type: str,
) -> Attachment | None:
    """Detach and return the attachment in *slot_type* from *weapon*.

    Returns ``None`` if *weapon* is not a :class:`Weapon` or the slot
    was empty.
    """
    if not isinstance(weapon, Weapon):
        return None
    return weapon.detach(slot_type)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def weapon_to_save_dict(weapon: Weapon) -> dict[str, Any]:
    """Serialize a weapon (including its equipped attachments) to a dict
    suitable for JSON persistence.
    """
    data: dict[str, Any] = {
        "item_id": weapon.item_id,
        "mod_slots": list(weapon.mod_slots),
        "attachments": {},
    }
    for slot_type, att in weapon.attachments.items():
        data["attachments"][slot_type] = {
            "item_id": att.item_id,
            "slot_type": att.slot_type,
            "stat_delta": dict(att.stat_delta),
            "compatible_weapons": list(att.compatible_weapons),
            "name": att.name,
            "rarity": att.rarity.value if hasattr(att.rarity, "value") else str(att.rarity),
            "weight": att.weight,
            "value": att.value,
        }
    return data


def weapon_from_save_dict(
    data: dict[str, Any],
    item_factory=None,
) -> dict[str, Attachment]:
    """Deserialize attachment data from a save dict.

    Args:
        data:         The dict produced by :func:`weapon_to_save_dict`.
        item_factory: Optional callable ``(item_id) -> Item`` used to
                      reconstruct attachments from the database.  If
                      ``None``, attachments are rebuilt from the inline
                      data.

    Returns:
        A dict mapping slot type to :class:`Attachment` instances.
    """
    from src.inventory.item import Attachment, make_item

    attachments: dict[str, Attachment] = {}
    raw_atts = data.get("attachments", {})
    for slot_type, att_data in raw_atts.items():
        if item_factory is not None:
            try:
                att = item_factory(att_data["item_id"])
                if isinstance(att, Attachment):
                    attachments[slot_type] = att
                    continue
            except (KeyError, TypeError):
                pass
        # Fallback: rebuild from inline data
        att = make_item(
            item_id=att_data.get("item_id", ""),
            name=att_data.get("name", ""),
            item_type="attachment",
            rarity=att_data.get("rarity", "common"),
            value=att_data.get("value", 0),
            weight=att_data.get("weight", 0.0),
            stat_delta=att_data.get("stat_delta", {}),
            compatible_weapons=att_data.get("compatible_weapons", []),
            slot_type=att_data.get("slot_type", slot_type),
        )
        if isinstance(att, Attachment):
            attachments[slot_type] = att
    return attachments
