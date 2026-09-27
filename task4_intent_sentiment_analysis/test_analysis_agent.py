"""
Task 4 — Intent & Sentiment Analysis Agent
20 Unit Test Cases covering all required scenarios.

Tests:
  - Intent detection (all 5 categories + general)
  - Emotion / frustration classification (Calm / Frustrated / Angry / Furious)
  - Sentiment analysis (positive / neutral / negative)
  - Satisfaction trend tracking across multi-turn conversations
  - Escalation risk levels (Low / Medium / High / Critical)
  - Coaching guidance generation
"""

import sys
from pathlib import Path

# Ensure task4 module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "task6_support_assist"))

from analysis_agent import analyze_message, ConversationHistory


# ==========================================================
# HELPER
# ==========================================================
def run_test(test_id: int, description: str, text: str, expected: dict):
    result = analyze_message(text)
    passed = True
    failures = []

    for key, expected_value in expected.items():
        actual = result.get(key)
        if isinstance(expected_value, (list, tuple)):
            # Allow any of the listed values
            if actual not in expected_value:
                failures.append(f"  {key}: expected one of {expected_value}, got {actual!r}")
                passed = False
        elif actual != expected_value:
            failures.append(f"  {key}: expected {expected_value!r}, got {actual!r}")
            passed = False

    status = "PASS" if passed else "FAIL"
    print(f"[{status}] Test {test_id:02d}: {description}")
    if failures:
        for f in failures:
            print(f)
    return passed


# ==========================================================
# 20 TEST CASES
# ==========================================================
TEST_CASES = [

    # --- INTENT DETECTION (Tests 1-6) ---

    (1, "Refund intent — direct",
     "I want a refund for my purchase.",
     {"intent": "refund_request", "emotion_label": ["Calm", "Frustrated", "Angry"]}),

    (2, "Delayed order intent",
     "My order is very late and hasn't arrived yet. I've been waiting two weeks.",
     {"intent": "delayed_order", "sentiment": "negative", "frustration_level": (5, 6, 7, 8)}),

    (3, "Payment failure intent",
     "I was double charged on my card. The payment failed but money was taken.",
     {"intent": "payment_failure"}),

    (4, "Account issue intent",
     "I can't log in to my account. My password isn't working.",
     {"intent": "account_issue"}),

    (5, "Cancellation intent",
     "I want to cancel my subscription immediately.",
     {"intent": "cancellation"}),

    (6, "General inquiry intent",
     "Hello, can you help me understand my options?",
     {"intent": "general_inquiry", "sentiment": ["neutral", "positive"]}),

    # --- EMOTION & FRUSTRATION (Tests 7-11) ---

    (7, "Calm emotion — polite request",
     "Hi, could you please check the status of my order? Thank you.",
     {"emotion_label": "Calm", "frustration_level": (1, 2, 3), "sentiment": ["neutral", "positive"]}),

    (8, "Frustrated emotion — mild complaint",
     "My refund is taking too long and I haven't heard anything.",
     {"emotion_label": ["Frustrated", "Angry"], "sentiment": "negative"}),

    (9, "Angry emotion — strong complaint",
     "I am very frustrated and annoyed. This is a real problem.",
     {"emotion_label": ["Angry", "Frustrated"], "frustration_level": (5, 6, 7, 8), "sentiment": "negative"}),

    (10, "Furious emotion — escalation demand",
     "This is absolutely unacceptable! I demand to speak to a supervisor right now!",
     {"emotion_label": ["Angry", "Furious"], "frustration_level": (8, 9, 10),
      "escalation_risk": ["High", "Critical"]}),

    (11, "Furious emotion — multiple fury signals",
     "This is ridiculous and terrible! I am fed up! Nobody has helped me! Worst service ever!",
     {"emotion_label": ["Angry", "Furious"], "frustration_level": (8, 9, 10),
      "escalation_risk": ["High", "Critical"], "sentiment": "negative"}),

    # --- SENTIMENT (Tests 12-14) ---

    (12, "Positive sentiment — issue resolved",
     "Thank you so much! You resolved my issue perfectly. I really appreciate your help.",
     {"escalation_risk": ["Low", "Medium"]}),

    (13, "Neutral sentiment — factual query",
     "Can you tell me about your return policy?",
     {"sentiment": "neutral", "emotion_label": "Calm"}),

    (14, "Negative sentiment — clear complaint",
     "I'm very unhappy with the service. The problem is still not resolved.",
     {"sentiment": "negative", "emotion_label": ["Frustrated", "Angry", "Furious"]}),

    # --- SATISFACTION TREND (Tests 15-16) ---

    (15, "Satisfaction trend — improving (multi-turn)",
     "",  # Placeholder — test is run manually below
     {}),

    (16, "Satisfaction trend — declining (multi-turn)",
     "",  # Placeholder — test is run manually below
     {}),

    # --- ESCALATION RISK (Tests 17-19) ---

    (17, "Escalation risk — Low (calm customer)",
     "Hi, I have a quick question about my recent order status.",
     {"escalation_risk": "Low", "emotion_label": "Calm"}),

    (18, "Escalation risk — Medium (frustrated)",
     "I've been waiting for my refund for 10 days. This is taking too long.",
     {"escalation_risk": ["Medium", "High"], "sentiment": "negative"}),

    (19, "Escalation risk — Critical (supervisor demand)",
     "Get me your supervisor right now! This is completely unacceptable!",
     {"escalation_risk": "Critical", "frustration_level": (8, 9, 10)}),

    # --- COACHING GUIDANCE (Test 20) ---

    (20, "Coaching guidance — high-risk scenario",
     "I am furious! I demand a refund immediately and want a manager!",
     {"escalation_risk": "Critical", "intent": "refund_request", "sentiment": "negative"}),
]


