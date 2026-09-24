"""Live check of the running Task 6 backend (port 8000).

Exercises every Task 6 endpoint the Support Console UI calls and prints a
compact summary. Run while the backend is up:

    python _t6_live_check.py
"""

import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = resp.read().decode()
        return resp.status, (json.loads(body) if body else None)


# 1. health
status, payload = call("GET", "/support/health")
print(f"[1] GET  /support/health           -> {status} {payload}")

# 2. knowledge retrieval (RAG) + full pipeline
status, payload = call(
    "POST",
    "/support/analyze",
    {
        "query": "What is your refund policy and how long does a refund take?",
        "session_id": "live-check-1",
        "turn": 1,
    },
)
print(f"[2] POST /support/analyze          -> {status}")
print(f"    intent={payload['intent']} emotion={payload['emotion']}")
print(f"    knowledge_available={payload['knowledge_available']} "
      f"knowledge_results={len(payload['knowledge_results'])}")
print(f"    suggested_response={payload['suggested_response'][:70]!r}...")
print(f"    coaching_tips={len(payload['coaching_tips'])} "
      f"risk={payload['escalation_score']} ({payload['escalation_level']})")
if payload["knowledge_results"]:
    top = payload["knowledge_results"][0]
    print(f"    top result keys={sorted(top.keys())}")
    print(f"    top preview={json.dumps(top)[:160]}...")

# 3. coaching evaluation of an agent draft
status, payload = call(
    "POST",
    "/coaching/evaluate",
    {
        "response": "I apologise for the delay. I understand how frustrating "
                    "this is and I will resolve it for you right away.",
        "intent": "late_delivery",
        "sentiment": "negative",
        "frustration_score": 8,
    },
)
print(f"[3] POST /coaching/evaluate        -> {status}")
dims = {k: payload[k]["score"] for k in
        ("tone", "clarity", "empathy", "professionalism")}
print(f"    dimensions={dims}")
print(f"    overall={payload['overall']} meets_standard={payload['meets_standard']}")

# 4. escalation threshold read + update
status, payload = call("GET", "/escalation/threshold")
print(f"[4] GET  /escalation/threshold     -> {status} threshold={payload.get('threshold')}")
status, payload = call("POST", "/escalation/threshold", {"threshold": 75})
print(f"    POST /escalation/threshold     -> {status} threshold={payload.get('threshold')}")
status, payload = call("POST", "/escalation/threshold", {"threshold": 70})
print(f"    POST /escalation/threshold     -> {status} reset to {payload.get('threshold')}")

# 5. session escalation snapshot
status, payload = call("GET", "/escalation/live-check-1")
current = payload.get("current") or {}
print(f"[5] GET  /escalation/{{session}}     -> {status} "
      f"messages={payload.get('message_count')} "
      f"negative_streak={payload.get('negative_streak')} "
      f"risk={current.get('escalation_score')} "
      f"level={current.get('escalation_level')} "
      f"alerts={len(payload.get('alerts') or [])}")

# 6. legacy enriched endpoint
status, payload = call(
    "POST", "/analyze", {"query": "Where is my order?", "session_id": "live-check-2"}
)
print(f"[6] POST /analyze                  -> {status} fields={len(payload)}")

print("\nALL LIVE CHECKS PASSED")
