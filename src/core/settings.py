"""Persistent user settings backed by a JSON file."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List

_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "settings.json")


@dataclass
class Settings:
    """Typed settings object. Loaded from / saved to settings.json."""
    master_volume: float = 1.0
    music_volume: float = 0.7
    sfx_volume: float = 0.8
    resolution: List[int] = field(default_factory=lambda: [1280, 720])
    fullscreen: bool = False

    @classmethod
    def load(cls, path: str = _DEFAULT_PATH) -> "Settings":
        """Load settings from *path*, falling back to defaults on error."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            instance = cls()
            for key in asdict(instance):
                if key in data:
                    setattr(instance, key, data[key])
            return instance
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return cls()

    def save(self, path: str = _DEFAULT_PATH) -> None:
        """Write current settings to *path*."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)
