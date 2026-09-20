"""
Tests for Task 6: Coaching, Response Suggestion & Escalation Risk
Monitoring.

Run from the customer_simulator folder:

    python -m pytest test_support_assist.py -v
"""

import pytest
from fastapi.testclient import TestClient

import analysis_core as ac
from support_assist import (
    CoachingResponseAgent,
    EscalationRiskMonitor,
    risk_level_for_score,
)


# ==========================================================
# analysis_core - Intent & Sentiment Analysis
# ==========================================================
def test_detect_intent_refund():
    assert ac.detect_intent("i want my refund right now") == "refund_request"


def test_detect_intent_delayed_order():
    assert (
        ac.detect_intent(
            "where is my order, it is late and tracking shows nothing"
        )
        == "delayed_order"
    )


def test_detect_intent_general():
    assert ac.detect_intent("hello there") == "general_inquiry"


def test_detect_emotion_furious():
    emotion, score = ac.detect_emotion("this is unacceptable and ridiculous")
    assert emotion == "Furious"
    assert score == 9


def test_detect_emotion_calm():
    emotion, score = ac.detect_emotion(
        "thank you so much for the help please"
    )
    assert emotion == "Calm"
    assert score == 3


def test_detect_sentiment_negative():
    result = ac.detect_sentiment("this is terrible and still not resolved")
    assert result["label"] == "negative"
    assert result["score"] < 0


def test_detect_sentiment_positive():
    result = ac.detect_sentiment("thank you, that was great and fast")
    assert result["label"] == "positive"
    assert result["score"] > 0


def test_detect_sentiment_neutral():
    result = ac.detect_sentiment("my order number is 12345")
    assert result["label"] == "neutral"


# ==========================================================
# CoachingResponseAgent
# ==========================================================
@pytest.fixture()
def agent():
    return CoachingResponseAgent()


def test_suggestion_includes_empathy_and_action(agent):
    suggestions = agent.generate_suggestions(
        intent="refund_request",
        sentiment="negative",
        emotion_label="Angry",
        frustration_score=7,
        customer_message="I want my refund",
    )
    text = suggestions["primary"].lower()
    assert "sorry" in text
    assert "refund" in text
    assert suggestions["alternates"]
    assert suggestions["followup_question"]


def test_suggestion_uses_knowledge_results(agent):
    knowledge = [{
        "text": (
            "Refunds are processed within 5-7 business days of "
            "approval."
        ),
        "score": 0.82,
        "metadata": {"source": "Refund Policy.pdf", "page": 2},
    }]
    suggestions = agent.generate_suggestions(
        intent="refund_request",
        sentiment="neutral",
        frustration_score=5,
        knowledge_results=knowledge,
    )
    assert suggestions["knowledge_used"]
    assert "Refund Policy.pdf" in suggestions["primary"]
    assert "business days" in suggestions["primary"]


def test_evaluate_response_scores_in_range(agent):
    evaluation = agent.evaluate_response(
        "I'm very sorry for the trouble. I've initiated your refund "
        "and it will arrive within 5 business days. Is there anything "
        "else I can help you with?"
    )
    for dimension in ("tone", "clarity", "empathy", "professionalism"):
        assert 0 <= evaluation[dimension]["score"] <= 100
        assert evaluation[dimension]["notes"]
    assert 0 <= evaluation["overall"] <= 100
    assert isinstance(evaluation["meets_standard"], bool)


def test_evaluate_harsh_response_scores_low_empathy(agent):
    evaluation = agent.evaluate_response(
        "Can't help with that. Not my problem. You should have read "
        "the policy."
    )
    assert evaluation["empathy"]["score"] < 60
    assert evaluation["meets_standard"] is False


def test_coaching_tips_mention_escalation_when_high(agent):
    tips = agent.generate_coaching_tips(
        intent="refund_request",
        sentiment="negative",
        frustration_score=9,
        escalation_level="Critical",
    )
    assert any("escalation" in tip.lower() for tip in tips)


# ==========================================================
# EscalationRiskMonitor
# ==========================================================
@pytest.fixture()
def monitor():
    return EscalationRiskMonitor(threshold=70)


def test_risk_level_bands():
    assert risk_level_for_score(10) == "Low"
    assert risk_level_for_score(30) == "Medium"
    assert risk_level_for_score(60) == "High"
    assert risk_level_for_score(90) == "Critical"


def test_low_risk_for_polite_message(monitor):
    result = monitor.assess(
        "s-low",
        "Hi, I ordered last week and it has not arrived yet. "
        "Please help.",
        intent="delayed_order",
        sentiment="neutral",
        frustration_score=5,
        turn=1,
    )
    assert result["escalation_level"] == "Low"
    assert result["alert"]["triggered"] is False


def test_critical_risk_alert_and_reasoning(monitor):
    monitor.assess(
        "s-crit",
        "My order still hasn't arrived, this is getting annoying.",
        intent="delayed_order",
        sentiment="negative",
        frustration_score=6,
        turn=1,
    )
    result = monitor.assess(
        "s-crit",
        "This is still not resolved. I want a refund immediately and "
        "I want to speak to a manager!",
        intent="refund_request",
        sentiment="negative",
        emotion_label="Furious",
        frustration_score=9,
        turn=2,
    )
    assert result["escalation_level"] == "Critical"
    assert result["escalation_score"] >= 75
    assert result["alert"]["triggered"] is True
    assert result["reasoning"]
    assert any(
        "supervisor" in line.lower() for line in result["reasoning"]
    )
    actions = " ".join(result["recommended_actions"]).lower()
    assert "supervisor" in actions or "escalate" in actions


