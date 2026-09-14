"""
Customer Simulator Agent – core logic.

Persona controls the customer's communication style.
Frustration level controls emotional intensity.

Frustration scale:
1-2  = calm / polite
3-4  = concerned
5-6  = frustrated
7-8  = angry
9-10 = furious
"""

import uuid
import json
from typing import Dict, Any, List, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

from config import (
    OPENAI_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    MAX_TOKENS,
    DEFAULT_PERSONA,
    DEFAULT_SCENARIO,
    DEFAULT_INITIAL_EMOTION,
    DEFAULT_ISSUE_SEVERITY,
    DEFAULT_EXPECTED_RESOLUTION,
)

from personas import get_persona
from scenarios import get_scenario
from emotion_manager import EmotionManager
from logger import ConversationLogger


class CustomerSimulator:

    def __init__(
        self,
        persona: str = DEFAULT_PERSONA,
        scenario: str = DEFAULT_SCENARIO,
        initial_emotion: str = DEFAULT_INITIAL_EMOTION,
        issue_severity: int = DEFAULT_ISSUE_SEVERITY,
        frustration_level: int = 5,
        expected_resolution: str = DEFAULT_EXPECTED_RESOLUTION,
        session_id: Optional[str] = None,
        use_llm: bool = True,
    ):

        # =========================================================
        # BASIC CONFIGURATION
        # =========================================================

        self.session_id = session_id or str(uuid.uuid4())[:8]

        self.persona_name = persona.lower().strip()
        self.scenario_name = scenario.lower().strip()

        self.issue_severity = max(
            1,
            min(10, int(issue_severity))
        )

        self.frustration_level = max(
            1,
            min(10, int(frustration_level))
        )

        self.expected_resolution = expected_resolution

        self.use_llm = (
            use_llm
            and bool(OPENAI_API_KEY)
            and OpenAI is not None
        )

        # =========================================================
        # LOAD PERSONA / SCENARIO
        # =========================================================

        self.persona = get_persona(
            self.persona_name
        )

        self.scenario = get_scenario(
            self.scenario_name
        )

        # =========================================================
        # EMOTION MANAGER
        # =========================================================

        try:

            self.emotion_mgr = EmotionManager(
                initial_emotion=initial_emotion,
                frustration_level=self.frustration_level,
            )

        except TypeError:

            self.emotion_mgr = EmotionManager(
                initial_emotion=initial_emotion,
                initial_intensity=self.frustration_level,
            )

        # Make sure selected frustration level
        # becomes starting emotional intensity.

        try:

            self.emotion_mgr.force_set(
                self.frustration_level,
                reason="selected frustration level",
            )

        except Exception:

            pass

        # =========================================================
        # CONVERSATION STATE
        # =========================================================

        self.history: List[Dict[str, str]] = []

        self.turn_count = 0

        self.finished = False

        # =========================================================
        # LOGGER
        # =========================================================

        self.logger = ConversationLogger(
            self.session_id
        )

        self.logger.set_config({

            "persona": self.persona_name,

            "scenario": self.scenario_name,

            "initial_emotion": initial_emotion,

            "issue_severity": self.issue_severity,

            "frustration_level": self.frustration_level,

            "expected_resolution": self.expected_resolution,

            "use_llm": self.use_llm,
        })

        # =========================================================
        # OPENAI CLIENT
        # =========================================================

        self.client = None

        if self.use_llm:

            self.client = OpenAI(
                api_key=OPENAI_API_KEY
            )

    # =============================================================
    # SESSION START
    # =============================================================

    def start(self) -> Dict[str, Any]:

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
    # AGENT RESPONSE
    # =============================================================

    def respond(
        self,
        agent_message: str
    ) -> Dict[str, Any]:

        if self.finished:

            return self._build_response(
                "I think we're done here. Thank you.",
                extra={
                    "status": "already_finished"
                },
            )

        # Record support agent message

        self._record(
            "agent",
            agent_message
        )

        # Update emotional state

        emotion = self.emotion_mgr.update(
            agent_message
        )

        # Check whether conversation should finish

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

        # Generate next customer response

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
    # STATE
    # =============================================================

    def get_state(
        self
    ) -> Dict[str, Any]:

        emotion = self.emotion_mgr.get_state()

        return {

            "session_id":
                self.session_id,

            "persona":
                self.persona_name,

            "scenario":
                self.scenario_name,

            "turn_count":
                self.turn_count,

            "frustration_level":
                self.frustration_level,

            "emotion":
                emotion.to_dict(),

            "finished":
                self.finished,

            "history":
                self.history,

            "log_path":
                self.logger.get_log_path(),
        }

    # =============================================================
    # RECORD MESSAGE
    # =============================================================

    def _record(
        self,
        role: str,
        content: str
    ):

        self.turn_count += 1

        self.history.append({

            "role":
                role,

            "content":
                content,
        })

        emotion = (

            self.emotion_mgr
            .get_state()
            .to_dict()

            if role == "customer"

            else None
        )

        self.logger.log_turn(

            turn_number=
                self.turn_count,

            role=
                role,

            message=
                content,

            emotion=
                emotion,
        )

    # =============================================================
    # BUILD API RESPONSE
    # =============================================================

    def _build_response(
        self,
        customer_message: str,
        extra: Optional[Dict] = None,
    ) -> Dict[str, Any]:

        emotion = self.emotion_mgr.get_state()

        payload = {

            "session_id":
                self.session_id,

            "customer_message":
                customer_message,

            "emotion":
                emotion.to_dict(),

            "frustration_level":
                self.frustration_level,

            "turn":
                self.turn_count,

            "finished":
                self.finished,

            "persona":
                self.persona_name,

            "scenario":
                self.scenario_name,
        }

        if extra:

            payload.update(
                extra
            )

        return payload

    # =============================================================
    # DETERMINE WHETHER CONVERSATION SHOULD END
    # =============================================================

    def _should_end(
        self,
        agent_message: str,
        emotion,
    ) -> bool:

        text = agent_message.lower()

        positive = any(

            phrase in text

            for phrase in [

                "refund has been processed",

                "refund will be",

                "i have processed",

                "i've processed",

                "cancellation confirmed",

                "account has been unlocked",

                "new delivery date",

                "i've escalated",

                "i have escalated",

                "compensation of",
            ]
        )

        if positive and emotion.intensity <= 4:

            return True

        if self.turn_count >= 14:

            return True

        return False

    # =============================================================
    # CLOSING MESSAGE
    # =============================================================

    def _generate_closing(
        self,
        agent_message: str,
    ) -> str:

        emotion = self.emotion_mgr.get_state()

        if emotion.intensity <= 2:

            return (
                "Thank you, that resolves it for me. "
                "I appreciate your help."
            )

        if emotion.intensity <= 4:

            return (
                "Alright, that sounds good. "
                "Thanks for getting this sorted out."
            )

        if emotion.intensity <= 6:

            return (
                "Okay, I'll take that. "
                "Please make sure it actually gets done."
            )

        if emotion.intensity <= 8:

            return (
                "Fine. I'll be watching closely. "
                "I really hope this gets resolved this time."
            )

        return (
            "Fine, but I'm not satisfied with how this was handled. "
            "I'll be watching my account closely and I will escalate "
            "this if it isn't fixed."
        )

    # =============================================================
    # GENERATE CUSTOMER MESSAGE
    # =============================================================

    def _generate_customer_message(
        self,
        is_opening: bool = False,
    ) -> str:

        if self.use_llm and self.client:

            try:

                return self._llm_generate(
                    is_opening
                )

            except Exception as e:

                print(
                    f"[Simulator] LLM error: {e}. "
                    f"Falling back to rule-based."
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

    def _build_system_prompt(
        self
    ) -> str:

        emotion = self.emotion_mgr.get_state()

        facts = json.dumps(
            self.scenario["key_facts"],
            indent=2,
        )

        # =========================================================
        # PERSONA-SPECIFIC INSTRUCTIONS
        # =========================================================

        persona_name = self.persona.get(
            "name",
            self.persona_name
        )

        communication_style = self.persona.get(
            "communication_style",
            ""
        )

        vocabulary = self.persona.get(
            "vocabulary",
            []
        )

        behavior_notes = self.persona.get(
            "behavior_notes",
            ""
        )

        # =========================================================
        # FRUSTRATION LEVEL
        # =========================================================

        if emotion.intensity <= 2:

            tone_instruction = """
The customer is CALM and POLITE.

Use:
- friendly wording
- patient language
- cooperative communication
- polite questions
- no unnecessary urgency

The customer should sound relaxed and reasonable.
"""

        elif emotion.intensity <= 4:

            tone_instruction = """
The customer is CONCERNED.

Use:
- slightly worried language
- polite but direct wording
- questions for clarification
- show that the issue matters

The customer is still cooperative.
"""

        elif emotion.intensity <= 6:

            tone_instruction = """
The customer is FRUSTRATED.

Use:
- noticeably impatient wording
- direct questions
- clear dissatisfaction
- request a concrete solution
- request a timeline

The customer is still willing to cooperate,
but patience is decreasing.
"""

        elif emotion.intensity <= 8:

            tone_instruction = """
The customer is ANGRY.

Use:
- firm wording
- strong dissatisfaction
- urgency
- direct demands
- request a clear resolution

Do not make the customer overly calm.
"""

        else:

            tone_instruction = """
The customer is FURIOUS.

Use:
- very strong frustration
- forceful and urgent language
- short, direct sentences
- escalation pressure
- clear dissatisfaction
- demand immediate action

Do not use cheerful or overly calm language.
"""

        # =========================================================
        # FINAL SYSTEM PROMPT
        # =========================================================

        return f"""
You are role-playing as a real customer talking to a company
support agent in a live chat.

PERSONA:
{persona_name}

Communication style:
{communication_style}

Typical vocabulary:
{', '.join(vocabulary)}

Behavior notes:
{behavior_notes}


SCENARIO:
{self.scenario['name']}

Context:
{self.scenario['context']}

Key facts:
{facts}

Customer goal:
{self.scenario['customer_goal']}


CURRENT FRUSTRATION LEVEL:
{emotion.intensity}/10

CURRENT EMOTION:
{emotion.label}


{tone_instruction}


IMPORTANT PERSONA RULE:

The selected PERSONA must strongly affect the customer's
communication style.

Different personas MUST NOT produce identical responses.

For example:

- POLITE customers should sound respectful and cooperative.
- CONCERNED customers should sound worried and ask questions.
- FRUSTRATED customers should sound impatient and dissatisfied.
- ANGRY customers should sound firm and demanding.
- FURIOUS customers should sound extremely upset and may request escalation.

The response should reflect BOTH:
1. The selected persona.
2. The current frustration level.


IMPORTANT:

A polite persona at frustration level 5 should still sound
more respectful than an angry persona at frustration level 5.

The persona controls the communication style.

The frustration level controls emotional intensity.


RULES:

1. Reply ONLY as the customer.

2. Never break character.

3. Never mention that you are an AI.

4. Keep responses realistic:
   1-4 sentences.

5. Match the selected persona.

6. Match the current frustration level.

7. React directly to the support agent's previous message.

8. Stay consistent with previous messages.

9. Do not solve the problem yourself.

10. Push the support agent toward the customer's desired resolution.

11. Never invent new order IDs, amounts, dates, or other facts.

12. Use only the scenario facts provided.

13. If the support agent is helpful, frustration can decrease.

14. If the support agent is dismissive or vague,
    frustration can increase.

15. Do not repeat the exact same sentence unnecessarily.

16. Output ONLY the customer's next message.

Do not include:
"Customer:"
"AI:"
"Response:"
or any other label.
"""

    # =============================================================
    # LLM GENERATION
    # =============================================================

    def _llm_generate(
        self,
        is_opening: bool,
    ) -> str:

        system = self._build_system_prompt()

        messages = [

            {
                "role":
                    "system",

                "content":
                    system,
            }
        ]

        # ---------------------------------------------------------
        # RECENT CONVERSATION
        # ---------------------------------------------------------

        for turn in self.history[-8:]:

            role = (

                "user"

                if turn["role"] == "agent"

                else "assistant"
            )

            messages.append({

                "role":
                    role,

                "content":
                    turn["content"],
            })

        # ---------------------------------------------------------
        # OPENING
        # ---------------------------------------------------------

        if is_opening:

            messages.append({

                "role":
                    "user",

                "content":
                    (
                        "The chat has just started. "
                        "Write the customer's FIRST message describing "
                        "the problem and what they want. "
                        "Make the message clearly match the selected "
                        "persona AND current frustration level. "
                        "Do not copy a generic response."
                    ),
            })

        # ---------------------------------------------------------
        # FOLLOW-UP
        # ---------------------------------------------------------

        else:

            messages.append({

                "role":
                    "user",

                "content":
                    (
                        "The support agent just replied. "
                        "Write the customer's next realistic reply. "
                        "React directly to what the agent said. "
                        "Make the response clearly different according "
                        "to the selected persona. "
                        "Also match the current frustration level."
                    ),
            })

        # ---------------------------------------------------------
        # OPENAI REQUEST
        # ---------------------------------------------------------

        response = self.client.chat.completions.create(

            model=
                LLM_MODEL,

            messages=
                messages,

            temperature=
                LLM_TEMPERATURE,

            max_tokens=
                MAX_TOKENS,
        )

        text = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        if (
            text.startswith('"')
            and text.endswith('"')
        ):

            text = text[1:-1]

        return text

    # =============================================================
    # RULE-BASED GENERATION
    #
    # IMPORTANT:
    # Persona + frustration level both affect the response.
    # =============================================================

    def _rule_based_generate(
        self,
        is_opening: bool,
    ) -> str:

        emotion = self.emotion_mgr.get_state()

        facts = self.scenario["key_facts"]

        intensity = emotion.intensity

        # =========================================================
        # NORMALIZE PERSONA
        # =========================================================

        persona = self.persona_name.lower().strip()

        if persona in [
            "polite",
            "calm",
            "friendly",
            "professional",
        ]:

            persona_type = "polite"

        elif persona in [
            "concerned",
            "worried",
            "anxious",
        ]:

            persona_type = "concerned"

        elif persona in [
            "frustrated",
            "impatient",
        ]:

            persona_type = "frustrated"

        elif persona in [
            "angry",
            "aggressive",
        ]:

            persona_type = "angry"

        elif persona in [
            "furious",
            "very_angry",
        ]:

            persona_type = "furious"

        else:

            # Fallback based on frustration

            if intensity <= 3:

                persona_type = "polite"

            elif intensity <= 4:

                persona_type = "concerned"

            elif intensity <= 6:

                persona_type = "frustrated"

            elif intensity <= 8:

                persona_type = "angry"

            else:

                persona_type = "furious"

        # =========================================================
        # OPENING MESSAGE
        # =========================================================

        if is_opening:

            # =====================================================
            # REFUND REQUEST
            # =====================================================

            if self.scenario_name == "refund_request":

                if persona_type == "polite":

                    return (
                        f"Hi, I received order "
                        f"{facts.get('order_id')} and unfortunately "
                        f"the {facts.get('product')} is damaged. "
                        f"Could you please help me with a refund "
                        f"of {facts.get('amount')}?"
                    )

                elif persona_type == "concerned":

                    return (
                        f"Hi, I'm a little concerned about order "
                        f"{facts.get('order_id')}. The "
                        f"{facts.get('product')} arrived damaged, "
                        f"and I'd like to know how I can get my "
                        f"{facts.get('amount')} refunded."
                    )

                elif persona_type == "frustrated":

                    return (
                        f"I'm really frustrated with order "
                        f"{facts.get('order_id')}. The "
                        f"{facts.get('product')} arrived damaged, "
                        f"and I need the {facts.get('amount')} "
                        f"refunded. Can you please sort this out?"
                    )

                elif persona_type == "angry":

                    return (
                        f"Order {facts.get('order_id')} arrived "
                        f"damaged, and this is unacceptable. "
                        f"I want my {facts.get('amount')} refund "
                        f"processed as soon as possible."
                    )

                else:

                    return (
                        f"I need a refund for order "
                        f"{facts.get('order_id')} immediately. "
                        f"The {facts.get('product')} is damaged "
                        f"and unusable. Please resolve this now."
                    )

            # =====================================================
            # DELAYED ORDER
            # =====================================================

            elif self.scenario_name == "delayed_order":

                if persona_type == "polite":

                    return (
                        f"Hi, I noticed that order "
                        f"{facts.get('order_id')} hasn't arrived yet. "
                        f"The tracking number "
                        f"{facts.get('tracking_number')} hasn't "
                        f"updated recently. Could you please check "
                        f"the latest status?"
                    )

                elif persona_type == "concerned":

                    return (
                        f"Hi, I'm a little worried about order "
                        f"{facts.get('order_id')}. The tracking number "
                        f"{facts.get('tracking_number')} hasn't "
                        f"updated in days, and I really need it this "
                        f"week. Could you please check what's happening?"
                    )

                elif persona_type == "frustrated":

                    return (
                        f"I'm getting really frustrated with order "
                        f"{facts.get('order_id')}. The tracking number "
                        f"{facts.get('tracking_number')} hasn't updated "
                        f"in days, and I really need it this week. "
                        f"Can you please give me a clear update?"
                    )

                elif persona_type == "angry":

                    return (
                        f"Order {facts.get('order_id')} is already late, "
                        f"and the tracking number "
                        f"{facts.get('tracking_number')} hasn't updated "
                        f"in days. This is unacceptable. I need a clear "
                        f"answer about my delivery."
                    )

                else:

                    return (
                        f"Where is my order "
                        f"{facts.get('order_id')}?! The tracking number "
                        f"{facts.get('tracking_number')} hasn't updated "
                        f"in days. I need this order urgently. "
                        f"Please give me an answer now."
                    )

            # =====================================================
            # PAYMENT FAILURE
            # =====================================================

            elif self.scenario_name == "payment_failure":

                if persona_type == "polite":

                    return (
                        f"Hi, I tried to make a payment for my "
                        f"{facts.get('subscription')}, but it didn't "
                        f"go through. My card ends in "
                        f"{facts.get('card_last4')}. Could you please "
                        f"help me?"
                    )

                elif persona_type == "concerned":

                    return (
                        f"I'm concerned because my payment for "
                        f"{facts.get('subscription')} failed. "
                        f"My card ends in {facts.get('card_last4')}. "
                        f"Could you please check what went wrong?"
                    )

                elif persona_type == "frustrated":

                    return (
                        f"I'm getting frustrated because my payment "
                        f"of {facts.get('amount')} keeps failing. "
                        f"I need my {facts.get('subscription')} active. "
                        f"Can you please fix this?"
                    )

                elif persona_type == "angry":

                    return (
                        f"My payment of {facts.get('amount')} keeps "
                        f"failing even though I have funds available. "
                        f"This is unacceptable. Please fix the payment "
                        f"issue."
                    )

                else:

                    return (
                        f"This payment problem needs to be fixed "
                        f"immediately. My {facts.get('subscription')} "
                        f"isn't active and I need this resolved now."
                    )

            # =====================================================
            # ACCOUNT ISSUE
            # =====================================================

            elif self.scenario_name == "account_issue":

                if persona_type == "polite":

                    return (
                        f"Hello, I can't log into my account "
                        f"({facts.get('account_email')}). "
                        f"The password reset isn't working. "
                        f"Could you please help me?"
                    )

                elif persona_type == "concerned":

                    return (
                        f"I'm concerned because I'm unable to access "
                        f"my account. The password reset isn't working, "
                        f"and I need access soon. Could you please help?"
                    )

                elif persona_type == "frustrated":

                    return (
                        f"I'm getting frustrated because I'm locked "
                        f"out of my account. The password reset isn't "
                        f"working, and I need access today. "
                        f"What can you do?"
                    )

                elif persona_type == "angry":

                    return (
                        f"I'm locked out of my account and the password "
                        f"reset isn't working. This is unacceptable. "
                        f"I need access restored immediately."
                    )

                else:

                    return (
                        f"My account is locked and I can't access it. "
                        f"The password reset isn't working. "
                        f"Fix this immediately because I need access now."
                    )

            # =====================================================
            # CANCELLATION
            # =====================================================

            elif self.scenario_name == "cancellation":

                if persona_type == "polite":

                    return (
                        f"Hi, I'd like to cancel my "
                        f"{facts.get('subscription')}. "
                        f"Could you please confirm when the cancellation "
                        f"will take effect?"
                    )

                elif persona_type == "concerned":

                    return (
                        f"I'd like to cancel my "
                        f"{facts.get('subscription')}, but I want to "
                        f"make sure there won't be any more charges. "
                        f"Could you please confirm?"
                    )

                elif persona_type == "frustrated":

                    return (
                        f"Please cancel my "
                        f"{facts.get('subscription')} and stop any "
                        f"future charges. I'm frustrated with having "
                        f"to deal with this."
                    )

                elif persona_type == "angry":

                    return (
                        f"I want my {facts.get('subscription')} "
                        f"cancelled immediately. Stop all future "
                        f"charges. I need confirmation that this is done."
                    )

                else:

                    return (
                        f"Cancel my subscription immediately and stop "
                        f"charging me. I don't want any more delays. "
                        f"Confirm the cancellation now."
                    )

            # =====================================================
            # DEFAULT SCENARIO
            # =====================================================

            else:

                if persona_type == "polite":

                    return (
                        "Hi, I need some help with an issue I'm having. "
                        "Could you please assist me?"
                    )

                elif persona_type == "concerned":

                    return (
                        "I'm a little concerned about this issue. "
                        "Could you please help me understand what is "
                        "happening?"
                    )

                elif persona_type == "frustrated":

                    return (
                        "I'm getting frustrated because this issue "
                        "hasn't been resolved. Can you please help me?"
                    )

                elif persona_type == "angry":

                    return (
                        "I'm very unhappy with this situation. "
                        "I need a clear solution as soon as possible."
                    )

                else:

                    return (
                        "This situation is completely unacceptable. "
                        "I need this resolved immediately."
                    )

        # =========================================================
        # FOLLOW-UP RESPONSES
        # =========================================================

        if persona_type == "polite":

            return (
                "Thank you for explaining that. "
                "I appreciate your help. Could you please confirm "
                "what the next step will be?"
            )

        elif persona_type == "concerned":

            return (
                "I understand, but I'm still a little concerned. "
                "Could you please give me a clear update and let me "
                "know when this should be resolved?"
            )

        elif persona_type == "frustrated":

            return (
                "I'm still frustrated because I don't have a concrete "
                "solution yet. Can you please tell me exactly what "
                "will happen next and when?"
            )

        elif persona_type == "angry":

            return (
                "I'm not satisfied with that response. "
                "I need a clear resolution and timeline. "
                "Please don't make me wait any longer."
            )

        elif persona_type == "furious":

            return (
                "This is still completely unacceptable. "
                "I need this resolved immediately. "
                "If this cannot be fixed now, I want the issue escalated."
            )

        # =========================================================
        # FINAL FALLBACK
        # =========================================================

        if intensity >= 9:

            return (
                "This is completely unacceptable. "
                "I need this fixed immediately. "
                "If you can't resolve it now, I want to speak to a manager."
            )

        if intensity >= 7:

            return (
                "I'm really frustrated with this response. "
                "I already explained the problem. "
                "Give me a clear resolution and timeline."
            )

        if intensity >= 5:

            return (
                "I'm getting frustrated because I still don't have "
                "a concrete solution. What exactly are you going to do "
                "and when will it be resolved?"
            )

        if intensity >= 3:

            return (
                "I understand, but I'm still concerned about this. "
                "Could you please give me a clear next step and timeline?"
            )

        return (
            "Thanks for helping with this. "
            "Could you please confirm the details so I know everything "
            "is being taken care of?"
        )


# =============================================================
# FACTORY FUNCTION
# =============================================================

def create_simulator(
    **kwargs
) -> CustomerSimulator:

    return CustomerSimulator(
        **kwargs
    )