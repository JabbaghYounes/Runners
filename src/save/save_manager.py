"""SaveManager — read/write the player's persistent save file.

Design notes:
- Only ``PostRound`` and ``HomeBaseScene`` (on exit) call ``save()``.
  All other runtime code works against already-loaded state objects.
- Writes are atomic: data is flushed to a ``.tmp`` file then renamed into
  place so a crash mid-write never corrupts the existing save.
- A missing or corrupt save file silently falls back to a fresh new-game
  state — the player simply starts from zero.
- The ``version`` field allows future migrations without breaking old saves.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SAVE_VERSION: int = 1
_DEFAULT_SAVE_PATH = Path("saves/save.json")


class SaveManager:
    """Handles JSON persistence for player progression."""

    def __init__(self, save_path: Path = _DEFAULT_SAVE_PATH) -> None:
        self._save_path = save_path

    def load(self) -> dict:
        """Load the save file and return the state dictionary.

        On ``FileNotFoundError`` or any JSON parse error the method
        returns a fresh new-game state without raising.

        Returns:
            A fully populated state dict (see :meth:`_new_game` for schema).
        """
        try:
            with open(self._save_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return self._migrate(data)
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
            return self._new_game()

    def save(
        self,
        home_base,
        currency,
        xp_system,
        inventory=None,
    ) -> None:
        """Persist the current progression state to disk atomically.

        The state dict is written to a temporary file alongside the real
        save file, then renamed into place. This prevents partial writes
        from corrupting the save.

        Args:
            home_base: HomeBase object — provides to_save_dict().
            currency: Currency object — provides .balance.
            xp_system: XPSystem object — provides .level and .xp.
            inventory: Optional Inventory — provides to_save_list().
        """
        data = {
            "version": SAVE_VERSION,
            "player": {
                "level": xp_system.level,
                "xp": xp_system.xp,
                "money": currency.balance,
            },
            "inventory": inventory.to_save_list() if inventory is not None else [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": home_base.to_save_dict(),
        }
        # Ensure the saves/ directory exists
        self._save_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._save_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        tmp_path.replace(self._save_path)

    def _new_game(self) -> dict:
        """Return the canonical zero-state for a brand-new player."""
        return {
            "version": SAVE_VERSION,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0},
        }

    def _migrate(self, data: dict) -> dict:
        """Apply any schema migrations required to bring *data* up to the
        current ``SAVE_VERSION``.

        Args:
            data: Raw dict loaded from the JSON save file.

        Returns:
            A fully migrated state dict.
        """
        file_version = data.get("version", 0)
        defaults = self._new_game()

        # Ensure all top-level keys exist (forward-compatibility)
        for key, default_val in defaults.items():
            if key not in data:
                data[key] = default_val

        # Ensure home_base block exists
        if "home_base" not in data:
            data["home_base"] = defaults["home_base"]

        # Ensure player.money exists
        if "money" not in data.get("player", {}):
            data.setdefault("player", {})["money"] = 0

        return data
