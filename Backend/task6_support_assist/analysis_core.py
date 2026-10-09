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
    # NOTE: the escalation nouns ("manager", "supervisor", "escalate")
    # are NOT here on purpose. A bare mention of one is not fury, and
    # weighting them as such made "your manager reviewed it" score as
    # Furious 9/10. A genuine demand is handled separately by
    # `_is_escalation_demand` below.
    severe_words = {  # weight 3 - strongest escalation / fury signals
        "furious": 3, "unacceptable": 3, "ridiculous": 3, "worst": 3,
        "demand": 3,
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
    # strongest possible signal - but ONLY when the customer is
    # actually ASKING to be escalated to someone.
    #
    # A bare mention of the word is NOT a demand. These are all false
    # positives that this used to read as "furious, escalate now":
    #   "manager"                                 (a single word)
    #   "I do not want to speak to a manager"     (negated)
    #   "your manager reviewed it"                (already handled)
    #   'he said "I demand a manager"'            (someone else did)
    #   "Could you ask your manager to review?"   (polite request)
    # So a demand needs BOTH an escalation noun AND a demand verb /
    # negated-away form, which is what `_is_escalation_demand` checks.
    escalation_demand = _is_escalation_demand(text_lower)

    # A public-complaint threat ("I will be posting about this on social
    # media") is not an escalation demand, but it IS a strong
    # dissatisfaction signal and must not read as Calm. Without this the
    # message fell through to the "no vocabulary" branch and scored 3/10
    # even though the monitor itself raised a +15 reputation indicator.
    reputation_threat = any(
        phrase in text_lower for phrase in REPUTATION_PHRASES
    )

    # ---- map to (emotion_label, frustration 1..10) ----
    # The LABEL always comes from the shared band helper so an emotion
    # and its intensity can never disagree.
    #
    # COUPLING WITH SENTIMENT: a message that carries NO negative
    # substance (no negative words, no complaint nouns with a negative
    # modifier, no multi-word negative phrase) is a factual REQUEST -
    # "Hello, just asking about my order." - and must therefore be
    # labelled Calm, not Frustrated. Without this coupling the emotion
    # label and the sentiment label can contradict each other (label
    # "Frustrated" + sentiment "neutral"), which is exactly what made
    # the legacy /analyze endpoint report escalation_risk="High" for a
    # calm message.
    negative_substance = (
        any(w in text_lower for w in NEGATIVE_WORDS)
        or any(phrase in text_lower for phrase in NEGATIVE_PHRASES)
        or any(phrase in text_lower for phrase in REPUTATION_PHRASES)
        or _is_escalation_demand(text_lower)
    )

    if escalation_demand:
        frustration = 9
    elif reputation_threat:
        # A public-complaint threat is real anger (7-8), and reaches 9
        # when it is stacked with other fury vocabulary.
        if severe_hits:
            frustration = 9
        else:
            frustration = 7 if not calm_hits else 6
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

    # No negative substance -> the customer is not expressing anger,
    # so force the label to Calm regardless of the bare complaint
    # nouns that may have nudged the intensity up.
    if not negative_substance:
        frustration = 3

    return emotion_label_for_level(frustration), frustration


# ==========================================================
# ESCALATION-DEMAND DETECTION
# ==========================================================

# Nouns that name WHO the customer wants to be escalated to, plus the
# bare imperative verb form ("escalate this now", "escalating it").
_ESCALATION_NOUNS = (
    "supervisor", "manager", "escalation", "human agent", "real person",
    "human being", "someone else", "higher department", "senior",
    "escalate",
)

# Verbs / frames that turn an escalation noun into an actual DEMAND.
_ESCALATION_DEMAND_PATTERNS = (
    r"\b(?:get|give|put|connect|put me)\s+(?:me\s+)?"
    r"(?:a|an|the|my|to|with|through|on|to talk)?\s*"
    r"(?:your\s+|the\s+|a\s+)?"
    r"(?:supervisor|manager|human|real)\b",
    r"\b(?:speak|talk|chat)\s+to\s+(?:a|an|the|your|my)?\s*"
    r"(?:supervisor|manager|human|real|senior)\b",
    r"\b(?:demand|request|insist)\s+(?:a|an|the|to see|to speak to|to "
    r"talk to)?\s*(?:supervisor|manager|human|real)\b",
    r"\b(?:put|connect|patch|transfer)\s+me\s+(?:straight\s+)?"
    r"(?:through|over)?\s*(?:to\s+)?(?:your\s+|the\s+|a\s+)?"
    r"(?:supervisor|manager|senior|higher)\b",
    r"\b(?:escalate|escalating|escalation)\b",
    r"\b(?:want|need|require)\s+(?:a|an|the|to talk to|to speak to)?\s*"
    r"(?:supervisor|manager|human agent|real person)\b",
    r"\b(?:supervisor|manager)\s+(?:now|today|asap|urgently|immediately)\b",
    r"\b(?:higher|senior)\s+(?:department|manager|team|level)\b",
    r"\blet\s+me\s+speak\s+to\b",
    r"\bbring\s+me\s+(?:a|an|the)\b",
)

# Phrases that explicitly REFUSE an escalation. These must never count.
_ESCALATION_NEGATIONS = (
    r"\bdo\s+not\s+(?:want|need)\s+(?:to\s+)?(?:speak|talk|see)\b",
    r"\bdon'?t\s+(?:want|need)\s+(?:to\s+)?(?:speak|talk|see)\b",
    r"\bno\s+(?:need|point)\s+(?:to\s+)?(?:speak|talk)\s+to\b",
    r"\bwithout\s+(?:a\s+)?(?:supervisor|manager)\b",
    r"\bnot\s+(?:a\s+)?(?:supervisor|manager)\s+problem\b",
    r"\b(?:my|your|the)\s+manager\s+(?:has\s+)?"
    r"(?:already\s+)?(?:reviewed|approved|handled|sorted|resolved|looked)\b",
    r"\bmanager\s+(?:has\s+)?(?:reviewed|approved|handled|sorted|resolved)\b",
)

# "ask your manager to review" is a polite REQUEST, not a demand.
_ESCALATION_POLITE = (
    r"\b(?:ask|contact|email|call)\s+(?:your|the|my)\s+"
    r"(?:supervisor|manager|team|lead)\b",
    r"\bwould\s+you\s+(?:ask|pass)\b",
    r"\bif\s+you\s+could\s+(?:ask|check)\b",
)


def _is_escalation_demand(text_lower: str) -> bool:
    """
    True only when the CUSTOMER is genuinely demanding an escalation.

    A demand needs an escalation noun AND a demand frame. A bare noun
    ("manager"), a negated request ("I do not want to speak to a
    manager"), an already-handled mention ("your manager reviewed it")
    and a polite request ("could you ask your manager to review?") are
    all deliberately NOT demands, because treating them as such made a
    calm, satisfied customer score as Furious 9/10.
    """
    if not any(noun in text_lower for noun in _ESCALATION_NOUNS):
        return False

    for pattern in _ESCALATION_NEGATIONS:
        if re.search(pattern, text_lower):
            return False

    for pattern in _ESCALATION_POLITE:
        if re.search(pattern, text_lower):
            return False

    return any(
        re.search(pattern, text_lower)
        for pattern in _ESCALATION_DEMAND_PATTERNS
    )


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
    # NOTE: the escalation nouns ("manager", "supervisor", "escalate",
    # ...) are deliberately NOT listed here. A bare mention of them is
    # not negative affect - "your manager reviewed it" is good news.
    # They are scored by `_is_escalation_demand` instead, so only a
    # genuine demand contributes negativity.
    # Intensifiers / negative modifiers: when they appear next to a
    # complaint noun the whole phrase is negative ("very late",
    # "still not working", "really bad"). Without a modifier a bare
    # complaint noun ("my order", "the refund", "my account") is a
    # factual REQUEST and must stay NEUTRAL.
    # NOTE: "so" is deliberately NOT here - it is too ambiguous
    # ("thank you so much" is positive, "so late" is negative) and
    # the bare complaint nouns below already carry the negative
    # signal when they appear unmodified.
    "very", "really", "extremely", "too", "quite",
    "not", "no", "never", "can't", "cant", "won't", "wont",
    "still", "long", "bad", "wrong", "broken", "awful",
    "terrible", "horrible", "worst", "useless", "waste",
    # Worry / eroding patience: a customer who is "concerned" or
    # "beginning to lose patience" about an unresolved issue is NOT
    # neutral - they are voicing a negative affect that must keep the
    # escalation monitor's negative-sentiment streak alive.
    "concerned", "concerning", "worrying", "worried", "impatient",
    "unhelpful", "dissatisfied",
]

