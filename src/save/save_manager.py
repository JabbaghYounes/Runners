import json
import os
from typing import Any, Dict, Optional

class SaveManager:
    def __init__(self, save_path: str = 'saves/save.json'):
        self.save_path = save_path

    def load(self) -> Dict[str, Any]:
        if os.path.exists(self.save_path):
            try:
                with open(self.save_path, 'r') as f:
                    data = json.load(f)
                return self._migrate(data)
            except Exception as e:
                print(f"[SaveManager] Load failed: {e}")
        return self._new_game()

    def save(self, home_base: Any, currency: Any, xp_system: Any,
             inventory: Optional[Any] = None) -> None:
        os.makedirs(os.path.dirname(self.save_path) or '.', exist_ok=True)
        tmp_path = self.save_path + '.tmp'
        data = {
            'schema_version': 1,
            'home_base': home_base.to_save_dict(),
            'currency': currency.to_save_dict(),
            'xp': xp_system.to_save_dict(),
        }
        try:
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.save_path)
        except Exception as e:
            print(f"[SaveManager] Save failed: {e}")

    def _new_game(self) -> Dict[str, Any]:
        return {
            'schema_version': 1,
            'home_base': {'facilities': {}},
            'currency': {'balance': 0},
            'xp': {'xp': 0, 'level': 1},
        }

    def _migrate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if data.get('schema_version', 0) < 1:
            data = self._new_game()
        return data