def test_repeated_complaints_increase_score(monitor):
    first = monitor.assess(
        "s-repeat",
        "I want a refund for my order, it never arrived.",
        intent="refund_request",
        sentiment="negative",
        frustration_score=6,
        turn=1,
    )
    second = monitor.assess(
        "s-repeat",
        "I still want my refund, why is this not resolved again?",
        intent="refund_request",
        sentiment="negative",
        frustration_score=6,
        turn=2,
    )
    assert second["escalation_score"] > first["escalation_score"]
    assert second["negative_streak"] == 2


def test_threshold_configurable_and_override(monitor):
    assert monitor.get_threshold() == 70
    assert monitor.set_threshold(50) == 50
    assert monitor.get_threshold() == 50

    result = monitor.assess(
        "s-thr",
        "This is unacceptable, I want to talk to a manager "
        "immediately!",
        intent="refund_request",
        sentiment="negative",
        frustration_score=9,
        turn=1,
        threshold_override=100,
    )
    assert result["alert"]["triggered"] is False
    assert result["alert"]["threshold"] == 100


def test_idempotent_same_message(monitor):
    message = "I want a refund immediately, still not resolved!"
    first = monitor.assess(
        "s-idem", message,
        intent="refund_request", sentiment="negative",
        frustration_score=9, turn=1,
    )
    again = monitor.assess(
        "s-idem", message,
        intent="refund_request", sentiment="negative",
        frustration_score=9, turn=1,
    )
    assert again["message_count"] == first["message_count"]
    assert again["escalation_score"] == first["escalation_score"]


def test_state_snapshot(monitor):
    monitor.assess(
        "s-state",
        "Where is my order? It is late.",
        intent="delayed_order",
        sentiment="neutral",
        frustration_score=6,
        turn=1,
    )
    state = monitor.get_state("s-state")
    assert state["message_count"] == 1
    assert state["assessments"]
    assert state["current"]["escalation_level"] in (
        "Low", "Medium", "High", "Critical"
    )
    monitor.reset_session("s-state")
    assert monitor.get_state("s-state")["message_count"] == 0


# ==========================================================
# API endpoints (TestClient)
# ==========================================================
@pytest.fixture(scope="module")
def client():
    from api import app
    return TestClient(app)


def test_support_analyze_pipeline(client):
    response = client.post(
        "/support/analyze",
        json={
            "query": (
                "This is ridiculous, my refund still hasn't arrived "
                "and I want to speak to a manager immediately!"
            ),
            "session_id": "api-test-1",
            "turn": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Intent & sentiment
    assert data["intent"] == "refund_request"
    assert data["sentiment"] in ("positive", "neutral", "negative")
    assert data["emotion"] in ("Furious", "Angry", "Calm", "Frustrated")

    # Escalation monitor
    assert data["escalation_level"] in (
        "Low", "Medium", "High", "Critical"
    )
    assert 0 <= data["escalation_score"] <= 100
    assert data["escalation_reasoning"]
    assert data["alert"]["threshold"] > 0

    # Coaching agent
    assert data["suggested_response"]
    assert data["response_evaluation"]["overall"] > 0
    assert data["coaching_tips"]

    # Knowledge agent
    assert isinstance(data["knowledge_results"], list)
    assert "knowledge_available" in data


def test_support_analyze_stateful_escalation(client):
    payload = {"session_id": "api-test-2"}
    polite = client.post(
        "/support/analyze",
        json={
            **payload,
            "query": "Hi, my order is late. Please help.",
            "turn": 1,
        },
    ).json()
    angry = client.post(
        "/support/analyze",
        json={
            **payload,
            "query": (
                "Still no delivery! This is unacceptable, I demand a "
                "refund immediately and want a supervisor!"
            ),
            "turn": 2,
        },
    ).json()
    assert angry["escalation_score"] >= polite["escalation_score"]


def test_coaching_evaluate_endpoint(client):
    response = client.post(
        "/coaching/evaluate",
        json={
            "response": (
                "I'm so sorry for the delay. I've checked your order "
                "and it will arrive within 2 days. Thank you for "
                "your patience."
            ),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "tone" in data and "clarity" in data
    assert "empathy" in data and "professionalism" in data


def test_escalation_threshold_endpoints(client):
    got = client.get("/escalation/threshold").json()
    assert 0 <= got["threshold"] <= 100
    assert "bands" in got

    updated = client.post(
        "/escalation/threshold", json={"threshold": 65}
    ).json()
    assert updated["status"] == "updated"
    assert updated["threshold"] == 65

    restored = client.post(
        "/escalation/threshold", json={"threshold": 70}
    ).json()
    assert restored["threshold"] == 70


def test_legacy_analyze_still_works(client):
    response = client.post("/analyze", json={"query": "I want a refund"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "refund_request"
    assert "escalation_risk" in data
    assert "suggested_response" in data
    assert "coaching_tips" in data
    assert "knowledge_results" in data