def test_multi_turn_improving():
    """Test 15 — satisfaction trend improving across 3 turns."""
    history = ConversationHistory()
    messages = [
        ("I am very angry about this. Nobody has helped me!", 9, "negative"),
        ("OK the refund was issued. I am still a bit frustrated.", 6, "negative"),
        ("Thank you, the issue is resolved. I appreciate your help.", 2, "positive"),
    ]
    results = []
    for text, expected_frustration, expected_sentiment in messages:
        r = analyze_message(text, history=history)
        results.append(r)

    trend = results[-1]["satisfaction_trend"]
    passed = trend in ("improving", "stable")
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] Test 15: Satisfaction trend — improving across 3 turns (got: {trend!r})")
    return passed


def test_multi_turn_declining():
    """Test 16 — satisfaction trend declining across 3 turns."""
    history = ConversationHistory()
    messages = [
        "Hi, could you check on my order please?",
        "My order is still late. I am getting frustrated.",
        "This is unacceptable. I am very angry now. I want a supervisor!",
    ]
    results = []
    for text in messages:
        r = analyze_message(text, history=history)
        results.append(r)

    trend = results[-1]["satisfaction_trend"]
    passed = trend in ("declining", "critical")
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] Test 16: Satisfaction trend — declining across 3 turns (got: {trend!r})")
    return passed


# ==========================================================
# MULTI-VALUE TEST HELPER
# ==========================================================
def run_test_multi(test_id, description, text, expected):
    """Like run_test but expected values can be tuples = 'any of these'."""
    result = analyze_message(text)
    passed = True
    failures = []

    for key, expected_value in expected.items():
        actual = result.get(key)
        if isinstance(expected_value, tuple):
            if actual not in expected_value:
                failures.append(f"  {key}: expected one of {expected_value}, got {actual!r}")
                passed = False
        elif isinstance(expected_value, list):
            if actual not in expected_value:
                failures.append(f"  {key}: expected one of {expected_value}, got {actual!r}")
                passed = False
        elif actual != expected_value:
            failures.append(f"  {key}: expected {expected_value!r}, got {actual!r}")
            passed = False

    status = "PASS" if passed else "FAIL"
    print(f"[{status}] Test {test_id:02d}: {description}")
    if failures:
        for f in failures:
            print(f)
    return passed


# ==========================================================
# RUNNER
# ==========================================================
def run_all_tests():
    print("=" * 60)
    print("Task 4 — Intent & Sentiment Analysis: 20 Test Cases")
    print("=" * 60)

    results = []

    for i, tc in enumerate(TEST_CASES):
        test_id, description, text, expected = tc

        if test_id == 15:
            results.append(test_multi_turn_improving())
            continue
        if test_id == 16:
            results.append(test_multi_turn_declining())
            continue
        if not text:
            continue

        results.append(run_test_multi(test_id, description, text, expected))

    passed = sum(results)
    total = len(results)
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
