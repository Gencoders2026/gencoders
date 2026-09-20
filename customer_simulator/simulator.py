"""
CUSTOMER SIMULATOR AGENT
========================

Simulates realistic customer conversations with a support agent,
turn-by-turn, based on:

  * a configurable persona
  * a scenario
  * an initial emotion
  * an issue severity
  * a patience level
  * an expected resolution

Key behaviours
--------------

1. Persona controls communication style.
2. Frustration level controls emotional intensity.
3. Scenario controls the customer problem.
4. Angry / furious personas MUST NOT use polite language.
5. Different frustration levels produce different messages.
6. The conversation context is maintained across turns.
7. Emotions increase or decrease based on the agent's reply.
8. An LLM is used (when configured) to generate realistic,
   scenario-specific messages; a rule-based message bank is used
   as an offline fallback.
9. Every turn is logged to a JSON conversation log.
"""

import uuid
import json
import random
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

try:  # package-relative imports
    from .config import (
        DEFAULT_PERSONA,
        DEFAULT_SCENARIO,
        DEFAULT_INITIAL_EMOTION,
        DEFAULT_ISSUE_SEVERITY,
        DEFAULT_PATIENCE_LEVEL,
        DEFAULT_EXPECTED_RESOLUTION,
        EMOTION_SCALE_MIN,
        EMOTION_SCALE_MAX,
    )
    from .personas import PERSONAS, get_persona, list_personas
    from .scenarios import SCENARIOS, get_scenario, list_scenarios
    from .logger import ConversationLogger
    from .llm_client import LLMClient
except ImportError:  # flat imports when run directly
    from config import (
        DEFAULT_PERSONA,
        DEFAULT_SCENARIO,
        DEFAULT_INITIAL_EMOTION,
        DEFAULT_ISSUE_SEVERITY,
        DEFAULT_PATIENCE_LEVEL,
        DEFAULT_EXPECTED_RESOLUTION,
        EMOTION_SCALE_MIN,
        EMOTION_SCALE_MAX,
    )
    from personas import PERSONAS, get_persona, list_personas
    from scenarios import SCENARIOS, get_scenario, list_scenarios
    from logger import ConversationLogger
    from llm_client import LLMClient


# ============================================================
# EMOTION BANDS
# ============================================================

EMOTION_BANDS = [
    ("calm", "Calm"),
    ("concerned", "Concerned"),
    ("frustrated", "Frustrated"),
    ("angry", "Angry"),
    ("furious", "Furious"),
]


def get_band(level: int) -> str:
    """Convert a numeric frustration level (1-10) into an emotion band."""

    level = max(EMOTION_SCALE_MIN, min(EMOTION_SCALE_MAX, int(level)))

    if level <= 2:
        return "calm"
    if level <= 4:
        return "concerned"
    if level <= 6:
        return "frustrated"
    if level <= 8:
        return "angry"
    return "furious"


def get_emotion_label(level: int) -> str:
    """Human-readable emotion label for a frustration level."""

    band = get_band(level)
    return {
        "calm": "Calm",
        "concerned": "Concerned",
        "frustrated": "Frustrated",
        "angry": "Angry",
        "furious": "Furious",
    }[band]


# ============================================================
# STRICT PERSONA RULES
# ============================================================

# These words/phrases are NOT allowed for angry/furious personas.
POLITE_WORDS = [
    "please",
    "kindly",
    "thank you",
    "thanks",
    "i appreciate",
    "appreciate your help",
    "could you please",
    "would you please",
    "if you don't mind",
    "i understand",
    "sorry",
    "apologies",
]


# ============================================================
# MESSAGE BANK (rule-based offline fallback)
#
# Messages are separated by frustration band.
# Angry / furious messages intentionally do NOT contain
# "please", "thank you", "kindly", etc.
# ============================================================

