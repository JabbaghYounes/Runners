"""SaveManager -- read/write the player's persistent save file.

Design notes:
- Only ``PostRound`` and ``HomeBaseScene`` (on exit) call ``save()``.
  All other runtime code works against already-loaded state objects.
- Writes are atomic: data is flushed to a ``.tmp`` file then renamed into
  place so a crash mid-write never corrupts the existing save.
- A missing or corrupt save file silently falls back to a fresh new-game
  state -- the player simply starts from zero.
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

    def __init__(self, save_path: Path | str = _DEFAULT_SAVE_PATH) -> None:
        self._save_path = Path(save_path)

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

    def save(self, state: dict | Any = None, **kwargs: Any) -> None:
        """Persist the current progression state to disk atomically.

        Supports two calling conventions:
        1. save(state_dict) -- writes the dict directly
        2. save(home_base, currency, xp_system, inventory=None,
               skill_tree=None) -- builds the dict from live objects
        """
        if isinstance(state, dict):
            data = state
        elif state is not None:
            # Legacy calling convention: save(home_base, currency, xp_system, ...)
            home_base = state
            currency = kwargs.get("currency") or (
                kwargs.get("currency") if "currency" in kwargs else None
            )
            xp_system = kwargs.get("xp_system")
            inventory = kwargs.get("inventory")
            skill_tree = kwargs.get("skill_tree")
            data = self._build_state_dict(
                home_base=home_base,
                currency=currency,
                xp_system=xp_system,
                inventory=inventory,
                skill_tree=skill_tree,
            )
        elif any(k in kwargs for k in ("home_base", "currency", "xp_system",
                                         "inventory", "skill_tree")):
            # Calling convention: save(home_base=..., currency=..., xp_system=..., ...)
            data = self._build_state_dict(
                home_base=kwargs.get("home_base"),
                currency=kwargs.get("currency"),
                xp_system=kwargs.get("xp_system"),
                inventory=kwargs.get("inventory"),
                skill_tree=kwargs.get("skill_tree"),
            )
        else:
            data = self._new_game()

        # Ensure the saves/ directory exists
        self._save_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._save_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        tmp_path.replace(self._save_path)

    # ------------------------------------------------------------------
    # Build state dict from live game objects
    # ------------------------------------------------------------------

    @staticmethod
    def _build_state_dict(
        *,
        home_base: Any = None,
        currency: Any = None,
        xp_system: Any = None,
        inventory: Any = None,
        skill_tree: Any = None,
    ) -> dict:
        """Construct a save-file dict from live game objects."""
        return {
            "version": SAVE_VERSION,
            "player": {
                "level": getattr(xp_system, "level", 1) if xp_system else 1,
                "xp": getattr(xp_system, "xp", 0) if xp_system else 0,
                "money": getattr(currency, "balance", 0) if currency else 0,
            },
            "inventory": (
                inventory.to_save_list()
                if inventory is not None and hasattr(inventory, "to_save_list")
                else []
            ),
            "skill_tree": (
                {
                    "unlocked_nodes": skill_tree.to_save_dict().get("unlocked", []),
                    "unlocked": skill_tree.to_save_dict().get("unlocked", []),
                }
                if skill_tree is not None and hasattr(skill_tree, "to_save_dict")
                else {"unlocked_nodes": [], "unlocked": []}
            ),
            "home_base": (
                home_base.to_save_dict()
                if home_base is not None and hasattr(home_base, "to_save_dict")
                else {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0}
            ),
        }

    # ------------------------------------------------------------------
    # Restore state into live game objects
    # ------------------------------------------------------------------

    def restore(
        self,
        *,
        currency: Any = None,
        xp_system: Any = None,
        inventory: Any = None,
        skill_tree: Any = None,
        home_base: Any = None,
    ) -> dict:
        """Load the save file and push values into the supplied game objects.

        Any object parameter that is ``None`` is simply skipped.  Returns
        the raw state dict for callers that need additional fields.
        """
        state = self.load()

        player = state.get("player", {})
        if currency is not None:
            currency.balance = max(0, int(player.get("money", 0)))
        if xp_system is not None:
            xp_system.xp = player.get("xp", 0)
            xp_system.level = player.get("level", 1)
        if inventory is not None and hasattr(inventory, "from_save_list"):
            inventory.from_save_list(state.get("inventory", []))
        if skill_tree is not None:
            if hasattr(skill_tree, "load_state"):
                st_data = state.get("skill_tree", {})
                # Normalise: the skill_tree.load_state() expects {"unlocked": [...]},
                # while save file stores {"unlocked_nodes": [...]}.
                skill_tree.load_state(
                    {"unlocked": st_data.get("unlocked_nodes", st_data.get("unlocked", []))}
                )
        if home_base is not None:
            if hasattr(home_base, "from_save_dict"):
                home_base.from_save_dict(state.get("home_base", {}))
            elif hasattr(home_base, "load_state"):
                home_base.load_state(state.get("home_base", {}))

        return state

    def _new_game(self) -> dict:
        """Return the canonical zero-state for a brand-new player."""
        return {
            "version": SAVE_VERSION,
            "player": {"level": 1, "xp": 0, "money": 0},
            "inventory": [],
            "skill_tree": {"unlocked_nodes": []},
            "home_base": {"armory": 0, "med_bay": 0, "storage": 0, "comms": 0},
        }

    def _migrate(self, data: dict) -> dict:
        """Apply any schema migrations required to bring *data* up to the
        current ``SAVE_VERSION``.

        Args:
            data: Raw dict loaded from the JSON save file.

        Returns:
            A fully migrated state dict.
        """
        defaults = self._new_game()

        # Ensure all top-level keys exist (forward-compatibility)
        for key, default_val in defaults.items():
            if key not in data:
                data[key] = default_val

        file_version = data.get("version", 0)

        # v0 -> v1 migration
        if file_version < 1:
            data["version"] = 1

        # Ensure player block and sub-fields exist
        data.setdefault("player", {})
        for pkey in ("level", "xp", "money"):
            data["player"].setdefault(pkey, defaults["player"][pkey])

        # Ensure home_base block with all facilities
        data.setdefault("home_base", {})
        for facility in ("armory", "med_bay", "storage", "comms"):
            data["home_base"].setdefault(facility, 0)

        # Ensure skill_tree
        data.setdefault("skill_tree", {"unlocked_nodes": []})

        return data
