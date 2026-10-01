"""
Task 8 - Post-Interaction Summary Agent.

Turns a COMPLETED conversation into the structured report the brief asks
for:

    1. a concise summary of the interaction,
    2. the customer's primary issue,
    3. the final resolution,
    4. the customer sentiment journey / timeline,
    5. a resolution quality score built from
       - issue resolution,
       - communication quality,
       - customer sentiment improvement,
       - adherence to support guidelines,
    6. the strengths and weaknesses of the agent's replies,
    7. personalised coaching recommendations for future interactions.

All inputs come from the real conversation + the existing Task 4/5/6
agents (`conversation_analysis.analyse_conversation`), so the report is
reproducible and consistent with the rest of the application.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent

for _candidate in (
    str(_MODULE_DIR),
    str(_REPO_ROOT / "task4_task5_task6_support_assist_agents"),
    str(_REPO_ROOT),
):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import conversation_analysis  # noqa: E402
from support_assist import CoachingResponseAgent, clamp_score  # noqa: E402

# Weight of each factor in the resolution-quality score (they add up to 1).
QUALITY_WEIGHTS = {
    "issue_resolution": 0.35,
    "communication_quality": 0.25,
    "sentiment_improvement": 0.20,
    "guideline_adherence": 0.20,
}

# Base score per resolution status, before evidence-based adjustments.
RESOLUTION_BASE = {
    "resolved": 100,
    "offered": 76,
    "open": 32,
    "unknown": 52,
}

RESOLUTION_LABELS = {
    "resolved": "Resolved - the customer confirmed the fix",
    "offered": "Solution offered - the agent gave a concrete commitment",
    "open": "Still open - the customer was still pressing for a solution",
    "unknown": "Unclear - the conversation ended without a resolution signal",
}

INTENT_LABELS = {
    "refund_request": "Refund request",
    "delayed_order": "Delayed order / delivery",
    "payment_failure": "Payment failure",
    "account_issue": "Account access issue",
    "cancellation": "Cancellation request",
    "general_inquiry": "General enquiry",
}


def intent_label(intent: Optional[str]) -> str:
    return INTENT_LABELS.get(
        intent or "",
        (intent or "General enquiry").replace("_", " ").title(),
    )


# ---------------------------------------------------------------------------
# Factor scoring
# ---------------------------------------------------------------------------
def _issue_resolution_score(analysis: Dict) -> Dict:
    """Did the customer's issue actually get resolved?"""
    status = analysis["resolution"]["status"]
    score = RESOLUTION_BASE.get(status, 52)
    notes: List[str] = []

    last = analysis.get("last") or {}
    peak = analysis.get("peak") or {}

    if (last.get("sentiment") or "") == "negative":
        score -= 12
        notes.append("The conversation ended on a negative customer message.")
    if (last.get("sentiment") or "") == "positive":
        notes.append("The customer's final message was positive.")

    if int(peak.get("escalation_score") or 0) >= 50:
        score -= 8
        notes.append(
            "Escalation risk reached "
            f"{peak['escalation_score']}/100 during the conversation."
        )

    if status == "resolved":
        notes.append("The customer explicitly confirmed the fix.")
    elif status == "offered":
        notes.append(
            "The agent committed to a concrete next step and the customer "
            "did not contradict it."
        )
    elif status == "open":
        notes.append("No confirmation that the problem was fixed.")

    return {"score": clamp_score(score), "notes": notes}


def _communication_quality_score(analysis: Dict) -> Dict:
    """Average quality of the agent's replies (all four dimensions)."""
    statistics = analysis["statistics"]
    average = statistics.get("avg_response_quality")
    notes: List[str] = []

    if average is None:
        return {
            "score": 0,
            "notes": ["No agent reply was captured in this conversation."],
        }

    if statistics.get("below_bar_responses"):
        notes.append(
            f"{statistics['below_bar_responses']} of "
            f"{statistics['agent_messages']} replies fell below the "
            "quality bar."
        )

    weakest = None
    for name, value in (statistics.get("dimension_averages") or {}).items():
        if value is None:
            continue
        if weakest is None or value < weakest[1]:
            weakest = (name, value)
    if weakest and weakest[1] < 75:
        notes.append(f"Weakest dimension: {weakest[0]} ({weakest[1]}/100).")

    notes.append(f"Average response score {average}/100.")

    return {"score": clamp_score(average), "notes": notes}


