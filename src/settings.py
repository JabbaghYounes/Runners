"""Game settings with JSON persistence and sensible defaults."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_KEYS: dict[str, str] = {
    "move_up": "w",
    "move_down": "s",
    "move_left": "a",
    "move_right": "d",
    "sprint": "lshift",
    "crouch": "lctrl",
    "slide": "c",
    "jump": "space",
    "interact": "e",
    "reload": "r",
    "inventory": "tab",
    "pause": "escape",
}

DEFAULT_SETTINGS_PATH = Path("data/settings.json")


@dataclass
class Settings:
    """Persisted user preferences.

    Attributes are populated from ``data/settings.json`` when available,
    falling back to the defaults declared here.
    """

    screen_width: int = 1280
    screen_height: int = 720
    fullscreen: bool = False
    music_volume: float = 0.7
    sfx_volume: float = 0.7
    keybindings: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_KEYS))

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict representation suitable for JSON."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        """Create a Settings instance from a dict, ignoring unknown keys."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Settings":
        """Load settings from *path* (defaults to ``data/settings.json``).

        Returns default settings without error when the file is missing
        or contains invalid JSON.
        """
        path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            return cls.from_dict(data)
        except FileNotFoundError:
            logger.info("Settings file %s not found; using defaults.", path)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse settings file %s: %s; using defaults.", path, exc)
        return cls()

    def save(self, path: Path | str | None = None) -> None:
        """Persist current settings to *path* as pretty-printed JSON."""
        path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
