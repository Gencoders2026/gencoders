# emotion_manager.py

class EmotionManager:
    def __init__(self, initial_emotion="frustrated", intensity=5, patience=5):
        self.emotion = initial_emotion
        self.intensity = intensity          # 1 to 10
        self.patience = patience            # 1 to 10

        self.emotion_levels = ["calm", "confused", "frustrated", "angry"]

    def update_emotion(self, agent_response: str):
        """
        Very simple rule-based emotion update.
        Later you can make this smarter with LLM.
        """
        positive_words = ["sorry", "apologize", "refund", "help", "resolve", "immediately", "understand"]
        negative_words = ["cannot", "unable", "policy", "wait", "later", "unfortunately"]

        score = 0
        response_lower = agent_response.lower()

        for word in positive_words:
            if word in response_lower:
                score += 1

        for word in negative_words:
            if word in response_lower:
                score -= 1

        # Update intensity
        if score > 0:
            self.intensity = max(1, self.intensity - 1)
        elif score < 0:
            self.intensity = min(10, self.intensity + 2)

        # Change emotion based on intensity
        if self.intensity <= 3:
            self.emotion = "calm"
        elif self.intensity <= 5:
            self.emotion = "confused"
        elif self.intensity <= 7:
            self.emotion = "frustrated"
        else:
            self.emotion = "angry"

        return self.emotion, self.intensity