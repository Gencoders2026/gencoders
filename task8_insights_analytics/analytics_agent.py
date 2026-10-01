"""
Task 8 - Performance Analytics module.

Aggregates many customer-support sessions into the analytics the brief
asks for:

    * interaction + resolution trends across sessions
    * common escalation triggers and recurring customer issues
    * knowledge gaps and repeated knowledge-base searches
    * incorrect responses and unresolved queries
    * sentiment handling, response quality
    * resolution rate and escalation frequency
    * session-level + overall insights, charts and actionable
      recommendations

Data sources (real data first):

    1. conversations recorded by the Task 7 Live Support Console,
    2. the Task 3 Customer Simulator conversation logs (read-only),
    3. clearly-labelled demo conversations, used only when nothing has
       been recorded yet so the dashboard is never empty.

Every metric is computed from the conversations with the existing
Task 4/5/6 agents - nothing is hard-coded.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent

for _candidate in (
    str(_MODULE_DIR),
    str(_REPO_ROOT / "task7_live_support_console"),
    str(_REPO_ROOT / "task4_task5_task6_support_assist_agents"),
    str(_REPO_ROOT),
):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import conversation_analysis  # noqa: E402
import session_store  # noqa: E402
from analysis_core import detect_intent  # noqa: E402
from support_assist import clamp_score  # noqa: E402

# The knowledge-base lookup is cached per intent: the coverage of an intent
# does not change between sessions, so the RAG engine is only asked once.
_KNOWLEDGE_CACHE: Dict[str, Dict] = {}

INTENT_LABELS = {
    "refund_request": "Refund request",
    "delayed_order": "Delayed order",
    "payment_failure": "Payment failure",
    "account_issue": "Account access",
    "cancellation": "Cancellation",
    "general_inquiry": "General enquiry",
}

TRIGGER_LABELS = {
    "urgency_pressure": "Urgency / time pressure",
    "furious_customer": "Furious customer",
    "very_high_frustration": "Very high frustration",
    "elevated_frustration": "Elevated frustration",
    "mild_frustration": "Mild frustration",
    "negative_streak": "Repeated negative messages",
    "repeated_complaint": "Same complaint raised again",
    "supervisor_request": "Asked for a supervisor",
    "threat_to_leave": "Threat to leave / cancel",
    "urgent_unmet_demand": "Unmet urgent demand",
    "tone_holding_or_worsening": "Tone not improving",
    "unresolved_issue": "Issue still unresolved",
    "repeated_contact": "Contacted support before",
    "policy_frustration": "Frustration with policy",
}


def intent_label(intent: Optional[str]) -> str:
    return INTENT_LABELS.get(
        intent or "",
        (intent or "General enquiry").replace("_", " ").title(),
    )


def trigger_label(name: Optional[str]) -> str:
    return TRIGGER_LABELS.get(
        name or "",
        (name or "Trigger").replace("_", " ").title(),
    )


# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------
def load_conversations(
    limit: int = 40,
    include_demo: bool = True,
    simulator_limit: int = 25,
) -> List[Dict]:
    """
    Collect the conversations to analyse.

    Recorded Task 7 sessions come first (real data), then the Task 3
    simulator logs, then the labelled demo conversations, so the dashboard
    always has the multi-session history analytics needs.
    """
    records: List[Dict] = session_store.list_sessions(
        include_messages=True, include_demo=include_demo
    )
    seen_ids = {record["id"] for record in records}

    for conversation in session_store.list_simulator_conversations(
        limit=simulator_limit
    ):
        if conversation["id"] in seen_ids:
            continue
        records.append(conversation)
        seen_ids.add(conversation["id"])

    records = sorted(
        records,
        key=lambda record: (
            record.get("created_at") or "",
            record.get("id") or "",
        ),
        reverse=True,
    )

    if limit:
        records = records[: max(1, int(limit))]

    # oldest -> newest makes "trend over time" read naturally
    return list(reversed(records))


def knowledge_coverage(intent: str, query: str = "") -> Dict:
    """
    Does the knowledge base have anything for this intent?

    Cached per intent (the answer cannot change between sessions) so the
    analytics stay fast even with many conversations.
    """
    key = intent or "general_inquiry"

    if key in _KNOWLEDGE_CACHE:
        return _KNOWLEDGE_CACHE[key]

    result = {
        "intent": key,
        "label": intent_label(key),
        "retrieved": 0,
        "sources": [],
        "available": False,
        "gap": False,
    }

    try:
        from knowledge_bridge import knowledge_status, search_knowledge

        status = knowledge_status()
        result["available"] = bool(status.get("available"))

        probe = query or f"{intent_label(key)} support help"
        hits = search_knowledge(probe, top_k=3, intent=key) or []
        result["retrieved"] = len(hits)
        result["sources"] = sorted({
            str((hit.get("metadata") or {}).get("source"))
            for hit in hits
            if (hit.get("metadata") or {}).get("source")
        })
        result["gap"] = bool(result["available"]) and not hits
    except Exception:  # pragma: no cover - knowledge engine unavailable
        result["available"] = False

    _KNOWLEDGE_CACHE[key] = result
    return result



# ---------------------------------------------------------------------------
# Session-level insight
# ---------------------------------------------------------------------------
def agent_turn_findings(messages, session_id: str) -> List[Dict]:
    """The weak / incorrect replies of one conversation, ready to display."""
    analysis = conversation_analysis.analyse_conversation(
        messages, session_key=f"t8-weak-{session_id}"
    )
    findings: List[Dict] = []

    for turn in analysis.get("agent_turns") or []:
        if not turn["below_bar"]:
            continue
        findings.append({
            "session_id": session_id,
            "turn": turn["turn"],
            "reply": turn["reply"],
            "quality": turn["overall"],
            "issues": turn["issues"],
            "intent": turn.get("responding_to_intent"),
        })

    return findings


def _sentiment_handling(start, end, frustration_start, frustration_end) -> str:
    """Did the agent's handling improve, hold or worsen the sentiment?"""
    if not start or not end:
        return "unknown"

    rank = {"negative": 0, "neutral": 1, "positive": 2}
    change = rank.get(end, 1) - rank.get(start, 1)

    if change > 0:
        return "improved"
    if change < 0:
        return "declined"

    if frustration_start is not None and frustration_end is not None:
        if int(frustration_end) < int(frustration_start):
            return "improved"
        if int(frustration_end) > int(frustration_start):
            return "declined"

    return "steady"


