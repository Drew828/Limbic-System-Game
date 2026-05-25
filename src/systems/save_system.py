# =============================================================================
# systems/save_system.py
# Save and load the entire game state as a single JSON file.
# =============================================================================

from __future__ import annotations
import json
import os
from datetime import datetime
from typing import Optional

from src.models.player import PlayerState

_SAVE_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "saves")
_SAVE_FILE = os.path.join(_SAVE_DIR, "save.json")


class SaveSystem:

    @staticmethod
    def save(player: PlayerState, slot: str = "default") -> bool:
        os.makedirs(_SAVE_DIR, exist_ok=True)
        path = SaveSystem._path(slot)
        data = {
            "version":   1,
            "timestamp": datetime.utcnow().isoformat(),
            "player":    player.to_dict(),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"[SaveSystem] Save failed: {e}")
            return False

    @staticmethod
    def load(slot: str = "default") -> Optional[PlayerState]:
        path = SaveSystem._path(slot)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PlayerState.from_dict(data["player"])
        except Exception as e:
            print(f"[SaveSystem] Load failed: {e}")
            return None

    @staticmethod
    def has_save(slot: str = "default") -> bool:
        return os.path.exists(SaveSystem._path(slot))

    @staticmethod
    def delete_save(slot: str = "default") -> None:
        path = SaveSystem._path(slot)
        if os.path.exists(path):
            os.remove(path)

    @staticmethod
    def _path(slot) -> str:
        safe = "".join(c for c in str(slot) if c.isalnum() or c in ("-", "_"))
        return os.path.join(_SAVE_DIR, f"save_{safe}.json")
