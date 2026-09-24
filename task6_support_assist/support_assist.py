"""
Support Assistance Module (Task 6).

Implements the two agents required by the task:

1. CoachingResponseAgent  - Coaching & Response Suggestion Agent
   - Generates context-aware suggested responses for support agents
     using customer intent, sentiment, conversation history and
     knowledge-base results.
   - Evaluates suggested responses for tone, clarity, empathy and
     professionalism.
   - Provides actionable communication improvement tips.

2. EscalationRiskMonitor  - Escalation Risk Monitor Agent
   - Continuously monitors the conversation and calculates an
     escalation-risk score (0-100) after every customer message.
   - Identifies indicators such as repeated complaints, high
     frustration, negative sentiment, unresolved issues and requests
     for a supervisor.
   - Classifies conversations into Low / Medium / High / Critical
     risk levels and provides the reasoning for the score.
   - Raises a configurable alert when the high-escalation threshold
     is reached and recommends appropriate actions.

Both agents are deterministic rule-based implementations (no external
LLM call required) so they always respond in real time.
"""

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from analysis_core import (
    detect_emotion as ac_detect_emotion,
    detect_intent as ac_detect_intent,
    detect_sentiment as ac_detect_sentiment,
    emotion_label_for_level,
)


# ==========================================================
# CONFIGURATION
# ==========================================================
def _env_threshold() -> int:
    try:
        return int(os.getenv("ESCALATION_ALERT_THRESHOLD", "70"))
    except (TypeError, ValueError):
        return 70


DEFAULT_ALERT_THRESHOLD = _env_threshold()

# Risk-level bands (score is 0-100)
RISK_LEVEL_BANDS: List[Tuple[int, str]] = [
    (75, "Critical"),
    (50, "High"),
    (25, "Medium"),
    (0, "Low"),
]

VALID_SENTIMENTS = {"positive", "neutral", "negative"}

# Shared streak vocabulary (customer history only): negatives must
# outweigh these positives for a past customer message to keep a
# negative-sentiment streak alive.
_NEGATIVE_STREAK_WORDS = frozenset([
    "angry", "annoyed", "awful", "bad", "broken", "cancel",
    "complaint", "contacted", "delivery", "delay", "delayed",
    "disappointed", "disgusted", "error",
    "extremely", "failed", "failure", "fed up", "frustrated", "frustrating", "frustration",
    "furious", "horrible", "impossible", "must",
    "need", "needs", "needed", "never",
    "no help", "nobody", "not happy", "not resolved", "not satisfied",
    "order", "pathetic", "poor", "refund", "ridiculous", "sad",
    "slow", "still",
    "terrible", "twice", "unacceptable", "unhappy", "unresolved",
    "upset", "useless", "waiting", "waste", "worst", "wrong",
    # Eroding patience / worry: keeps a streak alive for a politely
    # worded repeat complaint ("I'm starting to get concerned").
    "concerned", "concerning", "worrying", "worried", "impatient",
    "unhelpful", "dissatisfied",
])
# Multi-word negatives must also count in the streak check, where
# `re.findall(r"[a-z']+")` drops spaces.
_NEGATIVE_STREAK_PHRASES = frozenset([
    "fed up", "no help", "not happy", "not resolved", "not satisfied",
    "long enough",
    "lose patience", "losing patience", "losing my patience",
    "no update", "no progress", "no response", "no reply",
    "keeps happening", "same issue", "same problem", "no solution",
    "nothing happened", "not helpful", "waste of time",
    "still waiting", "still no", "still not", "still nothing",
])
_POSITIVE_STREAK_WORDS = frozenset([
    "appreciate", "awesome", "excellent", "fast", "good", "great",
    "happy", "helpful", "love", "nice", "perfect", "quick",
    "resolved", "solved", "thank", "thanks", "understood", "wonderful",
])

# Resolution request signals: the customer states the issue is STILL
# open (a polite wrapper like "please" must not hide them).
_RESOLUTION_REQUEST_WORDS = frozenset([
    "need", "needs", "needed", "must", "should", "long enough",
    "asap", "urgent", "urgently", "immediately", "right now",
    "end of day", "as soon as possible",
    "still", "yet", "again", "waiting", "waited",
])

# Evidence that the issue is genuinely resolved (a satisfied customer
# says so). Politeness or apologies from the AGENT are NOT evidence —
# only the customer's own confirmation counts.
_CUSTOMER_RESOLUTION_WORDS = frozenset([
    "resolved", "solved", "fixed", "received", "arrived safely",
    "working now", "works now", "all good", "sorted out", "taken care of",
])

# Evidence the agent gave a CONCRETE commitment (used for the
# "resolution offered" boost). A vague "I will check" is politeness,
# NOT a commitment — only a specific timeline / concrete action or a
# processed refund/replacement counts, per the global fix.
_AGENT_COMMITMENT_RE = re.compile(
    r"within\s+\d+\s*(?:-\s*\d+\s*)?(?:business\s+)?(?:day|hour|minute)s?"
    r"|within\s+(?:a|an|one|two|three|four|five|\d+)\s*(?:business\s+)?"
    r"(?:day|hour|minute)s?"
    r"|by\s+(?:tomorrow|end of day|the end of day|tonight)"
    r"|(?:has|have|is|was|were)\s+(?:been\s+)?(?:processed|issued|refunded|escalated)"
    r"|\bescalated\b"
    r"|\breship(?:ped|ment)?\b"
    r"|replacement is on the way"
    r"|i will (?:refund|process|escalate|reship|replace|issue)"
    r"|i'll (?:refund|process|escalate|reship|replace|issue)"
)

# Pure agent politeness that carries NO resolution commitment.
_AGENT_POLITENESS_WORDS = frozenset([
    "sorry", "apologize", "apologies", "apology", "thank", "thanks",
    "please", "appreciate", "happy to help", "glad to help",
    "kindly", "of course", "great question", "wonderful",
])

# NOTE: multi-word negatives are covered by the single
# `_NEGATIVE_STREAK_PHRASES` definition next to the streak vocabulary
# above - `re.findall(r"[a-z']+")` drops spaces, so phrases are matched
# against the raw text there.


# ==========================================================
# CUSTOMER-STATE EVIDENCE
# ==========================================================
# The customer's emotion / frustration may ONLY move when the
# CUSTOMER'S OWN message provides evidence. Agent politeness never
# appears in these lists.

# Genuine calming evidence (the customer sounds reassured / satisfied).
_CALM_APPRECIATION_WORDS = (
    "thank", "thanks", "appreciate", "appreciated", "grateful",
)
_CALM_POSITIVE_WORDS = (
    "good", "great", "perfect", "glad", "pleased", "happy", "excellent",
    "awesome", "wonderful", "helpful", "that works", "that helped",
    "sounds good", "no problem", "all good", "love it", "nice",
)
_CALM_UNDERSTANDING_RE = re.compile(
    r"\b(?:ok|okay|fine|understood|understands|got it|noted|"
    r"makes sense|i understand|fair enough)\b"
)

# Negation guard: "not happy", "isn't resolved", "don't understand" ...
# must NEVER be read as calming / resolved evidence.
_NEGATION_RE = re.compile(
    r"\b(?:not|no|never|n't|isn't|wasn't|weren't|aren't|don't|doesn't|"
    r"didn't|can't|cannot|won't|nothing|none)\b"
)


def _has_unnegated(text_lower: str, needles) -> bool:
    """
    True when at least one needle occurs in the text WITHOUT being
    negated shortly before it.

    This is what stops "not resolved" from counting as a resolution
    confirmation and "not happy" from counting as calming evidence.
    """
    if isinstance(needles, str):
        needles = (needles,)
    for needle in needles:
        start = 0
        while True:
            index = text_lower.find(needle, start)
            if index == -1:
                break
            window = text_lower[max(0, index - 24):index]
            if not _NEGATION_RE.search(window):
                return True
            start = index + len(needle)
    return False

# How much each kind of calming evidence counts (capped at 1.0). The
# sum decides HOW FAR frustration is allowed to fall - it is never a
# fixed per-turn step.
_CALM_EVIDENCE_WEIGHTS = {
    "resolution confirmed": 1.0,
    "appreciation": 0.35,
    "positive language": 0.30,
    "understanding": 0.20,
    "agent commitment": 0.30,
}

