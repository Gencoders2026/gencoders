"""
Live end-to-end check of the Task 6 escalation alert path.

Drives one real conversation that escalates from a polite question to an
explicit request for a supervisor and asserts, against the running API:

  * the score is always 0-100 and the level always matches the risk band
    (Low 0-24 | Medium 25-49 | High 50-74 | Critical 75-100),
  * the reasoning ("why this score") and the indicator list are always
    present, and a request for a supervisor is picked up as an indicator,
  * the alert fires exactly when score >= threshold and carries the
    recommended actions the console renders in the alert banner,
  * lowering the configurable threshold makes the same conversation
    alert earlier (and the threshold is restored afterwards),
  * the session snapshot (GET /escalation/{session}) reports the raised
    alerts plus the counters the Risk Monitor card renders,
  * every turn also returns the Task 5 knowledge results and the Task 6
    coaching evaluation, so the integration is exercised too.

Run with the backend already listening on http://127.0.0.1:8000
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
DEFAULT_THRESHOLD = 70

PASSED = 0
FAILED = 0
FAILURES = []


def check(label, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED += 1
        FAILURES.append(label)
        print(f"  [FAIL] {label} {detail}")


def call(method, path, payload=None, timeout=120):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(
        BASE + path, data=data, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def expected_level(score):
    for minimum, level in (
        (75, "Critical"), (50, "High"), (25, "Medium"), (0, "Low"),
    ):
        if score >= minimum:
            return level


def _indicator_names(data):
    return [
        item.get("name")
        for item in (data.get("escalation_indicators") or [])
        if isinstance(item, dict)
    ]


def replay(session_key, turns):
    """Send a conversation and return the per-turn analysis payloads."""
    history = []
    payloads = []
    for turn, text in enumerate(turns, 1):
        history.append({"role": "customer", "content": text})
        payloads.append(call("POST", "/support/analyze", {
            "query": text,
            "session_id": session_key,
            "sender": "customer",
            "turn": turn,
            "history": list(history),
        }))
    return payloads


CALM_TURN = "Hi, my order is a little late, could you check the status?"

ESCALATING_TURNS = [
    "It is still not here and nobody has helped me. This is unacceptable!",
    "I have contacted support three times and it is still not resolved. "
    "I demand to speak to a supervisor right now!",
    "This is ridiculous. Get me a manager NOW and I want compensation!",
]

# Indicator names the monitor uses for the escalation drivers the task
# description calls out (repeated complaints, high frustration, negative
# sentiment, unresolved issues, supervisor / escalation demands).
DRIVER_KEYWORDS = (
    "frustration", "furious", "streak", "complaint", "unresolved",
    "raised_before", "demand", "tone_",
)


def main():
    turns = [CALM_TURN] + ESCALATING_TURNS

    print("A. ESCALATING CONVERSATION -> RISK, REASONING, ALERTS")
    # Unique session per run: the monitor keeps its state in memory, so a
    # reused session id would accumulate turns from earlier runs.
    session = f"alert-overlay-{int(time.time())}"
    payloads = replay(session, turns)
    scores = []
    levels = []
    triggered_turns = []

    for turn, (text, data) in enumerate(zip(turns, payloads), 1):
        score = data.get("escalation_score")
        level = data.get("escalation_level")
        alert = data.get("alert") or {}
        names = _indicator_names(data)
        reasoning = data.get("escalation_reasoning") or []
        scores.append(score)
        levels.append(level)
        if alert.get("triggered"):
            triggered_turns.append(turn)

        print(f"  T{turn} risk={score:>3} {level:<8} "
              f"trend={data.get('escalation_trend')} "
              f"streak={data.get('negative_streak')} "
              f"alert={alert.get('triggered')} "
              f"threshold={alert.get('threshold')}")
        print(f"      indicators: {names or '(none)'}")
        if reasoning:
            print(f"      why: {reasoning[0][:96]}")

        check(f"T{turn} score {score} is within 0-100",
              isinstance(score, int) and 0 <= score <= 100)
        check(f"T{turn} level {level!r} matches the score band",
              level == expected_level(score),
              f"(expected {expected_level(score)})")
        check(f"T{turn} reasoning explains the score", bool(reasoning))
        check(f"T{turn} alert threshold is the configured {DEFAULT_THRESHOLD}",
              alert.get("threshold") == DEFAULT_THRESHOLD)
        check(f"T{turn} alert fires exactly when score >= threshold",
              bool(alert.get("triggered")) == (score >= DEFAULT_THRESHOLD))
        if alert.get("triggered"):
            check(f"T{turn} alert carries a message and recommended actions",
                  bool(alert.get("message"))
                  and bool(data.get("recommended_actions")))
            check(f"T{turn} alert level equals the risk level",
                  alert.get("level") == level)

    print()
    print("B. RISK MOVES WITH THE CONVERSATION")
    check("risk rises as the customer escalates", scores[-1] > scores[0],
          f"({scores[0]} -> {scores[-1]})")
    worst = max(levels, key=["Low", "Medium", "High", "Critical"].index)
    check("a supervisor demand reaches High or Critical",
          worst in ("High", "Critical"), f"(levels seen: {levels})")
    check("escalation alert raised during the conversation",
          bool(triggered_turns), f"(turns: {triggered_turns})")

    print()
    print("C. INDICATORS FOR THE DRIVERS THE TASK LISTS")
    all_names = [n for d in payloads for n in _indicator_names(d)]
    drivers = [n for n in all_names
               if any(k in (n or "") for k in DRIVER_KEYWORDS)]
    print(f"  drivers: {sorted(set(all_names))}")
    check("driver indicators are reported (frustration / repeats / "
          "streak / unresolved / demands)", bool(drivers))

    supervisor_turn = payloads[2]
    check("supervisor request is analysed as a severe escalation signal",
          (supervisor_turn.get("frustration_level") or 0) >= 7
          and supervisor_turn.get("escalation_level") in ("High", "Critical"),
          f"(frustration={supervisor_turn.get('frustration_level')} "
          f"level={supervisor_turn.get('escalation_level')})")

    print()
    print("D. TASK 6 INTEGRATION ON THE SAME PAYLOAD")
    last = payloads[-1]
    check("coaching evaluation is returned with the risk score",
          bool(last.get("response_evaluation")
               or last.get("coaching_guidance")))
    counts = [len(d.get("knowledge_results") or []) for d in payloads]
    print(f"  knowledge results per turn: {counts}")
    check("knowledge results ground the suggestion on topic turns",
          any(counts), f"(per turn: {counts})")
    # Documented behaviour of the knowledge bridge: a message that names no
    # topic (pure fury / demand) must never be answered with an unrelated
    # policy, so it returns no results instead of a wrong one.
    check("a topic-free demand never quotes an unrelated policy",
          counts[-1] == 0
          or last.get("intent") not in ("general_inquiry", "escalation"),
          f"(intent={last.get('intent')} results={counts[-1]})")
    check("a suggested response is returned",
          bool(last.get("suggested_response")))

    print()
    print("E. SESSION SNAPSHOT (GET /escalation/{session})")
    snapshot = call("GET", f"/escalation/{session}")
    current = snapshot.get("current") or {}
    alerts = snapshot.get("alerts") or []
    print(f"  messages={snapshot.get('message_count')} "
          f"streak={snapshot.get('negative_streak')} "
          f"alerts={len(alerts)} risk={current.get('escalation_score')} "
          f"level={current.get('escalation_level')}")
    check("snapshot counts every customer message",
          snapshot.get("message_count") == len(turns))
    check("snapshot reports the raised alert(s)", len(alerts) >= 1)
    check("snapshot current level matches the last analysis",
          current.get("escalation_level") == levels[-1])
    check("snapshot current score matches the last analysis",
          current.get("escalation_score") == scores[-1])
    check("snapshot exposes the configured alert threshold",
          (current.get("alert") or {}).get("threshold")
          == DEFAULT_THRESHOLD)

    print()
    print("F. CONFIGURABLE THRESHOLD CHANGES WHEN THE ALERT APPEARS")
    try:
        lowered = call("POST", "/escalation/threshold",
                       {"threshold": 30}).get("threshold")
        check("threshold can be lowered to 30", lowered == 30)
        probe = replay(f"alert-threshold-{int(time.time())}",
                       [ESCALATING_TURNS[0]])[0]
        alert = probe.get("alert") or {}
        print(f"  risk={probe.get('escalation_score')} "
              f"level={probe.get('escalation_level')} "
              f"alert={alert.get('triggered')} "
              f"threshold={alert.get('threshold')}")
        check("the alert uses the newly configured threshold",
              alert.get("threshold") == 30)
        check("lowering the threshold raises the alert earlier",
              probe.get("escalation_score") >= 30
              and alert.get("triggered") is True)
    finally:
        restored = call("POST", "/escalation/threshold",
                        {"threshold": DEFAULT_THRESHOLD}).get("threshold")
        check(f"threshold restored to {DEFAULT_THRESHOLD}",
              restored == DEFAULT_THRESHOLD)

    print()
    print("G. CONSOLE RENDERS THE ALERT OVERLAY")
    root = Path(__file__).resolve().parent.parent
    pages = root / "support_console_frontend" / "src" / "pages"
    for name in ("SupportConsole.jsx", "Task6EscalationRiskMonitor.jsx"):
        source = (pages / name).read_text(encoding="utf-8", errors="ignore")
        check(f"{name} renders the escalation alert banner",
              "Escalation Alert" in source or "Escalation alert" in source)
        check(f"{name} renders the recommended actions in the banner",
              "recommended_actions" in source)
        check(f"{name} renders the 'Why this score:' reasoning",
              "Why this score:" in source)
        check(f"{name} lets the agent configure the alert threshold",
              "setEscalationThreshold" in source)

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  checks passed : {PASSED}")
    print(f"  checks failed : {FAILED}")
    if FAILURES:
        print("  failures:")
        for label in FAILURES:
            print(f"    - {label}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())



