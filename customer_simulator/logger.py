"""
Conversation logging for the Customer Simulator.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

try:  # package-relative import
    from .config import LOG_DIR
except ImportError:  # flat import when run directly
    from config import LOG_DIR


class ConversationLogger:
    def __init__(self, session_id: str, log_dir: str = LOG_DIR):
        self.session_id = session_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self.log_dir / f"session_{session_id}.json"
        self.entries: List[Dict[str, Any]] = []
        self.meta: Dict[str, Any] = {
            "session_id": session_id,
            "started_at": _utc_now(),
            "ended_at": None,
            "config": {},
            "final_emotion": None,
            "turn_count": 0,
        }

    def set_config(self, config: Dict[str, Any]):
        self.meta["config"] = config

    def log_turn(
        self,
        turn_number: int,
        role: str,
        message: str,
        emotion: Optional[Dict] = None,
        extra: Optional[Dict] = None,
    ):
        entry = {
            "turn": turn_number,
            "timestamp": _utc_now(),
            "role": role,
            "message": message,
            "emotion": emotion,
        }
        if extra:
            entry["extra"] = extra
        self.entries.append(entry)
        self.meta["turn_count"] = turn_number
        self._flush()

    def finalize(self, final_emotion: Optional[Dict] = None):
        self.meta["ended_at"] = _utc_now()
        if final_emotion:
            self.meta["final_emotion"] = final_emotion
        self._flush()

    def _flush(self):
        payload = {
            "meta": self.meta,
            "conversation": self.entries,
        }
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def get_log_path(self) -> str:
        return str(self.filepath)

    def get_full_log(self) -> Dict:
        return {"meta": self.meta, "conversation": self.entries}