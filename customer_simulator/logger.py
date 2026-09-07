# logger.py

import json
from datetime import datetime
import os

class ConversationLogger:
    def __init__(self, session_id):
        self.session_id = session_id
        self.log = []
        os.makedirs("logs", exist_ok=True)

    def add_turn(self, agent_msg, customer_msg, emotion, intensity):
        turn = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_msg,
            "customer": customer_msg,
            "emotion": emotion,
            "intensity": intensity
        }
        self.log.append(turn)

    def save(self):
        filename = f"logs/{self.session_id}.json"
        with open(filename, "w") as f:
            json.dump(self.log, f, indent=2)
        print(f"Conversation saved to {filename}")