"""SaveManager — JSON save file read/write."""
from __future__ import annotations
import json
import os
from typing import Optional

_DEFAULT_SAVE_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'saves', 'save.json'
)

_DEFAULT_STATE = {
    'version': 1,
    'player': {'level': 1, 'xp': 0, 'money': 0},
    'inventory': [],
    'skill_tree': {'unlocked_nodes': []},
    'home_base': {},
}


class SaveManager:
    """Reads and writes saves/save.json."""

    def load(self, path: str = _DEFAULT_SAVE_PATH) -> dict:
        """Load save.json; return default state on error."""
        try:
            with open(path, encoding='utf-8') as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return dict(_DEFAULT_STATE)

    def save(self, state: dict, path: str = _DEFAULT_SAVE_PATH) -> None:
        """Write *state* to save.json, creating directories if needed."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(state, fh, indent=2)
