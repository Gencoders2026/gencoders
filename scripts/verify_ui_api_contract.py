"""
Contract check: every field the Support Console reads from the analysis
payload must actually be present in the API response.

A missing field renders as `undefined` in the UI (a blank gauge, no
indicators, no tips) without any error, so this is checked explicitly
before a demo.

Run with the backend already listening on http://127.0.0.1:8000
"""

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"

# Taken from the field accesses in support_console_frontend/src/pages/
# SupportConsole.jsx. `emotion_score` is deliberately NOT in this list:
# the UI only reads it as a dead fallback behind `frustration_level`,
# which is always present (checked below).
UI_FIELDS = [
    "intent",
    "emotion",
    "emotion_label",
    "confidence",
    "frustration_level",
    "frustration_score",
    "sentiment",
    "satisfaction_trend",
    "escalation_score",
    "escalation_level",
    "escalation_risk",
    "escalation_trend",
    "escalation_indicators",
    "escalation_reasoning",
    "recommended_actions",
    "negative_streak",
    "alert",
    "knowledge_results",
    "suggested_response",
    "suggested_responses",
    "response_evaluation",
    "coaching_guidance",
    "turn",
]

ALERT_FIELDS = ["triggered", "threshold", "score", "level", "message"]

# `frustration_level` is what the console actually renders, and the
# agent-message pass-through short-circuits before the normal pipeline.
FRUSTRATION_CASES = [
    ("calm customer", "hello, what is the status of my order?", "customer"),
    ("furious customer",
     "THIS IS FURIOUS! GET ME A MANAGER RIGHT NOW!", "customer"),
    ("thankful customer", "thanks, that is sorted, I appreciate it",
     "customer"),
    ("agent message", "I am so sorry, we will fix this within 24 hours.",
     "agent"),
]


def _call(payload):
    request = urllib.request.Request(
        BASE + "/support/analyze",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(request, timeout=30).read())


def main():
    data = _call({
        "query": "This is still not resolved. I demand a manager and I "
                 "will be posting about this on social media.",
        "session_id": "ui-contract-probe",
        "sender": "customer",
    })

    passed = 0
    failed = 0
    for field in UI_FIELDS:
        if field in data:
            passed += 1
        else:
            failed += 1
            print(f"  [FAIL] analysis payload is missing {field!r}")

    alert = data.get("alert") or {}
    for field in ALERT_FIELDS:
        if field in alert:
            passed += 1
        else:
            failed += 1
            print(f"  [FAIL] analysis alert is missing {field!r}")

    for i, (label, query, sender) in enumerate(FRUSTRATION_CASES):
        probe = _call({
            "query": query,
            "session_id": f"frustration-probe-{i}",
            "sender": sender,
        })
        level = probe.get("frustration_level")
        ok = (
            isinstance(level, int)
            and 1 <= level <= 10
        )
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] frustration_level sane for "
              f"{label:18} = {level!r}")

    print()
    print(f"  risk={data.get('escalation_score')}/100 "
          f"level={data.get('escalation_level')} "
          f"trend={data.get('escalation_trend')} "
          f"alert={data.get('alert', {}).get('triggered')}")
    print(f"  indicators={len(data.get('escalation_indicators') or [])} "
          f"reasoning={len(data.get('escalation_reasoning') or [])} "
          f"tips={len(data.get('coaching_guidance') or [])} "
          f"knowledge={len(data.get('knowledge_results') or [])}")
    print()
    print(f"  checks passed : {passed}")
    print(f"  checks failed : {failed}")
    print()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