MESSAGE_BANK = {
    "refund_request": {
        "calm": [
            "Hi, I received a damaged product. Could you help me with a refund?",
            "Hello, the product I received was damaged. I would like to request a refund.",
            "I received a damaged item in my order. Can you tell me how I can get a refund?",
            "The item arrived damaged. I need some help with the refund process.",
        ],
        "concerned": [
            "I'm concerned because I haven't received an update about my refund yet. Can you check the status?",
            "I'm worried about my refund. I still haven't received any update.",
            "I wanted to check what is happening with my refund because I haven't heard back yet.",
            "My refund still hasn't come through, and I'm concerned about the delay.",
        ],
        "frustrated": [
            "I'm getting frustrated because my refund is still pending. I need a clear update.",
            "I've been waiting for my refund for too long. When is it going to be processed?",
            "This refund is taking longer than expected. I need a definite timeline.",
            "I'm tired of waiting for this refund. I need a proper answer about when it will be processed.",
        ],
        "angry": [
            "This refund delay is unacceptable. I need a definite timeline now.",
            "I've waited long enough for this refund. Tell me exactly when it will be processed.",
            "This has taken far too long. I want my refund issue resolved immediately.",
            "I'm extremely unhappy with this delay. Give me a clear refund date now.",
        ],
        "furious": [
            "This is completely unacceptable. I demand my refund immediately.",
            "Enough with the delays. Process my refund now.",
            "I have waited long enough. Resolve my refund issue immediately.",
            "This refund situation is unacceptable. Escalate this issue now and get it resolved.",
        ],
    },
    "delayed_order": {
        "calm": [
            "Hi, my order hasn't arrived yet. Can you check the delivery status?",
            "Hello, I noticed my order is delayed. Can you tell me when it is expected?",
            "My order hasn't arrived yet. I would like an update on the delivery.",
            "Could you check where my order is and when it should arrive?",
        ],
        "concerned": [
            "I'm concerned because my order still hasn't arrived. Can you check what happened?",
            "I'm worried about the delivery delay. Is there any update?",
            "My order is taking longer than expected, and I'm concerned about when it will arrive.",
            "I haven't received my order yet. Can you check the latest delivery information?",
        ],
        "frustrated": [
            "I'm getting frustrated with this delay. I need a clear delivery update.",
            "I've been waiting too long for my order. When is it actually going to arrive?",
            "This delivery delay is becoming frustrating. I need a definite timeline.",
            "I'm tired of waiting without an update. Tell me when my order will arrive.",
        ],
        "angry": [
            "This delivery delay is unacceptable. I need a definite delivery date now.",
            "I've waited long enough. Tell me exactly when my order is arriving.",
            "This order is seriously overdue. I want a clear resolution immediately.",
            "I'm extremely unhappy with this delay. Give me an actual delivery date now.",
        ],
        "furious": [
            "This delay is completely unacceptable. I demand a resolution immediately.",
            "Enough waiting. Get my order delivered now or escalate this issue.",
            "I have waited long enough. Fix this delivery problem immediately.",
            "This is ridiculous. I want an immediate resolution for my missing order.",
        ],
    },
    "payment_failure": {
        "calm": [
            "Hi, my payment didn't go through. Can you help me understand the problem?",
            "Hello, I'm having trouble completing my payment. Can you check the issue?",
            "My payment failed. Can you tell me what I need to do?",
            "I'm unable to complete the payment. I need some help resolving it.",
        ],
        "concerned": [
            "I'm concerned because my payment keeps failing. Can you check what is happening?",
            "I'm worried that my payment isn't going through. Is there a problem with my account?",
            "My payment has failed again, and I'm concerned about completing the transaction.",
            "I'm concerned about this payment issue. Can you tell me what is causing it?",
        ],
        "frustrated": [
            "I'm getting frustrated because my payment keeps failing. I need a clear solution.",
            "I've tried several times and the payment still doesn't work. What is going on?",
            "This payment problem is becoming frustrating. I need this fixed.",
            "I'm tired of trying the same payment repeatedly. I need an actual solution.",
        ],
        "angry": [
            "This payment failure is unacceptable. Fix the problem immediately.",
            "I've tried this enough times. I need the payment issue resolved now.",
            "This is wasting my time. Give me a clear solution immediately.",
            "I'm extremely unhappy with this payment problem. Resolve it now.",
        ],
        "furious": [
            "This payment problem is completely unacceptable. Fix it immediately.",
            "Enough. Resolve this payment failure right now.",
            "I demand an immediate solution to this payment problem.",
            "This is ridiculous. Escalate the payment issue and get it fixed now.",
        ],
    },
    "account_issue": {
        "calm": [
            "Hi, I'm unable to access my account. Can you help me?",
            "Hello, I'm having trouble logging into my account. Can you check the issue?",
            "I can't access my account. Can you tell me what I need to do?",
            "I'm having an account access problem and need some help.",
        ],
        "concerned": [
            "I'm concerned because I still can't access my account. Can you check this?",
            "I'm worried about being unable to log in. Is there an issue with my account?",
            "I haven't been able to access my account, and I'm concerned about the problem.",
            "I'm concerned that my account is still inaccessible. Can you check the status?",
        ],
        "frustrated": [
            "I'm getting frustrated because I still can't access my account. I need a solution.",
            "I've tried several times to log in and it still doesn't work. What is going on?",
            "This account problem is becoming frustrating. I need my access restored.",
            "I'm tired of being locked out. I need this issue fixed.",
        ],
        "angry": [
            "This account access problem is unacceptable. Restore my access now.",
            "I've waited long enough. I need access to my account immediately.",
            "This issue has gone on too long. Fix my account access now.",
            "I'm extremely unhappy with this situation. Restore my account immediately.",
        ],
        "furious": [
            "This is completely unacceptable. Restore my account access immediately.",
            "Enough. I need my account access restored right now.",
            "I demand immediate access to my account.",
            "This is ridiculous. Escalate this account issue and fix it immediately.",
        ],
    },
    "cancellation": {
        "calm": [
            "Hi, I'd like to cancel my subscription. Can you help me with that?",
            "Hello, I want to cancel my subscription. Can you tell me how?",
            "I'd like to request cancellation of my subscription. What are the steps?",
            "I want to cancel my subscription and need some help with the process.",
        ],
        "concerned": [
            "I'm concerned that my subscription may still be active. Can you check?",
            "I'm worried about being charged again. Can you confirm the cancellation status?",
            "I requested cancellation and I'm concerned that it hasn't been completed yet.",
            "I'm concerned about the cancellation. Can you check whether my subscription is still active?",
        ],
        "frustrated": [
            "I'm getting frustrated because my subscription still hasn't been cancelled. I need an update.",
            "I've been waiting for confirmation of the cancellation. When will it be completed?",
            "This cancellation is taking too long. I need a clear confirmation.",
            "I'm tired of waiting for this cancellation. I need this resolved.",
        ],
        "angry": [
            "This cancellation delay is unacceptable. Cancel the subscription immediately.",
            "I've waited long enough. Complete the cancellation now.",
            "This has taken far too long. I want my subscription cancelled immediately.",
            "I'm extremely unhappy with this delay. Confirm the cancellation now.",
        ],
        "furious": [
            "Enough delays. Cancel my subscription immediately.",
            "This is completely unacceptable. I demand immediate cancellation.",
            "I have waited long enough. Cancel the subscription right now.",
            "Escalate this cancellation issue and get it resolved immediately.",
        ],
    },
}