# Signals that the customer's concern is still NOT addressed.
_UNRESOLVED_MARKERS = (
    "still", "again", "yet", "not resolved", "isn't resolved", "unresolved",
    "no update", "no solution", "nothing happened", "keeps happening",
    "same issue", "same problem", "how long", "when will", "no help",
    "nobody", "no one", "twice", "two times", "waiting", "waited",
    "long enough", "contacted support", "contacted you", "fed up",
)
_REPEAT_MARKERS = (
    "twice", "two times", "three times", "multiple times", "again",
    "contacted support", "contacted you", "nobody has helped",
    "nobody helped", "no one has helped", "still no", "still not",
    "keeps happening", "same issue", "same problem",
)
_ESCALATION_DEMAND_MARKERS = (
    "supervisor", "manager", "escalate", "human agent", "real person",
    "someone else", "higher department", "speak to a", "talk to a",
)
_URGENCY_MARKERS = (
    "immediately", "urgent", "urgently", "asap", "right now",
    "as soon as possible", "end of day",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp_score(value: float, low: int = 0, high: int = 100) -> int:
    """Clamp a float score into an inclusive integer range."""
    return int(max(low, min(high, round(value))))


def risk_level_for_score(score: int) -> str:
    """Map a 0-100 escalation score to Low/Medium/High/Critical."""
    for minimum, level in RISK_LEVEL_BANDS:
        if score >= minimum:
            return level
    return "Low"


# ==========================================================
# REPEAT-PRESSURE CURVE (single source of truth)
# ==========================================================
# How much a repeated complaint is worth depends on HOW MANY CUSTOMER
# MESSAGES raised the same issue, so the escalation risk keeps moving
# as long as the conversation is not resolved instead of saturating
# after the first repeat:
#
#   mentions 1            -> 18  (strong complaint, no repeat yet)
#   mentions 2            -> 24
#   mentions 3, 4, 5, ... -> 26, 28, 30 (capped)
#
# Nothing here is a per-turn increment: `mentions` always comes from
# the conversation itself (customer history + the monitor's counters),
# never from the turn number.
_REPEAT_MENTION_BASE_POINTS = 18
_REPEAT_POINTS_START = 24
_REPEAT_POINTS_STEP = 2
_REPEAT_POINTS_CAP = 30

# A repeat that is not phrased as a complaint (no complaint wording, but
# the same issue for the 3rd+ time) also grows: 6, 9, 12, ... (capped).
_RAISED_BEFORE_POINTS = 6
_RAISED_BEFORE_STEP = 3
_RAISED_BEFORE_CAP = 20


def repeated_complaint_points(mentions: int) -> int:
    """Repeat-pressure points for a complaint raised `mentions` times."""
    try:
        mentions = int(mentions)
    except (TypeError, ValueError):
        mentions = 1
    if mentions < 2:
        return _REPEAT_MENTION_BASE_POINTS
    return min(
        _REPEAT_POINTS_CAP,
        _REPEAT_POINTS_START + _REPEAT_POINTS_STEP * (mentions - 2),
    )


def raised_before_points(mentions: int) -> int:
    """Repeat-pressure points for the Nth raising of the same issue."""
    try:
        mentions = int(mentions)
    except (TypeError, ValueError):
        mentions = 3
    mentions = max(3, mentions)
    return min(
        _RAISED_BEFORE_CAP,
        _RAISED_BEFORE_POINTS + _RAISED_BEFORE_STEP * (mentions - 3),
    )


# ==========================================================
# COACHING & RESPONSE SUGGESTION AGENT
# ==========================================================
class CoachingResponseAgent:
    """
    Generates context-aware response suggestions for support agents
    and evaluates them for tone, clarity, empathy and professionalism.
    """

    INTENT_NEXT_STEPS = {
        "refund_request": (
            "Would you like me to check the refund eligibility for your "
            "order and confirm the current refund policy with you?"
        ),
        "delayed_order": (
            "Would you like me to look up the current delivery status of "
            "your order and walk you through the available options?"
        ),
        "payment_failure": (
            "Would you like me to check what happened with the payment on "
            "our side and go over the retry options with you?"
        ),
        "account_issue": (
            "Would you like me to walk you through the account-recovery "
            "steps, or would a password reset be the best next step?"
        ),
        "cancellation": (
            "Would you like me to confirm what applies to your plan "
            "before we finalise the cancellation?"
        ),
        "general_inquiry": (
            "Could you share a bit more detail (for example your order ID) "
            "so I can pull up the exact information and help you from "
            "there?"
        ),
    }

    # Generic empathic OPENERS, selected by the customer's sentiment /
    # frustration level (not by persona). Persona affects the CLOSING
    # tone only via the caller if it chooses.

    EMPATHY_OPENERS = {
        "calm": (
            "Thanks for reaching out — I'm happy to help you with this "
            "right away."
        ),
        "frustrated": (
            "I'm sorry for the inconvenience — I completely understand how "
            "frustrating this is, and I'll sort it out for you now."
        ),
        "negative": (
            "I'm really sorry about this experience. You're right to be "
            "upset, and I'm going to take care of this personally right "
            "now."
        ),
        "neutral": (
            "Thanks for getting in touch. Let me look into this for you "
            "straight away."
        ),
        "positive": (
            "Thank you for your patience — let me get this wrapped up for "
            "you."
        ),
    }

    # Tone escalators: when frustration is very high we can strengthen
    # the opener slightly without fabricating any completed action.
    FRUSTRATION_ESCALATORS = {
        9: " I understand this is really frustrating, and I'll do my best "
            "to resolve it for you now.",
        10: " I completely understand how frustrating this is. I'm going "
             "to take this on personally and get this sorted out for you.",
    }

    CLOSING = (
        "Thank you for your patience — is there anything else I can help "
        "you with while I'm here?"
    )

    SHORT_CLOSING = "Let me know if there's anything else you need."

    # ------------------------------------------------------
    # Suggestion generation
    # ------------------------------------------------------
    def generate_suggestions(
        self,
        *,
        intent: str,
        sentiment: str,
        emotion_label: str = "",
        frustration_score: int = 5,
        customer_message: str = "",
        knowledge_results: Optional[List[Dict]] = None,
        history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Generate a primary suggested response plus alternates,
        grounded in the knowledge base when results are available.

        `frustration_score` is derived from the CUSTOMER message only
        and is clamped to 1..10 so it can never inflate the tone.
        """
        if frustration_score is None:
            frustration_score = 5
        try:
            frustration_score = int(frustration_score)
        except (TypeError, ValueError):
            frustration_score = 5
        frustration_score = max(1, min(10, frustration_score))
        sentiment_key = (
            sentiment if sentiment in self.EMPATHY_OPENERS else "neutral"
        )

        if frustration_score >= 8:
            sentiment_key = "negative"
        elif frustration_score >= 6 and sentiment_key == "neutral":
            sentiment_key = "frustrated"
        elif frustration_score <= 3 and sentiment_key == "neutral":
            sentiment_key = "calm"

        opener = self.EMPATHY_OPENERS.get(
            sentiment_key, self.EMPATHY_OPENERS["neutral"]
        )
        # Non-fabricating next step: the suggestion only offers to
        # check / confirm something, it never claims an action that
        # has not happened (see INTENT_NEXT_STEPS).
        action = self.INTENT_NEXT_STEPS.get(
            intent, self.INTENT_NEXT_STEPS["general_inquiry"]
        )

        knowledge_line, knowledge_used = self._build_knowledge_line(
            intent, knowledge_results
        )

        primary = " ".join(
            part for part in [opener, action, knowledge_line, self.CLOSING]
            if part
        )

        return {
            "primary": primary,
            "alternates": [
                " ".join(part for part in [opener, action] if part),
                (
                    "Dear customer, thank you for contacting support. "
                    + action
                    + " "
                    + self.SHORT_CLOSING
                ),
            ],
            "followup_question": self._build_followup_question(intent),
            "knowledge_used": knowledge_used,
            "basis": {
                "intent": intent,
                "sentiment": sentiment,
                "emotion": emotion_label,
                "frustration_score": frustration_score,
                "history_turns": len(history or []),
                "knowledge_chunks": len(knowledge_results or []),
            },
        }

    def _build_knowledge_line(
        self,
        intent: str,
        knowledge_results: Optional[List[Dict]],
    ) -> Tuple[str, List[Dict]]:
        """Extract a policy line from retrieved knowledge chunks."""
        if not knowledge_results:
            return "", []

        keywords = {
            "refund_request": ["refund", "money back", "days"],
            "delayed_order": ["delivery", "shipping", "track", "days"],
            "payment_failure": ["payment", "charged", "card", "retry"],
            "account_issue": ["password", "login", "reset", "account"],
            "cancellation": ["cancel", "cancellation", "billing"],
        }.get(intent, [])

        for result in knowledge_results:
            text = result.get("text", "")
            if not text:
                continue

            sentences = re.split(r"(?<=[.!?])\s+", text.strip())
            best_sentence = ""
            keyword_sentence = ""
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:
                    continue
                if not best_sentence:
                    best_sentence = sentence
                if keywords and any(
                    k in sentence.lower() for k in keywords
                ):
                    keyword_sentence = sentence
                    break

            # Relevance guard: when the intent has specific keywords,
            # ONLY use a sentence that actually matches them. Never
            # quote an unrelated policy line (e.g. refund terms while
            # the customer asked about a delayed delivery).
            if keywords:
                if not keyword_sentence:
                    continue
                best_sentence = keyword_sentence
            if not best_sentence:
                continue

            source = (result.get("metadata") or {}).get(
                "source", "our policy"
            )

            line = (
                f"As per our {source}: {best_sentence}"
                if not best_sentence.lower().startswith("as per")
                else best_sentence
            )

            used = [{
                "source": source,
                "page": (result.get("metadata") or {}).get("page"),
                "score": result.get("score"),
                "excerpt": best_sentence[:200],
            }]

            return line, used

        return "", []

    def _build_followup_question(self, intent: str) -> str:
        questions = {
            "refund_request": (
                "Would you prefer the refund to your original payment "
                "method, or as store credit with a 10% bonus?"
            ),
            "delayed_order": (
                "If the new delivery date doesn't work for you, would "
                "you like a reshipment of the same item instead?"
            ),
            "payment_failure": (
                "Would you like to retry with the same card, or shall "
                "I suggest an alternative payment method?"
            ),
            "account_issue": (
                "Are you able to access the registered email inbox "
                "right now?"
            ),
            "cancellation": (
                "Before I cancel — would a plan pause or downgrade "
                "work better for you?"
            ),
        }
        return questions.get(
            intent,
            "Could you share any additional details that would help "
            "me resolve this faster?",
        )

    # ------------------------------------------------------
    # Response evaluation (tone / clarity / empathy / professionalism)
    # ------------------------------------------------------
    EMPATHY_PHRASES = [
        "sorry", "apologize", "apologies", "regret",
        "understand", "frustrat", "inconvenience",
    ]
    APOLOGY_PHRASES = ["sorry", "apologize", "apologies", "regret"]
    HARSH_PHRASES = [
        "can't", "cannot", "won't", "impossible",
        "not my problem", "calm down", "no refund",
        "as i already said", "you should have", "your fault",
    ]
    COURTESY_PHRASES = [
        "please", "thank", "happy to help", "glad to help",
        "kindly", "appreciate", "of course",
    ]
    CASUAL_PHRASES = [
        "gonna", "wanna", "kinda", "yeah", "yep", "nope",
        "lol", "stuff", "guys",
    ]
    TIMELINE_RE = re.compile(
        r"\b\d+\s*(?:minutes?|mins?|hours?|hrs?|days?|business days?)\b"
    )

    def evaluate_response(
        self,
        text: str,
        *,
        sentiment: str = "neutral",
        frustration_score: int = 5,
    ) -> Dict:
        """
        Evaluate a suggested or agent-drafted response for tone,
        clarity, empathy and professionalism.

        Returns 0-100 scores with short notes for each dimension.
        """
        text = (text or "").strip()
        text_lower = text.lower()
        words = text_lower.split()
        word_count = len(words)
        sentences = [
            s for s in re.split(r"(?<=[.!?])\s+", text_lower) if s.strip()
        ]
        sentence_count = max(1, len(sentences))

        has_empathy = any(p in text_lower for p in self.EMPATHY_PHRASES)
        has_apology = any(p in text_lower for p in self.APOLOGY_PHRASES)
        has_acknowledgment = any(
            p in text_lower
            for p in ("understand", "frustrat", "inconvenience")
        )
        harsh = any(p in text_lower for p in self.HARSH_PHRASES)
        courtesy = any(p in text_lower for p in self.COURTESY_PHRASES)
        casual_hits = sum(
            1 for p in self.CASUAL_PHRASES if p in text_lower
        )
        timeline = bool(self.TIMELINE_RE.search(text_lower))
        caps_words = [w for w in words if len(w) > 2 and w.isupper()]
        exclaims = text.count("!")
        ends_with_question = text_lower.endswith("?")

        # ---- TONE ---------------------------------------------
        tone = 70
        if has_empathy:
            tone += 10
        if courtesy:
            tone += 8
        if ends_with_question:
            tone += 5
        if harsh:
            tone -= 15
        tone = clamp_score(tone, 5, 100)
        tone_notes = []
        if harsh:
            tone_notes.append("Contains blunt or negative phrasing.")
        elif tone >= 80:
            tone_notes.append("Warm, cooperative tone.")
        else:
            tone_notes.append("Tone is acceptable but could be warmer.")
        tone_result = {"score": tone, "notes": " ".join(tone_notes)}

        # ---- CLARITY -------------------------------------------
        clarity = 75
        if word_count < 8:
            clarity -= 30
        if word_count > 250:
            clarity -= 15
        if timeline:
            clarity += 10
        if word_count / sentence_count > 40:
            clarity -= 10
        clarity = clamp_score(clarity, 5, 100)
        clarity_notes = []
        if word_count < 8:
            clarity_notes.append("Response is too short to be useful.")
        if not timeline:
            clarity_notes.append("No concrete timeline or next step.")
        if word_count / sentence_count > 40:
            clarity_notes.append("Sentences are long — break them up.")
        if not clarity_notes:
            clarity_notes.append("Clear structure with a concrete step.")
        clarity_result = {"score": clarity, "notes": " ".join(clarity_notes)}

        # ---- EMPATHY -------------------------------------------
        empathy = 55
        if has_apology:
            empathy += 15
        if has_acknowledgment:
            empathy += 10
        if frustration_score >= 7 and has_apology:
            empathy += 10
        if harsh:
            empathy -= 20
        if courtesy:
            empathy += 5
        empathy = clamp_score(empathy, 5, 100)
        empathy_notes = []
        if has_apology and has_acknowledgment:
            empathy_notes.append(
                "Apologises and acknowledges the customer's situation."
            )
        elif has_apology:
            empathy_notes.append(
                "Apologises but could acknowledge feelings explicitly."
            )
        elif harsh:
            empathy_notes.append("No empathy shown; phrasing is cold.")
        else:
            empathy_notes.append(
                "Missing an explicit apology or acknowledgement."
            )
        empathy_result = {"score": empathy, "notes": " ".join(empathy_notes)}

        # ---- PROFESSIONALISM ------------------------------------
        professionalism = 80
        professionalism -= min(30, casual_hits * 10)
        if len(caps_words) > 2:
            professionalism -= 10
        if exclaims > 2:
            professionalism -= 5
        if harsh:
            professionalism -= 10
        if re.match(r"^(dear|hello|hi|good)", text_lower):
            professionalism += 5
        professionalism = clamp_score(professionalism, 5, 100)
        prof_notes = []
        if casual_hits:
            prof_notes.append("Casual wording detected.")
        if len(caps_words) > 2:
            prof_notes.append("Excessive capitalisation.")
        if not prof_notes:
            prof_notes.append("Professional, business-appropriate wording.")
        prof_result = {
            "score": professionalism,
            "notes": " ".join(prof_notes),
        }

        overall = clamp_score(
            (tone + clarity + empathy + professionalism) / 4, 5, 100
        )

        dimensions = {
            "tone": tone_result,
            "clarity": clarity_result,
            "empathy": empathy_result,
            "professionalism": prof_result,
        }

        weakest = min(dimensions.items(), key=lambda kv: kv[1]["score"])

        if overall >= 85:
            summary = "Excellent response — ready to send as is."
        elif overall >= 70:
            summary = (
                f"Good response. Improve {weakest[0]} for an even "
                f"better customer experience."
            )
        else:
            summary = (
                f"Needs improvement — focus on {weakest[0]} before "
                f"sending."
            )

        return {
            "tone": tone_result,
            "clarity": clarity_result,
            "empathy": empathy_result,
            "professionalism": prof_result,
            "overall": overall,
            "meets_standard": overall >= 70,
            "summary": summary,
        }

    # ------------------------------------------------------
    # Coaching tips
    # ------------------------------------------------------
    def generate_coaching_tips(
        self,
        *,
        intent: str,
        sentiment: str = "neutral",
        emotion_label: str = "",
        frustration_score: int = 5,
        escalation_level: str = "Low",
        evaluation: Optional[Dict] = None,
        knowledge_used: Optional[List[Dict]] = None,
    ) -> List[str]:
        """
        Provide actionable communication improvement tips combining
        the conversation analysis, the response evaluation and the
        escalation context.
        """
        tips: List[str] = []

        if frustration_score >= 7:
            tips.append(
                "Start by acknowledging the emotion — e.g. “I completely "
                "understand how frustrating this must be.”"
            )
        elif sentiment == "negative":
            tips.append(
                "Open with a short apology before explaining anything "
                "else."
            )

        tips.append(
            "Give a clear next step with a timeline (e.g. “I'm checking "
            "this now and will have an update within 2 minutes.”)."
        )

        if intent == "delayed_order":
            tips.append(
                "Proactively offer delivery-focused options: expedited "
                "shipping, a reshipment, or a confirmed new delivery "
                "date. Stay on the delivery topic the customer raised."
            )
            tips.append(
                "Share the tracking number and expected delivery date "
                "if available."
            )
        elif intent == "refund_request":
            tips.append(
                "Confirm refund eligibility and the exact processing "
                "time (e.g. 3-5 business days)."
            )
        elif intent == "payment_failure":
            tips.append(
                "Reassure the customer that no duplicate charge will "
                "remain and offer an alternative payment method."
            )
        elif intent == "account_issue":
            tips.append(
                "Walk the customer through the reset steps one at a "
                "time instead of all at once."
            )
        elif intent == "cancellation":
            tips.append(
                "Confirm what the customer will lose/gain before "
                "finalising the cancellation."
            )

        if knowledge_used:
            source = knowledge_used[0].get("source", "the policy")
            tips.append(
                f"Ground your answer in the retrieved policy "
                f"({source}) so the customer gets consistent, "
                f"accurate information."
            )

        if escalation_level in ("High", "Critical"):
            tips.append(
                "Escalation risk is high — set expectations early, "
                "offer a concrete resolution, and mention the option "
                "of a supervisor."
            )

        if evaluation:
            for dimension in ("empathy", "clarity", "tone", "professionalism"):
                dim = evaluation.get(dimension) or {}
                if dim.get("score", 100) < 70:
                    tips.append(
                        f"{dimension.capitalize()} scored "
                        f"{dim['score']}/100 — {dim.get('notes', '')}"
                    )

        if not tips:
            tips.append(
                "Keep the response concise, acknowledge the customer's "
                "concern, and provide a clear next step."
            )

        return tips


# ==========================================================
# ESCALATION RISK MONITOR AGENT
# ==========================================================
class EscalationRiskMonitor:
    """
    Continuously monitors a support conversation and recalculates an
    escalation-risk score after every customer message.

    Score composition (0-100):
        supervisor_request      +35
        legal_or_bank_threat    +20
        reputation_threat       +15
        unresolved_issue        +16
        cancellation_threat     +10
        urgency_pressure         +8
        repeated complaints   +18..30  (grows with EVERY repeat of the
                                       same unresolved issue)
        same issue raised again,
        without complaint wording  +6..20 (grows with every repeat)
        high frustration       +5..18
        negative sentiment
        streak (>=2 messages) +10..15
        explicit demand + unresolved compound   +10

    Every component is a pure function of the latest CUSTOMER message
    plus the customer-only conversation context, so the score is
    recalculated (and therefore changes) after every customer reply:
    it rises while the same unresolved issue keeps being raised and
    falls only when the customer's own words show genuine improvement.

    Levels:  Low <25 | Medium 25-49 | High 50-74 | Critical >=75
    """

    INDICATOR_PATTERNS = {
        "supervisor_request": (
            35,
            [
                "supervisor", "manager", "escalate",
                "higher department", "someone else", "real person",
                "human agent", "speak to a", "talk to a",
            ],
        ),
        "legal_or_bank_threat": (
            20,
            [
                "legal action", "lawyer", "consumer court",
                "consumer forum", "consumer protection", "chargeback",
                "bank dispute", "dispute the charge", "report you",
                "sue you", "suing",
            ],
        ),
        "reputation_threat": (
            15,
            [
                "social media", "twitter", "instagram", "facebook",
                "trustpilot", "leave a review", "bad review",
                "one star", "1 star", "tell everyone", "expose",
                "post about this",
            ],
        ),
        "unresolved_issue": (
            16,
            [
                "still", "again", "not resolved", "isn't resolved",
                "unresolved", "no update", "third time", "fourth time",
                "keeps happening", "same issue", "same problem",
                "nothing happened", "no solution", "waiting since",
                "how long", "when will", "contacted support",
                "contacted you", "twice", "two times",
                "nobody has helped", "nobody helped", "no one has helped",
                "no help", "waited", "long enough",
            ],
        ),
        "cancellation_threat": (
            10,
            [
                "cancel my account", "close my account",
                "cancel everything", "take my business", "switch to",
                "never use", "last chance", "done with you",
            ],
        ),
        "urgency_pressure": (
            8,
            [
                "immediately", "right now", "asap", "urgent",
                "as soon as possible", "end of day",
            ],
        ),
    }

    REPEAT_COMPLAINT_MARKERS = [
        "refund", "money back", "not resolved", "unresolved", "still",
        "again", "no update", "when will", "how long", "waiting",
        "keeps happening", "same issue", "same problem", "why",
        "contacted", "twice", "two times", "nobody", "no one",
        "nobody has helped", "no help",
    ]

    INDICATOR_REASONS = {
        "supervisor_request": (
            "Customer explicitly asked for a supervisor / human agent"
        ),
        "legal_or_bank_threat": (
            "Customer threatened legal action or a bank dispute"
        ),
        "reputation_threat": (
            "Customer threatened negative public feedback"
        ),
        "unresolved_issue": (
            "Customer signalled the issue is still unresolved"
        ),
        "cancellation_threat": (
            "Customer threatened to cancel / leave the service"
        ),
        "urgency_pressure": (
            "Customer applied strong urgency pressure"
        ),
    }

    RECOMMENDED_ACTIONS = {
        "Low": [
            "Continue with the current approach.",
            "Confirm the resolution clearly and thank the customer.",
        ],
        "Medium": [
            "Acknowledge the customer's frustration explicitly.",
            "Provide a concrete timeline for the next update.",
            "Double-check that the resolution matches the "
            "customer's expectation.",
        ],
        "High": [
            "Change the response approach — lead with the "
            "solution, not the policy.",
            "Offer a concrete alternative or compensation "
            "proactively.",
            "Flag the conversation for supervisor visibility.",
        ],
        "Critical": [
            "Escalate to a human agent / supervisor immediately.",
            "Apologise sincerely and take full ownership of the "
            "resolution.",
            "Offer a direct callback or priority channel.",
        ],
    }

    # ------------------------------------------------------
    # Lifecycle / configuration
    # ------------------------------------------------------
    def __init__(self, threshold: Optional[int] = None):
        self.threshold = self._validate_threshold(
            DEFAULT_ALERT_THRESHOLD if threshold is None else threshold
        )
        self._sessions: Dict[str, Dict] = {}

    @staticmethod
    def _validate_threshold(value) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            return DEFAULT_ALERT_THRESHOLD
        return max(0, min(100, value))

    def get_threshold(self) -> int:
        return self.threshold

    def set_threshold(self, value: int) -> int:
        """Set the configurable high-escalation alert threshold."""
        self.threshold = self._validate_threshold(value)
        return self.threshold

    def reset_session(self, session_key: str) -> None:
        self._sessions.pop(session_key, None)

    @staticmethod
    def _same_issue(intent: str, current: str, past: str) -> bool:
        """Decide whether a past CUSTOMER message is about the same issue."""
        if not past:
            return False
        if intent != "general_inquiry":
            intent_cues = {
                "refund_request": ["refund", "money back", "return"],
                "delayed_order": [
                    "late", "delay", "tracking", "arrived", "delivery",
                ],
                "payment_failure": ["payment", "charged", "declined", "card"],
                "account_issue": ["login", "password", "locked", "account"],
                "cancellation": ["cancel", "unsubscribe", "billing"],
            }.get(intent, [])
            if intent_cues and any(c in past for c in intent_cues):
                return True
            return any(c in past for c in intent.split("_"))
        current_markers = [
            m for m in EscalationRiskMonitor.REPEAT_COMPLAINT_MARKERS
            if m in current
        ]
        return (
            len(current_markers) >= 2
            and any(m in past for m in current_markers)
        )

    @staticmethod
    def _count_customer_negative_streak(
        current_label: str, customer_past_texts
    ) -> int:
        """
        Trailing negative streak over CUSTOMER history (latest first),
        excluding the message currently being assessed.
        """
        if current_label != "negative":
            return 0
        streak = 0
        for past in reversed(customer_past_texts or []):
            neg = sum(1 for phrase in _NEGATIVE_STREAK_PHRASES if phrase in past)
            words = set(re.findall(r"[a-z']+", past))
            neg += sum(1 for w in words if w in _NEGATIVE_STREAK_WORDS)
            pos = sum(1 for w in words if w in _POSITIVE_STREAK_WORDS)
            if neg > pos:
                streak += 1
            else:
                break
        return streak

    @staticmethod
    def _customer_history_texts(
        history: Optional[List[Dict]],
        _include_roles: bool = False,
    ):
        """
        Extract CUSTOMER-written text from a role-tagged history.

        Agent/support entries (role agent/support/assistant/bot/system,
        or matching author/speaker/sender markers) are dropped, so
        agent politeness can never dilute customer signals. Entries
        without a role are treated as customer text to stay backward
        compatible.

        With `_include_roles=True` each entry is returned as a
        `(role, text)` tuple so context-sensitive callers can tell
        genuine customer repeats apart from agent echo.
        """
        texts: List[str] = []
        for item in history or []:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "customer") or "customer").lower()
            agent_markers = [
                str(item.get("author", "") or "").lower(),
                str(item.get("speaker", "") or "").lower(),
                str(item.get("sender", "") or "").lower(),
                str(item.get("from", "") or "").lower(),
            ]
            if role in ("agent", "support", "assistant", "bot", "system"):
                continue
            if any(
                m in ("agent", "support", "assistant", "bot")
                for m in agent_markers
            ):
                continue
            content = (
                item.get("content")
                if item.get("content") is not None
                else item.get("message", "")
            )
            content = str(content or "").strip()
            if not content:
                continue
            if _include_roles:
                texts.append((role, content.lower()))
            else:
                texts.append(content.lower())
        return texts

    @staticmethod
    def _repeat_issue_customers_only(
        intent: str,
        current: str,
        customer_history_with_roles,
    ) -> List:
        """
        Return the CUSTOMER history entries that describe the same
        issue as `current`. Agent entries are never consulted, so an
        agent repeating the complaint ("still waiting?", "twice"?)
        cannot manufacture a false repeat signal.
        """
        repeats = []
        for entry in customer_history_with_roles or []:
            if isinstance(entry, tuple):
                role, past = entry
            else:
                role, past = "customer", str(entry)
            if role != "customer":
                continue
            if EscalationRiskMonitor._same_issue(intent, current, past):
                repeats.append(past)
        return repeats

    @staticmethod
    def _agent_entries(history: Optional[List[Dict]]) -> List[str]:
        """AGENT/support-written history entries, lowercased."""
        out: List[str] = []
        for item in history or []:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "") or "").lower()
            markers = [
                str(item.get("author", "") or "").lower(),
                str(item.get("speaker", "") or "").lower(),
                str(item.get("sender", "") or "").lower(),
                str(item.get("from", "") or "").lower(),
            ]
            is_agent = role in (
                "agent", "support", "assistant", "bot", "system"
            ) or any(
                m in ("agent", "support", "assistant", "bot")
                for m in markers
            )
            if not is_agent:
                continue
            content = (
                item.get("content")
                if item.get("content") is not None
                else item.get("message", "")
            )
            content = str(content or "").strip()
            if content:
                out.append(content.lower())
        return out

    def _context_from_history(
        self,
        customer_history: Optional[List[Dict]],
        current_text_lower: str,
    ) -> Tuple[List, List[str]]:
        """
        Split a role-tagged conversation into
        (customer history with roles, agent history).

        The message currently being assessed is REMOVED from the
        customer history when the caller passed the whole conversation
        (as the UI does), so it can never be counted as its own
        "previous" message - no double-counted streaks or repeats.
        """
        roles = self._customer_history_texts(
            customer_history, _include_roles=True
        )
        if roles:
            last_role, last_text = roles[-1]
            if last_role == "customer" and last_text.strip() == (
                current_text_lower or ""
            ).strip():
                roles = roles[:-1]
        return roles, self._agent_entries(customer_history)

    @staticmethod
    def _resolution_state(
        customer_past_texts: List,
        agent_past_texts: List[str],
    ) -> Dict:
        """
        Decide whether the issue is STILL OPEN or shows genuine
        resolution progress, using only evidence — never politeness.

        Returns {"status": "open"|"unknown"|"offered"|"resolved",
                 "evidence": [...]} where:
        - "resolved"  only the CUSTOMER confirms a fix ("thank you,
                      it's resolved now"). A NEGATED mention such as
                      "not resolved" never counts.
        - "offered"   the AGENT gave a concrete commitment ("within
                      2 days", "I have escalated") AND the customer
                      does not contradict it in any later customer
                      message.
        - "open"      the customer restates an unmet need after any
                      agent reply, or nothing suggests a fix.
        """
        past_customers = [
            t[1] if isinstance(t, tuple) else str(t)
            for t in (customer_past_texts or [])
        ]

        def _phrases(texts, vocab):
            hits = []
            for text in texts:
                for phrase in vocab:
                    if phrase in text and phrase not in hits:
                        hits.append(phrase)
            return hits

        # "not resolved" / "isn't fixed" must never read as resolved.
        customer_resolved = [
            t for t in past_customers
            if _phrases([t], _CUSTOMER_RESOLUTION_WORDS)
            and _has_unnegated(t, _CUSTOMER_RESOLUTION_WORDS)
        ]
        customer_requests = [
            t for t in past_customers
            if _phrases([t], _RESOLUTION_REQUEST_WORDS)
        ]
        agent_commitments: List[str] = []
        for text in agent_past_texts or []:
            for match in _AGENT_COMMITMENT_RE.finditer(text):
                phrase = match.group(0).strip()
                if phrase and phrase not in agent_commitments:
                    agent_commitments.append(phrase)

        if customer_resolved and not customer_requests:
            return {
                "status": "resolved",
                "evidence": _phrases(
                    customer_resolved, _CUSTOMER_RESOLUTION_WORDS
                ),
            }
        if agent_commitments and not customer_requests:
            return {"status": "offered", "evidence": agent_commitments}
        if customer_requests:
            return {
                "status": "open",
                "evidence": _phrases(
                    customer_requests, _RESOLUTION_REQUEST_WORDS
                ),
            }
        return {"status": "unknown", "evidence": []}

    @staticmethod
    def _tone_worsening(
        current_text: str,
        current_label: str,
        current_frustration: int,
        customer_past_texts: List,
        agent_past_texts: List[str],
    ) -> Tuple[bool, List[str], int]:
        """
        Compare the CURRENT customer message with its CUSTOMER context.

        Returns (worsening, evidence, points) where `points` is
        PROPORTIONAL to the unresolved/urgency markers actually found in
        the message plus the repeat signals already present in the
        customer's earlier messages - there is no flat per-message
        penalty, and no points at all when there is no concrete
        evidence.
        """
        evidence: List[str] = []
        past_customers = [
            t[1] if isinstance(t, tuple) else str(t)
            for t in (customer_past_texts or [])
        ]
        intensity_markers = [
            "long enough", "fed up", "still", "again", "yet", "waiting",
            "waited", "never", "nobody", "no one", "no help",
            "twice", "two times", "three times", "multiple times",
            "contacted support", "contacted you", "unresolved",
            "not resolved", "no solution", "nothing happened",
            "immediately", "urgent", "urgently", "right now", "asap",
            "furious", "unacceptable", "ridiculous", "terrible",
            "worst", "horrible", "pathetic", "disgusted",
            "supervisor", "manager", "escalate",
        ]
        marker_count = sum(
            1 for marker in intensity_markers if marker in current_text
        )
        if marker_count:
            evidence.append(
                f"{marker_count} unresolved/urgency marker(s) in the "
                "latest customer message."
            )
        repeat_signals = sum(
            1 for t in past_customers
            for marker in (
                "still", "again", "yet", "waiting", "waited", "twice",
                "two times", "nobody", "no one", "no help",
                "contacted support", "contacted you",
            )
            if marker in t
        )
        if past_customers and repeat_signals:
            evidence.append(
                "Earlier customer message(s) already described the same "
                "unresolved issue."
            )

        # Points scale with the evidence found; a merely negative message
        # with no unresolved/urgency marker and no repeat context adds
        # nothing here.
        points = 0
        if marker_count or repeat_signals:
            points = min(8, 2 + marker_count + min(4, repeat_signals))
        worsening = bool(marker_count or repeat_signals)
        return worsening, evidence, points

    def _empty_state(self, session_key: str) -> Dict:
        return {
            "session_key": session_key,
            "message_count": 0,
            "negative_streak": 0,
            "intent_counts": {},
            "assessments": [],
            "alerts": [],
            "last_signature": None,
            "last_result": None,
            # Analysis snapshot for the latest CUSTOMER message only:
            # {"intent", "emotion", "frustration", "sentiment"}.
            "last_analysis": None,
            # Last CUSTOMER-written text (used only to detect customer
            # repeats; agent text is never stored here).
            "last_customer_message": None,
            # Analysis of the PREVIOUS customer message (for
            # satisfaction-trend evidence comparison).
            "previous_analysis": None,
        }

    def get_state(self, session_key: str) -> Dict:
        """Return a snapshot of the monitor state for a session."""
        state = self._sessions.get(session_key)
        if not state:
            return {
                "session_key": session_key,
                "message_count": 0,
                "negative_streak": 0,
                "intent_counts": {},
                "assessments": [],
                "alerts": [],
                "current": None,
            }
        return {
            "session_key": session_key,
            "message_count": state["message_count"],
            "negative_streak": state["negative_streak"],
            "intent_counts": dict(state["intent_counts"]),
            "assessments": list(state["assessments"]),
            "alerts": list(state["alerts"]),
            "current": state["last_result"],
            "previous_analysis": state.get("previous_analysis"),
        }

    def assess_non_customer_message(
        self,
        session_key: str,
        agent_message: str,
        turn=None,
    ):
        """
        No-op assessment for AGENT/support messages.

        Returns (last_risk_result, last_intent, last_emotion,
        last_frustration, last_sentiment) WITHOUT mutating any
        customer state: message counts, streaks, intent counts,
        assessments, alerts and signatures are untouched, so agent
        replies can never move customer risk or emotion.
        """
        state = self._sessions.setdefault(
            session_key, self._empty_state(session_key)
        )
        last = state["last_result"]

        if last is None:
            empty_alert = {
                "triggered": False,
                "threshold": self.threshold,
                "score": 0,
                "level": "Low",
                "triggered_at": None,
                "message": None,
                "recommended_actions": self.RECOMMENDED_ACTIONS["Low"],
            }
            return (
                {
                    "session_key": session_key,
                    "turn": turn if turn is not None else 0,
                    "escalation_score": 0,
                    "risk_score": 0,
                    "escalation_level": "Low",
                    "escalation_risk": "Low",
                    "trend": "first_message",
                    "indicators": [],
                    "reasoning": [
                        "No customer message assessed yet — agent "
                        "text is never analysed as customer state."
                    ],
                    "alert": empty_alert,
                    "recommended_actions": empty_alert[
                        "recommended_actions"
                    ],
                    "message_count": 0,
                    "negative_streak": 0,
                    "assessed_at": _utc_now_iso(),
                    # Customer state is unknown until a customer
                    # message has actually been assessed.
                    "intent": "general_inquiry",
                    "emotion": "",
                    "emotion_label": "",
                    "frustration": 5,
                    "frustration_level": 5,
                    "sentiment": {
                        "label": "neutral",
                        "score": 0.0,
                        "confidence": 0.4,
                    },
                    "sentiment_label": "neutral",
                    "satisfaction_trend": "unknown",
                    "unaddressed_pressure": False,
                    "de_escalation": "none",
                    "calm_evidence": [],
                    "state_drivers": [],
                },
                "general_inquiry",
                "",
                5,
                {
                    "label": "neutral",
                    "score": 0.0,
                    "confidence": 0.4,
                },
            )

        last_analysis = state.get("last_analysis") or {}
        return (
            last,
            last_analysis.get("intent", "general_inquiry"),
            last_analysis.get("emotion", ""),
            last_analysis.get("frustration", 5),
            last_analysis.get(
                "sentiment",
                {
                    "label": "neutral",
                    "score": 0.0,
                    "confidence": 0.4,
                },
            ),
        )

    # ------------------------------------------------------
    # Shared customer-message state (single source of truth)
    # ------------------------------------------------------
    def _customer_state_from_evidence(
        self,
        text_lower: str,
        customer_past_texts,
        agent_past_texts: Optional[List[str]] = None,
        previous_state: Optional[Dict] = None,
    ) -> Dict:
        """
        Recalculate the customer's emotion, emotion intensity and
        sentiment from the LATEST customer message PLUS the previous
        customer state and the conversation context.

        This is the ONLY place where the displayed emotion/frustration
        of a customer message is produced, so the UI values can never
        disagree with each other. Rules (evidence only):

        * the severity of the latest message is the base signal;
        * unresolved / repeated / urgent / escalation evidence raises it;
        * frustration may only FALL when the CUSTOMER'S message carries
          calming evidence (resolution confirmation, appreciation,
          positive language, understanding) or the agent gave a
          concrete, uncontradicted commitment - and the drop is
          proportional to that evidence, never a fixed -1/-2/-3;
        * a mildly negative or still-unresolved message can therefore
          never make a furious state collapse: without de-escalation
          evidence the running value is HELD;
        * nothing is ever changed randomly and nothing is ever driven
          by the turn number.
        """
        intent = ac_detect_intent(text_lower)
        _base_label, message_level = ac_detect_emotion(text_lower)
        analysed = ac_detect_sentiment(text_lower)
        sentiment_label = analysed.get("label", "neutral")
        sentiment_score = analysed.get("score", 0.0)
        sentiment_confidence = analysed.get("confidence", 0.4)

        past_customers = [
            t[1] if isinstance(t, tuple) else str(t)
            for t in (customer_past_texts or [])
        ]

        # ---- evidence in the LATEST message -------------------
        open_evidence = sorted(
            p for p in _RESOLUTION_REQUEST_WORDS if p in text_lower
        )
        unresolved_evidence = sorted(
            p for p in _UNRESOLVED_MARKERS if p in text_lower
        )
        repeat_evidence = sorted(
            p for p in _REPEAT_MARKERS if p in text_lower
        )
        escalation_evidence = sorted(
            p for p in _ESCALATION_DEMAND_MARKERS if p in text_lower
        )
        urgency_evidence = sorted(
            p for p in _URGENCY_MARKERS if p in text_lower
        )

        # An unmet need expressed together with unresolved history is
        # NEGATIVE: "I have waited long enough. I need this resolved
        # immediately." is not a neutral request.
        history_negative = any(
            self._count_customer_negative_streak("negative", [past]) >= 1
            for past in past_customers
        )
        if sentiment_label != "negative":
            if open_evidence and (unresolved_evidence or history_negative):
                sentiment_label = "negative"
                sentiment_score = min(-0.5, sentiment_score - 0.5)
                sentiment_confidence = max(0.6, sentiment_confidence)

        negative = sentiment_label == "negative"

        # ---- resolution state from the whole conversation -----
        resolution = self._resolution_state(
            customer_past_texts, agent_past_texts or []
        )
        resolved_now = _has_unnegated(text_lower, _CUSTOMER_RESOLUTION_WORDS)

        # ---- calming evidence (customer-written only) ---------
        calm_evidence: List[str] = []

        def _add_calm(name: str, present: bool) -> None:
            if present and name not in calm_evidence:
                calm_evidence.append(name)

        _add_calm("resolution confirmed", resolved_now)
        _add_calm(
            "appreciation",
            _has_unnegated(text_lower, _CALM_APPRECIATION_WORDS),
        )
        _add_calm(
            "positive language",
            _has_unnegated(text_lower, _CALM_POSITIVE_WORDS),
        )
        understanding_match = _CALM_UNDERSTANDING_RE.search(text_lower)
        _add_calm(
            "understanding",
            bool(understanding_match) and not _NEGATION_RE.search(
                text_lower[
                    max(0, understanding_match.start() - 24):
                    understanding_match.start()
                ]
            ) if understanding_match else False,
        )

        agent_commitment = None
        for agent_text in agent_past_texts or []:
            match = _AGENT_COMMITMENT_RE.search(agent_text or "")
            if match:
                agent_commitment = match.group(0).strip()
                break
        # A concrete commitment only counts while the customer has not
        # contradicted it and is no longer negative.
        _add_calm(
            "agent commitment",
            bool(agent_commitment)
            and not negative
            and not (unresolved_evidence or repeat_evidence
                     or escalation_evidence),
        )

        calming_strength = sum(
            _CALM_EVIDENCE_WEIGHTS.get(name, 0.0) for name in calm_evidence
        )
        if resolved_now:
            calming_strength = 1.0
        calming_strength = min(1.0, round(calming_strength, 2))

        # ---- is the customer's concern still NOT addressed? ---
        repeat_history = self._repeat_issue_customers_only(
            intent, text_lower, customer_past_texts
        )
        open_pressure = bool(
            open_evidence or unresolved_evidence or repeat_evidence
            or escalation_evidence or urgency_evidence
        )
        unaddressed_pressure = bool(
            open_pressure or repeat_history or negative
        )

        # ---- message-level target (context may only RAISE it) --
        target = message_level
        if escalation_evidence:
            target = max(target, 9)
        elif repeat_evidence and (unresolved_evidence or open_evidence):
            target = max(target, 7)
        elif urgency_evidence and negative:
            target = max(target, 7)
        target = max(1, min(10, int(target)))


        # ---- blend with the customer's RUNNING state ----------
        previous_level = None
        if isinstance(previous_state, dict):
            try:
                previous_level = int(previous_state.get("frustration"))
            except (TypeError, ValueError):
                previous_level = None
            if previous_level is not None and not 1 <= previous_level <= 10:
                previous_level = None

        drivers: List[str] = []

        if previous_level is None:
            level = target
            drivers.append(
                f"First customer message: frustration {level}/10 taken "
                "from the message itself."
            )
        elif target >= previous_level:
            level = target
            if target > previous_level:
                drivers.append(
                    "Latest customer message is harder than the running "
                    f"state ({previous_level} -> {target}/10)."
                )
            else:
                drivers.append(
                    "Latest customer message carries the same pressure as "
                    f"the running state ({previous_level}/10) - held, "
                    "not reduced."
                )
        elif resolved_now:
            level = target
            drivers.append(
                "Customer confirmed the issue is resolved - frustration "
                f"released {previous_level} -> {target}/10."
            )
        elif calming_strength >= 0.5 and not unaddressed_pressure:
            step = max(2, round((previous_level - target) * 0.7))
            level = max(target, previous_level - step)
            drivers.append(
                f"Strong calming evidence ({', '.join(calm_evidence)}) - "
                f"proportional release {previous_level} -> {level}/10."
            )
        elif calming_strength >= 0.15 and not unaddressed_pressure:
            step = max(1, round((previous_level - target) * 0.35))
            level = max(target, previous_level - step)
            drivers.append(
                f"Calming evidence ({', '.join(calm_evidence)}) allows a "
                f"proportional easing {previous_level} -> {level}/10."
            )
        else:
            level = previous_level
            pressure_note = (
                "issue still open/repeated"
                if unaddressed_pressure else "no calming language"
            )
            drivers.append(
                "No de-escalation evidence in this message "
                f"({pressure_note}) - frustration held at "
                f"{previous_level}/10 instead of dropping."
            )

        level = max(1, min(10, int(level)))

        # ---- how much genuine de-escalation evidence is there? --
        if resolved_now or (
            sentiment_label == "positive" and not unaddressed_pressure
        ):
            de_escalation = "strong"
        elif calming_strength >= 0.15 and not unaddressed_pressure:
            de_escalation = "moderate"
        else:
            de_escalation = "none"

        return {
            "intent": intent,
            "emotion_label": emotion_label_for_level(level),
            "frustration": level,
            "message_level": message_level,
            "sentiment_label": sentiment_label,
            "sentiment_score": round(sentiment_score, 3),
            "sentiment_confidence": round(sentiment_confidence, 3),
            "resolution": resolution,
            "resolved_now": resolved_now,
            "agent_commitment": agent_commitment,
            "calm_evidence": calm_evidence,
            "calming_strength": calming_strength,
            "open_evidence": open_evidence,
            "unresolved_evidence": unresolved_evidence,
            "repeat_evidence": repeat_evidence,
            "escalation_evidence": escalation_evidence,
            "urgency_evidence": urgency_evidence,
            "repeat_history": repeat_history,
            "unaddressed_pressure": unaddressed_pressure,
            "de_escalation": de_escalation,
            "drivers": drivers,
        }

    # ------------------------------------------------------
    # Backwards-compatible analysis helper
    # ------------------------------------------------------
    def _analyse_customer_message(
        self,
        text_lower: str,
        customer_past_texts,
        agent_past_texts: Optional[List[str]] = None,
        previous_state: Optional[Dict] = None,
    ) -> Dict:
        """
        Thin wrapper: the customer state for one message (+ context and,
        when provided, the running customer state) with no risk scoring.
        """
        return self._customer_state_from_evidence(
            text_lower,
            customer_past_texts,
            agent_past_texts,
            previous_state,
        )

    @staticmethod
    def _satisfaction_trend(
        *,
        first_message: bool,
        escalation_trend: str,
        sentiment_label: str,
        unaddressed_pressure: bool,
        de_escalation: str,
    ) -> str:
        """
        Satisfaction trend from the SAME evidence as the risk score, so
        it can never contradict the escalation trend:

        * risk rising            -> satisfaction declining
        * risk falling           -> satisfaction improving
        * risk unchanged         -> negative/unresolved stays declining,
                                    clear positive evidence improves,
                                    otherwise steady.

        A still-unresolved complaint therefore never reports "improving".
        """
        if first_message:
            return "unknown"
        if escalation_trend == "increasing":
            return "declining"
        if escalation_trend == "decreasing":
            return "improving"
        if sentiment_label == "negative" or unaddressed_pressure:
            return "declining"
        if sentiment_label == "positive" and de_escalation != "none":
            return "improving"
        return "steady"

    # ------------------------------------------------------
    # Core assessment
    # ------------------------------------------------------
    def assess(
        self,
        session_key: str,
        customer_message: str,
        *,
        intent: str = "general_inquiry",
        sentiment="neutral",
        emotion_label: str = "",
        frustration_score: int = 5,
        turn=None,
        threshold_override: Optional[int] = None,
        customer_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Assess one CUSTOMER message and update the session risk state.

        Role contract (enforced end to end):
        - The caller must ONLY pass customer-written text here.
          Agent/support replies must go through
          `assess_non_customer_message`, which is a pure no-op.
        - The provided `customer_history` is filtered to
          customer-role entries before use; any agent entries are
          ignored for risk, streak, repeat and complaint signals.

        Score composition (computed fresh for every assessment from
        the latest customer message + customer history context, NOT
        a fixed +/-N per turn):
        - explicit indicators found in the latest customer message,
        - frustration read from the latest customer message,
        - negative-sentiment streak over CUSTOMER messages,
        - repeat/repeat-complaint signals over CUSTOMER messages, where
          the pressure GROWS with every additional raising of the same
          unresolved issue (the 4th raising is worth more than the 3rd)
          so an unresolved conversation keeps moving the score instead
          of freezing at a fixed value.

        Idempotent: re-assessing the exact same message and turn
        returns the previous result without double counting.
        """
        # NOTE (assessed-later clamp): `frustration_score` is an
        # internal handoff between the pipeline and this monitor. It
        # must ALWAYS be re-derived from the assessed CUSTOMER message
        # + CUSTOMER context. A stale/fixed value from the caller can
        # never set the risk on its own.
        if isinstance(sentiment, dict):
            sentiment_label = sentiment.get("label", "neutral")
        else:
            sentiment_label = sentiment
        if sentiment_label not in VALID_SENTIMENTS:
            sentiment_label = "neutral"

        state = self._sessions.setdefault(
            session_key, self._empty_state(session_key)
        )

        message = (customer_message or "").strip()
        text_lower = message.lower()

        # Idempotency FIRST: re-assessing the exact same message + turn
        # must return the cached result and must never move the
        # stateful customer values twice.
        signature = hashlib.md5(
            f"{turn}|{text_lower}".encode("utf-8")
        ).hexdigest()
        if (
            state["last_signature"] == signature
            and state["last_result"] is not None
        ):
            return state["last_result"]

        customer_history_roles, agent_past_texts = (
            self._context_from_history(customer_history, text_lower)
        )
        customer_past_texts = [text for _, text in customer_history_roles]

        # Re-derive the CUSTOMER state (intent / emotion / frustration /
        # sentiment) from the message + customer context + the customer's
        # RUNNING state, so a stale caller value can never set the risk
        # and a mildly negative message can never collapse a furious
        # state (see `_customer_state_from_evidence`).
        analysis = self._customer_state_from_evidence(
            text_lower,
            customer_history_roles,
            agent_past_texts,
            state.get("last_analysis"),
        )
        intent = analysis["intent"]
        emotion_label = analysis["emotion_label"]
        frustration_score = analysis["frustration"]
        sentiment_label = analysis["sentiment_label"]
        sentiment = {
            "label": sentiment_label,
            "score": analysis["sentiment_score"],
            "confidence": analysis["sentiment_confidence"],
        }
        resolution = analysis["resolution"]
        resolved_now = analysis["resolved_now"]
        de_escalation = analysis["de_escalation"]
        unaddressed_pressure = analysis["unaddressed_pressure"]
        calm_evidence = analysis["calm_evidence"]
        state_drivers = analysis["drivers"]

        indicators: List[Dict] = []
        reasoning: List[str] = []
        score = 0

        worsening, tone_evidence, tone_points = self._tone_worsening(
            text_lower,
            sentiment_label,
            frustration_score,
            customer_history_roles,
            agent_past_texts,
        )
        repeat_matches = analysis["repeat_history"]

        def _add(name, points, matched, reason):
            nonlocal score
            score_points = int(points)
            score += score_points
            indicators.append({
                "name": name,
                "points": score_points,
                "matched_phrase": matched,
            })
            reasoning.append(f"{reason} (+{score_points}).")

        # ---- Resolution progress ---------------------------------
        # NO fixed per-turn easing: risk responds proportionally to the
        # actual customer message + context. "resolved"/"offered" only
        # SUPPRESS open-issue pressure below; they never subtract a
        # constant, and an agent reply alone can never lower the score.
        resolved_eased = resolution["status"] in ("resolved", "offered")
        if resolved_eased and (
            unaddressed_pressure or repeat_matches
        ):
            # Only reported when it actually changed the outcome.
            if resolution["status"] == "resolved":
                reasoning.append(
                    "Customer confirmed the issue is resolved "
                    f"({', '.join(resolution['evidence']) or 'explicit confirmation'}"
                    ") — no open-issue pressure added."
                )
            else:
                reasoning.append(
                    "Agent gave a concrete commitment and the customer has "
                    "not contradicted it "
                    f"({', '.join(resolution['evidence'])}) — no repeated-"
                    "complaint pressure added."
                )

        # ---- Phrase-based indicators --------------------------
        for name, (points, phrases) in self.INDICATOR_PATTERNS.items():
            matched = next(
                (p for p in phrases if p in text_lower), None
            )
            if matched:
                _add(name, points, matched, self.INDICATOR_REASONS[name])

        # ---- High frustration ---------------------------------
        # Read ONLY from the latest CUSTOMER message.
        if frustration_score >= 9:
            _add(
                "furious_customer", 18, emotion_label,
                "Customer is furious — very high frustration level",
            )
        elif frustration_score >= 8:
            _add(
                "very_high_frustration", 14, emotion_label,
                "Very high frustration level expressed",
            )
        elif frustration_score >= 7:
            _add(
                "elevated_frustration", 10, emotion_label,
                "Elevated frustration level expressed",
            )
        elif frustration_score >= 6:
            _add(
                "mild_frustration", 5, emotion_label,
                "Mildly elevated frustration",
            )

        # ---- Negative sentiment streak (CUSTOMER messages only) ----
        # Uses provided customer history when available so a restart
        # or an adhoc request still sees the real streak; falls back
        # to the in-memory counter otherwise. Agent entries were
        # already filtered out of `customer_past_texts`.
        past_negative_streak = self._count_customer_negative_streak(
            sentiment_label, customer_past_texts,
        )
        if sentiment_label == "negative":
            state["negative_streak"] = max(
                state["negative_streak"] + 1, past_negative_streak + 1,
            )
        elif (
            state["negative_streak"] >= 2
            and resolution["status"] in ("open", "unknown")
            and (repeat_matches or unaddressed_pressure)
        ):
            # Nothing has been fixed and the customer is still pressing
            # on the SAME open issue: a neutral re-statement of it
            # continues the pressure streak instead of erasing it.
            # A genuinely calmer message (no unresolved/repeat
            # pressure) still resets the streak below.
            state["negative_streak"] = max(
                state["negative_streak"], past_negative_streak,
            )
        else:
            state["negative_streak"] = 0

        streak = state["negative_streak"]
        if streak >= 2 and not resolved_eased:
            streak_points = 10 + min(5, 5 * (streak - 2))
            # The streak reflects the customer's OWN consecutive
            # negativity — it is context, not a fixed per-turn step.
            # It never fires when the latest message itself shows
            # genuine resolution progress.
            _add(
                "negative_streak", streak_points, f"streak={streak}",
                f"Negative sentiment in {streak} consecutive "
                "customer messages",
            )
        elif streak >= 2 and resolved_eased:
            reasoning.append(
                "Negative streak present, but the latest customer "
                "message shows resolution progress — no streak "
                "pressure added."
            )

        # ---- Repeated complaints (CUSTOMER messages only) --------
        # Context comes from customer-role history entries (agent
        # replies excluded) plus the monitor's in-memory counters.
        markers_hit = sum(
            1 for m in self.REPEAT_COMPLAINT_MARKERS if m in text_lower
        )
        complaint_like = markers_hit >= 2
        # Repeats are counted from CUSTOMER messages only (same issue,
        # agent echo excluded) plus the session's in-memory counters.
        history_repeats = len(repeat_matches)
        counter_repeats = state["intent_counts"].get(intent, 0)
        # `mentions` counts EVERY CUSTOMER message that raised this same
        # issue, including the one being assessed. It drives the
        # repeat-pressure curve below, so the risk keeps moving while a
        # conversation stays unresolved.
        mentions = max(counter_repeats, history_repeats, 0) + 1
        repeats = mentions - 1

        # A single customer message that BOTH names an unresolved
        # issue AND proves repetition ("twice", "contacted support",
        # "nobody has helped", ...) is itself a repeated complaint:
        # repeated, unresolved and high-frustration signals compound.
        explicit_repeat_evidence = any(
            phrase in text_lower
            for phrase in (
                "contacted support", "contacted you", "twice",
                "two times", "three times", "multiple times",
                "again and again", "nobody has helped",
                "nobody helped", "no one has helped",
                "still no", "still not",
            )
        )
        unresolved_signals = (
            "unresolved" in text_lower
            or "not resolved" in text_lower
            or "no solution" in text_lower
            or "nothing happened" in text_lower
        )

        # Repeat pressure may only be ADDED by a message that still
        # carries pressure of its own. A calm/positive or confirmed-
        # resolved reply must never look like "the customer raised the
        # same issue again", otherwise a satisfied customer's risk score
        # would climb while the conversation is actually improving.
        message_pressure = (
            sentiment_label == "negative"
            or unaddressed_pressure
            or explicit_repeat_evidence
            or unresolved_signals
        )
        repeat_pressure_allowed = not resolved_eased and message_pressure

        if complaint_like and not resolved_eased:
            # Repeat pressure scales with how many CUSTOMER times the
            # same issue was raised — derived from this message's own
            # evidence, never a fixed per-turn delta.
            repeat_points = repeated_complaint_points(
                mentions if mentions >= 2 else 2
            )
            if repeats >= 1 or explicit_repeat_evidence:
                total_mentions = mentions if mentions >= 2 else 2
                _add(
                    "repeated_complaint", repeat_points,
                    f"mentions={total_mentions}",
                    f"Repeated complaint: issue '{intent}' raised "
                    f"{total_mentions} times across customer messages "
                    "(repeat pressure grows with every unresolved "
                    "repeat)",
                )
            else:
                _add(
                    "complaint_language",
                    repeated_complaint_points(1), intent,
                    "Strong complaint language about "
                    f"'{intent}'",
                )
        elif complaint_like and resolved_eased:
            reasoning.append(
                "Complaint language present, but the message shows "
                "genuine resolution progress — no repeat pressure "
                "added."
            )
        elif explicit_repeat_evidence and unresolved_signals:
            _add(
                "repeated_unresolved", 18, intent,
                f"Repeated unresolved complaint about '{intent}' "
                "stated in this customer message",
            )
        elif mentions >= 3 and repeat_pressure_allowed:
            # Count-only inference: the same issue came up again without
            # complaint wording, so it may only add pressure while this
            # message itself still carries unresolved pressure.
            _add(
                "raised_before", raised_before_points(mentions),
                f"mentions={mentions}",
                f"Customer has raised '{intent}' {mentions} times "
                "- an unresolved issue raised again keeps adding "
                "pressure",
            )

        # ---- Compound escalation: explicit demand + unresolved ----
        # A customer who demands a supervisor/escalation while the
        # issue is demonstrably unresolved is escalating, not just
        # venting: add a compound bonus so HIGH/CRITICAL can trigger.
        explicit_demand = any(
            phrase in text_lower
            for phrase in (
                "supervisor", "manager", "escalate", "human agent",
                "real person", "someone else",
            )
        )
        unresolved_context = (
            any(
                name == "unresolved_issue" for name in
                [i["name"] for i in indicators]
            )
            or explicit_repeat_evidence
            or mentions >= 2
        )
        if explicit_demand and unresolved_context:
            _add(
                "demand_plus_unresolved", 10, "escalation demand",
                "Escalation demand combined with an unresolved "
                "issue",
            )

        # ---- Unmet urgent demand --------------------------------
        # "I have waited long enough. I need this resolved
        # immediately." — a furious, negative, URGENT demand on an
        # open issue is high risk even without a supervisor request.
        urgent_demand = (
            sentiment_label == "negative"
            and frustration_score >= 8
            and any(
                phrase in text_lower
                for phrase in ("immediately", "urgent", "urgently",
                               "asap", "right now", "long enough",
                               "end of day")
            )
        )
        issue_open = resolution["status"] in ("open", "unknown")
        if urgent_demand and issue_open:
            _add(
                "urgent_unmet_demand", 12, "urgent demand, issue open",
                "Customer demands an immediate resolution while the "
                "issue is still unresolved",
            )

        # ---- Tone drift vs CUSTOMER context ---------------------
        # The risk must not fall just because an agent reply was
        # polite: unresolved/urgency markers plus repeat context add
        # PROPORTIONAL pressure while the issue stays open.
        if (
            worsening
            and tone_points
            and resolution["status"] in ("open", "unknown")
            and not resolved_eased
        ):
            _add(
                "tone_holding_or_worsening", tone_points,
                "unresolved/urgency markers in the latest message",
                "Customer tone is holding or worsening while the "
                "issue stays open",
            )
            for line in tone_evidence:
                reasoning.append(f"Tone context: {line}")

        # ---- Final score: recomputed from THIS reply + context ----
        # Every customer reply triggers a FRESH score (computed above
        # from the latest message + conversation context: indicators,
        # frustration, negative streak, repeats, urgency, resolution).
        # The previous score is never reused as the value - it is only
        # the reference that decides whether the fresh evidence shows
        # genuine improvement:
        #   * fresh score above previous      -> used as-is (pressure
        #     evidence raises risk immediately)
        #   * fresh score lower WITH strong
        #     de-escalation/resolution evidence in THIS message
        #     -> used as-is (full evidence-based drop)
        #   * fresh score lower WITH moderate calming evidence
        #     -> eased proportionally to the gap (never a fixed
        #     per-turn delta, and only while the issue is open)
        #   * fresh score lower WITHOUT any improvement evidence
        #     (message still negative / issue still unresolved /
        #     no calming language) -> stays at the previous level:
        #     a milder phrasing alone is not evidence that anything
        #     got better, and risk must stay consistent with the
        #     still-high frustration and negative sentiment.
        # Agent replies never reach this method, so an agent
        # apology alone can never move the risk. Direction and size
        # of every change come from the message content, never from
        # the turn number.
        previous = (
            state["assessments"][-1]["score"]
            if state["assessments"] else None
        )
        score = clamp_score(score)

        if previous is None:
            reasoning.append(
                f"Risk initialised at {score}/100 from this first "
                "customer message."
            )
        elif score > previous:
            reasoning.append(
                f"Risk recalculated {previous} -> {score}/100: this "
                "customer message adds escalation evidence in context."
            )
        elif score < previous and (
            de_escalation == "strong" or resolved_now
        ):
            resolution_evidence = ", ".join(
                resolution.get("evidence") or []
            )
            drop_evidence = (
                ", ".join(calm_evidence)
                or resolution_evidence
                or "positive, pressure-free language"
            )
            reasoning.append(
                f"Risk recalculated {previous} -> {score}/100: the "
                "latest customer message shows genuine de-escalation "
                f"evidence ({drop_evidence})."
            )
        elif score < previous and de_escalation == "moderate":
            step = max(1, round((previous - score) * 0.4))
            score = max(score, previous - step)
            reasoning.append(
                f"Risk eased {previous} -> {score}/100: calming "
                "evidence in this customer message lowers pressure, "
                "but the issue is not confirmed resolved yet "
                f"({', '.join(calm_evidence) or 'calming language'})."
            )
        elif score < previous:
            # Recalculated fresh - and the fresh evidence shows no
            # improvement, so the lower number only reflects milder
            # phrasing, not a better situation.
            score = previous
            pressure_note = (
                "issue still negative/unresolved"
                if unaddressed_pressure or sentiment_label == "negative"
                else "no de-escalation evidence"
            )
            reasoning.append(
                f"Risk recalculated at {score}/100 with no lowering "
                f"evidence in this message ({pressure_note}): risk "
                "falls only when the customer's reply shows genuine "
                "improvement."
            )
        else:
            reasoning.append(
                f"Risk recalculated at {score}/100: this customer "
                "message neither adds nor removes escalation evidence."
            )

        level = risk_level_for_score(score)

        if previous is None:
            trend = "first_message"
        elif score > previous + 1:
            # Any real rise is reported as increasing: a still-unresolved
            # conversation must never label a rising risk as "stable"
            # (a 1-point difference is treated as noise/flat).
            trend = "increasing"
        elif score < previous - 1:
            trend = "decreasing"
        else:
            trend = "stable"

        if not reasoning:
            reasoning.append(
                "No escalation indicators and no de-escalation evidence "
                "in this customer message — low conversational risk."
            )

        # ---- Satisfaction trend from the SAME evidence -----------
        satisfaction_trend = self._satisfaction_trend(
            first_message=previous is None,
            escalation_trend=trend,
            sentiment_label=sentiment_label,
            unaddressed_pressure=unaddressed_pressure,
            de_escalation=de_escalation,
        )

        # ---- Configurable threshold alert -----------------------
        effective_threshold = (
            self._validate_threshold(threshold_override)
            if threshold_override is not None
            else self.threshold
        )
        triggered = score >= effective_threshold

        alert = {
            "triggered": triggered,
            "threshold": effective_threshold,
            "score": score,
            "level": level,
            "triggered_at": _utc_now_iso() if triggered else None,
            "message": (
                f"High escalation risk detected — score {score}/100 "
                f"({level}) reached the alert threshold of "
                f"{effective_threshold}."
                if triggered else None
            ),
            "recommended_actions": self.RECOMMENDED_ACTIONS[level],
        }

        # ---- Persist session state (CUSTOMER only) ---------------
        state["message_count"] += 1
        state["intent_counts"][intent] = (
            state["intent_counts"].get(intent, 0) + 1
        )
        # Capture the PREVIOUS customer state (before overwrite) and the
        # new one: the next customer message blends against it, and the
        # API reads the same object, so no second calculation exists.
        state["previous_analysis"] = state.get("last_analysis")
        state["last_analysis"] = {
            "intent": intent,
            "emotion": emotion_label,
            "frustration": frustration_score,
            "message_level": analysis["message_level"],
            "sentiment": {
                "label": sentiment_label,
                "score": sentiment["score"],
                "confidence": sentiment["confidence"],
            },
            "resolution_status": resolution["status"],
            "unaddressed_pressure": unaddressed_pressure,
            "de_escalation": de_escalation,
            "calm_evidence": calm_evidence,
            "drivers": state_drivers,
        }
        # Remember the latest CUSTOMER message so the next assessment
        # can compare against genuine customer context (agent replies
        # are never stored here).
        state["last_customer_message"] = text_lower

        assessment = {
            "turn": turn if turn is not None else state["message_count"],
            "message": message[:160],
            "score": score,
            "level": level,
            "trend": trend,
            "assessed_at": _utc_now_iso(),
        }
        state["assessments"].append(assessment)

        if triggered:
            state["alerts"].append({
                "turn": assessment["turn"],
                "score": score,
                "level": level,
                "threshold": effective_threshold,
                "message": alert["message"],
                "triggered_at": alert["triggered_at"],
            })

        result = {
            "session_key": session_key,
            "turn": assessment["turn"],
            "escalation_score": score,
            "risk_score": score,
            "escalation_level": level,
            "escalation_risk": level,
            "trend": trend,
            "indicators": indicators,
            "reasoning": reasoning,
            "alert": alert,
            "recommended_actions": alert["recommended_actions"],
            "message_count": state["message_count"],
            "negative_streak": state["negative_streak"],
            "assessed_at": assessment["assessed_at"],
            "customer_message": message,
            "analyzed_customer_message": True,
            "resolution_status": resolution["status"],

            # ---- Customer state: single source of truth for the UI ----
            # These are the exact values the displayed Emotion /
            # Intensity / Frustration / Sentiment / Trending come from.
            "intent": intent,
            "emotion": emotion_label,
            "emotion_label": emotion_label,
            "frustration": frustration_score,
            "frustration_level": frustration_score,
            "message_level": analysis["message_level"],
            "sentiment": sentiment,
            "sentiment_label": sentiment_label,
            "de_escalation": de_escalation,
            "calm_evidence": calm_evidence,
            "unaddressed_pressure": unaddressed_pressure,
            "state_drivers": state_drivers,
            "satisfaction_trend": satisfaction_trend,
        }

        state["last_signature"] = signature
        state["last_result"] = result

        return result









