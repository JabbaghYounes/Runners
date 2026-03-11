"""Typed settings dataclass with JSON persistence."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple


@dataclass
class Settings:
    """All user-configurable settings.

    Defaults match the canonical ``settings.json`` template.
    """

    resolution: List[int] = field(default_factory=lambda: [1280, 720])
    fullscreen: bool = False
    master_volume: float = 0.8
    music_volume: float = 0.6
    sfx_volume: float = 0.8
    key_bindings: Dict[str, str] = field(
        default_factory=lambda: {
            "move_up": "K_w",
            "move_down": "K_s",
            "move_left": "K_a",
            "move_right": "K_d",
            "jump": "K_SPACE",
            "crouch": "K_LCTRL",
            "sprint": "K_LSHIFT",
            "slide": "K_c",
            "interact": "K_e",
            "inventory": "K_TAB",
            "map": "K_m",
            "pause": "K_ESCAPE",
        }
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def resolution_tuple(self) -> Tuple[int, int]:
        """Return resolution as an immutable (width, height) tuple for Pygame."""
        return (int(self.resolution[0]), int(self.resolution[1]))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> "Settings":
        """Load settings from *path*.

        Returns a default ``Settings()`` instance when the file is missing,
        unreadable, or contains invalid JSON.
        """
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            # Only pass fields the dataclass actually has
            valid_fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
            filtered = {k: v for k, v in data.items() if k in valid_fields}
            return cls(**filtered)
        except (FileNotFoundError, json.JSONDecodeError, TypeError, KeyError):
            return cls()

    def save(self, path: str) -> None:
        """Serialise settings to *path* as pretty-printed JSON."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)

    def reload(self, path: str) -> None:
        """Re-read *path* and overwrite all fields in-place.

        Used by the SettingsScreen DISCARD action to restore the on-disk state
        without replacing the Settings object (other components hold a reference).
        """
        fresh = Settings.load(path)
        self.resolution = fresh.resolution
        self.fullscreen = fresh.fullscreen
        self.master_volume = fresh.master_volume
        self.music_volume = fresh.music_volume
        self.sfx_volume = fresh.sfx_volume
        self.key_bindings = fresh.key_bindings
