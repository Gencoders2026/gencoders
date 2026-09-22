"""
Tests for Task 6: Coaching, Response Suggestion & Escalation Risk
Monitoring.

Run from the task6_support_assist folder:

    python -m pytest test_support_assist.py -v

or from the repository root:

    python -m pytest task6_support_assist -v
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


def test_detect_emotion_twice_nobody_helped_is_furious():
    # Correction case (req 6): explicit repetition + no help must read
    # as high-frustration customer state.
    emotion, score = ac.detect_emotion(
        "i have contacted support twice and nobody has helped me. "
        "i am extremely frustrated"
    )
    assert emotion == "Furious"
    assert score == 9


def test_detect_emotion_supervisor_request_is_furious():
    emotion, score = ac.detect_emotion(
        "i want to speak to a supervisor immediately"
    )
    assert emotion == "Furious"
    assert score == 9


def test_detect_sentiment_still_frustrated_negative():
    result = ac.detect_sentiment(
        "i have contacted support twice and nobody has helped me. "
        "i am extremely frustrated"
    )
    assert result["label"] == "negative"
    assert result["score"] < 0


def test_detect_emotion_polite_customer_stays_calm():
    # Genuine politeness with no complaint markers must still be Calm.
    emotion, score = ac.detect_emotion(
        "thank you so much for the help please"
    )
    assert emotion == "Calm"
    assert score == 3


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
# Task 6 correction - role separation & customer-only state
# ==========================================================
def test_agent_reply_never_moves_customer_state(monitor):
    angry = monitor.assess(
        "s-role",
        "This is unacceptable and I want a refund right now!",
        intent="refund_request",
        sentiment="negative",
        emotion_label="Furious",
        frustration_score=9,
        turn=1,
    )
    polite_agent_reply = (
        "I am so sorry for the inconvenience. Thank you for your "
        "patience, I will check this and confirm you soon, please."
    )
    same, intent, emotion, frustration, sentiment = (
        monitor.assess_non_customer_message(
            "s-role", polite_agent_reply, turn=2,
        )
    )
    assert same["escalation_score"] == angry["escalation_score"]
    assert same["escalation_level"] == angry["escalation_level"]
    assert same["message_count"] == angry["message_count"]
    assert same["negative_streak"] == angry["negative_streak"]
    assert intent == "refund_request"
    assert emotion == "Furious"
    assert frustration == 9
    assert sentiment["label"] == "negative"
    # No silent state mutation: the store still shows 1 customer
    # message and no new assessments.
    assert monitor.get_state("s-role")["message_count"] == 1
    assert len(monitor.get_state("s-role")["assessments"]) == 1


def test_repeated_customer_complaint_recognised_as_high(monitor):
    first = monitor.assess(
        "s-repeat-fix",
        "Hi, my refund has not arrived yet, please check.",
        intent="refund_request",
        sentiment="neutral",
        frustration_score=5,
        turn=1,
    )
    second = monitor.assess(
        "s-repeat-fix",
        "I have contacted support twice and nobody has helped me. "
        "I am extremely frustrated.",
        intent="refund_request",
        sentiment="negative",
        emotion_label="Furious",
        frustration_score=9,
        turn=2,
    )
    assert second["escalation_score"] > first["escalation_score"]
    # Req 5/6: repeated + unresolved + high frustration must
    # meaningfully raise risk (at least High).
    assert second["escalation_level"] in ("High", "Critical")
    assert any(
        "repeat" in line.lower() for line in second["reasoning"]
    )


def test_polite_agent_history_does_not_dilute_customer_risk():
    fresh = EscalationRiskMonitor(threshold=70)
    history = [
        {"role": "customer", "content": "Hi, my refund is late, please check."},
        {
            "role": "agent",
            "content": (
                "I am so sorry, thank you for your patience, I will "
                "check and confirm you soon."
            ),
        },
    ]
    result = fresh.assess(
        "s-history",
        "I have contacted support twice and nobody has helped me. "
        "I am extremely frustrated.",
        intent="refund_request",
        sentiment="negative",
        emotion_label="Furious",
        frustration_score=9,
        turn=2,
        customer_history=history,
    )
    assert result["escalation_level"] in ("High", "Critical")
    assert result["negative_streak"] >= 1


def test_supervisor_request_triggers_alert(monitor):
    first = monitor.assess(
        "s-super-fix",
        "Hi, my order is late, please help.",
        intent="delayed_order",
        sentiment="neutral",
        frustration_score=5,
        turn=1,
    )
    second = monitor.assess(
        "s-super-fix",
        "Still no delivery and nobody has helped me. I want to speak "
        "to a supervisor immediately!",
        intent="delayed_order",
        sentiment="negative",
        emotion_label="Furious",
        frustration_score=9,
        turn=2,
    )
    assert second["escalation_score"] >= 70
    assert second["escalation_level"] in ("High", "Critical")
    assert second["alert"]["triggered"] is True
    assert second["alert"]["threshold"] == 70
    assert any(
        "supervisor" in line.lower() for line in second["reasoning"]
    )
    assert first["escalation_score"] < second["escalation_score"]


def test_customer_history_filters_agent_entries():
    texts = EscalationRiskMonitor._customer_history_texts([
        {"role": "customer", "content": "The refund is still late."},
        {"role": "agent", "content": "Sorry, thank you, will check soon."},
        {"content": "Also my order never arrived."},
        {"role": "support", "content": "Please wait patiently."},
        "not-a-dict",
    ])
    assert texts == [
        "the refund is still late.",
        "also my order never arrived.",
    ]


# ==========================================================
# API endpoints (TestClient)
# ==========================================================
@pytest.fixture(scope="module")
def client():
    from support_api import app
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


# ==========================================================
# Task 6 correction - API flow: customer/agent/full history
# ==========================================================
def test_support_analyze_angry_then_polite_agent_reply(client):
    angry = client.post(
        "/support/analyze",
        json={
            "query": (
                "This is unacceptable and I want a refund right now!"
            ),
            "session_id": "api-role-fix",
            "turn": 1,
        },
    ).json()
    assert angry["emotion"] == "Furious"
    assert angry["frustration_level"] == 9
    assert angry["sentiment"] == "negative"

    agent_reply = client.post(
        "/support/analyze",
        json={
            "query": (
                "I am so sorry for the inconvenience. Thank you for "
                "your patience, I will check this for you soon, "
                "please."
            ),
            "session_id": "api-role-fix",
            "sender": "agent",
            "turn": 2,
        },
    ).json()
    assert agent_reply["emotion"] == angry["emotion"]
    assert (
        agent_reply["frustration_level"]
        == angry["frustration_level"]
    )
    assert (
        agent_reply["escalation_score"]
        == angry["escalation_score"]
    )
    assert (
        agent_reply["escalation_level"]
        == angry["escalation_level"]
    )


def test_support_analyze_repeated_complaint_full_flow(client):
    first = client.post(
        "/support/analyze",
        json={
            "query": (
                "Hi, my refund has not arrived yet, please check."
            ),
            "session_id": "api-repeat-fix",
            "turn": 1,
            "history": [
                {
                    "role": "customer",
                    "content": "Hi, will my refund arrive soon?",
                },
                {
                    "role": "agent",
                    "content": "Sorry, thank you, I will check soon.",
                },
            ],
        },
    ).json()
    second = client.post(
        "/support/analyze",
        json={
            "query": (
                "I have contacted support twice and nobody has "
                "helped me. I am extremely frustrated."
            ),
            "session_id": "api-repeat-fix",
            "turn": 2,
            "history": [
                {
                    "role": "customer",
                    "content": "Hi, my refund has not arrived yet.",
                },
                {
                    "role": "agent",
                    "content": "Sorry, thank you, I will check soon.",
                },
            ],
        },
    ).json()
    assert second["frustration_level"] == 9
    assert second["sentiment"] == "negative"
    assert second["escalation_level"] in ("High", "Critical")
    assert (
        second["escalation_score"] > first["escalation_score"]
    )


def test_support_analyze_supervisor_alert_flow(client):
    polite = client.post(
        "/support/analyze",
        json={
            "query": "Hi, my order is late, please help.",
            "session_id": "api-super-fix",
            "turn": 1,
        },
    ).json()
    demand = client.post(
        "/support/analyze",
        json={
            "query": (
                "Still no delivery and nobody has helped me. I want "
                "to speak to a supervisor immediately!"
            ),
            "session_id": "api-super-fix",
            "turn": 2,
        },
    ).json()
    assert demand["escalation_level"] in ("High", "Critical")
    assert demand["alert"]["triggered"] is True
    assert polite["escalation_score"] < demand["escalation_score"]


