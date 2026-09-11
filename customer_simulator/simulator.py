"""
Customer Simulator Agent – core logic.
"""

import os
import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

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
    DEFAULT_PATIENCE_LEVEL,
    DEFAULT_EXPECTED_RESOLUTION,
)
from personas import get_persona, list_personas
from scenarios import get_scenario, list_scenarios
from emotion_manager import EmotionManager
from logger import ConversationLogger


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
    ):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.persona_name = persona.lower()
        self.scenario_name = scenario.lower()
        self.issue_severity = max(1, min(10, issue_severity))
        self.patience_level = max(1, min(10, patience_level))
        self.expected_resolution = expected_resolution
        self.use_llm = use_llm and bool(OPENAI_API_KEY) and OpenAI is not None

        self.persona = get_persona(self.persona_name)
        self.scenario = get_scenario(self.scenario_name)

        self.emotion_mgr = EmotionManager(
            initial_emotion=initial_emotion,
            patience_level=self.patience_level,
            persona_modifier=self.persona.get("patience_modifier", 0),
        )

        self.history: List[Dict[str, str]] = []
        self.turn_count = 0
        self.finished = False

        self.logger = ConversationLogger(self.session_id)
        self.logger.set_config({
            "persona": self.persona_name,
            "scenario": self.scenario_name,
            "initial_emotion": initial_emotion,
            "issue_severity": self.issue_severity,
            "patience_level": self.patience_level,
            "expected_resolution": self.expected_resolution,
            "use_llm": self.use_llm,
        })

        self.client = None
        if self.use_llm:
            self.client = OpenAI(api_key=OPENAI_API_KEY)

    def start(self) -> Dict[str, Any]:
        opening = self._generate_customer_message(is_opening=True)
        self._record("customer", opening)
        return self._build_response(opening)

    def respond(self, agent_message: str) -> Dict[str, Any]:
        if self.finished:
            return self._build_response(
                "I think we're done here. Thank you.",
                extra={"status": "already_finished"}
            )

        self._record("agent", agent_message)
        emotion = self.emotion_mgr.update(agent_message)

        if self._should_end(agent_message, emotion):
            closing = self._generate_closing(agent_message)
            self._record("customer", closing)
            self.finished = True
            self.logger.finalize(emotion.to_dict())
            return self._build_response(closing, extra={"status": "resolved"})

        next_msg = self._generate_customer_message(is_opening=False)
        self._record("customer", next_msg)
        return self._build_response(next_msg)

    def get_state(self) -> Dict[str, Any]:
        emotion = self.emotion_mgr.get_state()
        return {
            "session_id": self.session_id,
            "persona": self.persona_name,
            "scenario": self.scenario_name,
            "turn_count": self.turn_count,
            "emotion": emotion.to_dict(),
            "finished": self.finished,
            "history": self.history,
            "log_path": self.logger.get_log_path(),
        }

    def _record(self, role: str, content: str):
        self.turn_count += 1
        self.history.append({"role": role, "content": content})
        emotion = self.emotion_mgr.get_state().to_dict() if role == "customer" else None
        self.logger.log_turn(
            turn_number=self.turn_count,
            role=role,
            message=content,
            emotion=emotion,
        )

    def _build_response(self, customer_message: str, extra: Optional[Dict] = None) -> Dict[str, Any]:
        emotion = self.emotion_mgr.get_state()
        payload = {
            "session_id": self.session_id,
            "customer_message": customer_message,
            "emotion": emotion.to_dict(),
            "turn": self.turn_count,
            "finished": self.finished,
            "persona": self.persona_name,
            "scenario": self.scenario_name,
        }
        if extra:
            payload.update(extra)
        return payload

    def _should_end(self, agent_message: str, emotion) -> bool:
        text = agent_message.lower()
        positive = any(k in text for k in [
            "refund has been processed", "refund will be", "i have processed",
            "cancellation confirmed", "account has been unlocked",
            "new delivery date", "i've escalated", "compensation of"
        ])
        if positive and emotion.intensity <= 4:
            return True
        if self.turn_count >= 14:
            return True
        return False

    def _generate_closing(self, agent_message: str) -> str:
        emotion = self.emotion_mgr.get_state()
        if emotion.intensity <= 3:
            return "Thank you, that resolves it for me. I appreciate your help."
        if emotion.intensity <= 6:
            return "Alright, I'll take that. Please make sure it actually happens."
        return "Fine. I'll be watching my account closely. This better be fixed."

    def _generate_customer_message(self, is_opening: bool = False) -> str:
        if self.use_llm and self.client:
            try:
                return self._llm_generate(is_opening)
            except Exception as e:
                print(f"[Simulator] LLM error: {e}. Falling back to rule-based.")
                return self._rule_based_generate(is_opening)
        return self._rule_based_generate(is_opening)

    def _build_system_prompt(self) -> str:
        emotion = self.emotion_mgr.get_state()
        facts = json.dumps(self.scenario["key_facts"], indent=2)

        return f"""You are role-playing as a real customer talking to a company support agent in a live chat.

PERSONA: {self.persona['name']}
- Style: {self.persona['communication_style']}
- Typical vocabulary: {', '.join(self.persona['vocabulary'])}
- Behavior notes: {self.persona['behavior_notes']}

SCENARIO: {self.scenario['name']}
- Context: {self.scenario['context']}
- Key facts you know (use them naturally, do not invent new order numbers):
{facts}
- Your goal: {self.scenario['customer_goal']}

CURRENT EMOTIONAL STATE: {emotion.label} (intensity {emotion.intensity}/10)
Issue severity (how important this is to you): {self.issue_severity}/10
Patience level: {self.patience_level}/10
Expected resolution: {self.expected_resolution}

RULES:
1. Reply ONLY as the customer. Never break character or mention you are an AI.
2. Keep messages realistic: 1-4 sentences, natural chat language matching the persona.
3. Reflect the current emotion in tone, word choice, and punctuation.
4. Stay consistent with previous messages in the conversation.
5. Do not solve the problem yourself; push the agent for the resolution you want.
6. Never invent new order IDs, amounts, or dates – use only the key facts above.
7. If the agent is helpful, you may soften; if dismissive, you may escalate.
8. Output ONLY the customer's next message text – no quotes, no labels, no extra commentary.
"""

    def _llm_generate(self, is_opening: bool) -> str:
        system = self._build_system_prompt()
        messages = [{"role": "system", "content": system}]

        for turn in self.history[-8:]:
            role = "user" if turn["role"] == "agent" else "assistant"
            messages.append({"role": role, "content": turn["content"]})

        if is_opening:
            messages.append({
                "role": "user",
                "content": (
                    "The chat has just started. Write the customer's FIRST message "
                    "describing the problem and what they want. Be natural for the persona."
                )
            })
        else:
            messages.append({
                "role": "user",
                "content": (
                    "The support agent just replied (see history). "
                    "Write the customer's next realistic reply continuing the conversation."
                )
            })

        response = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        return text

    def _rule_based_generate(self, is_opening: bool) -> str:
        emotion = self.emotion_mgr.get_state()
        facts = self.scenario["key_facts"]
        intensity = emotion.intensity

        if is_opening:
            templates = {
                "refund_request": {
                    "low": f"Hi, I received order {facts.get('order_id')} and the {facts.get('product')} is damaged. I'd like a refund of {facts.get('amount')} please.",
                    "mid": f"I need a refund for order {facts.get('order_id')}. The {facts.get('product')} arrived damaged – {facts.get('reason')}. This is not acceptable.",
                    "high": f"I want a FULL REFUND for order {facts.get('order_id')} RIGHT NOW. The {facts.get('product')} is cracked and unusable. {facts.get('amount')} back to my card!",
                },
                "delayed_order": {
                    "low": f"Hello, my order {facts.get('order_id')} for the {facts.get('product')} was supposed to arrive {facts.get('promised_delivery')}. Can you check the status?",
                    "mid": f"Order {facts.get('order_id')} is late. Tracking {facts.get('tracking_number')} hasn't updated in days. I need it this week.",
                    "high": f"Where is my order {facts.get('order_id')}?! It was due {facts.get('promised_delivery')} and still nothing. This is ridiculous!",
                },
                "payment_failure": {
                    "low": f"Hi, I tried to pay for my {facts.get('subscription')} but it failed. Card ending {facts.get('card_last4')}. Can you help?",
                    "mid": f"My payment of {facts.get('amount')} for {facts.get('subscription')} keeps declining even though I have funds. Please fix this.",
                    "high": f"You charged me / declined my card for {facts.get('amount')} and the service isn't active! Sort this out immediately.",
                },
                "account_issue": {
                    "low": f"Hello, I can't log into my account ({facts.get('account_email')}). The password reset isn't working.",
                    "mid": f"I'm locked out of my account. Last login was {facts.get('last_successful_login')}. I need access restored today.",
                    "high": f"My account is locked and it shows the wrong plan! Fix this now – I pay for Premium!",
                },
                "cancellation": {
                    "low": f"Hi, I'd like to cancel my {facts.get('subscription')}. Please confirm when it will end.",
                    "mid": f"Please cancel my {facts.get('subscription')} and stop all future charges. I no longer need it.",
                    "high": f"Cancel my subscription NOW. Stop charging me. I want confirmation in writing.",
                },
            }
            level = "high" if intensity >= 7 else ("mid" if intensity >= 4 else "low")
            base = templates.get(self.scenario_name, templates["refund_request"])[level]
            return base

        if intensity >= 8:
            return "That doesn't help. I need this fixed immediately or I'm escalating to a manager."
        if intensity >= 6:
            return "I already explained the problem. Can you please give me a clear next step and a timeline?"
        if intensity >= 4:
            return "Okay, but I still need a concrete resolution. What exactly will you do and when?"
        return "Thank you. Could you confirm the details so I know it's taken care of?"


def create_simulator(**kwargs) -> CustomerSimulator:
    return CustomerSimulator(**kwargs)