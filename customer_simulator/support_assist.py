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
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


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
# COACHING & RESPONSE SUGGESTION AGENT
# ==========================================================
class CoachingResponseAgent:
    """
    Generates context-aware response suggestions for support agents
    and evaluates them for tone, clarity, empathy and professionalism.
    """

    EMPATHY_OPENERS = {
        "calm": (
            "Thanks for reaching out — I'm happy to help you with "
            "this right away."
        ),
        "neutral": (
            "Thanks for getting in touch. Let me look into this "
            "for you straight away."
        ),
        "frustrated": (
            "I'm sorry for the inconvenience — I completely "
            "understand how frustrating this is, and I'll sort it "
            "out for you now."
        ),
        "negative": (
            "I'm really sorry about this experience. You're right "
            "to be upset, and I'm going to take care of this "
            "personally right now."
        ),
        "positive": (
            "Thank you for your patience — let me get this "
            "wrapped up for you."
        ),
    }

    INTENT_ACTIONS = {
        "refund_request": (
            "I've checked your order and it is eligible for a refund. "
            "I've initiated the refund now — it will reach your "
            "original payment method within 3-5 business days, and "
            "you'll receive a confirmation email shortly."
        ),
        "delayed_order": (
            "I've located your parcel and flagged it for priority "
            "handling — you'll see an updated tracking status within "
            "24 hours. If it hasn't arrived by then, I'll arrange an "
            "expedited reshipment or a partial refund, whichever you "
            "prefer."
        ),
        "payment_failure": (
            "I've re-checked the transaction and no amount was "
            "captured on our side. Please retry the payment with the "
            "same card or an alternative method — if it fails again "
            "I'll raise it with our payments team immediately."
        ),
        "account_issue": (
            "I've sent a password-reset link to your registered "
            "email — it should arrive within a minute (please check "
            "spam as well). If it doesn't work, I'll unlock the "
            "account from our side right away."
        ),
        "cancellation": (
            "I can process the cancellation for you today. Your "
            "subscription will be cancelled and you will not be "
            "billed again — I'll email you the confirmation in the "
            "next few minutes."
        ),
        "general_inquiry": (
            "Could you share your order ID so I can pull up the "
            "exact details and resolve this for you right away?"
        ),
    }

    CLOSING = (
        "Thank you for your patience — is there anything else I can "
        "help you with while I'm here?"
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
        """
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
        action = self.INTENT_ACTIONS.get(
            intent, self.INTENT_ACTIONS["general_inquiry"]
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
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:
                    continue
                best_sentence = sentence
                if keywords and any(
                    k in sentence.lower() for k in keywords
                ):
                    break

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
                "you like a reshipment or a refund instead?"
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
                "Proactively offer options: expedited reshipment, "
                "partial refund, or full refund."
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
        supervisor_request      +30
        legal_or_bank_threat    +20
        reputation_threat       +15
        unresolved_issue        +12
        cancellation_threat     +10
        urgency_pressure         +8
        repeated complaints   +12..24
        high frustration       +4..15
        negative sentiment
        streak (>=2 messages) +10..15

    Levels:  Low <25 | Medium 25-49 | High 50-74 | Critical >=75
    """

    INDICATOR_PATTERNS = {
        "supervisor_request": (
            30,
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
            12,
            [
                "still", "again", "not resolved", "isn't resolved",
                "no update", "third time", "fourth time",
                "keeps happening", "same issue", "same problem",
                "nothing happened", "no solution", "waiting since",
                "how long", "when will",
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
        "refund", "money back", "not resolved", "still", "again",
        "no update", "when will", "how long", "waiting",
        "keeps happening", "same issue", "same problem", "why",
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
        }

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
    ) -> Dict:
        """
        Assess one customer message and update the session risk
        state. Recalculates the full escalation-risk score, level,
        indicators, reasoning and alert.

        Idempotent: re-assessing the exact same message and turn
        returns the previous result without double counting.
        """
        if isinstance(sentiment, dict):
            sentiment = sentiment.get("label", "neutral")
        if sentiment not in VALID_SENTIMENTS:
            sentiment = "neutral"

        state = self._sessions.setdefault(
            session_key, self._empty_state(session_key)
        )

        message = (customer_message or "").strip()
        text_lower = message.lower()

        signature = hashlib.md5(
            f"{turn}|{text_lower}".encode("utf-8")
        ).hexdigest()

        if (
            state["last_signature"] == signature
            and state["last_result"] is not None
        ):
            return state["last_result"]

        indicators: List[Dict] = []
        reasoning: List[str] = []
        score = 0

        # ---- Phrase-based indicators --------------------------
        for name, (points, phrases) in self.INDICATOR_PATTERNS.items():
            matched = next(
                (p for p in phrases if p in text_lower), None
            )
            if matched:
                score += points
                indicators.append({
                    "name": name,
                    "points": points,
                    "matched_phrase": matched,
                })
                reasoning.append(
                    f"{self.INDICATOR_REASONS[name]} (+{points})."
                )

        # ---- High frustration ---------------------------------
        if frustration_score >= 9:
            score += 15
            reasoning.append(
                "Customer is furious — very high frustration "
                "level (+15)."
            )
        elif frustration_score >= 8:
            score += 12
            reasoning.append(
                "Very high frustration level expressed (+12)."
            )
        elif frustration_score >= 7:
            score += 8
            reasoning.append(
                "Elevated frustration level expressed (+8)."
            )
        elif frustration_score >= 6:
            score += 4
            reasoning.append("Mildly elevated frustration (+4).")

        # ---- Negative sentiment streak -------------------------
        if sentiment == "negative":
            state["negative_streak"] += 1
        else:
            state["negative_streak"] = 0

        streak = state["negative_streak"]
        if streak >= 2:
            streak_points = 10 + min(5, 5 * (streak - 2))
            score += streak_points
            reasoning.append(
                f"Negative sentiment in {streak} consecutive "
                f"messages (+{streak_points})."
            )

        # ---- Repeated complaints -------------------------------
        markers_hit = sum(
            1 for m in self.REPEAT_COMPLAINT_MARKERS if m in text_lower
        )
        complaint_like = markers_hit >= 2
        repeats = state["intent_counts"].get(intent, 0)

        if complaint_like:
            repeat_points = min(24, 12 + 6 * repeats)
            score += repeat_points
            if repeats >= 1:
                reasoning.append(
                    f"Repeated complaint: issue '{intent}' raised "
                    f"{repeats + 1} times (+{repeat_points})."
                )
            else:
                reasoning.append(
                    f"Strong complaint language about "
                    f"'{intent}' (+{repeat_points})."
                )
        elif repeats >= 2:
            score += 6
            reasoning.append(
                f"Customer has raised '{intent}' {repeats + 1} "
                f"times (+6)."
            )

        # ---- Final score / level / trend ------------------------
        previous = (
            state["assessments"][-1]["score"]
            if state["assessments"] else None
        )

        score = clamp_score(score)
        level = risk_level_for_score(score)

        if previous is None:
            trend = "first_message"
        elif score > previous + 5:
            trend = "increasing"
        elif score < previous - 5:
            trend = "decreasing"
        else:
            trend = "stable"

        if previous is not None:
            reasoning.append(
                f"Risk trend: {previous} -> {score} after this "
                f"message ({trend})."
            )

        if not reasoning:
            reasoning.append(
                "No strong escalation indicators in this message — "
                "low conversational risk."
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

        # ---- Persist session state ------------------------------
        state["message_count"] += 1
        state["intent_counts"][intent] = (
            state["intent_counts"].get(intent, 0) + 1
        )

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
        }

        state["last_signature"] = signature
        state["last_result"] = result

        return result