def _sentiment_improvement_score(analysis: Dict) -> Dict:
    """How much did the customer's sentiment / frustration improve?"""
    first = analysis.get("first") or {}
    last = analysis.get("last") or {}

    start_frustration = first.get("frustration")
    end_frustration = last.get("frustration")

    if start_frustration is None or end_frustration is None:
        return {
            "score": 50,
            "notes": ["Not enough customer messages to measure the change."],
        }

    frustration_delta = int(end_frustration) - int(start_frustration)
    sentiment_delta = round(
        float(last.get("sentiment_score") or 0)
        - float(first.get("sentiment_score") or 0),
        3,
    )

    # -9 .. +9 frustration movement maps onto 0 .. 100 (a drop is good),
    # then the sentiment polarity move adjusts it further.
    score = 50 - frustration_delta * 5.5 + sentiment_delta * 22

    notes = [
        f"Frustration moved {start_frustration} -> {end_frustration} "
        f"({'+' if frustration_delta > 0 else ''}{frustration_delta}).",
        f"Sentiment polarity moved "
        f"{round(float(first.get('sentiment_score') or 0), 2)} -> "
        f"{round(float(last.get('sentiment_score') or 0), 2)} "
        f"({'+' if sentiment_delta > 0 else ''}{sentiment_delta}).",
    ]

    return {"score": clamp_score(score), "notes": notes}



def _guideline_adherence_score(analysis: Dict) -> Dict:
    """
    Guideline adherence: empathy / apology, acknowledgement, a concrete
    next step, professionalism and no stock non-answers.
    """
    turns = analysis.get("agent_turns") or []

    if not turns:
        return {
            "score": 0,
            "notes": ["No agent reply was captured in this conversation."],
        }

    total = len(turns)
    with_empathy = 0
    with_apology = 0
    with_ack = 0
    with_next_step = 0
    professional = 0
    stock = 0

    for turn in turns:
        reply = (turn.get("reply") or "").lower()
        if any(
            phrase in reply
            for phrase in ("i understand", "understand how", "appreciate")
        ):
            with_empathy += 1
        if any(
            phrase in reply
            for phrase in ("sorry", "apologise", "apologize", "my apologies")
        ):
            with_apology += 1
        if any(
            phrase in reply
            for phrase in ("you're right", "your frustration", "i can see")
        ):
            with_ack += 1
        if any(
            phrase in reply
            for phrase in (
                "i will", "i'll", "let me", "i have", "i've", "within",
                "in the next", "refund", "reset", "escalat", "replacement",
            )
        ):
            with_next_step += 1
        if turn.get("professionalism", 0) >= 75:
            professional += 1
        if any(phrase in reply for phrase in conversation_analysis.NON_ANSWERS):
            stock += 1

    score = (
        40
        + 18 * (with_empathy / total)
        + 12 * (with_apology / total)
        + 10 * (with_ack / total)
        + 12 * (with_next_step / total)
        + 8 * (professional / total)
    )

    if total == 1:
        # A single reply cannot demonstrate consistency; do not reward it
        # as if it were a full guideline-following conversation.
        score = min(score, 82)

    if stock:
        score -= 12 * (stock / total)

    notes = [
        f"Empathy language in {with_empathy}/{total} replies.",
        f"Apology present in {with_apology}/{total} replies.",
        f"Concrete next step promised in {with_next_step}/{total} replies.",
        f"Professional wording in {professional}/{total} replies.",
    ]
    if stock:
        notes.append(f"{stock} stock, non-answering repl(y/ies) detected.")

    return {"score": clamp_score(score), "notes": notes}


# ---------------------------------------------------------------------------
# Narrative building blocks
# ---------------------------------------------------------------------------
def _build_summary_text(analysis: Dict, meta: Optional[Dict] = None) -> str:
    statistics = analysis["statistics"]
    first = analysis.get("first") or {}
    last = analysis.get("last") or {}

    parts = [
        f"The customer raised {intent_label(analysis['primary_intent'])} "
        f"across {statistics['customer_messages']} message(s); the agent "
        f"replied {statistics['agent_messages']} time(s) over "
        f"{statistics['total_messages']} total messages."
    ]

    if first:
        parts.append(
            f"The conversation opened with the customer at "
            f"{first['frustration']}/10 frustration "
            f"({first['emotion']}, {first['sentiment']} sentiment)."
        )

    peak = analysis.get("peak")
    if peak and int(peak.get("escalation_score") or 0) >= 25:
        parts.append(
            f"Escalation risk peaked at {peak['escalation_score']}/100 "
            f"({peak['escalation_level']}) on turn {peak['turn']}."
        )
    elif peak:
        parts.append(
            f"Escalation risk stayed low (peak {peak['escalation_score']}/100)."
        )

    if last:
        parts.append(
            f"It closed with the customer at {last['frustration']}/10 "
            f"frustration ({last['emotion']}, {last['sentiment']} sentiment)."
        )

    parts.append(
        "Final resolution: "
        f"{RESOLUTION_LABELS.get(analysis['resolution']['status'], 'unknown')}"
        "."
    )

    if statistics.get("avg_response_quality") is not None:
        parts.append(
            f"Average agent response quality was "
            f"{statistics['avg_response_quality']}/100."
        )

    mode = (meta or {}).get("mode")
    if mode:
        parts.append(f"Interaction source: {mode} mode.")

    return " ".join(parts)



