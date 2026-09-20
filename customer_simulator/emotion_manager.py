"""
Emotion / Frustration State Manager for the Customer Simulator.
Analyzes the quality of the agent reply and changes intensity accordingly.
"""

from typing import Dict, Optional
from dataclasses import dataclass, field
import re

try:  # package-relative import
    from .config import EMOTION_SCALE_MIN, EMOTION_SCALE_MAX
except ImportError:  # flat import when run directly
    from config import EMOTION_SCALE_MIN, EMOTION_SCALE_MAX


EMOTION_LABELS = {
    1: "calm",
    2: "calm",
    3: "mildly_concerned",
    4: "concerned",
    5: "frustrated",
    6: "frustrated",
    7: "angry",
    8: "angry",
    9: "furious",
    10: "furious",
}


POSITIVE_SIGNALS = [
    r"\b(refund|full refund|process(ed|ing)? (the )?refund)\b",
    r"\b(apologi[sz]e|sorry for the (inconvenience|delay|trouble))\b",
    r"\b(escalat(e|ing|ed)|manager|supervisor)\b",
    r"\b(confirm(ed|ing)?|right away|immediately|within \d+ (hours?|days?))\b",
    r"\b(compensation|discount|credit|voucher)\b",
    r"\b(understood|I see the issue|you're right)\b",
    r"\b(I (will|can) (help|fix|take care))\b",
]

NEGATIVE_SIGNALS = [
    r"\b(policy|unfortunately we cannot|not possible|unable to)\b",
    r"\b(please wait|another \d+ days?|try again later)\b",
    r"\b(contact (the )?carrier|outside our control)\b",
    r"\b(no refund|store credit only|final sale)\b",
    r"\b(you (need|must|have) to)\b",
    r"\b(I don't have (access|permission|authority))\b",
]


@dataclass
class EmotionState:
    intensity: int = 5
    label: str = "frustrated"
    history: list = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "intensity": self.intensity,
            "label": self.label,
            "history": self.history[-8:],
        }


class EmotionManager:

    def __init__(
        self,
        initial_emotion: str = "frustrated",
        initial_intensity: Optional[int] = None,
        persona_modifier: int = 0,
    ):
        self.persona_modifier = persona_modifier

        emotion_start_map = {
            "calm": 2,
            "mildly_concerned": 3,
            "concerned": 4,
            "frustrated": 6,
            "angry": 8,
            "furious": 10,
            "impatient": 7,
            "polite": 2,
            "confused": 4,
        }

        if initial_intensity is not None:
            start = initial_intensity
        else:
            start = emotion_start_map.get(initial_emotion.lower(), 5)

        start = max(EMOTION_SCALE_MIN, min(EMOTION_SCALE_MAX, start))

        self.state = EmotionState(
            intensity=start,
            label=EMOTION_LABELS[start],
            history=[f"init → {start} ({EMOTION_LABELS[start]})"],
        )

    def get_state(self) -> EmotionState:
        return self.state

    def _score_agent_message(self, agent_message: str) -> float:
        text = agent_message.lower().strip()
        score = 0.0

        # Strong positive
        for pat in POSITIVE_SIGNALS:
            if re.search(pat, text, re.IGNORECASE):
                score += 1.6

        # Empathy
        empathy_phrases = [
            "i understand", "i can see", "that must be", "frustrating",
            "i'm sorry", "sorry for", "apologize", "i hear you",
            "you're right", "valid concern", "completely understand"
        ]
        for phrase in empathy_phrases:
            if phrase in text:
                score += 1.2
                break

        # Concrete action / timeline
        if re.search(r"\b(within|by|in)\s+\d+\s*(hour|day|business day|working day)s?\b", text):
            score += 1.4
        if re.search(r"\b(refund|process|escalate|credit|compensation)\b", text):
            score += 1.1

        # Negative
        for pat in NEGATIVE_SIGNALS:
            if re.search(pat, text, re.IGNORECASE):
                score -= 1.7

        # Short / vague
        word_count = len(text.split())
        if word_count < 7:
            score -= 1.3
        elif word_count < 14:
            score -= 0.5

        # Deflection (talking about delivery when customer wants refund)
        if re.search(r"\b(will be delivered|order will|delivery by|arrive)\b", text) and "refund" not in text:
            score -= 1.8

        return score

    def update(self, agent_message: str) -> EmotionState:
        raw_score = self._score_agent_message(agent_message)

        # Angry personas need stronger positive signals
        adjusted = raw_score - (self.persona_modifier * 0.5)

        # Quality-based delta
        if adjusted >= 4.0:
            delta = -3          # Excellent reply
        elif adjusted >= 2.5:
            delta = -2          # Very good reply
        elif adjusted >= 1.0:
            delta = -1          # Good reply
        elif adjusted <= -2.0:
            delta = +2          # Very bad reply
        elif adjusted <= -0.7:
            delta = +1          # Poor reply
        else:
            delta = 0           # Neutral

        old_intensity = self.state.intensity
        new_intensity = max(
            EMOTION_SCALE_MIN,
            min(EMOTION_SCALE_MAX, old_intensity + delta)
        )

        old_label = self.state.label
        new_label = EMOTION_LABELS[new_intensity]

        self.state.intensity = new_intensity
        self.state.label = new_label

        self.state.history.append(
            f"{old_label}({old_intensity}) → {new_label}({new_intensity}) "
            f"[Δ{delta:+d} | score={raw_score:.1f}]"
        )

        return self.state

    def force_set(self, intensity: int, reason: str = "manual") -> EmotionState:
        intensity = max(EMOTION_SCALE_MIN, min(EMOTION_SCALE_MAX, intensity))
        self.state.intensity = intensity
        self.state.label = EMOTION_LABELS[intensity]
        self.state.history.append(
            f"force → {intensity} ({self.state.label}) [{reason}]"
        )
        return self.state