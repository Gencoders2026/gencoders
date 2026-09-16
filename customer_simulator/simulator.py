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
from pathlib import Path
from typing import Dict, Any, Optional


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


class CustomerSimulator:

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

        # Keeps track of messages already displayed.
        self.used_messages = set()

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
        # FRUSTRATION CHANGES BASED ON AGENT RESPONSE
        # ------------------------------------------------------

        helpful_words = [
            "processed",
            "confirmed",
            "completed",
            "resolved",
            "refund",
            "delivery date",
            "tracking",
            "check",
            "checked",
            "escalated",
            "fixed",
            "solution",
            "timeline",
            "next step",
            "help"
        ]

        poor_words = [
            "wait",
            "soon",
            "later",
            "can't help",
            "cannot help",
            "nothing i can do",
            "don't know",
            "do not know",
            "not my problem"
        ]

        if any(word in text for word in poor_words):

            self.frustration_level = min(
                10,
                self.frustration_level + 1
            )

        elif any(word in text for word in helpful_words):

            self.frustration_level = max(
                1,
                self.frustration_level - 1
            )

        # ------------------------------------------------------
        # RESOLUTION
        # ------------------------------------------------------

        if (
            self._is_resolved(text)
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

        message = self._generate_customer_message(
            opening=False
        )

        self._record(
            "customer",
            message
        )

        return self._build_response(message)


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
                "unlocked"
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

    def _generate_customer_message(
        self,
        opening=False
    ):

        level = self.frustration_level

        band = get_band(level)

        scenario = SCENARIOS[
            self.scenario_name
        ]

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

        options = message_sets[
            self.scenario_name
        ][band]

        # Turn-based variation
        index = self.turn_count % len(options)

        message = options[index]

        # ------------------------------------------------------
        # PERSONA MODIFICATION
        # ------------------------------------------------------

        if self.persona_name == "polite":

            if band in ["angry", "furious"]:
                message = (
                    "I am very disappointed with this situation. "
                    + message
                )

        elif self.persona_name == "concerned":

            if band in ["angry", "furious"]:
                message = (
                    "I'm quite worried about this. "
                    + message
                )

        elif self.persona_name == "frustrated":

            if band == "calm":
                message = (
                    "I'm starting to get concerned. "
                    + message
                )

        elif self.persona_name == "angry":

            if band in ["calm", "concerned"]:
                message = (
                    "I'm not happy about this. "
                    + message
                )

        elif self.persona_name == "furious":

            if band in ["calm", "concerned", "frustrated"]:
                message = (
                    "I'm extremely unhappy with this situation. "
                    + message
                )

        # ------------------------------------------------------
        # ABSOLUTE NO-REPEAT PROTECTION
        # ------------------------------------------------------

        if message in self.used_messages:

            for candidate in options:

                if candidate not in self.used_messages:

                    message = candidate
                    break

        self.used_messages.add(message)

        return message


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