def _build_sentiment_timeline(analysis: Dict) -> List[Dict]:
    """One entry per customer message: the sentiment journey."""
    timeline: List[Dict] = []

    for index, entry in enumerate(analysis["timeline"]):
        if index == 0:
            note = "Opening message from the customer."
        elif entry["escalation_score"] > analysis["timeline"][index - 1][
            "escalation_score"
        ]:
            note = "Sentiment worsened - escalation risk increased."
        elif entry["escalation_score"] < analysis["timeline"][index - 1][
            "escalation_score"
        ]:
            note = "Sentiment recovered - escalation risk decreased."
        else:
            note = "Customer state stayed steady."

        timeline.append({
            "turn": entry["turn"],
            "label": entry["sentiment"],
            "sentiment_score": entry["sentiment_score"],
            "frustration": entry["frustration"],
            "emotion": entry["emotion"],
            "intent": entry["intent"],
            "intent_label": intent_label(entry["intent"]),
            "escalation_score": entry["escalation_score"],
            "escalation_level": entry["escalation_level"],
            "satisfaction_trend": entry["satisfaction_trend"],
            "message": entry["customer_message"],
            "note": note,
        })

    return timeline


def _build_sentiment_journey(analysis: Dict, timeline: List[Dict]) -> Dict:
    if not timeline:
        return {
            "start": None,
            "end": None,
            "direction": "unknown",
            "narrative": "No customer message was captured.",
        }

    start = timeline[0]
    end = timeline[-1]
    delta = end["frustration"] - start["frustration"]

    if delta <= -2 or (
        start["label"] != "positive" and end["label"] == "positive"
    ):
        direction = "improved"
    elif delta >= 2 or (
        start["label"] != "negative" and end["label"] == "negative"
    ):
        direction = "declined"
    else:
        direction = "steady"

    narrative_parts = [
        f"The customer started {start['label']} at "
        f"{start['frustration']}/10 frustration ({start['emotion']}) and "
        f"finished {end['label']} at {end['frustration']}/10 "
        f"({end['emotion']})."
    ]

    if direction == "improved":
        narrative_parts.append(
            "The agent's handling recovered the customer's sentiment."
        )
    elif direction == "declined":
        narrative_parts.append(
            "The customer became more frustrated as the conversation went on."
        )
    else:
        narrative_parts.append("The customer's sentiment stayed broadly level.")

    return {
        "start": {
            "label": start["label"],
            "frustration": start["frustration"],
            "emotion": start["emotion"],
        },
        "end": {
            "label": end["label"],
            "frustration": end["frustration"],
            "emotion": end["emotion"],
        },
        "delta_frustration": delta,
        "direction": direction,
        "narrative": " ".join(narrative_parts),
    }



