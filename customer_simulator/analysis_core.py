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

    IMPORTANT: this must ONLY be called with customer-written text,
    never with an agent/support reply. Agent politeness ("sorry",
    "please", "thank you") must not move the customer's emotion
    toward Calm.
    """
    high_frustration_words = [
        "furious", "unacceptable", "ridiculous", "worst",
        "immediately", "urgent", "urgently", "fed up",
        "this is ridiculous", "extremely frustrated", "extremely",
        "demand", "escalate", "supervisor", "manager", "nobody",
        "no one", "never helped", "still waiting", "done waiting",
    ]

    if any(w in text_lower for w in high_frustration_words):
        return "Furious", 9

    if any(w in text_lower for w in [
        "angry", "frustrated", "frustrating", "frustration",
        "upset", "annoyed", "not happy", "not satisfied",
    ]):
        return "Angry", 7

    calm_words = ["please", "thank", "appreciate", "thanks"]
    complaint_words = [
        "refund", "not resolved", "still", "again", "no update",
        "waiting", "delay", "late", "problem", "issue", "wrong",
        "broken", "unhappy", "disappointed", "complaint",
    ]

    if (
        any(w in text_lower for w in calm_words)
        and not any(w in text_lower for w in complaint_words)
        and "not " not in text_lower
    ):
        return "Calm", 3

    return "Frustrated", 5


# ==========================================================
# SENTIMENT DETECTION
# ==========================================================
NEGATIVE_WORDS = [
    "angry", "annoyed", "awful", "bad", "broken", "cancel",
    "complaint", "contacted", "disappointed", "disgusted",
    "extremely", "fed up", "frustrated", "frustrating", "frustration",
    "furious", "horrible", "impossible", "late", "missing", "never",
    "no help", "nobody", "not happy", "not resolved", "not satisfied",
    "pathetic", "poor", "refund", "ridiculous", "sad", "slow", "still",
    "terrible", "twice", "unacceptable", "unhappy", "unresolved",
    "upset", "useless", "waiting", "waste", "worst", "wrong",
]

POSITIVE_WORDS = [
    "appreciate", "awesome", "excellent", "fast", "good", "great",
    "happy", "helpful", "love", "nice", "perfect", "quick",
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