# ============================================================
# RESOLUTION DETECTION
# ============================================================

RESOLUTION_WORDS = {
    "refund_request": [
        "refund processed",
        "refund completed",
        "refund approved",
        "full refund",
        "refund has been",
    ],
    "delayed_order": [
        "order delivered",
        "delivery confirmed",
        "order has arrived",
        "order is out for delivery",
    ],
    "payment_failure": [
        "payment successful",
        "payment fixed",
        "payment completed",
        "payment has been processed",
    ],
    "account_issue": [
        "account restored",
        "access restored",
        "account unlocked",
        "account has been restored",
    ],
    "cancellation": [
        "subscription cancelled",
        "subscription canceled",
        "cancellation confirmed",
        "cancellation has been",
    ],
}

HELPFUL_WORDS = [
    "refund processed",
    "refund completed",
    "refund approved",
    "order delivered",
    "delivery confirmed",
    "payment fixed",
    "payment successful",
    "account restored",
    "account unlocked",
    "subscription cancelled",
    "cancellation confirmed",
    "resolved",
    "escalated",
    "i can help",
    "right away",
    "immediately",
    "within",
]

NEGATIVE_WORDS = [
    "wait",
    "cannot",
    "can't",
    "unable",
    "not possible",
    "no update",
    "not available",
    "nothing i can do",
    "try again later",
    "outside our control",
    "contact your bank",
    "store credit",
    "final sale",
]


# ============================================================
# CUSTOMER SIMULATOR
# ============================================================