def _build_strengths_and_weaknesses(analysis: Dict) -> Dict:
    """What the agent's replies did well and what needs work."""
    turns = analysis.get("agent_turns") or []
    statistics = analysis["statistics"]
    dimensions = statistics.get("dimension_averages") or {}

    strengths: List[Dict] = []
    weaknesses: List[Dict] = []

    if not turns:
        return {
            "strengths": [],
            "weaknesses": [{
                "title": "No agent reply captured",
                "detail": "The conversation contains no agent response, so "
                          "agent performance cannot be evaluated.",
            }],
        }

    if statistics.get("avg_response_quality") is not None:
        average = statistics["avg_response_quality"]
        if average >= 75:
            strengths.append({
                "title": "Consistently strong replies",
                "detail": f"Average response quality {average}/100 across "
                          f"{len(turns)} replies.",
            })
        elif average < 60:
            weaknesses.append({
                "title": "Low overall response quality",
                "detail": f"Average response quality is only {average}/100.",
            })

    for name, value in dimensions.items():
        if value is None:
            continue
        if value >= 80:
            strengths.append({
                "title": f"Strong {name}",
                "detail": f"{name.title()} scored {value}/100 on average.",
            })
        elif value < 65:
            weaknesses.append({
                "title": f"{name.title()} needs work",
                "detail": f"{name.title()} averaged only {value}/100.",
            })

    # Concrete evidence from the actual replies.
    for turn in turns:
        for issue in turn.get("issues", []):
            weaknesses.append({
                "title": f"Reply {turn['turn']} issue",
                "detail": f"{issue} Reply: \"{turn['reply'][:140]}\"",
            })

    if analysis["resolution"]["status"] == "resolved":
        strengths.append({
            "title": "Issue resolved",
            "detail": "The customer confirmed the problem was fixed.",
        })
    elif analysis["resolution"]["status"] == "offered":
        strengths.append({
            "title": "Clear commitment given",
            "detail": "The agent promised a concrete next step for the "
                      "customer.",
        })

    if not weaknesses:
        weaknesses.append({
            "title": "No material weaknesses found",
            "detail": "Every reply met the tone, clarity, empathy and "
                      "professionalism bar.",
        })

    if not strengths:
        strengths.append({
            "title": "Conversation handled",
            "detail": "The agent engaged with the customer's issue; see the "
                      "weaknesses below for the improvements.",
        })

    return {"strengths": strengths, "weaknesses": weaknesses}



def _build_coaching_recommendations(
    analysis: Dict, factors: Dict, journey: Dict
) -> List[Dict]:
    """Personalised, prioritised coaching for the next interaction."""
    recommendations: List[Dict] = []
    statistics = analysis["statistics"]
    dimensions = statistics.get("dimension_averages") or {}
    intent = analysis["primary_intent"]

    def add(priority: str, title: str, detail: str) -> None:
        recommendations.append({
            "priority": priority,
            "title": title,
            "detail": detail,
        })

    # 1. The weakest resolution-quality factor drives the first tip.
    weakest_factor = min(factors.items(), key=lambda item: item[1]["score"])
    if weakest_factor[1]["score"] < 70:
        add(
            "High",
            f"Improve {weakest_factor[0].replace('_', ' ')}",
            weakest_factor[1]["notes"][0]
            if weakest_factor[1]["notes"]
            else "This was the weakest part of the interaction.",
        )

    # 2. Dimension-specific coaching.
    if dimensions.get("empathy") is not None and dimensions["empathy"] < 75:
        add(
            "High",
            "Lead with empathy",
            "Open every reply by acknowledging the emotion before explaining "
            "anything: \"I completely understand how frustrating this must "
            "be.\"",
        )

    if dimensions.get("clarity") is not None and dimensions["clarity"] < 75:
        add(
            "Medium",
            "Make the next step explicit",
            "State exactly what happens next and when: \"I am refunding the "
            "duplicate charge now and you will see it within 24 hours.\"",
        )

    if (dimensions.get("tone") or 100) < 75:
        add(
            "Medium",
            "Match the customer's tone",
            "An upset customer needs a calmer, warmer register - avoid "
            "neutral or scripted phrasing.",
        )

    if (dimensions.get("professionalism") or 100) < 75:
        add(
            "Low",
            "Keep the wording professional",
            "Avoid casual abbreviations and exclamation marks in a support "
            "reply.",
        )

    # 3. Situational coaching from the escalation history.
    if statistics.get("peak_escalation_score", 0) >= 50:
        add(
            "High",
            "De-escalate earlier",
            "Escalation risk reached "
            f"{statistics['peak_escalation_score']}/100. Acknowledge the "
            "delay, apologise once, then give a concrete timeline - before "
            "the customer has to ask three times.",
        )

    if analysis["resolution"]["status"] in ("open", "unknown"):
        add(
            "High",
            "Close the loop",
            "The conversation ended without a confirmed resolution. Summarise "
            "what you did and confirm the customer can see the fix before "
            "closing.",
        )

    if intent == "payment_failure":
        add(
            "Medium",
            "Payment-specific handling",
            "Confirm whether the charge actually went through, mention the "
            "duplicate-charge guarantee and offer an alternative payment "
            "method.",
        )
    elif intent == "delayed_order":
        add(
            "Medium",
            "Delivery-specific handling",
            "Give the tracking status, a realistic new date and what happens "
            "if it does not arrive.",
        )

    # 4. Finish with the live coaching tips for the final state.
    last = analysis.get("last")
    if last:
        coaching = CoachingResponseAgent()
        for tip in coaching.generate_coaching_tips(
            intent=intent,
            sentiment=last["sentiment"],
            emotion_label=last["emotion"],
            frustration_score=last["frustration"],
            escalation_level=last["escalation_level"],
        )[:2]:
            add("Medium", "Coaching focus", tip)

    if journey["direction"] == "declined":
        add(
            "High",
            "Sentiment was declining",
            "The customer's sentiment got worse over the conversation. "
            "Re-read the last two exchanges and rehearse a de-escalating "
            "answer.",
        )

    # De-duplicate by title, keeping the highest priority.
    seen = {}
    for item in recommendations:
        seen.setdefault(item["title"], item)

    order = {"High": 0, "Medium": 1, "Low": 2}
    return sorted(seen.values(), key=lambda item: order.get(item["priority"], 3))



