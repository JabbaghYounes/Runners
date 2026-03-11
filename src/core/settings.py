"""Runtime user settings.

Loaded from settings.json at startup; written back with Settings.save().
Provides typed access to resolution, FPS target, volume levels, and key bindings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

import pygame

# Path resolved relative to this file so it works from any working directory.
_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "settings.json"


@dataclass
class Settings:
    """Typed container for all user-configurable options."""

    resolution:    Tuple[int, int]    = (1280, 720)
    fullscreen:    bool               = False
    target_fps:    int                = 60
    music_volume:  float              = 0.7
    sfx_volume:    float              = 1.0
    master_volume: float              = 1.0
    key_bindings:  Dict[str, int]     = field(default_factory=dict)

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: "Path | str" = _SETTINGS_PATH) -> "Settings":
        """Load settings from *path*.

        Falls back to default values if the file is missing, empty, or corrupt.
        """
        if isinstance(path, str):
            path = Path(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return cls()

        res_raw    = raw.get("resolution", [1280, 720])
        resolution = (int(res_raw[0]), int(res_raw[1]))

        return cls(
            resolution    = resolution,
            fullscreen    = bool(raw.get("fullscreen",    False)),
            target_fps    = int( raw.get("fps", raw.get("target_fps", 60))),
            music_volume  = float(raw.get("volume_music", raw.get("music_volume", 0.7))),
            sfx_volume    = float(raw.get("volume_sfx", raw.get("sfx_volume", 1.0))),
            master_volume = float(raw.get("volume_master", raw.get("master_volume", 1.0))),
            key_bindings  = _parse_key_bindings(raw.get("key_bindings", {})),
        )

    def save(self, path: "Path | str" = _SETTINGS_PATH) -> None:
        """Persist current settings to *path* as pretty-printed JSON."""
        if isinstance(path, str):
            path = Path(path)
        data = {
            "resolution":    list(self.resolution),
            "fullscreen":    self.fullscreen,
            "fps":           self.target_fps,
            "target_fps":    self.target_fps,
            "volume_music":  self.music_volume,
            "music_volume":  self.music_volume,
            "volume_sfx":    self.sfx_volume,
            "sfx_volume":    self.sfx_volume,
            "volume_master": self.master_volume,
            "master_volume": self.master_volume,
            "key_bindings":  {
                action: pygame.key.name(keycode)
                for action, keycode in self.key_bindings.items()
            },
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def fps(self) -> int:
        return self.target_fps

    @fps.setter
    def fps(self, value: int) -> None:
        self.target_fps = int(value)

    @property
    def width(self) -> int:
        return self.resolution[0]

    @property
    def height(self) -> int:
        return self.resolution[1]

    @property
    def resolution_tuple(self) -> Tuple[int, int]:
        if isinstance(self.resolution, (list, tuple)):
            return (int(self.resolution[0]), int(self.resolution[1]))
        return self.resolution

    # Volume aliases (some modules use volume_master, others master_volume)
    @property
    def volume_master(self) -> float:
        return self.master_volume

    @volume_master.setter
    def volume_master(self, value: float) -> None:
        self.master_volume = value

    @property
    def volume_music(self) -> float:
        return self.music_volume

    @volume_music.setter
    def volume_music(self, value: float) -> None:
        self.music_volume = value

    @property
    def volume_sfx(self) -> float:
        return self.sfx_volume

    @volume_sfx.setter
    def volume_sfx(self, value: float) -> None:
        self.sfx_volume = value


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_key_bindings(raw: Dict[str, str]) -> Dict[str, int]:
    """Convert string key names from JSON to pygame key constants.

    Unknown names fall back to the DEFAULT_KEYS mapping.
    Import is deferred to avoid a circular dependency with constants.py.
    """
    from src.constants import DEFAULT_KEYS  # noqa: PLC0415

    result: Dict[str, int] = {}
    for action, default_keycode in DEFAULT_KEYS.items():
        name = raw.get(action)
        if name:
            code = pygame.key.key_code(name)
            result[action] = code if code != -1 else default_keycode
        else:
            result[action] = default_keycode
    return result
