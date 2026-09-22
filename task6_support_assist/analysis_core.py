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

    Bands (kept in sync with the Escalation Risk Monitor thresholds
    and with the labels the UI expects):

        Furious      9-10  fury vocabulary or an explicit supervisor /
                           escalation / human-agent demand
        Angry         7-8  clear anger vocabulary
        Frustrated    5-6  mild complaint or negative request
        Calm          3    no complaint signal (polite / neutral)

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
        "delivery": 1, "delayed": 1, "order": 1,
        "failed": 1, "failure": 1, "error": 1,
        # Explicit unmet-demand signals mean the issue is still open.
        "need": 1, "needs": 1, "needed": 1, "must": 1, "should": 1,
        "long enough": 1,
    }
    # Genuine polite / appreciative words reduce intensity (calming signal).
    calm_words = {  # weight -1
        "please": -1, "thank": -1, "appreciate": -1, "thanks": -1,
        "sorry": -1, "understand": -1, "help": -1,
    }

    # ---- dynamic, severity-weighted complaint intensity ----
    severe_hits = [p for p in severe_words if p in text_lower]
    strong_hits = [p for p in strong_words if p in text_lower]
    mild_hits = [p for p in mild_words if p in text_lower]
    calm_hits = [p for p in calm_words if p in text_lower]

    # The vocabulary weights (3 = fury, 2 = anger, 1 = complaint,
    # -1 = calming) make the score scale with the message itself
    # instead of a fixed point-by-point increase.
    intensity = (
        sum(severe_words[p] for p in severe_hits)
        + sum(strong_words[p] for p in strong_hits)
        + sum(mild_words[p] for p in mild_hits)
        + sum(calm_words[p] for p in calm_hits)
    )

    # Explicit supervisor / escalation / human-agent demand is the
    # strongest possible signal regardless of word count.
    escalation_demand = any(
        w in text_lower for w in
        ("supervisor", "manager", "escalate", "human agent", "real person",
         "someone else", "speak to a", "talk to a", "higher department")
    )

    # ---- map to (emotion_label, frustration 1..10) ----
    if escalation_demand:
        label, frustration = "Furious", 9
    elif severe_hits:
        # Fury vocabulary: 9, or the maximum 10 when the message piles
        # up several fury signals and contains nothing calming.
        label = "Furious"
        if not calm_hits and (len(severe_hits) >= 3 or intensity >= 12):
            frustration = 10
        else:
            frustration = 9
    elif strong_hits:
        label, frustration = "Angry", 8 if intensity >= 8 else 7
    elif mild_hits:
        label, frustration = "Frustrated", 6 if intensity >= 3 else 5
    else:
        label, frustration = "Calm", 3

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
    "pathetic", "poor", "ridiculous", "sad", "slow", "still",
    "terrible", "twice", "unacceptable", "unhappy", "unresolved",
    "upset", "useless", "waiting", "waste", "worst", "wrong",
    # Complaint nouns are negative even without an adjective: the
    # customer would not mention them if nothing were wrong.
    "refund", "failed", "failure", "error",
    "delay", "delayed",
    # Escalation / dissatisfaction demand signals (negative affect)
    "supervisor", "manager", "escalate", "human agent", "real person",
    "someone else", "demand", "speak to a", "talk to a",
    # Explicit unmet-demand signals: "I need this resolved", ...
    "need", "needs", "needed", "must", "should", "long enough",
    "immediately", "urgent", "urgently", "asap", "right now",
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

    # Demand/urgency words that follow a positive verb ("resolved
    # immediately", "fixed urgently") are an unmet DEMAND, not
    # satisfaction — they must never flip the polarity to positive.
    DEMAND_WORDS = frozenset([
        "immediately", "urgent", "urgently", "asap", "now",
        "right now", "long enough",
    ])

    for index, word in enumerate(words):
        negated = index > 0 and words[index - 1] in NEGATIONS
        demand_tail = index + 1 < len(words) and words[index + 1] in DEMAND_WORDS

        if word in NEGATIVE_WORDS:
            if negated:
                positive_hits += 1
            else:
                negative_hits += 1
        elif word in POSITIVE_WORDS:
            if negated or demand_tail:
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
