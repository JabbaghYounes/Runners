"""Persistent user settings backed by a JSON file."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List

_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'settings.json')


@dataclass
class Settings:
    """Typed game settings with JSON persistence.

    All fields have sensible defaults so a missing settings.json
    never causes a crash.
    """
    volume_master: float = 0.8
    volume_music: float = 0.6
    volume_sfx: float = 0.8
    resolution_w: int = 1280
    resolution_h: int = 720
    fullscreen: bool = False

    @classmethod
    def load(cls, path: str = _DEFAULT_PATH) -> "Settings":
        """Load settings from *path*, falling back to defaults on error."""
        instance = cls()
        try:
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
            for key in asdict(instance):
                if key in data:
                    setattr(instance, key, data[key])
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        return instance

    def save(self, path: str = _DEFAULT_PATH) -> None:
        """Write current settings to *path*."""
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(asdict(self), fh, indent=2)