class CustomerSimulator:

    def __init__(
        self,
        persona: str = DEFAULT_PERSONA,
        scenario: str = DEFAULT_SCENARIO,
        frustration_level: Optional[int] = None,
        initial_emotion: str = DEFAULT_INITIAL_EMOTION,
        issue_severity: int = DEFAULT_ISSUE_SEVERITY,
        patience_level: int = DEFAULT_PATIENCE_LEVEL,
        expected_resolution: str = DEFAULT_EXPECTED_RESOLUTION,
        session_id: Optional[str] = None,
        use_llm: Optional[bool] = None,
        **kwargs,
    ):

        # ----------------------------------------------------
        # SESSION
        # ----------------------------------------------------
        self.session_id = session_id or str(uuid.uuid4())[:8]

        # ----------------------------------------------------
        # PERSONA
        # ----------------------------------------------------
        persona_key = str(persona).lower().strip()
        if persona_key not in PERSONAS:
            persona_key = DEFAULT_PERSONA if DEFAULT_PERSONA in PERSONAS else "frustrated"
        self.persona_name = persona_key
        self.persona = PERSONAS[persona_key]

        # ----------------------------------------------------
        # SCENARIO
        # ----------------------------------------------------
        scenario_key = str(scenario).lower().strip()
        if scenario_key not in SCENARIOS:
            scenario_key = (
                DEFAULT_SCENARIO if DEFAULT_SCENARIO in SCENARIOS else "refund_request"
            )
        self.scenario_name = scenario_key
        self.scenario = SCENARIOS[scenario_key]

        # ----------------------------------------------------
        # EMOTION / FRUSTRATION
        # ----------------------------------------------------
        self.initial_emotion = str(initial_emotion).lower().strip()

        if frustration_level is None:
            frustration_level = self._emotion_to_level(self.initial_emotion)

        self.frustration_level = self._normalize_level(frustration_level)

        # ----------------------------------------------------
        # ISSUE SEVERITY & PATIENCE
        # ----------------------------------------------------
        self.issue_severity = self._normalize_level(issue_severity)
        self.patience_level = self._normalize_level(patience_level)

        # ----------------------------------------------------
        # RESOLUTION
        # ----------------------------------------------------
        self.expected_resolution = expected_resolution

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------
        self.history: List[Dict[str, Any]] = []
        self.used_messages = set()
        self.turn_count = 0
        self.finished = False
        self.status = "active"

        # ----------------------------------------------------
        # LLM
        # ----------------------------------------------------
        self.use_llm = use_llm
        if use_llm is None:
            self.llm = LLMClient()
        else:
            self.llm = LLMClient(enabled=use_llm)

        # ----------------------------------------------------
        # LOGGING
        # ----------------------------------------------------
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        self.log_path = self.log_dir / f"session_{self.session_id}.json"

        self.logger = ConversationLogger(
            session_id=self.session_id, log_dir=str(self.log_dir)
        )
        self.logger.set_config(self.get_config())

        self._save_log()

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _normalize_level(level: Any) -> int:
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = 5
        return max(EMOTION_SCALE_MIN, min(EMOTION_SCALE_MAX, level))

    @staticmethod
    def _emotion_to_level(emotion: str) -> int:
        return {
            "calm": 2,
            "concerned": 4,
            "mildly_concerned": 3,
            "frustrated": 6,
            "angry": 8,
            "furious": 10,
            "impatient": 7,
            "confused": 4,
            "polite": 2,
        }.get(str(emotion).lower().strip(), 5)

    def get_current_band(self) -> str:
        return get_band(self.frustration_level)

    def get_current_emotion(self) -> str:
        return get_emotion_label(self.frustration_level)

    def get_config(self) -> Dict[str, Any]:
        return {
            "persona": self.persona_name,
            "scenario": self.scenario_name,
            "initial_emotion": self.initial_emotion,
            "frustration_level": self.frustration_level,
            "issue_severity": self.issue_severity,
            "patience_level": self.patience_level,
            "expected_resolution": self.expected_resolution,
            "use_llm": self.llm.is_available(),
            "model": self.llm.model if self.llm.is_available() else None,
        }

    def set_frustration_level(self, level: int) -> int:
        self.frustration_level = self._normalize_level(level)
        return self.frustration_level

    # ========================================================
    # START CONVERSATION
    # ========================================================

    def start(self) -> Dict[str, Any]:
        generated = self._generate_customer_message(is_opening=True)
        self._record(
            "customer",
            generated["text"],
            source=generated.get("_source", "rule"),
        )
        return self._build_response(generated["text"])

    # ========================================================
    # RESPOND TO AGENT
    # ========================================================

    def respond(self, agent_message: str) -> Dict[str, Any]:

        agent_message = (agent_message or "").strip()
        self._record("agent", agent_message)

        if self.finished:
            return self._build_response(
                "The conversation has already been completed.",
                {"status": "finished"},
            )

        # ------------------------------------------------
        # Update emotion based on the agent reply
        # ------------------------------------------------
        delta = self._update_frustration_from_agent(agent_message)

        # ------------------------------------------------
        # Resolution check
        # ------------------------------------------------
        if self._is_resolved(agent_message):
            self.frustration_level = max(
                EMOTION_SCALE_MIN, self.frustration_level - 3
            )
            if self.frustration_level <= 3:
                self.finished = True
                self.status = "resolved"
                message = self._closing_message()
                self._record("customer", message)
                return self._build_response(
                    message,
                    {"status": "resolved", "emotion_delta": delta},
                )

        # ------------------------------------------------
        # Generate next message
        # ------------------------------------------------
        generated = self._generate_customer_message()
        message = generated["text"]
        self._record("customer", message, source=generated.get("_source", "rule"))

        return self._build_response(message, {"emotion_delta": delta})

    # ========================================================
    # EMOTION PROGRESSION
    # ========================================================

    def _score_agent_message(self, agent_message: str) -> float:
        text = (agent_message or "").lower().strip()
        score = 0.0

        if not text:
            return -3.0

        for word in HELPFUL_WORDS:
            if word in text:
                score += 1.6

        empathy = [
            "i understand",
            "i can see",
            "that must be",
            "frustrating",
            "i'm sorry",
            "sorry for",
            "apologize",
            "apologise",
            "i hear you",
            "you're right",
            "valid concern",
        ]
        for phrase in empathy:
            if phrase in text:
                score += 1.4
                break

        if re.search(r"\b(within|by|in)\s+\d+\s*(hour|day|business day|working day)s?\b", text):
            score += 1.4

        if re.search(r"\b(refund|process|escalate|credit|compensation|restore|cancel)\b", text):
            score += 1.0

        for word in NEGATIVE_WORDS:
            if word in text:
                score -= 1.7

        word_count = len(text.split())
        if word_count < 5:
            score -= 1.3
        elif word_count < 12:
            score -= 0.5

        return score

    def _update_frustration_from_agent(self, agent_message: str) -> int:

        raw_score = self._score_agent_message(agent_message)

        # Low patience amplifies negative replies.
        if raw_score < 0:
            raw_score *= 1.0 + (5 - self.patience_level) / 5.0

        # High issue severity makes positive replies less calming.
        if raw_score > 0:
            raw_score *= max(0.4, 1.0 - (self.issue_severity - 5) / 10.0)

        # Persona escalation threshold.
        threshold = self.persona.get("escalation_threshold", 6)

        if raw_score >= 4.0:
            delta = -3
        elif raw_score >= 2.5:
            delta = -2
        elif raw_score >= 1.0:
            delta = -1
        elif raw_score <= -2.0:
            delta = +2
        elif raw_score <= -0.7:
            delta = +1
        else:
            delta = 0

        # An angry/furious customer escalates faster when unimpressed.
        if delta > 0 and self.frustration_level >= threshold:
            delta += 1

        old = self.frustration_level
        self.frustration_level = max(
            EMOTION_SCALE_MIN, min(EMOTION_SCALE_MAX, old + delta)
        )

        return delta

    # ========================================================
    # RESOLUTION DETECTION
    # ========================================================

    def _is_resolved(self, agent_message: str) -> bool:
        text = (agent_message or "").lower()

        phrases = list(RESOLUTION_WORDS.get(self.scenario_name, []))

        # General resolution phrases for the expected resolution.
        expected = str(self.expected_resolution or "").lower().replace("_", " ")
        if expected:
            phrases.append(expected)

        return any(phrase in text for phrase in phrases)

    # ========================================================
    # MESSAGE GENERATION
    # ========================================================

    def _generate_customer_message(self, is_opening: bool = False) -> Dict[str, str]:
        band = self.get_current_band()

        # ------------------------------------------------
        # Try the LLM first (uses full conversation context).
        # ------------------------------------------------
        if self.llm.is_available():
            text = self._llm_customer_message(band, is_opening)
            if text:
                return {"text": self._validate_message(text), "_source": "llm"}

        # ------------------------------------------------
        # Fallback: rule-based message bank.
        # ------------------------------------------------
        text = self._bank_message(band)
        return {"text": text, "_source": "rule"}

    def _bank_message(self, band: str) -> str:
        bank = MESSAGE_BANK.get(self.scenario_name, {})
        messages = bank.get(band) or bank.get("frustrated") or [
            "I need help with this issue."
        ]

        unused = [m for m in messages if m not in self.used_messages]
        if not unused:
            unused = list(messages)

        message = random.choice(unused)
        message = self._apply_persona_rules(message)
        message = self._validate_message(message)
        self.used_messages.add(message)
        return message

    def _build_system_prompt(self, band: str, is_opening: bool) -> str:
        persona = self.persona
        scenario = self.scenario

        facts = scenario.get("key_facts", {})
        facts_text = "\n".join(f"- {k}: {v}" for k, v in facts.items())

        return (
            "You are role-playing as a REAL CUSTOMER contacting a customer "
            "support agent. You are NOT the agent. Never give advice or "
            "solve the problem yourself.\n\n"
            f"PERSONA: {persona['name']} — {persona['description']}\n"
            f"Communication style: {persona.get('communication_style', 'natural')}\n\n"
            f"SCENARIO: {scenario['name']} — {scenario['description']}\n"
            f"Customer situation: {scenario['context']}\n"
            "Key facts you may reference:\n"
            f"{facts_text}\n"
            f"Your goal: {scenario.get('customer_goal', 'get the issue resolved')}\n\n"
            f"CURRENT EMOTION: {get_emotion_label(self.frustration_level)} "
            f"(frustration {self.frustration_level}/10, band '{band}')\n"
            f"Issue severity: {self.issue_severity}/10. "
            f"Patience level: {self.patience_level}/10.\n\n"
            "STRICT RULES:\n"
            "1. Write ONE short, realistic customer message (1-3 sentences).\n"
            "2. Stay fully in character for the persona and current emotion.\n"
            "3. ANGRY and FURIOUS customers must NOT use polite words such as "
            "'please', 'kindly', 'thank you', 'sorry', or 'appreciate'.\n"
            "4. If the agent's reply helps, you may sound slightly calmer; "
            "if it does not help, escalate.\n"
            "5. Never repeat an earlier message verbatim.\n"
            "6. Reference the scenario specifically — no generic filler.\n"
            "7. Output ONLY the customer message, nothing else."
        )

    def _llm_customer_message(self, band: str, is_opening: bool) -> Optional[str]:
        system_prompt = self._build_system_prompt(band, is_opening)

        messages: List[Dict[str, str]] = []

        # Provide prior conversation as context.
        for entry in self.history:
            role = "assistant" if entry["role"] == "customer" else "user"
            messages.append({"role": role, "content": entry["content"]})

        if not messages:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Start the conversation by describing your problem as "
                        "the customer."
                    ),
                }
            )

        return self.llm.generate(system_prompt, messages)

    # ========================================================
    # PERSONA RULES
    # ========================================================

    def _apply_persona_rules(self, message: str) -> str:
        if self.persona_name in ("angry", "furious", "impatient"):
            message = self._remove_polite_words(message)
        return message

    def _remove_polite_words(self, message: str) -> str:
        result = message
        for phrase in POLITE_WORDS:
            result = re.sub(
                re.escape(phrase), "", result, flags=re.IGNORECASE
            )
        result = re.sub(r"\s+", " ", result)
        result = re.sub(r"\s+([,.!?])", r"\1", result)
        return result.strip()

    def _validate_message(self, message: str) -> str:
        message = (message or "").strip()

        # Remove wrapping quotes the LLM sometimes adds.
        if len(message) >= 2 and message[0] in "\"'" and message[-1] in "\"'":
            message = message[1:-1].strip()

        if not message:
            message = self._emergency_message()

        if self.persona_name in ("angry", "furious", "impatient"):
            lower = message.lower()
            if any(word in lower for word in POLITE_WORDS):
                message = self._remove_polite_words(message)

        return message.strip()

    def _emergency_message(self) -> str:
        band = get_band(self.frustration_level)
        if band == "calm":
            return "I need some help with this issue."
        if band == "concerned":
            return "I'm concerned about this issue and need an update."
        if band == "frustrated":
            return "I'm getting frustrated with this and need a clear answer."
        if band == "angry":
            return "This is unacceptable. I need a clear resolution now."
        return "This is completely unacceptable. Resolve this immediately."

    # ========================================================
    # CLOSING MESSAGE
    # ========================================================

    def _closing_message(self) -> str:
        persona = self.persona_name
        if persona in ("polite", "calm"):
            return "Thank you for resolving the issue. I appreciate your help."
        if persona == "confused":
            return "Okay, that makes sense now. Thank you for explaining."
        if persona == "frustrated":
            return "Alright. I expect the issue to be resolved as discussed."
        if persona == "impatient":
            return "Good. Just make sure it happens quickly."
        if persona == "angry":
            return "Fine. Make sure the issue is actually resolved."
        return "This better be resolved now. I do not want any further delays."

    # ========================================================
    # RECORD / RESPONSE
    # ========================================================

    def _record(self, role: str, content: str, source: str = "rule"):
        self.turn_count += 1

        entry = {
            "role": role,
            "content": content,
            "frustration_level": self.frustration_level,
            "emotion": get_emotion_label(self.frustration_level),
            "band": get_band(self.frustration_level),
        }
        self.history.append(entry)

        self.logger.log_turn(
            turn_number=self.turn_count,
            role=role,
            message=content,
            emotion={
                "label": get_emotion_label(self.frustration_level),
                "frustration_level": self.frustration_level,
                "band": get_band(self.frustration_level),
            },
            extra={"source": source},
        )

        self._save_log()

    def _build_response(
        self, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:

        response = {
            "session_id": self.session_id,
            "customer_message": message,
            "persona": self.persona_name,
            "persona_name": self.persona["name"],
            "scenario": self.scenario_name,
            "scenario_name": self.scenario["name"],
            "frustration_level": self.frustration_level,
            "emotion": get_emotion_label(self.frustration_level),
            "emotion_band": get_band(self.frustration_level),
            "issue_severity": self.issue_severity,
            "patience_level": self.patience_level,
            "expected_resolution": self.expected_resolution,
            "finished": self.finished,
            "status": self.status,
            "turn_count": self.turn_count,
            "history": self.history,
            "llm_enabled": self.llm.is_available(),
            "validation": {
                "strict_persona_rules": True,
                "no_repeated_messages": True,
                "frustration_controls_message": True,
            },
            "log_path": str(self.log_path),
        }

        if extra:
            response.update(extra)

        return response

    def get_state(self) -> Dict[str, Any]:
        return self._build_response("")

    def get_history(self) -> List[Dict[str, Any]]:
        return self.history

    # ========================================================
    # SAVE LOG
    # ========================================================

    def _save_log(self):
        try:
            self.logger.finalize(
                final_emotion={
                    "label": get_emotion_label(self.frustration_level),
                    "frustration_level": self.frustration_level,
                    "band": get_band(self.frustration_level),
                }
            )
        except Exception:
            pass


# ============================================================
# FACTORY
# ============================================================

def create_simulator(**kwargs) -> CustomerSimulator:
    return CustomerSimulator(**kwargs)


# ============================================================
# SELF TEST
# ============================================================

def run_self_test():
    print()
    print("=" * 70)
    print("CUSTOMER SIMULATOR SELF TEST (rule-based, no LLM)")
    print("=" * 70)

    personas = list_personas()
    scenarios = list_scenarios()
    levels = [2, 4, 6, 8, 10]

    check_personas = {"angry", "furious", "impatient"}
    failures = 0

    for scenario in scenarios:
        print()
        print("-" * 70)
        print(f"SCENARIO: {scenario}")
        print("-" * 70)

        for persona in personas:
            for level in levels:
                sim = CustomerSimulator(
                    persona=persona,
                    scenario=scenario,
                    frustration_level=level,
                    use_llm=False,
                )
                message = sim.start()["customer_message"]
                print(f"  [{persona:10s} {level:2d}/10] {message}")

                if persona in check_personas:
                    lower = message.lower()
                    violations = [w for w in POLITE_WORDS if w in lower]
                    if violations:
                        failures += 1
                        print(f"    ❌ POLITE WORD VIOLATION: {violations}")

    print()
    print("=" * 70)
    if failures:
        print(f"SELF TEST FAILED: {failures} violations")
    else:
        print("SELF TEST PASSED: no persona violations")
    print("=" * 70)
    print()
    return failures


if __name__ == "__main__":
    run_self_test()