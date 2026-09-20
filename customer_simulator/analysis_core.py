"""
Shared intent & sentiment analysis helpers.

These functions implement the core of the Intent & Sentiment Analysis
Agent and are reused by both the legacy `/analyze` endpoint and the new
`/support/analyze` support-assistance pipeline (Task 6), so that the
Coaching & Response Suggestion Agent and the Escalation Risk Monitor
Agent always work from the same analysis.
"""

import re
from typing import Dict, Tuple


# ==========================================================
# INTENT DETECTION
# ==========================================================
INTENT_KEYWORDS = [
    ("refund_request", [
        "refund", "money back", "return",
    ]),
    ("delayed_order", [
        "late", "delay", "delayed", "tracking",
        "not arrived", "hasn't arrived", "hasnt arrived",
        "where is my order", "still waiting",
    ]),
    ("payment_failure", [
        "payment", "charged", "declined", "card",
        "transaction failed", "double charged",
    ]),
    ("account_issue", [
        "login", "log in", "sign in", "password",
        "locked", "account",
    ]),
    ("cancellation", [
        "cancel", "unsubscribe", "stop billing",
    ]),
]


def detect_intent(text_lower: str) -> str:
    """Detect the customer's intent from lowercase text."""
    for intent, keywords in INTENT_KEYWORDS:
        if any(word in text_lower for word in keywords):
            return intent
    return "general_inquiry"


# ==========================================================
# EMOTION / FRUSTRATION DETECTION
# ==========================================================
def detect_emotion(text_lower: str) -> Tuple[str, int]:
    """
    Detect the customer's emotional state.

    Returns:
        (emotion_label, frustration_score) where the score is 1-10.
    """
    if any(w in text_lower for w in [
        "furious", "unacceptable", "ridiculous", "manager",
        "worst", "immediately", "urgent", "urgently",
        "this is ridiculous", "fed up",
    ]):
        return "Furious", 9

    if any(w in text_lower for w in [
        "angry", "frustrated", "upset", "annoyed", "not happy",
    ]):
        return "Angry", 7

    if any(w in text_lower for w in [
        "please", "thank", "appreciate", "thanks",
    ]):
        return "Calm", 3

    return "Frustrated", 5


# ==========================================================
# SENTIMENT DETECTION
# ==========================================================
NEGATIVE_WORDS = [
    "angry", "annoyed", "awful", "bad", "broken", "cancel",
    "complaint", "disappointed", "disgusted", "fed up", "furious",
    "horrible", "impossible", "late", "missing", "never", "no help",
    "not happy", "not resolved", "pathetic", "poor", "refund",
    "ridiculous", "sad", "slow", "still", "terrible", "unacceptable",
    "unhappy", "upset", "useless", "waiting", "waste", "worst", "wrong",
]

POSITIVE_WORDS = [
    "appreciate", "awesome", "excellent", "fast", "good", "great",
    "happy", "helpful", "love", "nice", "perfect", "please", "quick",
    "resolved", "solved", "thank", "thanks", "understood", "wonderful",
]

NEGATIONS = [
    "not", "no", "never", "cannot", "can't", "cant", "won't", "wont",
    "didn't", "didnt", "isn't", "isnt", "don't", "dont",
]


def detect_sentiment(text_lower: str) -> Dict:
    """
    Rule-based sentiment analysis.

    Returns:
        {
            "label": "positive" | "neutral" | "negative",
            "score": float in [-1.0, 1.0],
            "confidence": float in [0.0, 1.0],
        }
    """
    words = re.findall(r"[a-z']+", text_lower)

    negative_hits = 0
    positive_hits = 0

    for index, word in enumerate(words):
        negated = index > 0 and words[index - 1] in NEGATIONS

        if word in NEGATIVE_WORDS:
            if negated:
                positive_hits += 1
            else:
                negative_hits += 1
        elif word in POSITIVE_WORDS:
            if negated:
                negative_hits += 1
            else:
                positive_hits += 1

    total_hits = negative_hits + positive_hits

    if total_hits == 0:
        return {
            "label": "neutral",
            "score": 0.0,
            "confidence": 0.4,
        }

    raw_score = (positive_hits - negative_hits) / max(total_hits, 1)

    if raw_score > 0.2:
        label = "positive"
    elif raw_score < -0.2:
        label = "negative"
    else:
        label = "neutral"

    return {
        "label": label,
        "score": round(max(-1.0, min(1.0, raw_score)), 3),
        "confidence": round(min(1.0, 0.5 + 0.15 * total_hits), 3),
    }
