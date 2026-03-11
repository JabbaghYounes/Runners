import json
import os
from dataclasses import dataclass, field
from typing import Tuple

@dataclass
class Settings:
    resolution: str = "1280x720"
    fullscreen: bool = False
    master_volume: float = 0.8
    music_volume: float = 0.6
    sfx_volume: float = 0.8

    @property
    def resolution_tuple(self) -> Tuple[int, int]:
        w, h = self.resolution.split('x')
        return int(w), int(h)

    @classmethod
    def load(cls, path: str) -> 'Settings':
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception as e:
                print(f"[Settings] Failed to load {path}: {e}")
        return cls()

    def save(self, path: str) -> None:
        try:
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w') as f:
                json.dump({
                    'resolution': self.resolution,
                    'fullscreen': self.fullscreen,
                    'master_volume': self.master_volume,
                    'music_volume': self.music_volume,
                    'sfx_volume': self.sfx_volume,
                }, f, indent=2)
        except Exception as e:
            print(f"[Settings] Failed to save {path}: {e}")
