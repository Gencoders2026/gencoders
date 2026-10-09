"""Live console-flow check: session -> agent replies -> risk movement.

Exercises the real endpoints the Support Console uses
(`/session/start`, `/session/respond`, `/support/analyze`) exactly the way
`support_console_frontend/src/pages/SupportConsole.jsx` does, and prints
the escalation-risk state after every customer reply.
"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

AGENT_REPLIES = [
    # Deliberately non-resolving replies: the monitor must keep reacting to
    # every customer message, so the conversation is allowed to continue.
    "I am sorry for the delay. I am checking the status of your refund "
    "right now and will come back to you shortly.",
    "Thanks for waiting. Could you confirm the transaction ID on the "
    "order so I can trace it?",
    "Thank you for your patience. I am still looking into this for you.",
]


def post(path, payload):
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


started = post("/session/start", {
    "persona": "frustrated",
    "scenario": "refund_request",
    "frustration_level": 7,
})
session_id = started["session_id"]
history = list(started["history"])

analysis = post("/support/analyze", {
    "query": started["customer_message"],
    "session_id": session_id,
    "turn": 1,
    "history": history,
})
print(f"session={session_id}")
print(
    f"T1 risk={analysis['escalation_score']:>3} "
    f"{analysis['escalation_level']:<8} {analysis['escalation_trend']:<13} "
    f"| {started['customer_message'][:60]}"
)

for turn, agent_reply in enumerate(AGENT_REPLIES, start=2):
    reply = post("/session/respond", {
        "session_id": session_id,
        "message": agent_reply,
    })
    if reply.get("finished"):
        print("   conversation finished by the simulator")
        break

    history = history + [
        {"role": "agent", "content": agent_reply},
        {"role": "customer", "content": reply["customer_message"]},
    ]
    analysis = post("/support/analyze", {
        "query": reply["customer_message"],
        "session_id": session_id,
        "turn": turn,
        "history": history,
    })
    print(
        f"T{turn} risk={analysis['escalation_score']:>3} "
        f"{analysis['escalation_level']:<8} "
        f"{analysis['escalation_trend']:<13} "
        f"sat={analysis['satisfaction_trend']:<10} "
        f"| {reply['customer_message'][:50]}"
    )

state = post("/support/analyze", {
    "query": started["customer_message"],
    "session_id": session_id + "-state",
    "turn": 1,
    "history": history,
})
print(f"\nFINAL: risk={state['escalation_score']} "
      f"{state['escalation_level']} alert={state['alert']['triggered']}")
