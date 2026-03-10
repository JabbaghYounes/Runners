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
    """Persisted user preferences."""

    screen_width: int = 1280
    screen_height: int = 720
    fullscreen: bool = False
    music_volume: float = 0.7
    sfx_volume: float = 0.7
    keybindings: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_KEYS))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Settings":
        path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            return cls.from_dict(data)
        except FileNotFoundError:
            logger.info("Settings file %s not found; using defaults.", path)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse settings: %s; using defaults.", exc)
        return cls()

    def save(self, path: Path | str | None = None) -> None:
        path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