# Complaint nouns that are ONLY negative when they appear with a
# negative modifier / in a complaint phrase. A bare mention of them
# ("my order", "the refund", "please check my account") is a factual
# request and must NOT flip the polarity to negative.
COMPLAINT_NOUNS = frozenset([
    "refund", "failed", "failure", "error",
    "delay", "delayed",
    "delivery", "order", "charged", "card", "payment",
    "login", "password", "locked", "account", "return",
    "cancel", "unsubscribe", "stop billing",
])

# Modifiers that, when adjacent to a complaint noun, make it negative.
# NOTE: "so" is deliberately NOT here: it is too ambiguous - "thank you
# so much" is positive while "so late" is negative. The bare complaint
# noun ("late", "bad", "broken") is already in NEGATIVE_WORDS, so the
# negative signal survives without "so".
NEGATIVE_MODIFIERS = frozenset([
    "very", "really", "extremely", "too", "quite",
    "not", "no", "never", "can't", "cant", "won't", "wont",
    "still", "long", "bad", "wrong", "broken", "awful",
    "terrible", "horrible", "worst", "useless", "waste",
    "immediately", "urgent", "urgently", "asap", "now",
    "right now", "long enough",
])

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
    # "nothing has changed" is the most common way a customer says
    # "still broken" and was scoring NEUTRAL, which silently reset the
    # monitor's negative streak mid-escalation.
    "nothing changed", "nothing has changed", "nothing has been done",
    "no change", "no changes", "not changed", "nothing new",
    "made no difference", "no difference", "same as before",
    # unresolved pressure
    "still waiting", "still no", "still not", "still nothing",
    "not helpful", "not good", "not acceptable",
]

