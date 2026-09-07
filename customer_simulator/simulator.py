# simulator.py

from .personas import PERSONAS
from .scenarios import SCENARIOS
from .emotion_manager import EmotionManager
from .logger import ConversationLogger
from groq import Groq
import os
from dotenv import load_dotenv

from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class CustomerSimulator:
    def __init__(self, persona="frustrated", scenario="delayed_order",
                 initial_emotion="frustrated", severity="medium", patience=5):

        self.persona = PERSONAS[persona]
        self.scenario = SCENARIOS[scenario]
        self.emotion_manager = EmotionManager(initial_emotion, intensity=6, patience=patience)
        self.history = []
        self.session_id = f"session_{persona}_{scenario}"
        self.logger = ConversationLogger(self.session_id)
        self.severity = severity

    def _build_prompt(self, agent_response: str) -> str:
        history_text = "\n".join(
            [f"Agent: {h['agent']}\nCustomer: {h['customer']}" for h in self.history]
        )

        prompt = f"""
You are a real customer talking to customer support.

PERSONA: {self.persona['name']}
Description: {self.persona['description']}
Speaking style: {self.persona['speaking_style']}

SCENARIO: {self.scenario['name']}
What happened: {self.scenario['description']}
What you know: {self.scenario['customer_knows']}
What you want: {self.scenario['expected_resolution']}

CURRENT EMOTION: {self.emotion_manager.emotion}
Emotion intensity (1-10): {self.emotion_manager.intensity}
Issue severity: {self.severity}

Previous conversation:
{history_text}

Support Agent just said:
"{agent_response}"

Now write ONLY the next message from the customer.
- Stay completely in character
- Make it realistic and natural
- Do not write any explanation or notes
- Keep it 1-3 sentences
"""
        return prompt

    def generate_next_message(self, agent_response: str) -> str:
        # Update emotion
        emotion, intensity = self.emotion_manager.update_emotion(agent_response)

        # Build prompt
        prompt = self._build_prompt(agent_response)

        # Call Groq LLM
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",   # Free and strong model
            messages=[
                {"role": "system", "content": "You are a realistic customer. Reply only with the customer's message."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8
        )

        customer_message = response.choices[0].message.content.strip()

        # Save to history
        self.history.append({
            "agent": agent_response,
            "customer": customer_message
        })

        # Log it
        self.logger.add_turn(agent_response, customer_message, emotion, intensity)

        return customer_message

    def save_conversation(self):
        self.logger.save()