def session_insight(record: Dict) -> Dict:
    """Analyse one conversation into a row of analytics facts."""
    messages = record.get("messages") or []
    analysis = conversation_analysis.analyse_conversation(
        messages, session_key=f"t8-{record.get('id')}"
    )

    statistics = analysis["statistics"]
    timeline = analysis["timeline"]
    primary = analysis["primary_intent"]
    coverage = knowledge_coverage(primary)
    resolution_status = analysis["resolution"]["status"]

    searched = record.get("knowledge_searches") or []

    return {
        "id": record.get("id"),
        "title": record.get("title"),
        "mode": record.get("mode"),
        "created_at": record.get("created_at"),
        "persona": record.get("persona"),
        "scenario": record.get("scenario"),
        "is_demo": bool(record.get("is_demo")),
        "primary_issue": primary,
        "primary_issue_label": intent_label(primary),
        "intents": analysis["intents"],
        "turns": statistics["customer_messages"],
        "messages": statistics["total_messages"],
        "resolution_status": resolution_status,
        "resolved": resolution_status in ("resolved", "offered"),
        "confirmed_resolved": resolution_status == "resolved",
        "unresolved": resolution_status in ("open", "unknown"),
        "peak_escalation_score": statistics["peak_escalation_score"],
        "peak_escalation_level": statistics["peak_escalation_level"],
        "escalated": statistics["peak_escalation_score"] >= 50,
        "alerts_triggered": statistics["alerts_triggered"],
        "frustration_start": statistics["frustration_start"],
        "frustration_end": statistics["frustration_end"],
        "sentiment_start": statistics["sentiment_start"],
        "sentiment_end": statistics["sentiment_end"],
        "sentiment_handling": _sentiment_handling(
            statistics["sentiment_start"],
            statistics["sentiment_end"],
            statistics["frustration_start"],
            statistics["frustration_end"],
        ),
        "response_quality": statistics["avg_response_quality"],
        "dimension_averages": statistics["dimension_averages"],
        "below_bar_responses": statistics["below_bar_responses"],
        "escalation_triggers": analysis["escalation_triggers"],
        "trigger_points": analysis["trigger_points"],
        "knowledge_coverage": coverage,
        "knowledge_searches": len(searched),
        "knowledge_searches_empty": sum(
            1 for item in searched if int(item.get("results") or 0) == 0
        ),
        "last_customer_message": (
            timeline[-1]["customer_message"] if timeline else ""
        ),
        "timeline": timeline,
    }



# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def _mean(values):
    clean = [value for value in values if value is not None]
    return round(sum(clean) / len(clean), 1) if clean else None


def _rate(part: int, whole: int) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


def _buckets(items: List[Dict], count: int = 4) -> List[List[Dict]]:
    """Split a session list into up to ``count`` even time buckets."""
    if not items:
        return []
    size = max(1, len(items) // count)
    buckets = [
        items[index:index + size]
        for index in range(0, len(items), size)
    ]

    # keep at most `count` buckets, merging the tail into the last one
    while len(buckets) > count:
        buckets[-2].extend(buckets[-1])
        buckets.pop()

    return buckets


def build_analytics(
    limit: int = 40,
    include_demo: bool = True,
    simulator_limit: int = 25,
) -> Dict:
    """Full performance-analytics payload for the dashboard."""
    records = load_conversations(
        limit=limit,
        include_demo=include_demo,
        simulator_limit=simulator_limit,
    )

    insights: List[Dict] = []
    weak_responses: List[Dict] = []
    repeated_searches: Counter = Counter()
    search_topics: Counter = Counter()
    topic_sessions: Dict[str, set] = {}
    search_sources: Dict[str, set] = {}

    for record in records:
        insight = session_insight(record)
        insights.append(insight)
        weak_responses.extend(
            agent_turn_findings(record.get("messages"), record.get("id"))
        )

        for search in record.get("knowledge_searches") or []:
            query = str(search.get("query") or "").strip()
            if not query:
                continue
            normalised = re.sub(r"[^a-z0-9 ]+", "", query.lower())
            normalised = re.sub(r"\s+", " ", normalised).strip()
            repeated_searches[normalised] += 1
            search_sources.setdefault(normalised, set()).update(
                search.get("sources") or []
            )

            # The knowledge base is usually searched again for the same
            # TOPIC (even when the wording differs), so the topic is
            # tracked too - it is what reveals a systemic knowledge need.
            topic = detect_intent(normalised) or "general_inquiry"
            search_topics[topic] += 1
            topic_sessions.setdefault(topic, set()).add(record.get("id"))

    return _assemble(
        records,
        insights,
        weak_responses,
        repeated_searches,
        search_sources,
        search_topics,
        topic_sessions,
    )



def _assemble(
    records,
    insights,
    weak_responses,
    repeated_searches,
    search_sources,
    search_topics=None,
    topic_sessions=None,
) -> Dict:
    search_topics = search_topics or Counter()
    topic_sessions = topic_sessions or {}
    total = len(insights)

    # ---- headline metrics ----
    resolved = sum(1 for item in insights if item["resolved"])
    confirmed = sum(1 for item in insights if item["confirmed_resolved"])
    escalated = sum(1 for item in insights if item["escalated"])
    unresolved = [item for item in insights if item["unresolved"]]

    response_quality = _mean([item["response_quality"] for item in insights])
    dimension_averages = {}
    for dimension in ("tone", "clarity", "empathy", "professionalism"):
        dimension_averages[dimension] = _mean([
            (item["dimension_averages"] or {}).get(dimension)
            for item in insights
        ])

    sentiment_handling = Counter(item["sentiment_handling"] for item in insights)
    frustration_start = _mean([item["frustration_start"] for item in insights])
    frustration_end = _mean([item["frustration_end"] for item in insights])

    # ---- issue + trigger distribution ----
    issue_counter = Counter(item["primary_issue"] for item in insights)
    trigger_counter: Counter = Counter()
    trigger_points: Counter = Counter()
    trigger_sessions: Dict[str, set] = {}
    for item in insights:
        for name, count in (item["escalation_triggers"] or {}).items():
            trigger_counter[name] += count
            trigger_sessions.setdefault(name, set()).add(item["id"])
        for name, points in (item["trigger_points"] or {}).items():
            trigger_points[name] += points

    # ---- knowledge gaps + repeated searches ----
    coverage_by_intent: Dict[str, Dict] = {}
    for item in insights:
        coverage = item["knowledge_coverage"]
        coverage_by_intent[coverage["intent"]] = coverage

    knowledge_gaps = [
        {
            "intent": coverage["intent"],
            "label": coverage["label"],
            "sessions": issue_counter.get(coverage["intent"], 0),
            "retrieved": coverage["retrieved"],
            "sources": coverage.get("sources") or [],
            "available": coverage.get("available", False),
            "gap": bool(coverage["gap"]),
            "detail": (
                "No knowledge-base article matched this issue type, so "
                "agents had to rely on memory."
                if coverage["gap"]
                else f"Only {coverage['retrieved']} article(s) available - "
                     "coverage is thin."
            ),
        }
        for coverage in coverage_by_intent.values()
        if coverage["gap"] or coverage["retrieved"] <= 1
    ]
    knowledge_gaps.sort(key=lambda item: item["sessions"], reverse=True)

    repeated = [
        {
            "query": query,
            "searches": count,
            "sources": sorted(search_sources.get(query) or []),
        }
        for query, count in repeated_searches.items()
        if count >= 2
    ]
    repeated.sort(key=lambda item: item["searches"], reverse=True)

    repeated_topics = [
        {
            "intent": topic,
            "label": intent_label(topic),
            "searches": count,
            "sessions": len(topic_sessions.get(topic) or []),
            "detail": (
                "The knowledge base was searched "
                f"{count} time(s) across "
                f"{len(topic_sessions.get(topic) or [])} conversation(s) for "
                "this topic."
            ),
        }
        for topic, count in search_topics.most_common()
        if count >= 2
    ]

    empty_searches = sum(
        item["knowledge_searches_empty"] for item in insights
    )

    # ---- trends ----
    interaction_trend = []
    resolution_trend = []
    for index, bucket in enumerate(_buckets(insights, 4), start=1):
        bucket_resolved = sum(1 for item in bucket if item["resolved"])
        bucket_escalated = sum(1 for item in bucket if item["escalated"])
        label = f"Block {index}"
        interaction_trend.append({
            "label": label,
            "sessions": len(bucket),
            "avg_turns": _mean([item["turns"] for item in bucket]),
            "avg_quality": _mean([item["response_quality"] for item in bucket]),
        })
        resolution_trend.append({
            "label": label,
            "resolution_rate": _rate(bucket_resolved, len(bucket)),
            "escalation_rate": _rate(bucket_escalated, len(bucket)),
            "avg_quality": _mean([item["response_quality"] for item in bucket]),
        })

    # ---- frustration curve (average per customer turn) ----
    max_turns = max((len(item["timeline"]) for item in insights), default=0)
    frustration_curve = []
    for turn in range(1, min(max_turns, 8) + 1):
        values = [
            item["timeline"][turn - 1]["frustration"]
            for item in insights
            if len(item["timeline"]) >= turn
        ]
        if values:
            frustration_curve.append({
                "label": f"#{turn}",
                "value": round(sum(values) / len(values), 1),
            })



    # ---- session rows (timeline stripped - it is already in the charts) ----
    session_rows = [
        {key: value for key, value in item.items() if key != "timeline"}
        for item in insights
    ]
    session_rows_newest = list(reversed(session_rows))

    # ---- overall insights ----
    overall_insights: List[str] = []

    overall_insights.append(
        f"{total} conversation(s) analysed: {resolved} reached a resolution "
        f"({_rate(resolved, total)}%), {confirmed} were confirmed by the "
        f"customer, and {len(unresolved)} ended unresolved."
    )
    overall_insights.append(
        f"Escalation risk crossed the High band in {escalated} session(s) "
        f"({_rate(escalated, total)}%)."
    )
    if response_quality is not None:
        overall_insights.append(
            f"Average agent response quality is {response_quality}/100 "
            f"(tone {dimension_averages.get('tone')}, clarity "
            f"{dimension_averages.get('clarity')}, empathy "
            f"{dimension_averages.get('empathy')}, professionalism "
            f"{dimension_averages.get('professionalism')})."
        )
    overall_insights.append(
        f"Customer sentiment improved in {sentiment_handling.get('improved', 0)} "
        f"session(s), stayed steady in {sentiment_handling.get('steady', 0)} "
        f"and worsened in {sentiment_handling.get('declined', 0)}."
    )
    if frustration_start is not None and frustration_end is not None:
        overall_insights.append(
            f"Average frustration moved {frustration_start} -> "
            f"{frustration_end} (out of 10) between the first and last "
            "customer message."
        )
    if issue_counter:
        top_issue, top_count = issue_counter.most_common(1)[0]
        overall_insights.append(
            f"Most common customer issue: {intent_label(top_issue)} "
            f"({top_count} session(s))."
        )
    if trigger_counter:
        top_trigger, trigger_count = trigger_counter.most_common(1)[0]
        overall_insights.append(
            f"Most common escalation trigger: {trigger_label(top_trigger)} "
            f"({trigger_count} occurrence(s))."
        )
    overall_insights.append(
        f"{len(weak_responses)} reply/replies fell below the response quality "
        "bar across all sessions."
        if weak_responses
        else "No reply fell below the response quality bar."
    )



    # ---- actionable recommendations ----
    recommendations: List[Dict] = []

    def recommend(priority: str, title: str, detail: str, metric=None) -> None:
        recommendations.append({
            "priority": priority,
            "title": title,
            "detail": detail,
            "metric": metric,
        })

    resolution_rate = _rate(resolved, total)
    escalation_rate = _rate(escalated, total)

    if total and resolution_rate < 70:
        recommend(
            "High",
            "Raise the resolution rate",
            f"Only {resolution_rate}% of sessions reached a resolution. Have "
            "agents confirm the fix with the customer before closing the "
            "conversation.",
            {"resolution_rate": resolution_rate},
        )

    if escalation_rate >= 25:
        top_trigger_label = (
            trigger_label(trigger_counter.most_common(1)[0][0])
            if trigger_counter else "n/a"
        )
        recommend(
            "High",
            "Attack the top escalation trigger",
            f"Escalation reached the High band in {escalation_rate}% of "
            f"sessions. Most common trigger: {top_trigger_label}. Coach "
            "agents to acknowledge the delay and give a concrete timeline in "
            "the first reply.",
            {"escalation_rate": escalation_rate},
        )

    empathy = dimension_averages.get("empathy")
    if empathy is not None and empathy < 78:
        recommend(
            "High",
            "Strengthen empathy in replies",
            f"Empathy averages {empathy}/100 - the weakest dimension. Open "
            "with a short acknowledgement (\"I understand how frustrating "
            "this must be\") before any explanation.",
            {"empathy": empathy},
        )

    clarity = dimension_averages.get("clarity")
    if clarity is not None and clarity < 78:
        recommend(
            "Medium",
            "Make replies more actionable",
            f"Clarity averages {clarity}/100. Always state the next step and "
            "its timeframe explicitly.",
            {"clarity": clarity},
        )

    if unresolved:
        recommend(
            "High",
            "Follow up on unresolved queries",
            f"{len(unresolved)} conversation(s) ended without a resolution: "
            + ", ".join(
                f"{item['primary_issue_label']} ({item['id']})"
                for item in unresolved[:3]
            )
            + ".",
            {"unresolved_sessions": len(unresolved)},
        )

    if knowledge_gaps:
        recommend(
            "Medium",
            "Close the knowledge gaps",
            "Add knowledge-base articles for: "
            + ", ".join(gap["label"] for gap in knowledge_gaps[:3])
            + ".",
            {"gap_count": len(knowledge_gaps)},
        )

    if repeated or repeated_topics:
        top_topic = (
            repeated_topics[0]["label"] if repeated_topics
            else repeated[0]["query"][:60]
        )
        recommend(
            "Medium",
            "Reduce repeated knowledge searches",
            f"{len(repeated)} identical question(s) and "
            f"{len(repeated_topics)} repeated topic(s) were searched more "
            f"than once (top: \"{top_topic}\"). Link those articles into the "
            "answer templates.",
            {
                "repeated_searches": len(repeated),
                "repeated_topics": len(repeated_topics),
            },
        )

    if empty_searches:
        recommend(
            "Medium",
            "Fix knowledge searches that returned nothing",
            f"{empty_searches} knowledge search(es) returned no result. "
            "Check the index and the article keywords.",
            {"empty_searches": empty_searches},
        )

    if weak_responses:
        recommend(
            "High",
            "Coach the weakest replies",
            f"{len(weak_responses)} reply/replies were below the quality bar. "
            "Review the flagged replies in the table below with each agent.",
            {"weak_responses": len(weak_responses)},
        )

    if total and not recommendations:
        recommend(
            "Low",
            "Maintain the standard",
            "No systemic issue was detected. Keep sampling conversations to "
            "confirm the trend.",
        )


    # ---- payload ----
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "data_sources": {
            "recorded_conversations": sum(
                1 for item in insights
                if not item["is_demo"] and item["mode"] != "simulator"
            ),
            "simulator_conversations": sum(
                1 for item in insights if item["mode"] == "simulator"
            ),
            "demo_conversations": sum(
                1 for item in insights if item["is_demo"]
            ),
            "total_analysed": total,
            "note": (
                "Recorded conversations come from the Task 7 Live Support "
                "Console, simulator conversations from the Task 3 logs, and "
                "demo conversations are clearly-labelled realistic test data "
                "used only to keep the dashboard populated."
            ),
        },
        "summary": {
            "sessions_analysed": total,
            "resolved_sessions": resolved,
            "confirmed_resolved_sessions": confirmed,
            "unresolved_sessions": len(unresolved),
            "resolution_rate": resolution_rate,
            "confirmed_resolution_rate": _rate(confirmed, total),
            "escalated_sessions": escalated,
            "escalation_frequency": escalation_rate,
            "avg_response_quality": response_quality,
            "dimension_averages": dimension_averages,
            "avg_turns": _mean([item["turns"] for item in insights]),
            "frustration_start": frustration_start,
            "frustration_end": frustration_end,
            "sentiment_improved": sentiment_handling.get("improved", 0),
            "sentiment_steady": sentiment_handling.get("steady", 0),
            "sentiment_declined": sentiment_handling.get("declined", 0),
            "weak_responses": len(weak_responses),
            "knowledge_searches": sum(
                item["knowledge_searches"] for item in insights
            ),
            "empty_knowledge_searches": empty_searches,
        },
        "charts": {
            "interaction_trend": interaction_trend,
            "resolution_trend": resolution_trend,
            "frustration_curve": frustration_curve,
            "issue_distribution": [
                {
                    "label": intent_label(intent),
                    "value": count,
                    "intent": intent,
                }
                for intent, count in issue_counter.most_common()
            ],
            "escalation_triggers": [
                {
                    "label": trigger_label(name),
                    "value": count,
                    "sessions": len(trigger_sessions.get(name) or []),
                    "points": trigger_points.get(name, 0),
                }
                for name, count in trigger_counter.most_common(8)
            ],
            "sentiment_flow": [
                {
                    "label": "Improved",
                    "value": sentiment_handling.get("improved", 0),
                },
                {
                    "label": "Steady",
                    "value": sentiment_handling.get("steady", 0),
                },
                {
                    "label": "Declined",
                    "value": sentiment_handling.get("declined", 0),
                },
            ],
            "resolution_breakdown": [
                {
                    "label": label,
                    "value": sum(
                        1 for item in insights
                        if item["resolution_status"] == status
                    ),
                }
                for status, label in (
                    ("resolved", "Confirmed resolved"),
                    ("offered", "Solution offered"),
                    ("open", "Still open"),
                    ("unknown", "Unclear"),
                )
            ],
            "response_quality": [
                {"label": name.title(), "value": value or 0}
                for name, value in dimension_averages.items()
            ],
            "knowledge_coverage": [
                {
                    "label": coverage["label"],
                    "value": coverage["retrieved"],
                    "gap": coverage["gap"],
                    "sessions": issue_counter.get(coverage["intent"], 0),
                }
                for coverage in sorted(
                    coverage_by_intent.values(),
                    key=lambda entry: issue_counter.get(entry["intent"], 0),
                    reverse=True,
                )
            ],
        },
        "issues": [
            {
                "intent": intent,
                "label": intent_label(intent),
                "sessions": count,
                "rate": _rate(count, total),
            }
            for intent, count in issue_counter.most_common()
        ],
        "recurring_issues": [
            {
                "intent": intent,
                "label": intent_label(intent),
                "sessions": count,
                "detail": (
                    "Raised in "
                    f"{_rate(count, total)}% of the analysed conversations."
                ),
            }
            for intent, count in issue_counter.most_common(5)
            if count >= 2
        ],
        "knowledge_gaps": knowledge_gaps,
        "repeated_searches": repeated,
        "repeated_search_topics": repeated_topics,
        "incorrect_responses": sorted(
            weak_responses, key=lambda item: item["quality"]
        )[:15],
        "unresolved_queries": [
            {
                "id": item["id"],
                "title": item["title"],
                "mode": item["mode"],
                "issue": item["primary_issue_label"],
                "status": item["resolution_status"],
                "turns": item["turns"],
                "peak_escalation_score": item["peak_escalation_score"],
                "last_customer_message": item["last_customer_message"],
            }
            for item in unresolved
        ],
        "session_insights": session_rows_newest,
        "overall_insights": overall_insights,
        "recommendations": recommendations,
    }

