"""
Shared intent & sentiment analysis helpers.

These functions implement the core of the Intent & Sentiment Analysis
Agent and are reused by both the legacy `/analyze` endpoint and the new
`/support/analyze` support-assistance pipeline (Task 6), so that the
Coaching & Response Suggestion Agent and the Escalation Risk Monitor
Agent always work from the same analysis.
"""

import re
from typing import Dict, List, Tuple


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
        "delivery", "waited",
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
# EMOTION BANDS (SINGLE SOURCE OF TRUTH)
# ==========================================================
# The emotion LABEL is always a pure function of the frustration
# intensity, so the UI can never display a label and an intensity that
# contradict each other (Task 6 requirement: consistency between
# emotion, emotion intensity and frustration).
#
#     1-3  Calm
#     4-6  Frustrated
#     7-8  Angry
#     9-10 Furious
EMOTION_BANDS: List[Tuple[int, str]] = [
    (9, "Furious"),
    (7, "Angry"),
    (4, "Frustrated"),
    (1, "Calm"),
]


def emotion_label_for_level(level: int) -> str:
    """
    Map a 1..10 frustration intensity to its emotion label.

    Every emotion label produced anywhere in Task 6 (including the
    history-aware escalation monitor) must come from this function so
    the label and the intensity always stay consistent.
    """
    try:
        level = int(level)
    except (TypeError, ValueError):
        level = 1
    for minimum, label in EMOTION_BANDS:
        if level >= minimum:
            return label
    return "Calm"


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
    # The LABEL always comes from the shared band helper so an emotion
    # and its intensity can never disagree.
    if escalation_demand:
        frustration = 9
    elif severe_hits:
        # Fury vocabulary: 9, or the maximum 10 when the message piles
        # up several fury signals and contains nothing calming.
        if not calm_hits and (len(severe_hits) >= 3 or intensity >= 12):
            frustration = 10
        else:
            frustration = 9
    elif strong_hits:
        # A politely phrased request whose own calming words fully
        # offset the complaint vocabulary ("Hi, I would like to cancel
        # my subscription. Could you please help me?") is a REQUEST,
        # not anger - so the calm language and the intensity agree.
        if intensity <= 0:
            frustration = 5
        elif intensity >= 8:
            frustration = 8
        else:
            frustration = 7
    elif mild_hits:
        frustration = 6 if intensity >= 3 else 5
    else:
        frustration = 3

    return emotion_label_for_level(frustration), frustration


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
    # Worry / eroding patience: a customer who is "concerned" or
    # "beginning to lose patience" about an unresolved issue is NOT
    # neutral - they are voicing a negative affect that must keep the
    # escalation monitor's negative-sentiment streak alive.
    "concerned", "concerning", "worrying", "worried", "impatient",
    "unhelpful", "dissatisfied",
]

# Multi-word negative expressions.
#
# The token loop in `detect_sentiment` can only see single words
# (`re.findall(r"[a-z']+")` drops the spaces), so every multi-word entry
# of NEGATIVE_WORDS *and* the expressions below are matched against the
# raw message. Without this, "I'm beginning to lose patience" or
# "still no update" scored as NEUTRAL, which reset the escalation
# monitor's negative streak while the customer was still escalating.
NEGATIVE_PHRASES = [
    # multi-word entries that already exist in NEGATIVE_WORDS
    "fed up", "no help", "not happy", "not resolved", "not satisfied",
    "human agent", "real person", "someone else",
    "speak to a", "talk to a", "long enough", "money back",
    # eroding patience / continued silence
    "lose patience", "losing patience", "losing my patience",
    "no update", "no updates", "no progress", "no response", "no reply",
    "keeps happening", "same issue", "same problem", "no solution",
    "nothing happened", "waste of time",
    # unresolved pressure
    "still waiting", "still no", "still not", "still nothing",
    "not helpful", "not good", "not acceptable",
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

    Multi-word negatives ("no update", "losing patience", "not
    helpful", ...) are matched against the raw message as well, because
    the word loop below can never see a phrase. A repeat complaint that
    is politely worded (still unresolved, but "I'd appreciate an
    update") therefore stays NEGATIVE - it must not reset the
    escalation monitor's negative-sentiment streak.
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

    # Multi-word negatives are checked against the raw text (the loop
    # above only ever sees single tokens). Each expression counts once.
    negative_hits += sum(
        1 for phrase in NEGATIVE_PHRASES if phrase in text_lower
    )

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
