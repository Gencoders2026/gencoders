"""
Task 7 - persistent conversation store for the Live Support Console.

Every conversation handled in the console (Manual mode, Replay mode and
the Task 3 simulator mode) can be saved here. Task 8 reads the same store
to build its post-interaction reports and the performance analytics, so
the analytics are driven by real conversations produced by this
application.

Stored in ``data/recorded_sessions.json``. The Task 3 simulator logs
(``task3_customer_simulator_agent/logs/session_*.json``) are also exposed
here, but strictly READ-ONLY - nothing writes into that folder.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parent
DATA_DIR = MODULE_DIR / "data"
STORE_PATH = DATA_DIR / "recorded_sessions.json"

SIMULATOR_LOG_DIR = REPO_ROOT / "task3_customer_simulator_agent" / "logs"

_lock = threading.RLock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _as_list(value) -> List:
    return value if isinstance(value, list) else []


# ---------------------------------------------------------------------------
# Store access
# ---------------------------------------------------------------------------
def _load() -> Dict:
    if not STORE_PATH.exists():
        return {"sessions": []}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"sessions": []}
    if not isinstance(payload, dict):
        return {"sessions": []}
    payload["sessions"] = _as_list(payload.get("sessions"))
    return payload


def _save(payload: Dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = _utc_now_iso()
    tmp_path = STORE_PATH.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    os.replace(tmp_path, STORE_PATH)


def count_sessions(include_demo: bool = True) -> int:
    with _lock:
        records = _load()["sessions"]
    if not include_demo:
        records = [r for r in records if not r.get("is_demo")]
    return len(records)


def summarise(record: Dict, include_messages: bool = False) -> Dict:
    """Compact view of a recorded conversation for list endpoints."""
    messages = _as_list(record.get("messages"))
    customer_count = sum(
        1 for message in messages
        if (message or {}).get("role") == "customer"
    )
    summary = {
        "id": record.get("id"),
        "mode": record.get("mode", "manual"),
        "title": record.get("title") or "Support conversation",
        "created_at": record.get("created_at"),
        "completed_at": record.get("completed_at"),
        "persona": record.get("persona"),
        "scenario": record.get("scenario"),
        "source_file": record.get("source_file"),
        "is_demo": bool(record.get("is_demo")),
        "tags": _as_list(record.get("tags")),
        "message_count": len(messages),
        "customer_messages": customer_count,
        "agent_messages": len(messages) - customer_count,
        "knowledge_search_count": len(
            _as_list(record.get("knowledge_searches"))
        ),
    }
    if include_messages:
        summary["messages"] = messages
        summary["knowledge_searches"] = _as_list(
            record.get("knowledge_searches")
        )
        summary["meta"] = record.get("meta") or {}
    return summary



def list_sessions(
    include_messages: bool = False,
    include_demo: bool = True,
    limit: Optional[int] = None,
) -> List[Dict]:
    """All recorded conversations, newest first."""
    with _lock:
        records = _load()["sessions"]

    if not include_demo:
        records = [r for r in records if not r.get("is_demo")]

    records = sorted(
        records,
        key=lambda r: (r.get("created_at") or "", r.get("id") or ""),
        reverse=True,
    )

    if limit:
        records = records[: max(0, int(limit))]

    return [summarise(record, include_messages) for record in records]


def get_session(
    session_id: str, include_messages: bool = True
) -> Optional[Dict]:
    if not session_id:
        return None
    with _lock:
        records = _load()["sessions"]
    for record in records:
        if str(record.get("id")) == str(session_id):
            return summarise(record, include_messages)
    return None


def record_session(record: Dict) -> Dict:
    """Persist one conversation. Returns the stored (compact) record."""
    record = dict(record or {})
    record["id"] = str(record.get("id") or f"conv-{uuid.uuid4().hex[:10]}")
    record["created_at"] = record.get("created_at") or _utc_now_iso()
    record["messages"] = _as_list(record.get("messages"))
    record["knowledge_searches"] = _as_list(record.get("knowledge_searches"))
    record.setdefault("mode", "manual")
    record.setdefault("title", "Support conversation")

    with _lock:
        payload = _load()
        sessions = [
            existing for existing in payload["sessions"]
            if str(existing.get("id")) != record["id"]
        ]
        sessions.append(record)
        payload["sessions"] = sessions
        _save(payload)

    return summarise(record, include_messages=True)


def delete_session(session_id: str) -> bool:
    with _lock:
        payload = _load()
        before = len(payload["sessions"])
        payload["sessions"] = [
            record for record in payload["sessions"]
            if str(record.get("id")) != str(session_id)
        ]
        changed = len(payload["sessions"]) != before
        if changed:
            _save(payload)
    return changed


def clear_sessions(only_demo: bool = False) -> int:
    with _lock:
        payload = _load()
        before = len(payload["sessions"])
        if only_demo:
            payload["sessions"] = [
                record for record in payload["sessions"]
                if not record.get("is_demo")
            ]
        else:
            payload["sessions"] = []
        removed = before - len(payload["sessions"])
        _save(payload)
    return removed


def upsert_many(records: List[Dict]) -> int:
    """Insert/overwrite several conversations (used by the demo seeder)."""
    written = 0
    with _lock:
        payload = _load()
        by_id = {
            str(record.get("id")): record for record in payload["sessions"]
        }
        for record in records or []:
            record = dict(record or {})
            record["id"] = str(
                record.get("id") or f"conv-{uuid.uuid4().hex[:10]}"
            )
            record["created_at"] = record.get("created_at") or _utc_now_iso()
            record["messages"] = _as_list(record.get("messages"))
            record["knowledge_searches"] = _as_list(
                record.get("knowledge_searches")
            )
            by_id[record["id"]] = record
            written += 1
        payload["sessions"] = list(by_id.values())
        _save(payload)

    return written


# ---------------------------------------------------------------------------
# Task 3 simulator logs (READ-ONLY)
# ---------------------------------------------------------------------------
def simulator_log_path(session_id: str) -> Path:
    return SIMULATOR_LOG_DIR / f"session_{session_id}.json"


def _conversation_from_log(
    payload: Dict, session_id: str, mtime: Optional[float] = None
) -> Optional[Dict]:
    history = _as_list(payload.get("history") or payload.get("conversation"))
    messages: List[Dict] = []

    for index, item in enumerate(history):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "customer").lower()
        role = "agent" if role in (
            "agent", "support", "assistant", "bot", "system"
        ) else "customer"
        content = str(
            item.get("content")
            if item.get("content") is not None
            else item.get("message", "")
        ).strip()
        if not content:
            continue
        messages.append({
            "role": role,
            "content": content,
            "timestamp": item.get("timestamp"),
            "turn": item.get("turn", index + 1),
        })

    if not messages:
        return None

    created_at = payload.get("started_at") or payload.get("ended_at")
    if not created_at and mtime is not None:
        created_at = datetime.fromtimestamp(
            mtime, tz=timezone.utc
        ).isoformat(timespec="seconds")

    scenario = payload.get("scenario")

    return {
        "id": f"sim-{session_id}",
        "mode": "simulator",
        "title": (
            f"Simulator session {session_id}"
            + (f" \u2013 {scenario}" if scenario else "")
        ),
        "created_at": created_at,
        "persona": payload.get("persona"),
        "scenario": scenario,
        "source_file": f"session_{session_id}.json",
        "is_demo": False,
        "tags": ["simulator", "task3"],
        "messages": messages,
        "knowledge_searches": [],
        "meta": {
            "final_emotion": payload.get("final_emotion"),
            "turn_count": payload.get("turn_count"),
            "expected_resolution": payload.get("expected_resolution"),
        },
    }


def get_simulator_conversation(session_id: str) -> Optional[Dict]:
    """Read one Task 3 simulator log as a conversation record."""
    if not session_id:
        return None
    path = simulator_log_path(session_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return _conversation_from_log(payload, str(session_id), path.stat().st_mtime)


def list_simulator_conversations(limit: int = 40) -> List[Dict]:
    """Newest ``limit`` Task 3 simulator conversations."""
    if not SIMULATOR_LOG_DIR.exists():
        return []

    paths = sorted(
        SIMULATOR_LOG_DIR.glob("session_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if limit:
        paths = paths[: max(1, int(limit))]

    conversations: List[Dict] = []

    for path in paths:
        session_id = path.stem.replace("session_", "", 1)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        conversation = _conversation_from_log(
            payload, session_id, path.stat().st_mtime
        )
        if conversation:
            conversations.append(conversation)

    return conversations

