"""
Task 8 - clearly-labelled realistic demo/test conversations.

Real data is always preferred: the Performance Analytics module analyses
the conversations recorded by the Task 7 Live Support Console and the Task
3 simulator logs first. However, the analytics dashboard is meant to show
*multi-session* trends, and a freshly-installed project may have no
recorded console sessions yet.

This module provides six realistic support conversations (and the
knowledge-base searches they triggered) so the dashboard is populated
from the first run. They are stored with ``is_demo = True`` and are
always reported separately in ``data_sources.demo_conversations`` - they
are never mixed with real sessions without being labelled.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

_SEED = "2026-01-01T09:00:00+00:00"


def _iso(offset_hours: int) -> str:
    base = datetime.fromisoformat(_SEED)
    return (base + timedelta(hours=offset_hours)).astimezone(
        timezone.utc
    ).isoformat(timespec="seconds")


# title, persona, scenario, hour offset, messages, knowledge searches
_SCENARIOS = [
    (
        "Demo - duplicate payment charge",
        "frustrated",
        "payment_failure",
        0,
        [
            ("customer", "My payment failed and I have been trying for two "
                         "hours."),
            ("agent", "I am really sorry about that. I can see two "
                      "authorisations on your card. Let me check the "
                      "transaction now."),
            ("customer", "This is ridiculous. Nobody is helping me and I "
                         "need this fixed immediately."),
            ("agent", "I completely understand how frustrating this is. I "
                      "have released the duplicate authorisation and it will "
                      "drop off within 24 hours."),
            ("customer", "Thank you, the issue is finally resolved."),
        ],
        [
            ("My payment failed and I have been trying for two hours.",
             3, ["payment_issues.txt"]),
            ("This is ridiculous. Nobody is helping me and I need this "
             "fixed immediately.", 0, []),
        ],
    ),
    (
        "Demo - delayed order follow-up",
        "concerned",
        "delayed_order",
        26,
        [
            ("customer", "Where is my order? It is very late and the "
                         "tracking has not changed in four days."),
            ("agent", "Thanks for flagging that. I am checking the courier "
                      "status for you right away."),
            ("customer", "I have already contacted support twice about this "
                         "and it is still not here."),
            ("agent", "I am sorry you had to chase this. I have raised a "
                      "priority tracer with the courier and you will have an "
                      "update within 24 hours."),
            ("customer", "Please make sure it actually arrives this time."),
        ],
        [
            ("Where is my order? It is very late and the tracking has not "
             "changed in four days.", 3, ["delivery_delays.txt"]),
            ("I have already contacted support twice about this and it is "
             "still not here.", 2,
             ["delivery_delays.txt", "order_tracking.txt"]),
        ],
    ),
    (
        "Demo - refund not received",
        "frustrated",
        "refund_request",
        52,
        [
            ("customer", "I returned the item two weeks ago and the refund "
                         "has not arrived."),
            ("agent", "Let me look into that for you."),
            ("customer", "This is unacceptable. I want my money back now."),
            ("agent", "I understand. I have processed the refund manually "
                      "and it will reach your account within 3 to 5 "
                      "business days."),
            ("customer", "Fine, I will wait and see."),
        ],
        [
            ("I returned the item two weeks ago and the refund has not "
             "arrived.", 3, ["Refund Policy.pdf"]),
            ("This is unacceptable. I want my money back now.", 2,
             ["Refund Policy.pdf"]),
        ],
    ),
]


_SCENARIOS.extend([
    (
        "Demo - locked account recovery",
        "angry",
        "account_issue",
        78,
        [
            ("customer", "I am locked out of my account and the password "
                         "reset email never arrives."),
            ("agent", "That sounds frustrating. Have you checked your spam "
                      "folder?"),
            ("customer", "Yes of course I have. Stop giving me generic "
                         "answers and unlock my account."),
            ("agent", "You are right, I am sorry. I have reset the account "
                      "manually and emailed you a secure link - it expires "
                      "in 15 minutes."),
            ("customer", "It works now, thank you."),
        ],
        [
            ("I am locked out of my account and the password reset email "
             "never arrives.", 3, ["login_issues.txt"]),
            ("Yes of course I have. Stop giving me generic answers and "
             "unlock my account.", 1, ["password_reset.txt"]),
        ],
    ),
    (
        "Demo - cancellation with retention offer",
        "polite",
        "cancellation",
        104,
        [
            ("customer", "I would like to cancel my subscription please."),
            ("agent", "Of course - may I ask what prompted the decision? I "
                      "may be able to offer an alternative."),
            ("customer", "It is too expensive for how little I use it."),
            ("agent", "Understood. I can move you to the lighter plan at "
                      "half the price, or cancel immediately if you prefer."),
            ("customer", "The lighter plan sounds good actually, thanks."),
        ],
        [
            ("I would like to cancel my subscription please.", 3,
             ["Cancellation Policy.pdf"]),
        ],
    ),
    (
        "Demo - unresolved billing query",
        "concerned",
        "general_inquiry",
        130,
        [
            ("customer", "I do not recognise a charge on my last invoice."),
            ("agent", "Thanks for reaching out, we will look into this for "
                      "you."),
            ("customer", "It has been two days and I still have no answer. I "
                         "need this sorted."),
            ("agent", "Is there anything else I can help you with today?"),
            ("customer", "That is not helpful. I will dispute the charge "
                         "with my bank."),
        ],
        [
            ("I do not recognise a charge on my last invoice.", 2,
             ["billing_queries.txt"]),
            ("It has been two days and I still have no answer.", 0, []),
        ],
    ),
])


def demo_conversations() -> List[Dict]:
    """The demo conversations in the Task 7 store record format."""
    records: List[Dict] = []

    for index, (
        title,
        persona,
        scenario,
        offset,
        messages,
        searches,
    ) in enumerate(_SCENARIOS, start=1):
        created = _iso(offset)

        records.append({
            "id": f"demo-conv-{index:02d}",
            "mode": "manual",
            "title": title,
            "persona": persona,
            "scenario": scenario,
            "source_file": "demo_sessions.py",
            "is_demo": True,
            "tags": ["demo", "task8", "test-data"],
            "created_at": created,
            "completed_at": created,
            "messages": [
                {"role": role, "content": content, "timestamp": created}
                for role, content in messages
            ],
            "knowledge_searches": [
                {
                    "turn": turn,
                    "query": query,
                    "results": results,
                    "sources": sources,
                }
                for turn, (query, results, sources) in enumerate(
                    searches, start=1
                )
            ],
            "meta": {
                "is_demo": True,
                "note": (
                    "Realistic demo conversation used to populate the "
                    "performance-analytics dashboard. Labelled as demo data "
                    "everywhere it is displayed."
                ),
            },
        })

    return records


def seed_demo_conversations(store=None) -> int:
    """Write the demo conversations into the Task 7 conversation store."""
    if store is None:
        import session_store as store_module  # local import: optional dep

        store = store_module

    return store.upsert_many(demo_conversations())

