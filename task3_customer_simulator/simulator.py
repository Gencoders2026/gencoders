"""
Customer Simulator Agent

PERSONA:
Controls how the customer communicates.

FRUSTRATION LEVEL:
Controls the customer's emotional intensity from 1 to 10.

1-2  = Calm
3-4  = Concerned
5-6  = Frustrated
7-8  = Angry
9-10 = Furious

IMPORTANT:
There is NO patience level.
Frustration level is the emotional control.
"""

import uuid
import json
import random
import re
from pathlib import Path
from typing import Dict, Any, Optional

try:
    # Normal package-relative / script-relative import.
    from .contextual_replies import CONTEXTUAL_REPLIES
except ImportError:  # pragma: no cover - depends on how the module is loaded
    try:
        from contextual_replies import CONTEXTUAL_REPLIES
    except ImportError:
        # Never let a missing/renamed data file break the simulator: the
        # generator falls back to the plain band messages.
        CONTEXTUAL_REPLIES = {}


PERSONAS = {
    "polite": {
        "name": "Polite Customer",
        "style": "respectful and cooperative"
    },
    "concerned": {
        "name": "Concerned Customer",
        "style": "worried and asks for clarification"
    },
    "frustrated": {
        "name": "Frustrated Customer",
        "style": "impatient and wants a concrete answer"
    },
    "angry": {
        "name": "Angry Customer",
        "style": "firm, demanding and urgent"
    },
    "furious": {
        "name": "Furious Customer",
        "style": "very strong dissatisfaction and escalation"
    }
}


SCENARIOS = {
    "refund_request": {
        "name": "Refund Request",
        "issue": "the damaged product I received",
        "goal": "a full refund"
    },

    "delayed_order": {
        "name": "Delayed Order",
        "issue": "my order that has not arrived",
        "goal": "a clear delivery update"
    },

    "payment_failure": {
        "name": "Payment Failure",
        "issue": "the payment that keeps failing",
        "goal": "a clear payment solution"
    },

    "account_issue": {
        "name": "Account Access Issue",
        "issue": "my account that I cannot access",
        "goal": "my account access to be restored"
    },

    "cancellation": {
        "name": "Cancellation Request",
        "issue": "my subscription",
        "goal": "confirmation that it is cancelled"
    }
}


def get_emotion(level: int) -> str:
    if level <= 2:
        return "Calm"
    elif level <= 4:
        return "Concerned"
    elif level <= 6:
        return "Frustrated"
    elif level <= 8:
        return "Angry"
    else:
        return "Furious"


def get_band(level: int) -> str:
    if level <= 2:
        return "calm"
    elif level <= 4:
        return "concerned"
    elif level <= 6:
        return "frustrated"
    elif level <= 8:
        return "angry"
    else:
        return "furious"


# Generic (non-reactive) conversation lines, keyed by scenario and then
# by emotional band. Populated the first time a message is generated and
# published here so the pools can be inspected and tested directly.
BAND_POOLS: Dict[str, Dict[str, list]] = {}