# Reputation / public-complaint threats are negative affect in their own
# right. Without these, "I will be posting about this on social media"
# scored NEUTRAL and read as a calmer message than the one before it.
REPUTATION_PHRASES = [
    "social media", "twitter", "instagram", "facebook", "trustpilot",
    "leave a review", "bad review", "one star", "1 star",
    "tell everyone", "tell the world", "expose you", "go public",
    "post about this", "posting about this", "write a review",
    "consumer forum", "consumer court", "consumer protection",
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

    # A complaint noun ("refund", "order", "account", ...) is only
    # negative when it is modified by a negative word ("very late",
    # "still not", "really bad"). A bare, polite mention of it ("my
    # order", "the refund", "please check my account") is a factual
    # REQUEST and must stay NEUTRAL — otherwise every polite customer
    # is permanently negative and the escalation monitor can never
    # read a calming reply.
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
        elif word in COMPLAINT_NOUNS:
            # Only count the noun as negative when it is modified by a
            # negative word in the surrounding window. Without a
            # modifier it is a neutral factual request.
            window = words[max(0, index - 2):index + 3]
            if any(w in NEGATIVE_MODIFIERS for w in window):
                negative_hits += 1

    # Multi-word negatives are checked against the raw text (the loop
    # above only ever sees single tokens). Each expression counts once.
    negative_hits += sum(
        1 for phrase in NEGATIVE_PHRASES if phrase in text_lower
    )

    # A genuine escalation demand is negative affect. A bare mention of
    # the same words is not, so it is scored here rather than being
    # baked into NEGATIVE_WORDS.
    if _is_escalation_demand(text_lower):
        negative_hits += 2

    # A public-complaint threat is negative affect too. Without this,
    # "I will be posting about this on social media" scored NEUTRAL and
    # the monitor treated a THREAT as a calmer turn.
    negative_hits += sum(
        1 for phrase in REPUTATION_PHRASES if phrase in text_lower
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

    # ------------------------------------------------------------------
    # LABEL DETERMINATION.
    #
    # Politeness words ("please", "thank you", "I appreciate") are a
    # SOCIAL CONVENTION, not an expression of satisfaction. A customer
    # who writes "I'm beginning to lose patience. I'd appreciate it if
    # you could look into my delayed order." is polite BUT still
    # escalating - the politeness must NOT cancel the negative signal
    # and flip the polarity to neutral, otherwise the escalation
    # monitor's negative-sentiment streak is silently erased while the
    # customer is still complaining.
    #
    # Genuine satisfaction ("Perfect, that resolved my issue. Thank
    # you!") has NO negative substance, so it stays positive and the
    # monitor reads the calming reply correctly.
    #
    # Rule: any NEGATIVE SUBSTANCE (a negative word, a multi-word
    # negative phrase, or a complaint noun with a negative modifier)
    # makes the message negative, unless the customer ALSO confirms
    # the issue is genuinely resolved. Positive politeness words never
    # override negative substance.
    # ------------------------------------------------------------------
    negative_substance = negative_hits > 0

    if negative_substance:
        label = "negative"
    elif positive_hits > 0:
        label = "positive"
    else:
        label = "neutral"

    # When the polarity is driven by negative substance, push the
    # score firmly negative so downstream consumers see a clear signal.
    if label == "negative":
        raw_score = min(-0.5, raw_score)
    elif label == "positive":
        raw_score = max(0.5, raw_score)

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
