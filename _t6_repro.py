"""
Reproduce the Support Console escalation-risk flow turn by turn.

Runs a real session against the Customer Simulator backend
(http://127.0.0.1:8000): the customer's message is pushed through
POST /support/analyze with the full role-tagged history - exactly the
way frontend/src/pages/SupportConsole.jsx does it - and the resulting
risk score / level / trend / streak is printed.

The agent reply for each turn is the AI-suggested response
(`suggested_response`), which is what happens when the user clicks
"Use this response" in the console.

Usage:
    python _t6_repro.py                    # frustrated / delayed_order / 7
    python _t6_repro.py angry refund_request 8
"""

import json
import random
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"

DEFAULT_PERSONA = "frustrated"
DEFAULT_SCENARIO = "delayed_order"
DEFAULT_LEVEL = 7
TURNS = 6


def post(path, payload):
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def run(persona, scenario, level):
    session_id = "repro-" + str(random.randint(1000, 9999))

    started = post(
        "/session/start",
        {
            "persona": persona,
            "scenario": scenario,
            "frustration_level": level,
            "expected_resolution": "new_delivery_date",
        },
    )

    print(
        f"session={started['session_id']} persona={started['persona']} "
        f"scenario={started['scenario']} level={level}"
    )
    print()

    history = list(started.get("history") or [])
    customer_message = started["customer_message"]
    previous_score = None

    for turn in range(1, TURNS + 1):
        customer_turn = len(
            [m for m in history if m.get("role") == "customer"]
        )

        analysis = post(
            "/support/analyze",
            {
                "query": customer_message,
                "session_id": session_id,
                "turn": customer_turn,
                "sender": "customer",
                "history": [
                    {"role": m.get("role"), "content": m.get("content", "")}
                    for m in history
                ],
            },
        )

        score = analysis["escalation_score"]
        delta = "" if previous_score is None else f" ({score - previous_score:+d})"
        previous_score = score
        print(
            f"T{turn} risk={score:>3}{delta:<6} "
            f"{analysis['escalation_level']:<8} "
            f"trend={analysis['escalation_trend']:<13} "
            f"frust={analysis['frustration_level']}/10 "
            f"sent={analysis['sentiment']:<8} "
            f"streak={analysis['negative_streak']} "
            f"deesc={analysis['de_escalation']}"
        )
        print(f"    customer: {analysis['customer_message'][:95]}")

        for line in analysis.get("escalation_reasoning", []):
            print(f"      - {line}")

        if turn == TURNS:
            break

        agent_reply = analysis.get("suggested_response") or "Okay, let me check."
        reply = post(
            "/session/respond",
            {"session_id": started["session_id"], "message": agent_reply},
        )

        history.append({"role": "agent", "content": agent_reply})
        history.append(
            {"role": "customer", "content": reply.get("customer_message", "")}
        )
        customer_message = reply.get("customer_message", "")
        print()


def main():
    persona = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PERSONA
    scenario = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SCENARIO
    level = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_LEVEL
    run(persona, scenario, level)


if __name__ == "__main__":
    main()
