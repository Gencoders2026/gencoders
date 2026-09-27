"""
Adversarial + edge-case stress test for the Escalation Risk Monitor.

Tries hard to BREAK it:
  A. Edge inputs      - empty-ish, punctuation, very long, unicode,
                        emoji, XSS payloads, shouting vs whispering
  B. Adversarial text - negation, quoted threats, keyword-only messages
  C. Invariants       - score always 0..100, level always matches the
                        score, trend always consistent, counters never
                        move backwards
  D. Session isolation, determinism and agent-message load

Every invariant is checked on EVERY turn of every conversation.
"""

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"

PASS = 0
FAIL = 0
FAILURES = []


def post(path, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(
        BASE + path, data=data, headers=headers,
        method="POST" if payload else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get(path):
    return post(path)


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{label} :: {detail}")
        print(f"  [FAIL] {label} :: {detail}")


def send(session, message, turn=None, sender="customer"):
    payload = {"query": message, "session_id": session, "sender": sender}
    if turn is not None:
        payload["turn"] = turn
    return post("/support/analyze", payload)


def info(label, value):
    print(f"  [info] {label:32} {value}")


# ==========================================================
# A. EDGE INPUTS
# ==========================================================

EDGE_INPUTS = [
    ("punctuation only", "!!!???"),
    ("dots", "...."),
    ("newlines", "\n\n\n\n"),
    ("tabs", "\t\t\t"),
    ("single char", "x"),
    ("long word", "supercalifragilistic" * 40),
    ("very long message", "this is still not resolved. " * 200),
    ("unicode", "eèü 你好 \U0001F621"),
    ("emoji only", "\U0001F621\U0001F621\U0001F621"),
    ("html/script", "<script>alert('xss')</script>"),
    ("quote injection", 'he said "I demand a manager" loudly'),
    ("all caps", "I AM FURIOUS AND I WANT A MANAGER NOW"),
    ("all lower", "i am furious and i want a manager now"),
    ("numbers only", "1234567890"),
    ("repeated char", "a" * 500),
    ("symbols", "!@#$%^&*()"),
]


def test_edge_inputs():
    print()
    print("A. EDGE INPUTS - must never crash or go out of range")
    for i, (label, text) in enumerate(EDGE_INPUTS):
        try:
            data = send(f"edge-{i}", text, turn=1)
        except Exception as exc:  # noqa: BLE001
            check(f"edge input accepted: {label}", False, str(exc)[:110])
            continue
        score = data.get("escalation_score")
        check(f"edge input accepted: {label}",
              isinstance(score, int) and 0 <= score <= 100,
              f"score={score!r} level={data.get('escalation_level')!r}")


# ==========================================================
# B. ADVERSARIAL TEXT
# ==========================================================

# These probe whether the monitor reads MEANING or just keywords.
ADVERSARIAL = [
    ("negated manager request",
     "I do not want to speak to a manager, please just fix my order",
     "Low"),
    ("negated anger",
     "I am not angry, I just need my refund processed", "Low"),
    ("quoted threat",
     'My friend told me "I will sue you" but I just want my money back',
     "Low"),
    ("polite manager request",
     "Could you please ask your manager to review my refund? Thank you.",
     None),
    ("genuine escalation",
     "I demand a supervisor right now or I will cancel everything", None),
    ("calm urgent",
     "Could you please process this today? Thank you for your help.",
     "Low"),
    ("bare keyword", "manager", None),
]


def test_adversarial():
    print()
    print("B. ADVERSARIAL TEXT - meaning vs keyword matching")
    for i, (label, text, expected) in enumerate(ADVERSARIAL):
        data = send(f"adv-{i}", text, turn=1)
        score = data["escalation_score"]
        level = data["escalation_level"]
        if expected is not None:
            check(f"{label}: stays {expected}", level == expected,
                  f"got {level} ({score}) for {text[:50]!r}")
        else:
            info(label, f"{score:3d} {level}")


# ==========================================================
# C. INVARIANTS ON EVERY TURN
# ==========================================================

def level_for(score):
    if score < 25:
        return "Low"
    if score < 50:
        return "Medium"
    if score < 75:
        return "High"
    return "Critical"


LONG_CONVERSATIONS = {
    "sustained escalation": [
        "My order is late and this is the third time I am asking.",
        "Still nothing. Nobody has helped me at all.",
        "This is really frustrating. I need it fixed immediately.",
        "I am done. Give me a manager or I will cancel everything.",
        "Nothing changed. I will be posting about this on social media.",
        "Nobody cares. I am done waiting, escalate this now.",
        "This is completely unacceptable. Escalate to a supervisor.",
        "I am still waiting and nobody has contacted me.",
    ],
    "slow de-escalation": [
        "This is unacceptable! I demand a manager immediately!",
        "Still not resolved and I am very frustrated about it.",
        "Okay, but I still have not heard anything back.",
        "I appreciate you checking, thank you for the update.",
        "Thanks, that is helpful. I understand the delay now.",
        "That is great, it is sorted. Thank you very much!",
    ],
    "volatile zigzag": [
        "I AM FURIOUS. GET ME A MANAGER NOW!",
        "thanks, that is sorted, appreciate it",
        "no wait, it is STILL not fixed. I am angry again!",
        "okay thank you, that is resolved now",
        "actually nobody has helped me, this is not resolved!",
        "thanks, sorted, appreciate your help",
    ],
    "whisper then shout": [
        "hello, quick question about my order please",
        "thanks a lot for the help",
        "this is unacceptable, nobody has helped me!",
        "I demand a manager immediately, escalate this now",
        "thanks, that is resolved now",
    ],
}


def test_invariants():
    print()
    print("C. INVARIANTS - checked on EVERY turn of every conversation")
    for title, messages in LONG_CONVERSATIONS.items():
        session = f"inv-{abs(hash(title)) % 100000}"
        previous_score = None
        previous_streak = 0
        scores = []
        for i, message in enumerate(messages, start=1):
            data = send(session, message, turn=i)
            score = data["escalation_score"]
            level = data["escalation_level"]
            trend = data["escalation_trend"]
            streak = data["negative_streak"]
            scores.append(score)

            check(f"{title} T{i}: score in 0..100",
                  isinstance(score, int) and 0 <= score <= 100,
                  f"score={score!r}")
            check(f"{title} T{i}: level matches score",
                  level == level_for(score),
                  f"score={score} level={level} expected={level_for(score)}")
            check(f"{title} T{i}: message_count tracks turns",
                  data["message_count"] == i,
                  f"count={data['message_count']} expected={i}")
            # The negative streak is CONSECUTIVE negative messages, so
            # it is EXPECTED to reset when the customer says something
            # calm. The real invariant is that it resets only when the
            # current message is not negative, and that it still grows
            # while every message stays negative.
            is_negative = data["sentiment"] == "negative"
            if is_negative:
                check(f"{title} T{i}: streak grows on a negative turn",
                      streak > previous_streak,
                      f"{previous_streak} -> {streak}")
            else:
                check(f"{title} T{i}: streak resets on a calm turn",
                      streak <= 1,
                      f"{previous_streak} -> {streak} (sentiment="
                      f"{data['sentiment']})")
            check(f"{title} T{i}: trend is valid",
                  trend in ("first_message", "increasing", "decreasing",
                            "stable"), f"trend={trend!r}")
            if previous_score is not None:
                expected = (
                    "increasing" if score > previous_score + 1
                    else "decreasing" if score < previous_score - 1
                    else "stable"
                )
                check(f"{title} T{i}: trend matches score movement",
                      trend == expected,
                      f"{previous_score} -> {score} trend={trend} "
                      f"expected={expected}")
            check(f"{title} T{i}: reasoning recorded",
                  bool(data.get("escalation_reasoning")), "no reasoning")
            previous_score = score
            previous_streak = streak
        info(title, " -> ".join(f"{s:3d}" for s in scores))



# ==========================================================
# D. ISOLATION, DETERMINISM, AGENT LOAD
# ==========================================================

HOT = "STRESS-ISOLATION-HOT"
COLD = "STRESS-ISOLATION-COLD"


def test_isolation():
    print()
    print("D. SESSION ISOLATION - conversations must not bleed together")
    for i in range(3):
        send(HOT, "I am furious, get me a manager, this is not resolved!",
             turn=i + 1)
    for i in range(3):
        send(COLD, "thanks, that is sorted, I appreciate your help",
             turn=i + 1)

    try:
        hot = get(f"/escalation/{HOT}")["current"]["risk_score"]
        cold = get(f"/escalation/{COLD}")["current"]["risk_score"]
    except Exception as exc:  # noqa: BLE001
        check("both sessions readable", False, str(exc)[:110])
        return

    check("angry session stayed high", hot >= 75, f"{hot}")
    check("thankful session stayed low", cold < 25, f"{cold}")
    check("sessions are fully isolated", hot != cold,
          f"hot={hot} cold={cold}")
    info("angry session", f"{hot} / 100")
    info("thankful session", f"{cold} / 100")


def test_determinism():
    print()
    print("E. DETERMINISM - identical input gives identical output")
    messages = [
        "My order is late and this is the third time I am asking.",
        "Still nothing resolved, nobody has helped me.",
        "I demand a manager immediately, escalate this now.",
        "thanks, that is sorted, I appreciate your help",
    ]
    runs = []
    for run in range(2):
        runs.append([
            send(f"det-{run}", m, turn=i)["escalation_score"]
            for i, m in enumerate(messages, start=1)
        ])
    check("two identical runs produce the same scores",
          runs[0] == runs[1], f"{runs[0]} vs {runs[1]}")
    info("run 1", str(runs[0]))
    info("run 2", str(runs[1]))


def test_agent_under_load():
    print()
    print("F. AGENT MESSAGES UNDER LOAD - never move customer state")
    session = "STRESS-AGENT-LOAD"
    send(session, "I am furious! Nobody has helped me, get me a manager!",
         turn=1)
    baseline = send(session, "I am still furious, this is not resolved!",
                    turn=2)

    # Everything is compared against the monitor's OWN stored state, so
    # the baseline is also read from the session endpoint (the POST
    # response and the stored state expose the same values, but the
    # stored state is the single source of truth being asserted on).
    before_state = get(f"/escalation/{session}")["current"]
    for _ in range(5):
        send(session,
             "I am so sorry, I fully understand and will fix this "
             "immediately, thank you for your patience.", sender="agent")
    state = get(f"/escalation/{session}")["current"]

    check("5 agent replies added no customer messages",
          state["message_count"] == baseline["message_count"],
          f"{baseline['message_count']} -> {state['message_count']}")
    for field in ("emotion_label", "frustration", "negative_streak",
                  "risk_score"):
        check(f"agent replies did not change {field}",
              state.get(field) == before_state.get(field),
              f"{before_state.get(field)!r} -> {state.get(field)!r}")

    # The customer speaking again must still move the risk.
    after = send(session, "I am still furious, this is not resolved!",
                 turn=3)
    check("a new customer message is counted",
          after["message_count"] == baseline["message_count"] + 1,
          f"{baseline['message_count']} -> {after['message_count']}")
    check("risk still tracks after an agent flood",
          after["escalation_score"] >= 50,
          f"score={after['escalation_score']}")


def main():
    test_edge_inputs()
    test_adversarial()
    test_invariants()
    test_isolation()
    test_determinism()
    test_agent_under_load()

    print()
    print("=" * 70)
    print(f"  checks passed : {PASS}")
    print(f"  checks failed : {FAIL}")
    if FAILURES:
        print()
        print("  failures:")
        for item in FAILURES[:40]:
            print(f"    - {item}")
        if len(FAILURES) > 40:
            print(f"    ... and {len(FAILURES) - 40} more")
    print()
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
