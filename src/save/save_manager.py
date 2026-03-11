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

# Current save schema version.  Bump when the schema changes in a
# backwards-incompatible way and add a migration path in _migrate().
SAVE_VERSION: int = 1

# Default location for the save file.
_DEFAULT_SAVE_PATH: Path = Path("saves") / "save.json"


class SaveManager:
    """Handles loading and saving the player's persistent game state.

    Args:
        save_path: Path to the save file.  Defaults to ``saves/save.json``.
    """

    def __init__(self, save_path: Path | str | None = None) -> None:
        self._save_path: Path = (
            Path(save_path) if save_path is not None else _DEFAULT_SAVE_PATH
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Load the save file and return the state dictionary.

        On ``FileNotFoundError`` or any JSON parse error the method
        returns a fresh new-game state without raising.

        Returns:
            A fully populated state dict (see :meth:`_new_game` for schema).
        """
        try:
            with self._save_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return self._new_game()
        except json.JSONDecodeError:
            # Corrupt file — start fresh.
            return self._new_game()

        return self._migrate(data)

    def save(self, state: dict[str, Any]) -> None:
        """Persist *state* to disk atomically.

        The state dict is written to a temporary file alongside the real
        save file, then renamed into place.  This prevents partial writes
        from corrupting the save.

        Args:
            state: The full game state dict to persist.
        """
        # Ensure the save directory exists.
        self._save_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self._save_path.with_suffix(".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2)
            # Atomic rename — on POSIX this is guaranteed; on Windows it
            # replaces the target if it exists (Python 3.3+).
            os.replace(tmp_path, self._save_path)
        except OSError:
            # Clean up the temp file if something went wrong.
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _new_game(self) -> dict[str, Any]:
        """Return the canonical zero-state for a brand-new player."""
        return {
            "version": SAVE_VERSION,
            "player": {
                "level": 1,
                "xp": 0,
                "money": 0,
            },
            "inventory": [],
            "skill_tree": {
                "unlocked_nodes": [],
            },
            "home_base": {
                "armory": 0,
                "med_bay": 0,
                "storage": 0,
                "comms": 0,
            },
        }

    def _migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Apply any schema migrations required to bring *data* up to the
        current ``SAVE_VERSION``.

        New migrations should be added as ``elif file_version == N:`` blocks.

        Args:
            data: Raw dict loaded from the JSON save file.

        Returns:
            A fully migrated state dict.
        """
        file_version: int = data.get("version", 0)

        if file_version < 1:
            # v0 → v1: add money field (not present in v0 saves).
            data.setdefault("player", {})
            data["player"].setdefault("money", 0)
            data.setdefault("home_base", {
                "armory": 0,
                "med_bay": 0,
                "storage": 0,
                "comms": 0,
            })
            data["version"] = 1

        # Ensure all top-level keys exist (defensive merge with new-game
        # defaults so callers never KeyError on an old/partial save).
        defaults = self._new_game()
        for key, default_val in defaults.items():
            if key not in data:
                data[key] = default_val

        # Ensure all player sub-keys exist.
        for key, default_val in defaults["player"].items():
            data["player"].setdefault(key, default_val)

        # Ensure all home_base facility keys exist.
        for key, default_val in defaults["home_base"].items():
            data["home_base"].setdefault(key, default_val)

        return data
