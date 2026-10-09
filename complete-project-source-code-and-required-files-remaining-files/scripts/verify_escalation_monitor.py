"""
End-to-end check of the Escalation Risk Monitor for a live demo.

Drives the running API (port 8000) with realistic multi-turn support
conversations and asserts the risk score actually TRACKS the customer:

  1. escalating      - risk must RISE as pressure builds
  2. de-escalating   - risk must FALL as the customer calms down
  3. full arc        - furious -> calm -> furious (both directions)
  4. agent no-op     - an agent reply must never move the risk
  5. idempotency     - the same message twice must not double count
  6. no false alarm  - a polite, resolved conversation stays low
  7. session state   - /escalation/{session_id} stays consistent
  8. threshold alert - the configurable alert fires and clears

Run with the backend already listening on http://127.0.0.1:8000
"""

import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000"

PASS = 0
FAIL = 0
FAILURES = []


def _request(path, payload=None, method="GET"):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(
        BASE + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {body}") from exc


def post(path, payload):
    return _request(path, payload, "POST")


def get(path):
    return _request(path)


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        FAILURES.append(f"{label} :: {detail}")
        print(f"  [FAIL] {label} :: {detail}")


def send(session, message, turn=None, sender="customer", history=None):
    payload = {"query": message, "session_id": session, "sender": sender}
    if turn is not None:
        payload["turn"] = turn
    if history is not None:
        payload["history"] = history
    return post("/support/analyze", payload)


def agent_says(session, message, turn=None):
    return send(session, message, turn=turn, sender="agent")


def risk_of(response):
    """Pull the escalation score out of whatever shape came back."""
    escalation = response.get("escalation")
    if isinstance(escalation, dict) and "risk_score" in escalation:
        return escalation["risk_score"]
    for key in ("escalation_score", "risk_score"):
        if key in response:
            return response[key]
    raise RuntimeError(
        f"no escalation score in response keys={list(response)}"
    )


def state_of(session):
    """
    Snapshot of the monitor state for a session. An unknown session is a
    404, which the checks treat as "clean default".
    """
    try:
        state = get(f"/escalation/{session}")
    except RuntimeError as exc:
        if "-> 404" not in str(exc):
            raise
        state = {
            "message_count": 0,
            "negative_streak": 0,
            "assessments": [],
            "current": {
                "risk_score": 0,
                "alert": {"triggered": False, "threshold": 70},
            },
        }
    state.setdefault("current", {})
    return state


def current_of(session):
    """The latest assessment held by the monitor for a session."""
    return state_of(session)["current"]


def drive(session, messages):
    scores = []
    for i, message in enumerate(messages, start=1):
        scores.append(risk_of(send(session, message, turn=i)))
    return scores


def banner(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


ESCALATING = [
    "Hi, I would like a refund for the damaged product I received.",
    "It is still not resolved. I am waiting since last week and "
    "there is still no update. This is really frustrating.",
    "Nobody has helped me at all. I have already contacted support "
    "twice about this refund and nothing happened.",
    "I am done waiting. I need this refund fixed immediately. If "
    "this is not resolved today I will cancel everything and take "
    "my business elsewhere.",
    "Nothing has changed. I demand to speak to a manager right now. "
    "I will be posting about this on social media and my bank will "
    "be disputing the charge. This is completely unacceptable.",
]

DEESCALATING = [
    "This is completely unacceptable! I demand a manager right now. "
    "Nobody has helped me and I will post about this on social media. "
    "My bank is going to dispute the charge too.",
    "I have still not received my refund and it is really "
    "frustrating. I need this resolved immediately.",
    "I understand the delay, thank you for checking. I appreciate "
    "your help with this.",
    "That is great, thank you. It is sorted now, I appreciate you "
    "getting this resolved.",
]

CALM = [
    "Hello, I would like to know the status of my order, thank you "
    "for your help.",
    "Thanks for the update, that is helpful. I appreciate it.",
    "Perfect, everything is sorted. Thank you very much!",
]


# ==========================================================
# 1. ESCALATING
# ==========================================================

banner("1. ESCALATING CONVERSATION - risk must RISE")
session = uuid.uuid4().hex[:8]
scores = drive(session, ESCALATING)
for i, score in enumerate(scores, start=1):
    print(f"    T{i}: risk={score:3d}")
check("risk ends in the Critical band", scores[-1] >= 75,
      f"final={scores[-1]}")
check("risk rises overall", scores[-1] > scores[0],
      f"{scores[0]} -> {scores[-1]}")
check("risk never drops during escalation",
      all(b >= a for a, b in zip(scores, scores[1:])), f"{scores}")
check("final alert fires at the default threshold",
      bool(current_of(session)["alert"]["triggered"]),
      f"score={scores[-1]}")

# ==========================================================
# 2. DE-ESCALATING
# ==========================================================

banner("2. DE-ESCALATING CONVERSATION - risk must FALL")
session = uuid.uuid4().hex[:8]
scores = drive(session, DEESCALATING)
for i, score in enumerate(scores, start=1):
    print(f"    T{i}: risk={score:3d}")
check("risk starts Critical", scores[0] >= 75, f"first={scores[0]}")
check("risk falls as the customer calms", scores[-1] < scores[0],
      f"{scores[0]} -> {scores[-1]}")
check("risk lands in the Low band at the end", scores[-1] < 25,
      f"final={scores[-1]}")
check("risk is monotonically non-increasing",
      all(b <= a for a, b in zip(scores, scores[1:])), f"{scores}")
check("the alert clears once the customer calms",
      not current_of(session)["alert"]["triggered"],
      f"score={scores[-1]}")

# ==========================================================
# 3. FULL ARC
# ==========================================================

banner("3. FULL ARC - furious -> calm -> furious")
ARC = [
    "I am absolutely furious! Get me a supervisor immediately, this "
    "is unacceptable and I will sue you and tell everyone!",
    "Thank you, that is sorted now. I really appreciate your help.",
    "Wait, nothing happened. This is still not resolved and I am "
    "furious again. Escalate this to a manager immediately!",
]
session = uuid.uuid4().hex[:8]
scores = drive(session, ARC)
for i, score in enumerate(scores, start=1):
    print(f"    T{i}: risk={score:3d}")
check("arc opens Critical", scores[0] >= 75, f"{scores[0]}")
check("arc drops on thanks", scores[1] < scores[0],
      f"{scores[0]} -> {scores[1]}")
check("arc climbs back on re-escalation", scores[2] > scores[1],
      f"{scores[1]} -> {scores[2]}")
check("arc ends Critical", scores[2] >= 75, f"{scores[2]}")



# ==========================================================
# 4. AGENT MESSAGES ARE A NO-OP
# ==========================================================

banner("4. AGENT REPLIES MUST NEVER MOVE THE RISK")
session = uuid.uuid4().hex[:8]
send(session, "I am furious. Nobody has helped me. Get me a manager "
              "immediately, this is completely unacceptable.", turn=1)
before = state_of(session)

# A perfectly polite, apologetic, committed agent message.
agent_says(
    session,
    "I am so sorry, I completely understand your frustration. I will "
    "escalate this to a manager right now and call you back within "
    "24 hours.",
)
after = state_of(session)
check("risk unchanged after a polite agent apology",
      after["current"]["risk_score"] == before["current"]["risk_score"],
      f"{before['current']['risk_score']} -> {after['current']['risk_score']}")
check("message count unchanged by an agent reply",
      after["message_count"] == before["message_count"],
      f"{before['message_count']} -> {after['message_count']}")
check("negative streak unchanged by an agent reply",
      after["negative_streak"] == before["negative_streak"],
      f"{before['negative_streak']} -> {after['negative_streak']}")

# ==========================================================
# 5. IDEMPOTENCY
# ==========================================================

banner("5. IDEMPOTENCY - the same message must not double count")
session = uuid.uuid4().hex[:8]
first = send(session, "This is still not resolved and I am furious. "
                      "Get me a manager.", turn=1)
second = send(session, "This is still not resolved and I am furious. "
                       "Get me a manager.", turn=1)
check("repeat of the same message returns the same score",
      risk_of(first) == risk_of(second),
      f"{risk_of(first)} vs {risk_of(second)}")
state = state_of(session)
check("repeat does not inflate the message count",
      state["message_count"] == 1,
      f"message_count={state['message_count']}")

# ==========================================================
# 6. NO FALSE ALARMS
# ==========================================================

banner("6. NO FALSE ALARMS - a calm conversation must stay low")
session = uuid.uuid4().hex[:8]
scores = drive(session, CALM)
for i, score in enumerate(scores, start=1):
    print(f"    T{i}: risk={score:3d}")
check("polite conversation stays below the alert threshold",
      max(scores) < 70, f"max={max(scores)}")
check("polite conversation never goes Critical", max(scores) < 75,
      f"max={max(scores)}")
check("polite conversation never triggers the alert",
      not current_of(session)["alert"]["triggered"], f"max={max(scores)}")



# ==========================================================
# 7. SESSION STATE CONSISTENCY
# ==========================================================

banner("7. SESSION STATE - /escalation/{session_id} stays consistent")
session = uuid.uuid4().hex[:8]
scores = drive(session, ESCALATING)
state = state_of(session)
check("message_count matches the number of turns sent",
      state["message_count"] == len(ESCALATING),
      f"{state['message_count']} vs {len(ESCALATING)}")
check("scores stay inside 0-100",
      all(0 <= a["score"] <= 100 for a in state["assessments"]),
      "score out of range")
check("the last assessment matches the last message",
      state["assessments"][-1]["score"] == scores[-1],
      f"{state['assessments'][-1]['score']} vs {scores[-1]}")
check("a level is attached to every assessment",
      all(a.get("level") for a in state["assessments"]), "missing level")
check("an unknown session returns a clean default",
      current_of("does-not-exist-at-all")["risk_score"] == 0,
      "unexpected default")
check("every assessment carries a trend",
      all(a.get("trend") for a in state["assessments"]), "missing trend")

# ==========================================================
# 8. THRESHOLD ALERT
# ==========================================================

banner("8. CONFIGURABLE ALERT THRESHOLD")
# A MID-RANGE conversation is used on purpose: a score of 100 fires
# the alert at ANY threshold, which would make the check meaningless.
# This pair of messages settles mid-scale, so the threshold genuinely
# decides the outcome.
MIDRANGE = ESCALATING[:2]

post("/escalation/threshold", {"threshold": 90})
session = uuid.uuid4().hex[:8]
drive(session, MIDRANGE)
strict = state_of(session)["current"]
check("the mid-range score is High but below 90",
      50 <= strict["risk_score"] < 90, f"score={strict['risk_score']}")
check("a strict threshold stops the alert firing",
      not strict["alert"]["triggered"],
      f"score={strict['risk_score']} threshold=90")
check("the threshold is reported as 90",
      strict["alert"]["threshold"] == 90,
      f"{strict['alert']['threshold']}")

post("/escalation/threshold", {"threshold": 40})
session = uuid.uuid4().hex[:8]
drive(session, MIDRANGE)
loose = state_of(session)["current"]
check("a loose threshold fires the alert on the same conversation",
      loose["alert"]["triggered"],
      f"score={loose['risk_score']} threshold=40")
check("the score itself is unchanged by the threshold",
      loose["risk_score"] == strict["risk_score"],
      f"{strict['risk_score']} vs {loose['risk_score']}")

post("/escalation/threshold", {"threshold": 70})
check("threshold is restored to the default",
      get("/escalation/threshold")["threshold"] == 70,
      f"{get('/escalation/threshold')['threshold']}")

# ==========================================================
# SUMMARY
# ==========================================================

banner("SUMMARY")
print(f"  checks passed : {PASS}")
print(f"  checks failed : {FAIL}")
if FAILURES:
    print("\n  failures:")
    for item in FAILURES:
        print(f"    - {item}")
print()
sys.exit(1 if FAIL else 0)