class CustomerSimulator:

    # Flavour prefixes added on top of the generated base line.
    # They are exposed on the class so tests (and the UI) can strip a
    # prefix back off and compare the underlying base lines.
    PERSONA_PREFIXES = {
        "polite": [
            "I am very disappointed with this situation. ",
            "This is really upsetting. ",
            "I did not expect this kind of experience. ",
        ],
        "concerned": [
            "I'm quite worried about this. ",
            "This is really concerning me. ",
            "I'm getting quite anxious about this. ",
        ],
        "frustrated": [
            "I'm starting to get concerned. ",
            "I'm beginning to lose patience. ",
            "This is becoming worrying. ",
        ],
        "angry": [
            "I'm not happy about this. ",
            "This is still frustrating. ",
            "I remain unhappy with this. ",
        ],
        "furious": [
            "I'm extremely unhappy with this situation. ",
            "This is absolutely unacceptable to me. ",
            "I'm furious about how this is going. ",
        ],
    }

    def __init__(
        self,
        persona: str = "frustrated",
        scenario: str = "refund_request",
        frustration_level: int = 5,
        expected_resolution: str = "full_refund",
        session_id: Optional[str] = None,
        use_llm: bool = False,
        **kwargs
    ):

        self.session_id = session_id or str(uuid.uuid4())[:8]

        self.persona_name = persona.lower().strip()
        self.scenario_name = scenario.lower().strip()

        if self.persona_name not in PERSONAS:
            self.persona_name = "frustrated"

        if self.scenario_name not in SCENARIOS:
            self.scenario_name = "refund_request"

        self.frustration_level = max(
            1,
            min(10, int(frustration_level))
        )

        self.expected_resolution = expected_resolution

        self.history = []

        self.turn_count = 0

        self.finished = False

        # Keeps track of messages already displayed (final text) and of
        # the BASE lines, so the no-repeat protection also works when a
        # persona prefix was prepended.
        self.used_messages = set()
        self.used_bases = set()

        # The BASE line said on the previous turn. It is never repeated
        # while any other line is still available.
        self._last_base = None

        # What the agent did in its last reply - drives the next
        # customer message.
        self._last_agent_kind = None

        # Avoid repeating the same persona prefix twice in a row.
        self._last_prefix = None

        # Log folder
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

        self.log_path = (
            self.log_dir /
            f"session_{self.session_id}.json"
        )

        self._save_log()


    # ==========================================================
    # SET FRUSTRATION LEVEL
    # ==========================================================

    def set_frustration_level(self, level: int) -> int:

        self.frustration_level = max(
            1,
            min(10, int(level))
        )

        return self.frustration_level


    # ==========================================================
    # START SESSION
    # ==========================================================

    def start(self):

        message = self._generate_customer_message(
            opening=True
        )

        self._record(
            "customer",
            message
        )

        return self._build_response(message)


    # ==========================================================
    # AGENT REPLY
    # ==========================================================

    def respond(self, agent_message: str):

        if self.finished:

            return self._build_response(
                "Thank you. This conversation has already been completed.",
                {
                    "status": "already_finished"
                }
            )

        # Record agent message
        self._record(
            "agent",
            agent_message
        )

        text = agent_message.lower()

        # ------------------------------------------------------
        # DYNAMIC FRUSTRATION ADJUSTMENT (evidence-based)
        # ------------------------------------------------------
        # Frustration is NEVER adjusted by a fixed per-turn delta.
        # The simulated customer's frustration is recalculated from the
        # evidence found in the AGENT's actual reply:
        #
        #   - a genuine, scenario-specific resolution releases a share
        #     of the CURRENT frustration (proportional, so a furious
        #     customer is released further than a mildly annoyed one);
        #   - every other reply is scored in [-1.0, 1.0] from concrete
        #     commitments, issue/goal acknowledgement, empathy and
        #     poor/evasive signals, and frustration moves by a
        #     proportional amount (never a flat +/-1 per turn).
        resolved = self._is_resolved(text)

        if resolved:
            # Proportional release: higher frustration means a bigger
            # drop because the customer is genuinely relieved.
            reduction = max(2, round(self.frustration_level * 0.55))
            self.frustration_level = max(
                1,
                self.frustration_level - reduction
            )
        else:
            quality = self._assess_agent_response_quality(agent_message)
            delta = round(quality * 3)
            if delta == 0 and abs(quality) >= 0.2:
                delta = 1 if quality > 0 else -1
            self.frustration_level = max(
                1,
                min(10, self.frustration_level - delta)
            )

        # ------------------------------------------------------
        # RESOLUTION FINISH CHECK
        # ------------------------------------------------------

        if (
            resolved
            and self.frustration_level <= 4
        ):

            self.finished = True

            message = self._closing_message()

            self._record(
                "customer",
                message
            )

            return self._build_response(
                message,
                {
                    "status": "resolved"
                }
            )

        # ------------------------------------------------------
        # NEXT CUSTOMER MESSAGE
        # ------------------------------------------------------
        # The agent's actual reply is passed in, so the customer answers
        # what the agent said (a request for details, a timeline, a
        # vague stall, ...) instead of repeating a generic line.
        message = self._generate_customer_message(
            opening=False,
            agent_message=agent_message
        )

        self._record(
            "customer",
            message
        )

        return self._build_response(message)

    # ==========================================================
    # AGENT RESPONSE QUALITY SCORING (dynamic, evidence-based)
    # ==========================================================
    def _assess_agent_response_quality(self, agent_message: str) -> float:
        """
        Dynamically score how helpful the agent's response is for the
        current scenario, returning a float in [-1.0, 1.0].

        The score reflects *evidence* found in the actual agent text —
        NOT a fixed per-turn change and NOT a scenario-agnostic keyword
        list.  A response with concrete commitments, issue-specific
        acknowledgment and empathy scores high (toward +1.0); a vague,
        evasive or outright poor reply scores low (toward -1.0).

        Scoring factors (each derived from the text, not a constant):
        - Concrete commitment signals (timeline, processed action, etc.)
        - Scenario-specific issue acknowledgment
        - Goal-oriented language
        - Genuine empathy / apology
        - Genuine resolution confirmation (strongest positive)
        - Poor / unhelpful / evasive signals
        - Effort / message length
        """
        text = agent_message.lower()
        scenario = SCENARIOS[self.scenario_name]
        issue = scenario["issue"]
        goal = scenario["goal"]

        score = 0.0

        # --- Concrete commitment signals ---
        commit_patterns = [
            r"within\s+\d+\s*(?:-\s*\d+\s*)?(?:business\s+)?"
            r"(?:day|hour|minute)s?",
            r"\b(processed|completed|confirmed|issued|"
            r"refunded|escalated)\b",
            r"\btracking\s+(number|status|shows?)\b",
            r"\bdelivery\s+date\b",
            r"\breship(?:ped|ment)?\b",
            r"\breplac(?:ed|ement|ing)\b",
            r"\b(compensation|discount|credit|voucher)\b",
            r"\b(next step|next steps)\b",
            r"\b(a full refund|refund)\b",
            r"\b(escalat(e|ing|ed) to (a )?(manager|supervisor))\b",
        ]
        commit_hits = sum(
            1 for p in commit_patterns if re.search(p, text)
        )
        if commit_hits >= 3:
            score += 0.6
        elif commit_hits == 2:
            score += 0.4
        elif commit_hits == 1:
            score += 0.2

        # --- Scenario-specific issue acknowledgment ---
        issue_terms = [
            t for t in re.findall(r"[a-z]+", issue.lower())
            if len(t) >= 4
        ]
        if issue_terms:
            hits = sum(1 for t in issue_terms if t in text)
            ratio = hits / len(issue_terms)
            if ratio >= 0.5:
                score += 0.2
            elif hits > 0:
                score += 0.1

        # --- Goal acknowledgment ---
        goal_terms = [
            t for t in re.findall(r"[a-z]+", goal.lower())
            if len(t) >= 4
        ]
        if goal_terms:
            hits = sum(1 for t in goal_terms if t in text)
            ratio = hits / len(goal_terms)
            if ratio >= 0.5:
                score += 0.15

        # --- Genuine empathy / apology ---
        empathy_words = [
            "sorry", "apologize", "apologies", "apology",
            "i understand", "i completely understand", "i can see",
            "that must be", "frustrating", "i get it", "of course",
            "i appreciate", "thank you for your patience",
            "i hear you", "i completely get it",
        ]
        empathy_hits = sum(1 for w in empathy_words if w in text)
        if empathy_hits >= 2:
            score += 0.15
        elif empathy_hits >= 1:
            score += 0.08

        # --- Genuine resolution (strongest positive evidence) ---
        if self._is_resolved(text):
            score += 0.4

        # --- Poor / unhelpful / evasive signals ---
        poor_patterns = [
            r"\bwait\b",
            r"\bsoon\b",
            r"\blater\b",
            r"can't help",
            r"cannot help",
            r"nothing i can do",
            r"don't know",
            r"do not know",
            r"not my problem",
            r"\bmaybe\b",
            r"i'll check",
            r"let me check",
            r"outside our control",
            r"unfortunately",
            r"\bpolicy\b",
            r"final sale",
            r"no refund",
            r"nothing (we|i) can do",
        ]
        poor_hits = sum(
            1 for p in poor_patterns if re.search(p, text)
        )
        if poor_hits >= 3:
            score -= 0.5
        elif poor_hits == 2:
            score -= 0.35
        elif poor_hits == 1:
            score -= 0.3

        # --- Effort / length ---
        word_count = len(agent_message.split())
        if word_count < 5:
            score -= 0.1
        elif word_count >= 20:
            score += 0.05

        return max(-1.0, min(1.0, round(score, 2)))

    # ==========================================================
    # RESOLUTION CHECK
    # ==========================================================

    def _is_resolved(self, text: str):

        checks = {

            "refund_request": [
                "refund has been processed",
                "refund processed",
                "full refund",
                "refund completed"
            ],

            "delayed_order": [
                "delivery date",
                "order has arrived",
                "order delivered",
                "delivered"
            ],

            "payment_failure": [
                "payment is successful",
                "payment succeeded",
                "payment fixed",
                "payment completed"
            ],

            "account_issue": [
                "access restored",
                "account restored",
                "account is unlocked",
                "unlocked",
                "restored",
                "logged in",
                "log in now",
                "login successful",
                "access is restored",
                "account access is working"
            ],

            "cancellation": [
                "cancelled",
                "cancellation confirmed",
                "subscription cancelled"
            ]
        }

        for phrase in checks.get(
            self.scenario_name,
            []
        ):

            if phrase in text:
                return True

        return False


    # ==========================================================
    # CUSTOMER MESSAGE GENERATOR
    # ==========================================================

    # ==========================================================
    # AGENT REPLY CLASSIFICATION (drives the next customer turn)
    # ==========================================================
    def _agent_reply_kind(self, agent_message: str) -> str:
        """
        Classify what the AGENT actually did, so the customer's next
        message can react to it instead of being picked blindly.

        The customer used to receive a message chosen only from the
        emotional band, which meant the conversation ignored what the
        agent said: the customer never answered a question, never
        acknowledged a timeline and never pushed back on a vague reply.
        The returned kind feeds `_contextual_replies`.

        Returns one of:
            asks_for_info     the agent asked the customer for something
            asks_confirmation the agent asked the customer to confirm
            gives_timeline    the agent made a concrete commitment
            apology_only      the agent apologised without any action
            vague             the agent stalled / deflected / hid policy
            offers_help       a generic but non-committal reply
        """
        text = (agent_message or "").lower()

        if not text.strip():
            return "vague"

        asks_for_info = re.search(
            r"\b(?:could|can|please)\s+(?:you\s+)?(?:please\s+)?"
            r"(?:provide|share|send|give|tell|forward|"
            r"need|require)\b"
            r"|\b(?:i|we)\s+(?:need|require)\s+(?:your|the|it|to)\b"
            r"|\b(?:order|transaction|invoice|booking|reference|"
            r"case|ticket)\s*(?:id|number|no\.?|#)\b"
            r"|\bemail address\b",
            text,
        )
        asks_confirmation = re.search(
            r"\b(?:could|can|would)\s+you\s+(?:please\s+)?confirm\b"
            r"|\bplease\s+confirm\b"
            r"|\b(?:let\s+me|can\s+i)\s+verify\b",
            text,
        )
        gives_timeline = re.search(
            r"within\s+\d+"
            r"|\b(?:processed|completed|confirmed|issued|refunded|"
            r"reshipped|replaced|escalated)\b"
            r"|\b\d+\s*(?:business\s+)?(?:day|hour|minute)s?\b"
            r"|\bby\s+(?:tomorrow|end of day|tonight|monday|"
            r"next week)\b",
            text,
        )
        vague = re.search(
            r"\b(?:let me|i'?ll|i will|we'?ll|we will)\s+"
            r"(?:check|look|see|review|investigate|get back)\b"
            r"|\b(?:look|check)ing\s+into\s+(?:this|it|that)\b"
            r"|\bsoon\b|\blater\b|\bmaybe\b|\bdon'?t know\b"
            r"|\bdo not know\b|\bunfortunately\b|\bpolicy\b"
            r"|\boutside our control\b|\bas soon as possible\b"
            r"|\bmight\b|\bpossibly\b",
            text,
        )
        apology = re.search(
            r"\bsorry\b|\bapolog(?:y|ies|ize|ise)\b"
            r"|\bi understand\b|\bfrustrating\b|\bpatience\b",
            text,
        )

        # `asks_confirmation` is checked BEFORE `asks_for_info` because
        # a confirmation question also matches the "can you ..." shape.
        if gives_timeline:
            return "gives_timeline"
        if asks_confirmation:
            return "asks_confirmation"
        if asks_for_info:
            return "asks_for_info"
        if vague:
            return "vague"
        if apology:
            return "apology_only"
        return "offers_help"

    def _contextual_replies(self, kind: str) -> list:
        """
        Scenario-specific replies that REACT to what the agent just did.

        Each entry is a list of (tone, message) pairs so the customer's
        emotional band is still respected: a calm customer stays polite,
        a furious one stays angry - but both now answer the agent.
        """
        return CONTEXTUAL_REPLIES.get(
            self.scenario_name, {}
        ).get(kind, [])

    @staticmethod
    def _pick_unused(
        candidates: list,
        used: set,
        turn_count: int,
        avoid: Optional[str] = None,
    ) -> Optional[str]:
        """
        Pick a line that has not been used yet, so the customer never
        repeats themselves inside a conversation.

        Candidates are rotated by the turn number (stable, predictable
        variety) and used ones are skipped. `avoid` is the line used on
        the previous turn and is never returned.

        Returns None when the pool has nothing new to offer, so the
        caller can fall through to the next (less specific) pool. Only
        the caller's final fallback allows an already-used line.
        """
        if not candidates:
            return None

        for offset in range(len(candidates)):
            candidate = candidates[
                (turn_count + offset) % len(candidates)
            ]
            if candidate not in used and candidate != avoid:
                return candidate

        return None

    def _generate_customer_message(
        self,
        opening=False,
        agent_message: Optional[str] = None
    ):

        level = self.frustration_level

        band = get_band(level)

        # ------------------------------------------------------
        # Improved natural messages for every turn
        # ------------------------------------------------------

        message_sets = {

            "refund_request": {

                "calm": [
                    "Hi, I received a damaged product in my order. Could you please help me with a refund?",
                    "Hello, the item I received arrived damaged. I’d like to request a refund when you have a moment.",
                    "Could you please check the status of my refund request for the damaged product?",
                    "Thank you. Could you let me know what the next step is for processing the refund?",
                    "I appreciate your help. Is there any additional information you need from me regarding the refund?",
                    "Just following up politely — has there been any update on my refund for the damaged item?"
                ],

                "concerned": [
                    "I'm a little concerned about my refund. Could you please check the status?",
                    "I'm worried that my refund has not been completed yet. Can you give me an update?",
                    "Could you please explain what is happening with my refund and when I can expect it?",
                    "I hope everything is okay with the refund process. Could you share the current status?",
                    "I'm slightly worried because I haven't heard back about the refund yet. Any news?"
                ],

                "frustrated": [
                    "I'm getting frustrated because my refund is still not sorted out. Can you give me a clear update?",
                    "This refund is taking too long. Please tell me exactly what will happen next.",
                    "I'm still waiting for my refund and I need a concrete answer. When will this be completed?",
                    "I need a proper update on this refund. The delay is becoming frustrating.",
                    "Can you please give me a definite timeline for the refund? This is taking longer than expected."
                ],

                "angry": [
                    "This refund delay is unacceptable. I need a definite answer and timeline now.",
                    "I'm very unhappy with this situation. Please stop giving vague answers and tell me when my refund will be completed.",
                    "I have waited long enough. I need this refund issue handled properly now.",
                    "I expect a clear resolution for this refund immediately. The delay is not acceptable.",
                    "Please provide a firm timeline for my refund right now. I'm not satisfied with the current status."
                ],

                "furious": [
                    "This is completely unacceptable. I need my refund resolved immediately.",
                    "I am extremely frustrated with this refund delay. Fix this immediately or escalate the issue.",
                    "Enough with the delays. I expect the refund to be handled now.",
                    "I demand that this refund be processed immediately. This situation is ridiculous.",
                    "Resolve my refund right now or escalate this to someone who can. I'm done waiting."
                ]
            },


            "delayed_order": {

                "calm": [
                    "Hi, my order has not arrived yet. Could you please check the latest delivery status?",
                    "Hello, I noticed that my order is delayed. Can you tell me when it is expected to arrive?",
                    "Could you please check the delivery status and give me an update?",
                    "Thank you. Do you have any updated information on when my order might arrive?",
                    "I’d appreciate it if you could look into the current status of my delayed order.",
                    "Just checking in — is there any new update on the delivery of my order?"
                ],

                "concerned": [
                    "I'm a little worried because my order is delayed. Could you please check what is happening?",
                    "I'm concerned about the delivery delay. Can you give me a clear update?",
                    "Could you please confirm the latest delivery information? I am not sure what to expect.",
                    "I hope the delay isn't too serious. Could you share the current expected arrival time?",
                    "I'm slightly concerned as the order is still delayed. Any update would be helpful."
                ],

                "frustrated": [
                    "I'm getting frustrated with this delay. I need a concrete delivery update.",
                    "My order is still delayed and this is becoming frustrating. Can you tell me when it will arrive?",
                    "I'm tired of waiting without a clear update. Please give me a definite delivery expectation.",
                    "This delay is frustrating. I need a clear answer about when my order will arrive.",
                    "Please provide a proper timeline for the delivery. Waiting without updates is not helpful."
                ],

                "angry": [
                    "This delivery delay is unacceptable. I need a definite delivery date now.",
                    "I'm very unhappy that my order is still delayed. Give me a clear answer.",
                    "I have waited long enough. I need this delivery issue resolved immediately.",
                    "I expect a firm delivery date right now. The current delay is unacceptable.",
                    "Stop the vague responses. Tell me exactly when my order will arrive."
                ],

                "furious": [
                    "Where is my order? This delay is completely unacceptable. I need a resolution immediately.",
                    "I am extremely frustrated with this delay. Give me a definite answer now.",
                    "Enough waiting. I need my order situation fixed immediately.",
                    "This is ridiculous. I demand an immediate update and resolution for my delayed order.",
                    "Resolve this delivery issue right now or escalate it. I'm done waiting."
                ]
            },


            "payment_failure": {

                "calm": [
                    "Hi, my payment did not go through. Could you please help me?",
                    "Hello, I am having trouble completing my payment. Can you check the issue?",
                    "Could you please help me fix the payment problem?",
                    "Thank you. Is there anything I need to do on my side to complete the payment?",
                    "I’d appreciate your help in resolving this payment issue.",
                    "Just following up — has there been any progress on fixing the payment problem?"
                ],

                "concerned": [
                    "I'm concerned because my payment keeps failing. Could you please check what is wrong?",
                    "I'm a little worried about the failed payment. Can you explain the next step?",
                    "Could you please confirm why my payment is failing?",
                    "I hope we can resolve this soon. Do you know what is causing the payment to fail?",
                    "I'm slightly concerned as the payment still isn't going through. Any advice?"
                ],

                "frustrated": [
                    "I'm getting frustrated because the payment still is not working. Can you fix this?",
                    "This payment problem is becoming frustrating. I need a clear solution.",
                    "I have tried to complete the payment and it still fails. What should I do?",
                    "The payment keeps failing and it's frustrating. Please give me a concrete solution.",
                    "I need this payment issue resolved. Waiting without a clear fix is not helpful."
                ],

                "angry": [
                    "This payment failure is unacceptable. I need it fixed now.",
                    "I'm very unhappy with this payment problem. Give me a clear solution immediately.",
                    "I cannot keep dealing with a failed payment. Please resolve it now.",
                    "I expect this payment issue to be fixed immediately. The delay is unacceptable.",
                    "Stop the delays. Fix the payment problem right now."
                ],

                "furious": [
                    "This payment issue is completely unacceptable. Fix it immediately.",
                    "I am extremely frustrated with this failed payment. Resolve it now.",
                    "Enough. I need this payment problem fixed immediately.",
                    "This is ridiculous. Resolve the payment failure right now or escalate it.",
                    "I demand an immediate fix for this payment issue. No more delays."
                ]
            },


            "account_issue": {

                "calm": [
                    "Hi, I cannot access my account. Could you please help me restore access?",
                    "Hello, I am having trouble logging into my account. Can you please help?",
                    "Could you please check why I cannot access my account?",
                    "Thank you. Is there any information you need from me to restore access?",
                    "I’d appreciate your help in getting my account access restored.",
                    "Just checking in — has there been any update on restoring my account access?"
                ],

                "concerned": [
                    "I'm concerned because I still cannot access my account. Could you please check this?",
                    "I'm worried about being locked out of my account. Can you help restore access?",
                    "Could you please explain what is preventing me from accessing my account?",
                    "I hope this can be resolved soon. Do you know why I can't log in?",
                    "I'm slightly worried as I still can't access my account. Any update?"
                ],

                "frustrated": [
                    "I'm getting frustrated because I still cannot access my account. Can you fix this?",
                    "This account access problem is becoming frustrating. I need a clear next step.",
                    "I have been trying to access my account without success. What should I do?",
                    "Being locked out is frustrating. Please give me a concrete solution.",
                    "I need my account access restored. This delay is becoming annoying."
                ],

                "angry": [
                    "This account access problem is unacceptable. I need access restored now.",
                    "I'm very unhappy that I am still locked out. Give me a clear solution immediately.",
                    "I cannot keep waiting to access my account. Please resolve this now.",
                    "I expect my account access to be restored immediately. This is unacceptable.",
                    "Stop delaying. Restore my account access right now."
                ],

                "furious": [
                    "This is completely unacceptable. I need my account access restored immediately.",
                    "I am extremely frustrated with being locked out. Fix this now.",
                    "Enough. I need access to my account restored immediately.",
                    "This situation is ridiculous. Restore my access now or escalate the issue.",
                    "I demand immediate restoration of my account access. No more delays."
                ]
            },


            "cancellation": {

                "calm": [
                    "Hi, I would like to cancel my subscription. Could you please help me?",
                    "Hello, I want to cancel my subscription. Can you guide me through the process?",
                    "Could you please confirm when my subscription cancellation will take effect?",
                    "Thank you. Is there anything else I need to do to complete the cancellation?",
                    "I’d appreciate confirmation once the cancellation has been processed.",
                    "Just following up — has my subscription cancellation been confirmed yet?"
                ],

                "concerned": [
                    "I'm a little concerned about future charges. Could you please confirm the cancellation?",
                    "I want to cancel my subscription, but I need to know whether there will be more charges.",
                    "Could you please explain what happens after I request cancellation?",
                    "I hope there won't be any further charges. Can you confirm the cancellation status?",
                    "I'm slightly worried about ongoing billing. Has the cancellation been completed?"
                ],

                "frustrated": [
                    "I'm getting frustrated because I still need confirmation that my subscription is cancelled.",
                    "I need this cancellation handled properly. Please give me a clear confirmation.",
                    "I'm tired of dealing with this. Please confirm exactly when the subscription will be cancelled.",
                    "Waiting for confirmation is frustrating. Please finalize the cancellation now.",
                    "I need a clear confirmation that the subscription has been cancelled. This is taking too long."
                ],

                "angry": [
                    "I want my subscription cancelled immediately. I need clear confirmation now.",
                    "This cancellation issue is unacceptable. Stop the subscription and confirm it.",
                    "I'm very unhappy with this delay. Complete the cancellation now.",
                    "I expect the cancellation to be completed immediately. No more delays.",
                    "Cancel the subscription right now and give me confirmation."
                ],

                "furious": [
                    "Cancel the subscription immediately. This delay is completely unacceptable.",
                    "Enough delays. I want the subscription cancelled now.",
                    "This is unacceptable. Cancel it immediately or escalate the issue.",
                    "I demand that the subscription be cancelled right now. This is ridiculous.",
                    "Stop delaying and cancel my subscription immediately."
                ]
            }
        }

        # The pools are also published at module level so they can be
        # inspected (and tested) without running a conversation.
        BAND_POOLS.update(message_sets)

        # ------------------------------------------------------
        # REACT TO THE AGENT'S REPLY (Task 3: the conversation must
        # depend on what the support agent said, not only on the
        # emotional band)
        # ------------------------------------------------------
        # When the agent asked for information, gave a timeline, only
        # apologised or stalled, the customer answers THAT instead of
        # repeating a generic line. The emotional band still decides
        # how the answer is worded.
        #
        # Pools are tried in order of "how well does this line answer
        # what the agent just said", and the first one that can still
        # supply a line wins. This keeps the conversation reactive while
        # still guaranteeing the customer never repeats itself.
        contextual = []

        if not opening and agent_message:
            kind = self._agent_reply_kind(agent_message)
            self._last_agent_kind = kind

            # Keep only the variants that match the current tone so a
            # furious customer never answers politely.
            contextual = [
                text
                for tone, text in self._contextual_replies(kind)
                if tone in (band, "any")
            ]

        # The band pool is the scenario's generic conversation pool and
        # is always available as a fallback.
        options = message_sets[self.scenario_name][band]

        pools = []
        if contextual:
            pools.append(contextual)

            # A reply to a DIFFERENT kind of agent message is still far
            # better than repeating the generic band line, so it is the
            # second choice once the matching pool is exhausted.
            for other_kind, lines in CONTEXTUAL_REPLIES.get(
                self.scenario_name, {}
            ).items():
                if other_kind == kind:
                    continue
                other = [
                    text for tone, text in lines if tone in (band, "any")
                ]
                if other:
                    pools.append(other)

        pools.append(options)

        base = None

        # Pass 1: only a line that has never been said.
        for pool in pools:
            base = self._pick_unused(
                pool,
                self.used_bases,
                self.turn_count,
                avoid=self._last_base,
            )
            if base:
                break

        if base is None:
            # Pass 2: everything reachable has been said already.
            # Reuse is acceptable, saying the SAME line twice in a row
            # is not, so every pool is scanned for anything else.
            widest = max(pools, key=len)
            for offset in range(len(widest)):
                candidate = widest[
                    (self.turn_count + offset) % len(widest)
                ]
                if candidate != self._last_base:
                    base = candidate
                    break

        if base is None:
            # Every reachable line is a single line already used. Reuse
            # the generic band pool so the conversation still moves on.
            base = options[0]

        # The BASE line is remembered separately from the final text
        # so a persona prefix never hides a repeated line.
        self.used_bases.add(base)
        self._last_base = base

        message = base

        # ------------------------------------------------------
        # PERSONA MODIFICATION
        # ------------------------------------------------------

        if self.persona_name == "polite":

            if band in ["angry", "furious"]:
                message = self._apply_prefix(
                    message,
                    self.PERSONA_PREFIXES["polite"]
                )

        elif self.persona_name == "concerned":

            if band in ["angry", "furious"]:
                message = self._apply_prefix(
                    message,
                    self.PERSONA_PREFIXES["concerned"]
                )

        elif self.persona_name == "frustrated":

            if band == "calm":
                message = self._apply_prefix(
                    message,
                    self.PERSONA_PREFIXES["frustrated"]
                )

        elif self.persona_name == "angry":

            if band in ["calm", "concerned"]:
                message = self._apply_prefix(
                    message,
                    self.PERSONA_PREFIXES["angry"]
                )

        elif self.persona_name == "furious":

            if band in ["calm", "concerned", "frustrated"]:
                message = self._apply_prefix(
                    message,
                    self.PERSONA_PREFIXES["furious"]
                )

        # ------------------------------------------------------
        # NO-REPEAT PROTECTION
        # ------------------------------------------------------
        # The BASE line is remembered separately from the final text
        # so a repeated line is detected even when a persona prefix
        # was prepended to it.
        self.used_messages.add(message)

        return message

    # ==========================================================
    # PERSONA PREFIX ROTATION
    # ==========================================================

    def _apply_prefix(
        self,
        message: str,
        prefixes: list
    ):
        """
        Prepend a persona flavour prefix without repeating the
        same one twice in a row.
        """

        choices = [p for p in prefixes if p != self._last_prefix]

        prefix = random.choice(choices)

        self._last_prefix = prefix

        return prefix + message


    # ==========================================================
    # CLOSING MESSAGE
    # ==========================================================

    def _closing_message(self):

        if self.frustration_level <= 2:
            return (
                "Thank you for resolving this. "
                "I really appreciate your help."
            )

        if self.frustration_level <= 4:
            return (
                "Alright, thank you for the update. "
                "I appreciate you getting this sorted out."
            )

        if self.frustration_level <= 6:
            return (
                "Okay, I will accept that for now. "
                "Please make sure the promised action is completed."
            )

        if self.frustration_level <= 8:
            return (
                "Fine, but I need to see the promised action completed. "
                "I hope there are no more delays."
            )

        return (
            "I still expect this to be fixed immediately. "
            "If it is not, I will need to escalate the issue."
        )


    # ==========================================================
    # RECORD
    # ==========================================================

    def _record(
        self,
        role: str,
        content: str
    ):

        self.turn_count += 1

        self.history.append({
            "role": role,
            "content": content,
            "frustration_level": (
                self.frustration_level
                if role == "customer"
                else None
            ),
            "emotion": (
                get_emotion(self.frustration_level)
                if role == "customer"
                else None
            )
        })

        self._save_log()


    # ==========================================================
    # API RESPONSE
    # ==========================================================

    def _build_response(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None
    ):

        data = {
            "session_id": self.session_id,

            "customer_message": message,

            "persona": self.persona_name,

            "persona_name": PERSONAS[
                self.persona_name
            ]["name"],

            "scenario": self.scenario_name,

            "scenario_name": SCENARIOS[
                self.scenario_name
            ]["name"],

            "frustration_level":
                self.frustration_level,

            "emotion": {
                "label":
                    get_emotion(
                        self.frustration_level
                    ),

                "intensity":
                    self.frustration_level
            },

            "finished": self.finished,

            "turn_count":
                self.turn_count,

            "history":
                self.history,

            "log_path":
                str(self.log_path)
        }

        if extra:
            data.update(extra)

        return data


    # ==========================================================
    # STATE
    # ==========================================================

    def get_state(self):

        return self._build_response(
            ""
        )


    # ==========================================================
    # SAVE LOG
    # ==========================================================

    def _save_log(self):

        try:

            data = {
                "session_id":
                    self.session_id,

                "persona":
                    self.persona_name,

                "scenario":
                    self.scenario_name,

                "frustration_level":
                    self.frustration_level,

                "history":
                    self.history
            }

            self.log_path.write_text(
                json.dumps(
                    data,
                    indent=2
                ),
                encoding="utf-8"
            )

        except Exception:
            pass


# ==============================================================
# FACTORY
# ==============================================================

def create_simulator(**kwargs):

    return CustomerSimulator(**kwargs)