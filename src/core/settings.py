"""Persistent user settings backed by a JSON file."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List


_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "settings.json",
)


@dataclass
class Settings:
    """All user-configurable knobs for the game.

    Instances are created via :meth:`load`; never construct directly unless
    you explicitly want factory defaults.
    """

    volume_master: float = 1.0
    volume_music: float = 0.7
    volume_sfx: float = 1.0
    resolution: List[int] = field(default_factory=lambda: [1280, 720])
    fps: int = 60

    # ------------------------------------------------------------------
    # Factory / persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str = _DEFAULT_PATH) -> "Settings":
        """Load settings from *path*.

        If the file is missing or malformed the factory defaults are returned
        (and the file is *not* auto-written — call :meth:`save` explicitly).
        """
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return cls()

        instance = cls()
        instance.volume_master = float(data.get("volume_master", instance.volume_master))
        instance.volume_music = float(data.get("volume_music", instance.volume_music))
        instance.volume_sfx = float(data.get("volume_sfx", instance.volume_sfx))
        instance.fps = int(data.get("fps", instance.fps))
        res = data.get("resolution", instance.resolution)
        if isinstance(res, list) and len(res) == 2:
            instance.resolution = [int(res[0]), int(res[1])]
        return instance

    def save(self, path: str = _DEFAULT_PATH) -> None:
        """Persist current settings to *path* (creates file if absent)."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)
