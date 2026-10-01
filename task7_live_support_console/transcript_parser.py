"""
Task 7 - conversation transcript parser.

Parses an uploaded support-conversation transcript into a normalised,
role-tagged message list that the Live Support Console can replay:

    [{"role": "customer" | "agent", "content": "...", "timestamp": str | None}]

Supported input formats (auto-detected, extension + content sniffing):

    *.txt   "Customer: ..." / "Agent: ..." style transcripts (role
            prefixes, with multi-line continuations). When no role marker
            is present the file is split into blocks and roles alternate
            customer -> agent -> customer, with a warning attached.
    *.csv   a role/message table (header row optional). Column order is
            detected from the header names, otherwise the first column is
            the role and the second the message.
    *.json  a list of message objects, or an object with a
            ``messages`` / ``conversation`` / ``history`` / ``transcript``
            key, or a ``{"customer": [...], "agent": [...]}`` mapping.

Everything is deliberately dependency-free (standard library only) and
never raises on unknown roles - the role is inferred from the marker text
or from the position of the message in the conversation.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Dict, List, Optional, Tuple

CUSTOMER = "customer"
AGENT = "agent"

# ---------------------------------------------------------------------------
# Role vocabulary
# ---------------------------------------------------------------------------
CUSTOMER_MARKERS = {
    "customer", "client", "user", "caller", "visitor", "guest", "requester",
    "cust", "c", "them",
}
AGENT_MARKERS = {
    "agent", "support", "support agent", "support-agent", "advisor", "adviser",
    "representative", "rep", "staff", "helpdesk", "help desk", "operator",
    "csr", "me", "you", "bot", "assistant", "ai", "system", "service",
    "support team", "a",
}

# "Customer: hello", "AGENT - hello", "user> hello", "[Agent] hello"
_PREFIX_RE = re.compile(
    r"^\s*(?:\[|\()?\s*([A-Za-z][A-Za-z .'\-_/]{0,24}?)\s*(?:\]|\))?\s*"
    r"(?::|->|-->|>|\-|\u2013|\u2014)\s*(.*)$"
)
_TIMESTAMP_RE = re.compile(
    r"^\s*\[?(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?"
    r"|\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?"
    r"|\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\]?\s*"
)


def _normalise_role(raw: Optional[str]) -> Optional[str]:
    """Map a free-text role marker onto customer/agent (None if unknown)."""
    if raw is None:
        return None
    token = str(raw).strip().lower().strip("[]()<>:.-_")
    token = re.sub(r"\s+", " ", token)
    if not token:
        return None
    if token in CUSTOMER_MARKERS:
        return CUSTOMER
    if token in AGENT_MARKERS:
        return AGENT
    # substring fallbacks ("support agent 2", "customer_service", ...)
    if "cust" in token or "user" in token or "client" in token:
        return CUSTOMER
    if any(
        word in token
        for word in ("agent", "support", "assistant", "bot", "advisor",
                     "representative", "staff", "operator", "help")
    ):
        return AGENT
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _decode(raw) -> str:
    """Decode an uploaded transcript that may be UTF-8, UTF-16 or legacy."""
    if isinstance(raw, str):
        return raw
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def _split_timestamp(text: str) -> Tuple[Optional[str], str]:
    match = _TIMESTAMP_RE.match(text or "")
    if not match:
        return None, (text or "")
    return match.group(1).strip(), text[match.end():]


def _infer_roles_alternating(messages: List[Dict]) -> List[Dict]:
    """Fallback: first block is the customer, roles then alternate."""
    for index, message in enumerate(messages):
        if message.get("role") in (CUSTOMER, AGENT):
            continue
        message["role"] = CUSTOMER if index % 2 == 0 else AGENT
    return messages



# ---------------------------------------------------------------------------
# TXT
# ---------------------------------------------------------------------------
def _parse_txt(text: str) -> Dict:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    messages: List[Dict] = []
    warnings: List[str] = []
    matched_markers = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        timestamp, remainder = _split_timestamp(stripped)
        match = _PREFIX_RE.match(remainder) if remainder else None

        role = _normalise_role(match.group(1)) if match else None
        body = (match.group(2) or "").strip() if match else ""

        # A prefix like "Note:" must not be treated as a speaker: the body
        # has to contain something, otherwise it stays part of the message.
        if match and role and (body or messages):
            matched_markers += 1
            messages.append({
                "role": role,
                "content": body,
                "timestamp": timestamp,
            })
            continue

        if messages:
            # Continuation line - append to the message currently open.
            previous = messages[-1]
            joiner = " " if previous["content"] else ""
            previous["content"] = f"{previous['content']}{joiner}{stripped}"
            if timestamp and not previous.get("timestamp"):
                previous["timestamp"] = timestamp
        else:
            # Preamble before the first speaker marker (title, date, ...).
            warnings.append(f"Ignored leading line: \"{stripped[:60]}\"")

    if matched_markers == 0:
        # No role markers at all: split into blocks and alternate.
        blocks = [
            _clean(block)
            for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
            if _clean(block)
        ]
        messages = [{"role": None, "content": b, "timestamp": None}
                    for b in blocks]
        if len(messages) < 2:
            messages = [
                {"role": None, "content": _clean(line), "timestamp": None}
                for line in lines if _clean(line)
            ]
        messages = _infer_roles_alternating(messages)
        warnings.append(
            "No 'Customer:'/'Agent:' markers were found, so roles were "
            "assigned by alternating position (customer first)."
        )

    return {"format": "txt", "messages": messages, "warnings": warnings}


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------
_HEADER_ROLE_HINTS = ("role", "speaker", "sender", "author", "from", "who",
                      "party", "type")
_HEADER_TEXT_HINTS = ("message", "text", "content", "body", "reply",
                      "utterance", "transcript", "dialog")
_HEADER_TIME_HINTS = ("time", "timestamp", "date", "at")


def _parse_csv(text: str) -> Dict:
    warnings: List[str] = []
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if any((cell or "").strip() for cell in row)]

    if not rows:
        return {"format": "csv", "messages": [],
                "warnings": ["The CSV file is empty."]}

    role_index, text_index, time_index = 0, 1, None
    header = [str(cell or "").strip().lower() for cell in rows[0]]
    looks_like_header = any(
        any(hint in column for hint in _HEADER_ROLE_HINTS) for column in header
    ) and any(
        any(hint in column for hint in _HEADER_TEXT_HINTS) for column in header
    )

    if looks_like_header:
        for index, column in enumerate(header):
            if any(hint in column for hint in _HEADER_ROLE_HINTS):
                role_index = index
                break
        for index, column in enumerate(header):
            if any(hint in column for hint in _HEADER_TEXT_HINTS):
                text_index = index
                break
        for index, column in enumerate(header):
            if any(hint in column for hint in _HEADER_TIME_HINTS):
                time_index = index
                break
        rows = rows[1:]
    else:
        # No header: [role, message] or [message, role] or [role, msg, time]
        if rows and _normalise_role(rows[0][0]) is None:
            role_index, text_index = 1, 0
            warnings.append(
                "No recognisable CSV header was found; the first column was "
                "treated as the message and the second as the speaker."
            )
        if len(header) > 2:
            time_index = 2

    messages: List[Dict] = []
    unknown_roles = 0

    for row in rows:
        if text_index >= len(row):
            continue
        role_raw = row[role_index] if role_index < len(row) else ""
        body = _clean(row[text_index])
        role = _normalise_role(role_raw)
        if role is None and body:
            unknown_roles += 1
        if not body:
            continue
        timestamp = None
        if time_index is not None and time_index < len(row):
            timestamp = _clean(row[time_index]) or None
        messages.append({"role": role, "content": body, "timestamp": timestamp})

    if unknown_roles:
        _infer_roles_alternating(messages)
        warnings.append(
            f"{unknown_roles} row(s) had an unrecognised speaker value; "
            "those roles were inferred by alternating position."
        )

    return {"format": "csv", "messages": messages, "warnings": warnings}


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------
_MESSAGE_LIST_KEYS = ("messages", "conversation", "history", "transcript",
                      "dialogue", "dialog", "turns", "data", "items")


def _message_from_object(item: Dict) -> Optional[Dict]:
    if not isinstance(item, dict):
        return None
    role_raw = None
    for key in ("role", "speaker", "sender", "author", "from", "party", "who"):
        if item.get(key) is not None:
            role_raw = item.get(key)
            break
    body = None
    for key in ("content", "message", "text", "body", "utterance", "reply",
                "value"):
        if item.get(key) is not None:
            body = item.get(key)
            break
    if body is None:
        return None
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False)
    timestamp = None
    for key in ("timestamp", "time", "date", "at", "created_at"):
        if item.get(key) is not None:
            timestamp = str(item.get(key))
            break
    return {
        "role": _normalise_role(role_raw),
        "content": _clean(body),
        "timestamp": timestamp,
    }


def _parse_json(text: str) -> Dict:
    warnings: List[str] = []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"The JSON transcript is not valid JSON (line {exc.lineno}, "
            f"column {exc.colno}): {exc.msg}"
        ) from exc

    raw_items: List = []

    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        for key in _MESSAGE_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                raw_items = value
                break
        else:
            # {"customer": [...], "agent": [...]}
            for role_key, role in (("customer", CUSTOMER), ("client", CUSTOMER),
                                   ("user", CUSTOMER), ("agent", AGENT),
                                   ("support", AGENT)):
                entries = payload.get(role_key)
                if isinstance(entries, list):
                    for entry in entries:
                        raw_items.append({
                            "role": role,
                            "content": (
                                entry.get("content", entry.get("message", ""))
                                if isinstance(entry, dict) else entry
                            ),
                        })
    else:
        raise ValueError(
            "The JSON transcript must be a list of messages or an object "
            "containing a message list."
        )

    if not raw_items:
        return {
            "format": "json",
            "messages": [],
            "warnings": ["No messages were found in the JSON transcript."],
        }

    messages: List[Dict] = []
    unknown_roles = 0

    for item in raw_items:
        if isinstance(item, str):
            messages.append({"role": None, "content": _clean(item),
                             "timestamp": None})
            continue
        parsed = _message_from_object(item)
        if parsed is None or not parsed["content"]:
            continue
        if parsed["role"] is None:
            unknown_roles += 1
        messages.append(parsed)

    if unknown_roles:
        _infer_roles_alternating(messages)
        warnings.append(
            f"{unknown_roles} message(s) had no recognisable role; those "
            "roles were inferred by alternating position."
        )

    return {"format": "json", "messages": messages, "warnings": warnings}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def detect_format(filename: str, text: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".txt") or name.endswith(".log") or name.endswith(".md"):
        return "txt"
    stripped = (text or "").lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    first_line = (text or "").split("\n", 1)[0]
    if "," in first_line and len(first_line.split(",")) >= 2:
        return "csv"
    return "txt"


def parse_transcript(filename: str, raw_content) -> Dict:
    """
    Parse an uploaded transcript.

    Parameters
    ----------
    filename:
        Original file name (used to detect the format).
    raw_content:
        ``bytes`` (from an upload) or ``str`` (already-decoded text).

    Returns
    -------
    dict with ``format``, ``filename``, ``messages``, ``counts``,
    ``warnings`` and ``stats``. Raises ``ValueError`` with a user-facing
    message when nothing usable could be parsed.
    """
    text = _decode(raw_content)
    if not text.strip():
        raise ValueError("The uploaded transcript is empty.")

    file_format = detect_format(filename, text)

    if file_format == "csv":
        parsed = _parse_csv(text)
    elif file_format == "json":
        parsed = _parse_json(text)
    else:
        parsed = _parse_txt(text)

    messages = [
        message for message in parsed["messages"]
        if message.get("content")
    ]

    if not messages:
        raise ValueError(
            "No messages could be extracted from this transcript. Provide a "
            "'Customer:'/'Agent:' text file, a role+message CSV, or a JSON "
            "list of messages."
        )

    if len(messages) < 2:
        raise ValueError(
            "The transcript contains only one message. A conversation needs "
            "at least a customer message and an agent reply."
        )

    _infer_roles_alternating(messages)

    customer_count = sum(1 for m in messages if m["role"] == CUSTOMER)
    agent_count = len(messages) - customer_count

    warnings = list(parsed["warnings"])
    if customer_count == 0 or agent_count == 0:
        warnings.append(
            "One side of the conversation is missing - the replay will still "
            "work, but agent-side metrics cannot be evaluated."
        )

    return {
        "format": parsed["format"],
        "filename": filename or "transcript",
        "messages": messages,
        "counts": {
            "messages": len(messages),
            "customer_messages": customer_count,
            "agent_messages": agent_count,
        },
        "warnings": warnings,
        "stats": {
            "characters": len(text),
            "lines": text.count("\n") + 1,
        },
    }


# ---------------------------------------------------------------------------
# Helpers reused by the summary / analytics agents
# ---------------------------------------------------------------------------
def customer_messages(messages: List[Dict]) -> List[Dict]:
    return [m for m in (messages or []) if m.get("role") == CUSTOMER]


def agent_messages(messages: List[Dict]) -> List[Dict]:
    return [m for m in (messages or []) if m.get("role") == AGENT]


def to_history(messages: List[Dict]) -> List[Dict]:
    """Convert parsed messages into the ``{role, content}`` history shape
    the Task 4/5/6 agents expect."""
    return [
        {"role": m.get("role", CUSTOMER), "content": _clean(m.get("content"))}
        for m in (messages or [])
        if _clean(m.get("content"))
    ]


def normalise_messages(raw_messages) -> List[Dict]:
    """
    Normalise an arbitrary incoming message list (e.g. the JSON body the
    console sends when recording a conversation) into
    ``[{role, content, timestamp}]``.
    """
    if not isinstance(raw_messages, list):
        raise ValueError(
            "'messages' must be a list of {role, content} objects."
        )

    normalised: List[Dict] = []

    for item in raw_messages:
        if isinstance(item, str):
            normalised.append({"role": None, "content": _clean(item),
                               "timestamp": None})
            continue
        if not isinstance(item, dict):
            continue
        parsed = _message_from_object(item)
        if parsed is None or not parsed["content"]:
            continue
        normalised.append(parsed)

    if not normalised:
        raise ValueError("No usable messages were provided.")

    _infer_roles_alternating(normalised)
    return normalised
