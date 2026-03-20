"""BotLoadoutBuilder — random weapon + optional armor for PvP bots.

Usage::

    from src.entities.bot_loadout import BotLoadoutBuilder
    loadout = BotLoadoutBuilder.random_loadout(item_db, difficulty="medium")
    # loadout == {"weapon": <Item|None>, "armor": <Item|None>}
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.inventory.item_database import ItemDatabase
    from src.inventory.item import Item


def _rarity_str(item: Any) -> str:
    """Return the rarity as a lower-case string regardless of storage type."""
    r = getattr(item, "rarity", "common")
    if hasattr(r, "value"):
        return r.value.lower()
    return str(r).lower()


# Difficulty → preferred weapon rarity
_DIFFICULTY_RARITY: dict[str, str] = {
    "easy":   "common",
    "medium": "uncommon",
    "hard":   "rare",
}


class BotLoadoutBuilder:
    """Assembles a random weapon + optional armor from the ItemDatabase."""

    @staticmethod
    def random_loadout(
        item_db: "ItemDatabase",
        difficulty: str = "medium",
    ) -> dict[str, "Item | None"]:
        """Pick one weapon and optionally one armor item.

        Args:
            item_db:    Loaded ``ItemDatabase`` instance.
            difficulty: ``"easy"`` / ``"medium"`` / ``"hard"`` — controls
                        preferred weapon rarity.  Falls back to any rarity
                        when no items match.

        Returns:
            ``{"weapon": Item | None, "armor": Item | None}``
        """
        weapon: Item | None = None
        armor: Item | None = None

        # --- Weapon selection ---
        all_weapons: list = item_db.get_all_by_type("weapon")
        if all_weapons:
            target_rarity = _DIFFICULTY_RARITY.get(difficulty, "uncommon")
            filtered = [w for w in all_weapons if _rarity_str(w) == target_rarity]
            pool = filtered if filtered else all_weapons
            weapon = random.choice(pool)

        # --- Armor selection (50 % chance) ---
        if random.random() >= 0.5:
            all_armors: list = item_db.get_all_by_type("armor")
            if all_armors:
                armor = random.choice(all_armors)

        return {"weapon": weapon, "armor": armor}
