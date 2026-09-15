"""
Customer Simulator Agent – core logic.

The simulator generates realistic customer responses based on:
- Customer persona
- Scenario
- Frustration level
- Expected resolution
- Optional Groq LLM generation

Patience Level and Issue Severity are retained for backward compatibility
with older API/frontend configurations but are not used as the primary
emotional control.
"""

import os
import uuid
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

try:
    from groq import Groq
except ImportError:
    Groq = None  # type: ignore

from .config import (
    GROQ_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    MAX_TOKENS,
    DEFAULT_PERSONA,
    DEFAULT_SCENARIO,
    DEFAULT_INITIAL_EMOTION,
    DEFAULT_ISSUE_SEVERITY,
    DEFAULT_PATIENCE_LEVEL,
    DEFAULT_EXPECTED_RESOLUTION,
)

from .personas import get_persona
from .scenarios import get_scenario
from .emotion_manager import EmotionManager
from .logger import ConversationLogger


class CustomerSimulator:

    def __init__(
        self,
        persona: str = DEFAULT_PERSONA,
        scenario: str = DEFAULT_SCENARIO,
        initial_emotion: str = DEFAULT_INITIAL_EMOTION,
        issue_severity: int = DEFAULT_ISSUE_SEVERITY,
        patience_level: int = DEFAULT_PATIENCE_LEVEL,
        expected_resolution: str = DEFAULT_EXPECTED_RESOLUTION,
        session_id: Optional[str] = None,
        use_llm: bool = True,
        frustration_level: Optional[int] = None,
    ):
        # ---------------------------------------------------------
        # Session
        # ---------------------------------------------------------
        self.session_id = session_id or str(uuid.uuid4())[:8]

        # ---------------------------------------------------------
        # Basic configuration
        # ---------------------------------------------------------
        self.persona_name = persona.lower()
        self.scenario_name = scenario.lower()

        self.issue_severity = max(
            1,
            min(10, int(issue_severity))
        )

        self.patience_level = max(
            1,
            min(10, int(patience_level))
        )

        self.expected_resolution = expected_resolution

        # ---------------------------------------------------------
        # Frustration level
        #
        # New design:
        # frustration_level is the primary emotional control.
        #
        # Backward compatibility:
        # if frustration_level is not supplied, derive a sensible
        # starting intensity from initial_emotion.
        # ---------------------------------------------------------
        if frustration_level is not None:
            self.frustration_level = max(
                1,
                min(10, int(frustration_level))
            )
        else:
            emotion_to_intensity = {
                "calm": 2,
                "confused": 3,
                "concerned": 4,
                "mildly_concerned": 4,
                "frustrated": 5,
                "angry": 7,
                "impatient": 7,
                "furious": 9,
                "polite": 2,
            }

            self.frustration_level = emotion_to_intensity.get(
                initial_emotion.lower(),
                5
            )

        # ---------------------------------------------------------
        # LLM configuration
        # ---------------------------------------------------------
        self.use_llm = (
            use_llm
            and bool(GROQ_API_KEY)
            and Groq is not None
        )

        # ---------------------------------------------------------
        # Persona and scenario
        # ---------------------------------------------------------
        self.persona = get_persona(self.persona_name)
        self.scenario = get_scenario(self.scenario_name)

        # ---------------------------------------------------------
        # Emotion manager
        #
        # IMPORTANT:
        # EmotionManager does NOT accept patience_level.
        # Use initial_intensity instead.
        # ---------------------------------------------------------
        self.emotion_mgr = EmotionManager(
            initial_emotion=initial_emotion,
            initial_intensity=self.frustration_level,
            persona_modifier=self.persona.get(
                "patience_modifier",
                0
            ),
        )

        # ---------------------------------------------------------
        # Conversation state
        # ---------------------------------------------------------
        self.history: List[Dict[str, str]] = []
        self.turn_count = 0
        self.finished = False

        # ---------------------------------------------------------
        # Logger
        # ---------------------------------------------------------
        self.logger = ConversationLogger(self.session_id)

        self.logger.set_config(
            {
                "persona": self.persona_name,
                "scenario": self.scenario_name,
                "initial_emotion": initial_emotion,
                "frustration_level": self.frustration_level,
                "issue_severity": self.issue_severity,
                "patience_level": self.patience_level,
                "expected_resolution": self.expected_resolution,
                "use_llm": self.use_llm,
            }
        )

        # ---------------------------------------------------------
        # Groq client
        # ---------------------------------------------------------
        self.client = None

        if self.use_llm:
            self.client = Groq(
                api_key=GROQ_API_KEY
            )

    # =============================================================
    # SESSION START
    # =============================================================

    def start(self) -> Dict[str, Any]:
        """
        Start the customer conversation.
        """

        opening = self._generate_customer_message(
            is_opening=True
        )

        self._record(
            "customer",
            opening
        )

        return self._build_response(
            opening
        )

    # =============================================================
    # CUSTOMER RESPONSE
    # =============================================================

    def respond(
        self,
        agent_message: str
    ) -> Dict[str, Any]:
        """
        Process the support agent's response and generate
        the customer's next response.
        """

        if self.finished:
            return self._build_response(
                "I think we're done here. Thank you.",
                extra={
                    "status": "already_finished"
                },
            )

        # ---------------------------------------------------------
        # Record agent message
        # ---------------------------------------------------------
        self._record(
            "agent",
            agent_message
        )

        # ---------------------------------------------------------
        # Update emotion based on agent response
        # ---------------------------------------------------------
        emotion = self.emotion_mgr.update(
            agent_message
        )

        # Keep public frustration level synchronized
        self.frustration_level = emotion.intensity

        # ---------------------------------------------------------
        # Check whether conversation should end
        # ---------------------------------------------------------
        if self._should_end(
            agent_message,
            emotion
        ):
            closing = self._generate_closing(
                agent_message
            )

            self._record(
                "customer",
                closing
            )

            self.finished = True

            self.logger.finalize(
                emotion.to_dict()
            )

            return self._build_response(
                closing,
                extra={
                    "status": "resolved"
                },
            )

        # ---------------------------------------------------------
        # Generate next customer message
        # ---------------------------------------------------------
        next_msg = self._generate_customer_message(
            is_opening=False
        )

        self._record(
            "customer",
            next_msg
        )

        return self._build_response(
            next_msg
        )

    # =============================================================
    # GET SESSION STATE
    # =============================================================

    def get_state(self) -> Dict[str, Any]:
        """
        Return current session state.
        """

        emotion = self.emotion_mgr.get_state()

        return {
            "session_id": self.session_id,
            "persona": self.persona_name,
            "scenario": self.scenario_name,
            "turn_count": self.turn_count,
            "emotion": emotion.to_dict(),
            "frustration_level": emotion.intensity,
            "issue_severity": self.issue_severity,
            "patience_level": self.patience_level,
            "expected_resolution": self.expected_resolution,
            "finished": self.finished,
            "history": self.history,
            "log_path": self.logger.get_log_path(),
        }

    # =============================================================
    # RECORD MESSAGE
    # =============================================================

    def _record(
        self,
        role: str,
        content: str
    ):
        """
        Record a conversation message.
        """

        self.turn_count += 1

        self.history.append(
            {
                "role": role,
                "content": content,
            }
        )

        emotion = (
            self.emotion_mgr
            .get_state()
            .to_dict()
            if role == "customer"
            else None
        )

        self.logger.log_turn(
            turn_number=self.turn_count,
            role=role,
            message=content,
            emotion=emotion,
        )

    # =============================================================
    # RESPONSE BUILDER
    # =============================================================

    def _build_response(
        self,
        customer_message: str,
        extra: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Build API response payload.
        """

        emotion = self.emotion_mgr.get_state()

        self.frustration_level = emotion.intensity

        payload = {
            "session_id": self.session_id,
            "customer_message": customer_message,
            "emotion": emotion.to_dict(),
            "frustration_level": emotion.intensity,
            "turn": self.turn_count,
            "finished": self.finished,
            "persona": self.persona_name,
            "scenario": self.scenario_name,
        }

        if extra:
            payload.update(extra)

        return payload

    # =============================================================
    # END CONDITION
    # =============================================================

    def _should_end(
        self,
        agent_message: str,
        emotion
    ) -> bool:
        """
        Decide whether the customer conversation should end.
        """

        text = agent_message.lower()

        positive = any(
            keyword in text
            for keyword in [
                "refund has been processed",
                "refund will be",
                "i have processed",
                "cancellation confirmed",
                "account has been unlocked",
                "new delivery date",
                "i've escalated",
                "compensation of",
            ]
        )

        # Successful resolution + low enough frustration
        if positive and emotion.intensity <= 4:
            return True

        # Safety limit for extremely long sessions
        if self.turn_count >= 14:
            return True

        return False

    # =============================================================
    # CLOSING MESSAGE
    # =============================================================

    def _generate_closing(
        self,
        agent_message: str
    ) -> str:
        """
        Generate final customer response based on emotion.
        """

        emotion = self.emotion_mgr.get_state()

        if emotion.intensity <= 3:
            return (
                "Thank you, that resolves it for me. "
                "I appreciate your help."
            )

        if emotion.intensity <= 6:
            return (
                "Alright, I'll take that. "
                "Please make sure it actually happens."
            )

        return (
            "Fine. I'll be watching my account closely. "
            "This better be fixed."
        )

    # =============================================================
    # CUSTOMER MESSAGE GENERATION
    # =============================================================

    def _generate_customer_message(
        self,
        is_opening: bool = False
    ) -> str:
        """
        Generate customer message using Groq or rule-based fallback.
        """

        if self.use_llm and self.client:
            try:
                return self._llm_generate(
                    is_opening
                )

            except Exception as e:
                print(
                    f"[Simulator] LLM error: {e}. "
                    "Falling back to rule-based."
                )

                return self._rule_based_generate(
                    is_opening
                )

        return self._rule_based_generate(
            is_opening
        )

    # =============================================================
    # SYSTEM PROMPT
    # =============================================================

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for Groq.
        """

        emotion = self.emotion_mgr.get_state()

        facts = json.dumps(
            self.scenario["key_facts"],
            indent=2
        )

        return f"""
You are role-playing as a real customer talking to a company support agent in a live chat.

PERSONA: {self.persona['name']}
- Style: {self.persona['communication_style']}
- Typical vocabulary: {', '.join(self.persona['vocabulary'])}
- Behavior notes: {self.persona['behavior_notes']}

SCENARIO: {self.scenario['name']}
- Context: {self.scenario['context']}
- Key facts you know (use them naturally, do not invent new order numbers):
{facts}
- Your goal: {self.scenario['customer_goal']}

CURRENT EMOTIONAL STATE:
{emotion.label} (intensity {emotion.intensity}/10)

Frustration level:
{self.frustration_level}/10

Issue severity:
{self.issue_severity}/10

Expected resolution:
{self.expected_resolution}

RULES:
1. Reply ONLY as the customer.
2. Never break character or mention you are an AI.
3. Keep messages realistic: 1-4 sentences.
4. Match the communication style of the persona.
5. Reflect the current emotion in tone, word choice, and punctuation.
6. Stay consistent with previous messages.
7. Do not solve the problem yourself.
8. Push the support agent toward the resolution you want.
9. Never invent new order IDs, amounts, or dates.
10. Use only the scenario key facts.
11. If the agent is helpful, you may soften.
12. If the agent is dismissive, you may become more frustrated.
13. Output ONLY the customer's next message text.
14. Do not use quotes, labels, or additional commentary.
"""

    # =============================================================
    # GROQ GENERATION
    # =============================================================

    def _llm_generate(
        self,
        is_opening: bool
    ) -> str:
        """
        Generate customer response using Groq.
        """

        system = self._build_system_prompt()

        messages = [
            {
                "role": "system",
                "content": system,
            }
        ]

        # ---------------------------------------------------------
        # Add recent conversation history
        # ---------------------------------------------------------
        for turn in self.history[-8:]:
            role = (
                "user"
                if turn["role"] == "agent"
                else "assistant"
            )

            messages.append(
                {
                    "role": role,
                    "content": turn["content"],
                }
            )

        # ---------------------------------------------------------
        # Opening message
        # ---------------------------------------------------------
        if is_opening:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "The chat has just started. "
                        "Write the customer's FIRST message "
                        "describing the problem and what they want. "
                        "Be natural for the persona."
                    ),
                }
            )

        # ---------------------------------------------------------
        # Continuing message
        # ---------------------------------------------------------
        else:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "The support agent just replied "
                        "(see history). Write the customer's "
                        "next realistic reply continuing "
                        "the conversation."
                    ),
                }
            )

        # ---------------------------------------------------------
        # Groq request
        # ---------------------------------------------------------
        response = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        text = response.choices[0].message.content.strip()

        # Remove accidental surrounding quotes
        if (
            text.startswith('"')
            and text.endswith('"')
        ):
            text = text[1:-1]

        return text

    # =============================================================
    # RULE-BASED GENERATION
    # =============================================================

    def _rule_based_generate(
        self,
        is_opening: bool
    ) -> str:
        """
        Generate customer messages without an LLM.
        """

        emotion = self.emotion_mgr.get_state()

        facts = self.scenario["key_facts"]

        intensity = emotion.intensity

        # ---------------------------------------------------------
        # Opening messages
        # ---------------------------------------------------------
        if is_opening:

            templates = {

                "refund_request": {
                    "low": (
                        f"Hi, I received order "
                        f"{facts.get('order_id')} and the "
                        f"{facts.get('product')} is damaged. "
                        f"I'd like a refund of "
                        f"{facts.get('amount')} please."
                    ),

                    "mid": (
                        f"I need a refund for order "
                        f"{facts.get('order_id')}. The "
                        f"{facts.get('product')} arrived damaged "
                        f"- {facts.get('reason')}. "
                        f"This is not acceptable."
                    ),

                    "high": (
                        f"I want a FULL REFUND for order "
                        f"{facts.get('order_id')} RIGHT NOW. "
                        f"The {facts.get('product')} is cracked "
                        f"and unusable. "
                        f"{facts.get('amount')} back to my card!"
                    ),
                },

                "delayed_order": {
                    "low": (
                        f"Hello, my order "
                        f"{facts.get('order_id')} for the "
                        f"{facts.get('product')} was supposed "
                        f"to arrive "
                        f"{facts.get('promised_delivery')}. "
                        f"Can you check the status?"
                    ),

                    "mid": (
                        f"Order {facts.get('order_id')} is late. "
                        f"Tracking "
                        f"{facts.get('tracking_number')} "
                        f"hasn't updated in days. "
                        f"I need it this week."
                    ),

                    "high": (
                        f"Where is my order "
                        f"{facts.get('order_id')}?! "
                        f"It was due "
                        f"{facts.get('promised_delivery')} "
                        f"and still nothing. "
                        f"This is ridiculous!"
                    ),
                },

                "payment_failure": {
                    "low": (
                        f"Hi, I tried to pay for my "
                        f"{facts.get('subscription')} but it failed. "
                        f"Card ending "
                        f"{facts.get('card_last4')}. "
                        f"Can you help?"
                    ),

                    "mid": (
                        f"My payment of "
                        f"{facts.get('amount')} for "
                        f"{facts.get('subscription')} "
                        f"keeps declining even though I have funds. "
                        f"Please fix this."
                    ),

                    "high": (
                        f"You charged me / declined my card for "
                        f"{facts.get('amount')} and the service "
                        f"isn't active! Sort this out immediately."
                    ),
                },

                "account_issue": {
                    "low": (
                        f"Hello, I can't log into my account "
                        f"({facts.get('account_email')}). "
                        f"The password reset isn't working."
                    ),

                    "mid": (
                        f"I'm locked out of my account. "
                        f"Last login was "
                        f"{facts.get('last_successful_login')}. "
                        f"I need access restored today."
                    ),

                    "high": (
                        "My account is locked and it shows "
                        "the wrong plan! Fix this now - "
                        "I pay for Premium!"
                    ),
                },

                "cancellation": {
                    "low": (
                        f"Hi, I'd like to cancel my "
                        f"{facts.get('subscription')}. "
                        f"Please confirm when it will end."
                    ),

                    "mid": (
                        f"Please cancel my "
                        f"{facts.get('subscription')} "
                        f"and stop all future charges. "
                        f"I no longer need it."
                    ),

                    "high": (
                        "Cancel my subscription NOW. "
                        "Stop charging me. "
                        "I want confirmation in writing."
                    ),
                },
            }

            level = (
                "high"
                if intensity >= 7
                else (
                    "mid"
                    if intensity >= 4
                    else "low"
                )
            )

            scenario_templates = templates.get(
                self.scenario_name,
                templates["refund_request"]
            )

            return scenario_templates[level]

        # ---------------------------------------------------------
        # Follow-up messages
        # ---------------------------------------------------------
        if intensity >= 8:
            return (
                "That doesn't help. I need this fixed "
                "immediately or I'm escalating to a manager."
            )

        if intensity >= 6:
            return (
                "I already explained the problem. "
                "Can you please give me a clear next step "
                "and a timeline?"
            )

        if intensity >= 4:
            return (
                "Okay, but I still need a concrete resolution. "
                "What exactly will you do and when?"
            )

        return (
            "Thank you. Could you confirm the details "
            "so I know it's taken care of?"
        )


# =============================================================
# FACTORY
# =============================================================

def create_simulator(
    **kwargs
) -> CustomerSimulator:
    """
    Factory function used by the FastAPI application.
    """

    return CustomerSimulator(
        **kwargs
    )