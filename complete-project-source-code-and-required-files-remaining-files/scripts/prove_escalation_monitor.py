"""
Print the FULL inner workings of the Escalation Risk Monitor for a
real conversation: the score, level, trend, every indicator that
contributed points, and every line of reasoning it recorded.

This is the evidence behind the number - not just the number.

Run with the backend already listening on http://127.0.0.1:8000
"""

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"

CONVERSATIONS = {
    "ESCALATING": [
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
    ],
    "DE-ESCALATING": [
        "This is completely unacceptable! I demand a manager right now. "
        "Nobody has helped me and I will post about this on social media. "
        "My bank is going to dispute the charge too.",
        "I have still not received my refund and it is really "
        "frustrating. I need this resolved immediately.",
        "I understand the delay, thank you for checking. I appreciate "
        "your help with this.",
        "That is great, thank you. It is sorted now, I appreciate you "
        "getting this resolved.",
    ],
    "MIXED ARC": [
        "I am absolutely furious! Get me a supervisor immediately, this "
        "is unacceptable and I will sue you and tell everyone!",
        "Thank you, that is sorted now. I really appreciate your help.",
        "Wait, nothing happened. This is still not resolved and I am "
        "furious again. Escalate this to a manager immediately!",
    ],
    "POLITE (no false alarm)": [
        "Hello, I would like to know the status of my order, thank you "
        "for your help.",
        "Thanks for the update, that is helpful. I appreciate it.",
        "Perfect, everything is sorted. Thank you very much!",
    ],
}


def call(payload):
    request = urllib.request.Request(
        BASE + "/support/analyze",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(request, timeout=30).read())


def bar(score):
    filled = int(round(score / 5))
    return "[" + "#" * filled + "." * (20 - filled) + f"] {score:3d}/100"


def show(title, messages):
    print()
    print("#" * 78)
    print(f"#  {title}")
    print("#" * 78)
    session = f"proof-{abs(hash(title)) % 100000}"
    for i, message in enumerate(messages, start=1):
        data = call({
            "query": message,
            "session_id": session,
            "sender": "customer",
            "turn": i,
        })
        score = data["escalation_score"]
        sentiment = data.get("sentiment")
        if isinstance(sentiment, dict):
            sentiment = sentiment.get("label", "?")
        print()
        print(f"  TURN {i}  {bar(score)}  {data['escalation_level']}  "
              f"trend={data['escalation_trend']}  "
              f"sentiment={sentiment}  "
              f"frustration={data['frustration_level']}/10  "
              f"streak={data['negative_streak']}")
        print(f"  CUSTOMER: {message[:96]}")
        print()
        indicators = data.get("escalation_indicators") or []
        if indicators:
            print("  INDICATORS THAT ADDED POINTS:")
            for ind in indicators:
                print(f"    +{ind['points']:>3}  {ind['name']}"
                      f"  (matched: {ind.get('matched_phrase')!r})")
        else:
            print("  INDICATORS THAT ADDED POINTS:  (none)")
        print()
        print("  REASONING:")
        for line in data.get("escalation_reasoning") or []:
            print(f"    - {line}")
        alert = data.get("alert") or {}
        if alert.get("triggered"):
            print()
            print(f"  *** ALERT FIRED at threshold {alert['threshold']} "
                  f"-> {alert['message']}")
            for action in (alert.get("recommended_actions") or [])[:3]:
                print(f"      * {action}")
    return session


def main():
    for title, messages in CONVERSATIONS.items():
        show(title, messages)
    print()
    print("=" * 78)
    print("  SCORE TRAJECTORIES")
    print("=" * 78)
    for title, messages in CONVERSATIONS.items():
        session = f"trace-{abs(hash(title)) % 100000}"
        scores = [
            call({"query": m, "session_id": session, "sender": "customer",
                  "turn": i})["escalation_score"]
            for i, m in enumerate(messages, start=1)
        ]
        arrow = " -> ".join(f"{s:3d}" for s in scores)
        direction = (
            "RISING" if scores[-1] > scores[0]
            else "FALLING" if scores[-1] < scores[0]
            else "FLAT"
        )
        print(f"  {title:26} {arrow}   ({direction})")
    print()


if __name__ == "__main__":
    main()
