"""
Task 8 - shared conversation analysis.

Turns a finished conversation into the machine-readable facts both Task 8
deliverables need:

    * per customer message: intent, emotion, frustration, sentiment,
      escalation score/level/trend, resolution status, escalation
      indicators (the "escalation triggers"), satisfaction trend;
    * per agent message: the four-dimension response evaluation
      (tone / clarity / empathy / professionalism) plus a flag when the
      reply is below the quality bar ("incorrect response").

Everything comes from the EXISTING Task 4/5/6 agents - this module only
sequences them over a conversation. No scoring rule is re-implemented.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List

_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent
_ENGINE_DIR = _REPO_ROOT / "task4_task5_task6_support_assist_agents"

for _candidate in (str(_ENGINE_DIR), str(_REPO_ROOT)):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from support_assist import (  # noqa: E402
    CoachingResponseAgent,
    EscalationRiskMonitor,
    _CUSTOMER_RESOLUTION_WORDS,
    _DEMANDS_A_RESOLUTION_RE,
    _has_unnegated,
)

CUSTOMER = "customer"
AGENT = "agent"

QUALITY_BAR = 60  # below this a reply is reported as a weak/incorrect response

# A reply that is only a stock non-answer never resolves anything.
NON_ANSWERS = (
    "is there anything else i can help you with",
    "anything else i can help",
    "have a nice day",
    "please try again later",
    "as per our policy",
)

# The engine's _DEMANDS_A_RESOLUTION_RE also matches DECLARATIVE statements
# such as "the issue is resolved" (its interrogative branch: "is ... resolved").
# For the FINAL post-interaction confirmation check that is too strict, so a
# message only vetoes the confirmation when it really still demands action:
# a question, an explicit outstanding need, or an unresolved/negated form.
_STILL_DEMANDS_RE = re.compile(
    r"\?"  # direct question: "has this been resolved?"
    r"|\b(?:when|how long|why)\b[^.?!]{0,40}\b(?:will|is|has|have|can|do)\b"
    r"|\b(?:i|we)\s+(?:need|want|require|expect|await)\b"
    r"|\b(?:need|want)\s+(?:this|it|that|you)\b"
    r"|\bplease\s+(?:fix|resolve|sort|update|process|refund|check)\b"
    r"|\b(?:tell|show|give)\s+me\b"
    r"|\b(?:still|not|never|yet|waiting)\b[^.?!]{0,40}"
    r"\b(?:resolved|fixed|sorted|processed|handled|reply|answer|update)\b"
)


def normalise(messages) -> List[Dict]:
    """Role-tag + clean an arbitrary conversation payload."""
    normalised: List[Dict] = []

    for item in messages or []:
        if isinstance(item, str):
            normalised.append({"role": CUSTOMER, "content": item.strip()})
            continue
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or item.get("speaker") or CUSTOMER).lower()
        role = AGENT if role in (
            "agent", "support", "assistant", "bot", "system", "you"
        ) else CUSTOMER
        content = str(
            item.get("content")
            if item.get("content") is not None
            else item.get("message", "")
        ).strip()
        if not content:
            continue
        normalised.append({
            "role": role,
            "content": content,
            "timestamp": item.get("timestamp"),
        })

    return normalised


def final_resolution(conversation) -> Dict:
    """
    The resolution state AFTER the whole conversation.

    The Escalation Risk Monitor reports ``resolution_status`` for the
    *previous* messages (it deliberately excludes the message being
    assessed), so the last customer confirmation would only be visible on
    a further turn. For a post-interaction report that is too late, so the
    engine's own resolution rule/vocabulary is applied once more with the
    complete transcript - the same words, regexes and negation handling,
    never a second scoring rule.
    """
    customers = [
        message["content"].lower()
        for message in conversation
        if message["role"] == CUSTOMER
    ]
    agents = [
        message["content"].lower()
        for message in conversation
        if message["role"] == AGENT
    ]

    if not customers:
        return {"status": "unknown", "evidence": []}

    try:
        engine_state = EscalationRiskMonitor._resolution_state(customers, agents)
    except Exception:  # pragma: no cover - defensive
        engine_state = {"status": "unknown", "evidence": []}

    # 1. Did the CUSTOMER confirm the fix in their final message?
    last_customer = customers[-1]
    confirms = [
        word for word in _CUSTOMER_RESOLUTION_WORDS
        if word in last_customer
    ]
    if (
        confirms
        and _has_unnegated(last_customer, _CUSTOMER_RESOLUTION_WORDS)
        and not _STILL_DEMANDS_RE.search(last_customer)
    ):
        return {
            "status": "resolved",
            "evidence": confirms,
            "confirmed_by": "customer",
        }

    # 2. Otherwise trust the engine's evidence-based verdict.
    if engine_state.get("status") in ("resolved", "offered", "open"):
        return {
            "status": engine_state["status"],
            "evidence": engine_state.get("evidence") or [],
            "confirmed_by": (
                "customer" if engine_state["status"] == "resolved"
                else "agent" if engine_state["status"] == "offered"
                else None
            ),
        }

    return {"status": "unknown", "evidence": []}


def analyse_conversation(
    messages,
    session_key: str = "task8-analysis",
) -> Dict:
    """
    Run the full support-assistance pipeline over one conversation.

    Returns a dict with ``timeline`` (one entry per customer message),
    ``agent_turns`` (one entry per agent reply), ``resolution``,
    ``peak``, ``statistics`` and the chart-ready curves.
    """
    conversation = normalise(messages)
    monitor = EscalationRiskMonitor()
    coaching = CoachingResponseAgent()

    history: List[Dict] = []
    timeline: List[Dict] = []
    agent_turns: List[Dict] = []
    trigger_counts: Dict[str, int] = {}
    trigger_points: Dict[str, int] = {}

    customer_turn = 0
    last_state = {
        "intent": None,
        "emotion_label": None,
        "frustration_level": None,
        "sentiment": None,
        "sentiment_score": 0.0,
        "escalation_score": 0,
        "escalation_level": "Low",
    }

    for index, message in enumerate(conversation):
        history.append({"role": message["role"], "content": message["content"]})

        if message["role"] == CUSTOMER:
            customer_turn += 1
            risk = monitor.assess(
                session_key,
                message["content"],
                turn=customer_turn,
                customer_history=history,
            )

            entry = {
                "index": index,
                "turn": customer_turn,
                "customer_message": message["content"],
                "intent": risk["intent"],
                "emotion": risk["emotion_label"],
                "frustration": risk["frustration_level"],
                "sentiment": risk["sentiment_label"],
                "sentiment_score": round(
                    float(risk["sentiment"]["score"]), 3
                ),
                "sentiment_confidence": round(
                    float(risk["sentiment"]["confidence"]), 3
                ),
                "escalation_score": risk["escalation_score"],
                "escalation_level": risk["escalation_level"],
                "escalation_trend": risk["trend"],
                "resolution_status": risk.get("resolution_status", "unknown"),
                "satisfaction_trend": risk.get("satisfaction_trend", "unknown"),
                "negative_streak": risk["negative_streak"],
                "de_escalation": risk.get("de_escalation", "none"),
                "indicators": [
                    indicator["name"]
                    for indicator in risk.get("indicators") or []
                ],
                "reasoning": risk.get("reasoning") or [],
                "alert_triggered": bool(
                    (risk.get("alert") or {}).get("triggered")
                ),
            }
            timeline.append(entry)

            for indicator in risk.get("indicators") or []:
                name = indicator.get("name")
                if not name:
                    continue
                trigger_counts[name] = trigger_counts.get(name, 0) + 1
                trigger_points[name] = trigger_points.get(name, 0) + int(
                    indicator.get("points") or 0
                )

            last_state = {
                "intent": entry["intent"],
                "emotion_label": entry["emotion"],
                "frustration_level": entry["frustration"],
                "sentiment": entry["sentiment"],
                "sentiment_score": entry["sentiment_score"],
                "escalation_score": entry["escalation_score"],
                "escalation_level": entry["escalation_level"],
            }
            continue

        # ---- agent reply: score it with the Coaching agent ----
        evaluation = coaching.evaluate_response(
            message["content"],
            sentiment=last_state["sentiment"] or "neutral",
            frustration_score=last_state["frustration_level"] or 5,
        )

        reply_lower = message["content"].lower()
        issues: List[str] = []

        if evaluation["overall"] < QUALITY_BAR:
            issues.append(
                f"Low quality score ({evaluation['overall']}/100): "
                f"{evaluation['summary']}"
            )
        if len(reply_lower.split()) < 5:
            issues.append("Reply is too short to resolve anything.")
        if any(phrase in reply_lower for phrase in NON_ANSWERS):
            issues.append("Stock non-answer that does not address the issue.")
        if (
            last_state["frustration_level"] is not None
            and last_state["frustration_level"] >= 7
            and evaluation["empathy"]["score"] < 60
        ):
            issues.append(
                "Emotionally loaded message handled without enough empathy."
            )
        if (
            last_state["frustration_level"] is not None
            and last_state["frustration_level"] >= 6
            and evaluation["tone"]["score"] < 60
        ):
            issues.append("Tone does not match an upset customer.")

        agent_turns.append({
            "index": index,
            "turn": len(agent_turns) + 1,
            "reply": message["content"],
            "overall": evaluation["overall"],
            "meets_standard": evaluation["meets_standard"],
            "summary": evaluation["summary"],
            "tone": evaluation["tone"]["score"],
            "clarity": evaluation["clarity"]["score"],
            "empathy": evaluation["empathy"]["score"],
            "professionalism": evaluation["professionalism"]["score"],
            "below_bar": bool(issues),
            "issues": issues,
            "responding_to_intent": last_state["intent"],
            "responding_to_frustration": last_state["frustration_level"],
        })

    return _summarise(
        conversation,
        timeline,
        agent_turns,
        trigger_counts,
        trigger_points,
        final_resolution(conversation),
    )


def _summarise(
    conversation,
    timeline,
    agent_turns,
    trigger_counts,
    trigger_points,
    resolution=None,
) -> Dict:
    """Aggregate the per-message results into conversation-level facts."""
    customer_count = sum(1 for m in conversation if m["role"] == CUSTOMER)
    agent_count = len(conversation) - customer_count

    overall_scores = [turn["overall"] for turn in agent_turns]
    dimensions = {
        "tone": [turn["tone"] for turn in agent_turns],
        "clarity": [turn["clarity"] for turn in agent_turns],
        "empathy": [turn["empathy"] for turn in agent_turns],
        "professionalism": [
            turn["professionalism"] for turn in agent_turns
        ],
    }

    def _mean(values):
        return round(sum(values) / len(values), 1) if values else None

    first = timeline[0] if timeline else None
    last = timeline[-1] if timeline else None
    peak = (
        max(timeline, key=lambda entry: entry["escalation_score"])
        if timeline
        else None
    )

    resolution_status = (
        last["resolution_status"] if last else "unknown"
    )

    intents: List[str] = []
    for entry in timeline:
        if entry["intent"] and entry["intent"] not in intents:
            intents.append(entry["intent"])

    # "Primary issue" = the intent the customer pressed on most often
    # (ties fall back to the first one raised).
    intent_counts: Dict[str, int] = {}
    for entry in timeline:
        intent_counts[entry["intent"]] = (
            intent_counts.get(entry["intent"], 0) + 1
        )

    return {
        "messages": conversation,
        "timeline": timeline,
        "agent_turns": agent_turns,
        "intents": intents,
        "intent_counts": intent_counts,
        "primary_intent": _primary_intent(intent_counts, timeline),
        "resolution": {
            "status": (
                resolution["status"] if resolution else resolution_status
            ),
            "evidence": (
                (resolution or {}).get("evidence")
                or ((last or {}).get("reasoning", [])[-1:] if last else [])
            ),
            "confirmed_by": (resolution or {}).get("confirmed_by"),
        },
        "first": first,
        "last": last,
        "peak": peak,
        "escalation_triggers": trigger_counts,
        "trigger_points": trigger_points,
        "statistics": {
            "total_messages": len(conversation),
            "customer_messages": customer_count,
            "agent_messages": agent_count,
            "avg_response_quality": _mean(overall_scores),
            "dimension_averages": {
                name: _mean(values) for name, values in dimensions.items()
            },
            "below_bar_responses": sum(
                1 for turn in agent_turns if turn["below_bar"]
            ),
            "peak_escalation_score": (
                peak["escalation_score"] if peak else 0
            ),
            "peak_escalation_level": peak["escalation_level"] if peak else "Low",
            "alerts_triggered": sum(
                1 for entry in timeline if entry["alert_triggered"]
            ),
            "frustration_start": first["frustration"] if first else None,
            "frustration_end": last["frustration"] if last else None,
            "sentiment_start": first["sentiment"] if first else None,
            "sentiment_end": last["sentiment"] if last else None,
        },
        "frustration_curve": [
            {
                "label": f"#{entry['turn']}",
                "value": entry["frustration"],
                "escalation": entry["escalation_score"],
            }
            for entry in timeline
        ],
        "sentiment_curve": [
            {
                "label": f"#{entry['turn']}",
                "value": entry["sentiment_score"],
                "sentiment": entry["sentiment"],
                "message": entry["customer_message"],
            }
            for entry in timeline
        ],
    }


def _primary_intent(intent_counts: Dict[str, int], timeline) -> str:
    """Most frequently raised intent, ties resolved by first mention."""
    if not intent_counts:
        return "general_inquiry"

    order = [entry["intent"] for entry in timeline]
    best = None
    best_count = -1

    for intent, count in intent_counts.items():
        if count > best_count:
            best, best_count = intent, count
        elif count == best_count and best is not None:
            if order.index(intent) < order.index(best):
                best = intent

    return best or "general_inquiry"

    return normalised
