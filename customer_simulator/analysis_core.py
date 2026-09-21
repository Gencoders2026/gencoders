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
    Detect the customer's emotional state and a frustration intensity
    (1..10) from the meaning and intensity of their message.

    The returned frustration is DYNAMIC: it scales with how much
    negative/severe language the message contains, not a fixed
    point-by-point increase.

    IMPORTANT: this must ONLY be called with customer-written text,
    never with an agent/support reply. Agent politeness ("sorry",
    "please", "thank you") must not move the customer's emotion
    toward Calm.
    """
    # ---- severity vocabulary (each phrase has a weight 1..3) ----
    severe_words = {  # weight 3 - strongest escalation / fury signals
        "furious": 3, "unacceptable": 3, "ridiculous": 3, "worst": 3,
        "escalate": 3, "supervisor": 3, "manager": 3, "demand": 3,
        "immediately": 3, "urgent": 3, "urgently": 3, "fed up": 3,
        "never helped": 3, "nobody": 3, "no one": 3, "done waiting": 3,
        "still waiting": 3, "unhappy": 3, "disgusted": 3, "horrible": 3,
        "terrible": 3, "pathetic": 3,
    }
    strong_words = {  # weight 2 - clear anger / frustration
        "angry": 2, "frustrated": 2, "frustration": 2, "frustrating": 2,
        "upset": 2, "annoyed": 2, "not happy": 2, "not satisfied": 2,
        "awful": 2, "bad": 2, "broken": 2, "cancel": 2, "complaint": 2,
        "disappointed": 2, "delay": 2, "late": 2, "missing": 2, "slow": 2,
        "wrong": 2, "problem": 2, "issue": 2, "waste": 2, "useless": 2,
        "never": 2, "no help": 2, "still": 2, "again": 2, "contacted": 2,
    }
    mild_words = {  # weight 1 - mild complaint / neutral-negative
        "refund": 1, "return": 1, "money back": 1, "charged": 1, "card": 1,
        "declined": 1, "payment": 1, "login": 1, "password": 1, "locked": 1,
        "account": 1, "unsubscribe": 1, "stop billing": 1,
    }
    # Genuine polite / appreciative words reduce intensity (calming signal).
    calm_words = {  # weight -1
        "please": -1, "thank": -1, "appreciate": -1, "thanks": -1,
        "sorry": -1, "understand": -1, "help": -1,
    }

    # ---- compute a continuous intensity score ----
    intensity = 0
    for phrase, weight in severe_words.items():
        if phrase in text_lower:
            intensity += weight
    for phrase, weight in strong_words.items():
        if phrase in text_lower:
            intensity += weight
    for phrase, weight in mild_words.items():
        if phrase in text_lower:
            intensity += weight
    for phrase, weight in calm_words.items():
        if phrase in text_lower:
            intensity += weight

    # ---- map intensity to (emotion_label, frustration 1..10) ----
    if intensity >= 12:
        label, frustration = "Furious", 10
    elif intensity >= 8:
        label, frustration = "Angry", 8
    elif intensity >= 5:
        label, frustration = "Upset", 6
    elif intensity >= 3:
        label, frustration = "Frustrated", 4
    else:
        label, frustration = "Calm", 2

    # Explicit supervisor / escalation / human-agent demand is the
    # strongest possible signal regardless of word count.
    escalation_demand = any(
        w in text_lower for w in
        ("supervisor", "manager", "escalate", "human agent", "real person",
         "someone else", "speak to a", "talk to a", "higher department")
    )
    if escalation_demand:
        label, frustration = "Furious", 10

    return label, frustration


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
    # Escalation / dissatisfaction demand signals (negative affect)
    "supervisor", "manager", "escalate", "human agent", "real person",
    "someone else", "demand", "speak to a", "talk to a",
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
            "score": float in [-1.0, 1.0],   # polarity (positive - negative)
            "confidence": float in [0.0, 1.0],  # certainty in the label
        }

    Both `score` and `confidence` are DYNAMIC:
    - `score` reflects the balance of positive vs negative words.
    - `confidence` reflects how clear-cut the signal is: it rises with
      the number of sentiment hits and with the magnitude of the
      polarity, and is lowest when the message contains no sentiment
      vocabulary at all.
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
        # No sentiment vocabulary detected at all -> neutral, but
        # confidence is LOW because we have no evidence either way.
        return {
            "label": "neutral",
            "score": 0.0,
            "confidence": 0.25,
        }

    raw_score = (positive_hits - negative_hits) / max(total_hits, 1)
    raw_score = max(-1.0, min(1.0, raw_score))

    # Label thresholds: only call it positive/negative when the
    # polarity is meaningfully away from zero.
    if raw_score > 0.15:
        label = "positive"
    elif raw_score < -0.15:
        label = "negative"
    else:
        label = "neutral"

    # Confidence is dynamic: higher when (a) there is more evidence
    # (more sentiment hits) and (b) the polarity is more decisive
    # (further from zero). Lowest when the message is near-neutral
    # despite having some sentiment words.
    evidence_factor = min(1.0, total_hits / 8.0)          # 0..1, saturates at 8 hits
    decisiveness = abs(raw_score)                          # 0..1
    confidence = round(min(0.95, 0.35 + 0.4 * evidence_factor + 0.3 * decisiveness), 3)

    # If we called it neutral despite having hits, lower confidence
    # a touch because the signal is ambiguous.
    if label == "neutral":
        confidence = round(min(0.8, confidence - 0.05), 3)

    return {
        "label": label,
        "score": round(raw_score, 3),
        "confidence": confidence,
    }