def quality_band(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 55:
        return "Fair"
    if score >= 40:
        return "Needs improvement"
    return "Poor"


def build_report(
    messages,
    meta: Optional[Dict] = None,
    session_key: str = "task8-summary",
) -> Dict:
    """
    Build the complete post-interaction report for one conversation.

    Parameters
    ----------
    messages:
        The finished conversation (``[{role, content}, ...]``).
    meta:
        Optional metadata from the recording (mode, persona, scenario,
        title, timestamps...).
    """
    meta = dict(meta or {})
    analysis = conversation_analysis.analyse_conversation(
        messages, session_key=session_key
    )

    if not analysis["timeline"]:
        raise ValueError(
            "This conversation has no customer message, so no report can be "
            "generated."
        )

    factors = {
        "issue_resolution": _issue_resolution_score(analysis),
        "communication_quality": _communication_quality_score(analysis),
        "sentiment_improvement": _sentiment_improvement_score(analysis),
        "guideline_adherence": _guideline_adherence_score(analysis),
    }

    overall = clamp_score(
        sum(
            QUALITY_WEIGHTS[name] * factors[name]["score"]
            for name in QUALITY_WEIGHTS
        )
    )

    sentence_timeline = _build_sentiment_timeline(analysis)
    journey = _build_sentiment_journey(analysis, sentence_timeline)
    strengths_weaknesses = _build_strengths_and_weaknesses(analysis)
    recommendations = _build_coaching_recommendations(
        analysis, factors, journey
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "session_key": session_key,
        "conversation_id": meta.get("id"),
        "title": meta.get("title") or "Support conversation",
        "mode": meta.get("mode"),
        "persona": meta.get("persona"),
        "scenario": meta.get("scenario"),
        "completed_at": meta.get("completed_at") or meta.get("created_at"),
        "summary": _build_summary_text(analysis, meta),
        "primary_issue": {
            "intent": analysis["primary_intent"],
            "label": intent_label(analysis["primary_intent"]),
            "intents_seen": [
                {"intent": intent, "label": intent_label(intent)}
                for intent in analysis["intents"]
            ],
            "evidence": (
                analysis["timeline"][0]["customer_message"]
                if analysis["timeline"] else ""
            ),
        },
        "final_resolution": {
            "status": analysis["resolution"]["status"],
            "label": RESOLUTION_LABELS.get(
                analysis["resolution"]["status"], "Unknown"
            ),
            "evidence": analysis["resolution"]["evidence"],
            "customer_confirmed": (
                analysis["resolution"]["status"] == "resolved"
            ),
            "agent_commitment_confirmed": (
                analysis["resolution"]["status"] == "offered"
            ),
        },
        "sentiment_timeline": sentence_timeline,
        "sentiment_journey": journey,
        "resolution_quality": {
            "score": overall,
            "band": quality_band(overall),
            "weights": QUALITY_WEIGHTS,
            "factors": factors,
        },
        "strengths": strengths_weaknesses["strengths"],
        "weaknesses": strengths_weaknesses["weaknesses"],
        "coaching_recommendations": recommendations,
        "statistics": analysis["statistics"],
        "escalation_triggers": analysis["escalation_triggers"],
        "risk_progression": [
            {
                "turn": entry["turn"],
                "label": f"#{entry['turn']}",
                "value": entry["escalation_score"],
                "level": entry["escalation_level"],
                "frustration": entry["frustration"],
                "sentiment": entry["sentiment"],
            }
            for entry in analysis["timeline"]
        ],
        "messages": analysis["messages"],
    }

