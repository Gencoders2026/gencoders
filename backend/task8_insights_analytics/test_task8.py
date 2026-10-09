"""
Task 8 - Insights & Performance Analytics test suite.

Covers both required deliverables end to end:

* Post-Interaction Summary Agent - a structured report for ONE conversation
  (resolution quality + weighted factors, statistics, sentiment timeline and
  journey, escalation triggers, strengths/weaknesses, prioritised coaching
  recommendations, overall summary text).
* Performance Analytics - multi-session aggregation: resolution and
  escalation frequency, response quality, customer sentiment, recurring
  issues, knowledge coverage / gaps, repeated searches, incorrect
  responses, unresolved queries, charts, insights and recommendations.

Demo conversations are always labelled (is_demo = True) and reported
separately from real data.

Run with:

    python -m pytest task8_insights_analytics/test_task8.py -v
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

for candidate in (
    str(HERE),
    str(REPO_ROOT / "task7_live_support_console"),
    str(REPO_ROOT / "task4_task5_task6_support_assist_agents"),
):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import insights_api  # noqa: E402
import session_store  # noqa: E402

# A short, complete conversation with agent replies - used for the
# deterministic inline-summary tests (no store dependency).
INLINE_CONVERSATION = [
    {
        "role": "customer",
        "content": "My payment failed and I have been trying for two hours.",
    },
    {
        "role": "agent",
        "content": (
            "I am really sorry about that. Let me check the transaction "
            "right away."
        ),
    },
    {
        "role": "customer",
        "content": "Thank you - I need this fixed today, it is urgent.",
    },
    {
        "role": "agent",
        "content": (
            "I have reprocessed the payment and it has now gone through. "
            "Could you confirm on your side?"
        ),
    },
    {
        "role": "customer",
        "content": "Great, the payment went through. The issue is resolved, thank you.",
    },
]

TEST_SESSION_ID = "conv-pytest-task8"
TEST_SESSION_TITLE = "pytest task8 summary session"

REQUIRED_CHART_KEYS = [
    "interaction_trend",
    "resolution_trend",
    "frustration_curve",
    "issue_distribution",
    "escalation_triggers",
    "sentiment_flow",
    "resolution_breakdown",
    "response_quality",
    "knowledge_coverage",
]

REQUIRED_ANALYTICS_KEYS = [
    "summary",
    "charts",
    "issues",
    "recurring_issues",
    "knowledge_gaps",
    "repeated_searches",
    "repeated_search_topics",
    "incorrect_responses",
    "unresolved_queries",
    "session_insights",
    "overall_insights",
    "recommendations",
    "data_sources",
]

REQUIRED_SUMMARY_KEYS = [
    "summary",
    "resolution_quality",
    "statistics",
    "sentiment_timeline",
    "sentiment_journey",
    "risk_progression",
    "escalation_triggers",
    "final_resolution",
    "strengths",
    "weaknesses",
    "coaching_recommendations",
]


@pytest.fixture(scope="module")
def client():
    application = insights_api.create_app()
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture()
def recorded_session():
    """Persist one test conversation and remove it afterwards."""
    record = session_store.record_session({
        "id": TEST_SESSION_ID,
        "title": TEST_SESSION_TITLE,
        "mode": "replay",
        "persona": "Impatient buyer",
        "scenario": "failed_payment",
        "messages": INLINE_CONVERSATION,
        "knowledge_searches": [
            {"turn": 1, "query": "payment failed", "results": 2,
             "sources": ["payments-policy.pdf"]},
        ],
        "is_demo": False,
    })
    yield record
    session_store.delete_session(TEST_SESSION_ID)


# ===========================================================================
# 1. HEALTH + CONVERSATION PICKER
# ===========================================================================
class TestHealth:
    def test_health_reports_ok(self, client):
        response = client.get("/task8/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["service"] == "task8-insights-analytics"
        assert payload["recorded_conversations"] >= 0
        assert payload["simulator_conversations_available"] >= 0
        assert payload["demo_conversations_available"] >= 0


class TestConversationList:
    def test_lists_conversations_with_source_and_demo_flag(self, client):
        response = client.get("/task8/conversations")
        assert response.status_code == 200
        payload = response.json()
        # `count` is how many conversations exist in total; `conversations`
        # is the page (capped by `limit`).
        assert payload["count"] >= len(payload["conversations"])
        for conversation in payload["conversations"]:
            assert conversation["source"] in {"recorded", "simulator"}
            assert isinstance(conversation["is_demo"], bool)
            assert conversation["id"]

    def test_demo_sessions_are_labelled(self, client):
        # The demo seeder keeps a labelled set in the Task 7 store.
        client.post("/task8/demo-data")
        response = client.get(
            "/task8/conversations?include_demo=true&limit=200"
        )
        conversations = response.json()["conversations"]
        demo = [c for c in conversations if c["is_demo"]]
        real = [c for c in conversations if not c["is_demo"]]
        assert len(demo) >= 1, "demo conversations should be available"
        assert len(real) >= 1, "real conversations should also be listed"

    def test_demo_sessions_can_be_excluded(self, client):
        response = client.get("/task8/conversations?include_demo=false")
        conversations = response.json()["conversations"]
        assert all(not c["is_demo"] for c in conversations)


# ===========================================================================
# 2. POST-INTERACTION SUMMARY
# ===========================================================================
class TestSummaryInlineMessages:
    """Summary built from an inline message list (no store dependency)."""

    @pytest.fixture(scope="class")
    def report(self, client):
        response = client.post(
            "/task8/summary",
            json={
                "messages": INLINE_CONVERSATION,
                "meta": {"id": "inline-test", "title": "inline conversation"},
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    def test_response_labels_the_conversation(self, report):
        assert report["conversation_id"] == "inline-test"
        assert report["title"] == "inline conversation"
        assert report["generated_at"]
        assert report["session_key"]

    def test_overall_summary_is_present(self, report):
        assert isinstance(report["summary"], str)
        assert len(report["summary"]) > 40

    def test_resolution_quality_shape(self, report):
        quality = report["resolution_quality"]
        assert 0 <= quality["score"] <= 100
        assert isinstance(quality["band"], str) and quality["band"]
        assert set(quality["factors"]) == {
            "issue_resolution",
            "communication_quality",
            "sentiment_improvement",
            "guideline_adherence",
        }
        for factor in quality["factors"].values():
            assert 0 <= factor["score"] <= 100
        weights = quality["weights"]
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_statistics_count_messages(self, report):
        stats = report["statistics"]
        assert stats["total_messages"] == len(INLINE_CONVERSATION)
        assert stats["customer_messages"] == 3
        assert stats["agent_messages"] == 2
        assert "dimension_averages" in stats

    def test_sentiment_timeline_has_one_point_per_customer_message(self, report):
        timeline = report["sentiment_timeline"]
        assert len(timeline) == 3
        for point in timeline:
            assert 0 <= point["frustration"] <= 10
            assert point["label"] in {"positive", "neutral", "negative"}
            assert point["escalation_level"] in {"Low", "Medium", "High", "Critical"}

    def test_sentiment_journey_has_narrative(self, report):
        journey = report["sentiment_journey"]
        assert journey["direction"] in {"improved", "steady", "declined"}
        assert isinstance(journey["narrative"], str)
        assert journey["delta_frustration"] == (
            journey["end"]["frustration"] - journey["start"]["frustration"]
        )

    def test_risk_progression_follows_the_messages(self, report):
        assert len(report["risk_progression"]) == 3
        for point in report["risk_progression"]:
            assert 0 <= point["value"] <= 100

    def test_final_resolution_detects_confirmation(self, report):
        resolution = report["final_resolution"]
        assert resolution["status"] in {"resolved", "offered", "open", "unknown"}
        assert resolution["label"]
        # The last customer message confirms the fix, so the report must
        # show a customer-confirmed resolution.
        assert resolution["status"] == "resolved"
        assert resolution["customer_confirmed"] is True

    def test_coaching_recommendations_are_prioritised(self, report):
        recommendations = report["coaching_recommendations"]
        assert len(recommendations) >= 1
        for recommendation in recommendations:
            assert recommendation["priority"] in {"High", "Medium", "Low"}
            assert recommendation["title"]
            assert recommendation["detail"]

    def test_strengths_and_weaknesses_are_lists(self, report):
        assert isinstance(report["strengths"], list)
        assert isinstance(report["weaknesses"], list)


class TestSummaryFromStore:
    def test_summary_for_recorded_conversation(self, client, recorded_session):
        response = client.post(
            "/task8/summary", json={"conversation_id": TEST_SESSION_ID}
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["conversation_id"] == TEST_SESSION_ID
        assert payload["title"] == TEST_SESSION_TITLE
        for key in REQUIRED_SUMMARY_KEYS:
            assert key in payload

    def test_unknown_conversation_returns_404(self, client):
        response = client.post(
            "/task8/summary", json={"conversation_id": "conv-does-not-exist"}
        )
        assert response.status_code == 404

    def test_missing_source_returns_422(self, client):
        response = client.post("/task8/summary", json={})
        assert response.status_code == 422

    def test_empty_message_list_returns_422(self, client):
        response = client.post("/task8/summary", json={"messages": []})
        assert response.status_code == 422

    def test_summary_for_simulator_conversation(self, client):
        available = client.get("/task8/conversations").json()["conversations"]
        simulator = [c for c in available if c["source"] == "simulator"]
        if not simulator:
            pytest.skip("no Task 3 simulator logs available")
        response = client.post(
            "/task8/summary",
            json={"simulator_session_id": simulator[0]["id"]},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        for key in REQUIRED_SUMMARY_KEYS:
            assert key in payload



# ===========================================================================
# 3. PERFORMANCE ANALYTICS (multi-session)
# ===========================================================================
class TestAnalytics:
    @pytest.fixture(scope="class")
    def analytics(self, client):
        # Make sure there is at least one labelled demo set to aggregate.
        client.post("/task8/demo-data")
        response = client.get(
            "/task8/analytics?limit=15&simulator_limit=10&include_demo=true"
        )
        assert response.status_code == 200, response.text
        return response.json()

    def test_all_required_sections_are_present(self, analytics):
        for key in REQUIRED_ANALYTICS_KEYS:
            assert key in analytics, f"missing analytics section: {key}"
        assert analytics["generated_at"]

    def test_summary_metrics_are_present(self, analytics):
        summary = analytics["summary"]
        for key in (
            "sessions_analysed",
            "resolved_sessions",
            "unresolved_sessions",
            "resolution_rate",
            "escalated_sessions",
            "escalation_frequency",
            "avg_response_quality",
            "frustration_start",
            "frustration_end",
            "sentiment_improved",
            "sentiment_steady",
            "sentiment_declined",
        ):
            assert key in summary, f"missing summary metric: {key}"
        assert summary["sessions_analysed"] >= 1
        assert 0 <= summary["resolution_rate"] <= 100
        assert 0 <= summary["escalation_frequency"] <= 100
        assert 0 <= summary["avg_response_quality"] <= 100
        assert (
            summary["sentiment_improved"]
            + summary["sentiment_steady"]
            + summary["sentiment_declined"]
            == summary["sessions_analysed"]
        )

    def test_resolution_and_escalation_split_matches_total(self, analytics):
        summary = analytics["summary"]
        assert (
            summary["resolved_sessions"] + summary["unresolved_sessions"]
            == summary["sessions_analysed"]
        )

    def test_charts_cover_every_required_visualisation(self, analytics):
        for key in REQUIRED_CHART_KEYS:
            assert key in analytics["charts"], f"missing chart: {key}"

    def test_issue_distribution_rates_sum_up(self, analytics):
        issues = analytics["issues"]
        assert len(issues) >= 1
        total = sum(issue["rate"] for issue in issues)
        assert 95 <= total <= 105  # rounded to whole percents
        for issue in issues:
            assert issue["label"]
            assert issue["sessions"] >= 1

    def test_escalation_trigger_counts(self, analytics):
        triggers = analytics["charts"]["escalation_triggers"]
        assert isinstance(triggers, list)
        for trigger in triggers:
            assert trigger["value"] > 0

    def test_knowledge_section_has_coverage_and_gaps(self, analytics):
        assert isinstance(analytics["knowledge_gaps"], list)
        assert isinstance(analytics["repeated_searches"], list)
        assert isinstance(analytics["repeated_search_topics"], list)
        assert isinstance(analytics["incorrect_responses"], list)
        assert isinstance(analytics["unresolved_queries"], list)


    def test_session_insights_are_labelled_with_demo_flag(self, analytics):
        for session in analytics["session_insights"]:
            assert "is_demo" in session
            assert session["resolution_status"] in {
                "resolved",
                "offered",
                "open",
                "unknown",
            }
        demo = [s for s in analytics["session_insights"] if s["is_demo"]]
        real = [s for s in analytics["session_insights"] if not s["is_demo"]]
        assert len(demo) >= 1
        assert len(real) >= 1

    def test_recommendations_and_insights_are_prioritised(self, analytics):
        assert len(analytics["overall_insights"]) >= 1
        assert len(analytics["recommendations"]) >= 1
        for recommendation in analytics["recommendations"]:
            assert recommendation["priority"] in {"High", "Medium", "Low"}
            assert recommendation["title"]
            assert recommendation["detail"]

    def test_data_sources_report_demo_separately(self, analytics):
        sources = analytics["data_sources"]
        assert sources["demo_conversations"] >= 1
        assert sources["recorded_conversations"] >= 1
        assert (
            sources["recorded_conversations"]
            + sources["simulator_conversations"]
            + sources["demo_conversations"]
            == sources["total_analysed"]
        )
        assert "demo" in sources["note"].lower()


class TestAnalyticsWithoutDemo:
    def test_demo_sessions_are_excluded_when_requested(self, client):
        response = client.get(
            "/task8/analytics?limit=10&simulator_limit=5&include_demo=false"
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["data_sources"]["demo_conversations"] == 0
        assert all(
            not session["is_demo"] for session in payload["session_insights"]
        )


# ===========================================================================
# 4. TURN-BY-TURN CONVERSATION ANALYSIS
# ===========================================================================
class TestConversationAnalysis:
    def test_analysis_of_recorded_conversation(self, client, recorded_session):
        response = client.get(
            f"/task8/conversations/{TEST_SESSION_ID}/analysis"
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        stats = payload["statistics"]
        assert stats["total_messages"] == len(INLINE_CONVERSATION)
        assert stats["customer_messages"] == 3
        assert stats["agent_messages"] == 2
        assert len(payload["timeline"]) == 3  # one point per customer message
        assert len(payload["agent_turns"]) == 2
        for turn in payload["agent_turns"]:
            for dimension in ("tone", "clarity", "empathy", "professionalism"):
                assert dimension in turn
                assert 0 <= turn[dimension] <= 100
            assert 0 <= turn["overall"] <= 100
            assert isinstance(turn["meets_standard"], bool)

    def test_unknown_conversation_returns_404(self, client):
        response = client.get("/task8/conversations/conv-missing/analysis")
        assert response.status_code == 404

