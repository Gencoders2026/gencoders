"""
Emotion / State Manager for the Customer Simulator.
"""

from typing import Dict, Optional
from dataclasses import dataclass, field
import re

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
    r"\b(I (will|can) (help|fix|take care))\b",
    r"\b(compensation|discount|credit|voucher)\b",
    r"\b(understood|I see the issue|you're right)\b",
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
        initial_emotion: str = "angry",
        initial_intensity: Optional[int] = None,
        patience_level: int = 5,
        persona_modifier: int = 0,
    ):
        self.patience_level = max(1, min(10, patience_level))
        self.persona_modifier = persona_modifier

        emotion_start_map = {
            "calm": 2,
            "mildly_concerned": 3,
            "concerned": 4,
            "frustrated": 6,
            "angry": 8,
            "furious": 9,
            "impatient": 7,
            "polite": 2,
            "confused": 4,
        }
        start = initial_intensity
        if start is None:
            start = emotion_start_map.get(initial_emotion.lower(), 6)

        start = max(EMOTION_SCALE_MIN, min(EMOTION_SCALE_MAX, start))
        self.state = EmotionState(
            intensity=start,
            label=EMOTION_LABELS[start],
            history=[f"init → {start} ({EMOTION_LABELS[start]})"],
        )

    def get_state(self) -> EmotionState:
        return self.state

    def _score_agent_message(self, agent_message: str) -> int:
        text = agent_message.lower()
        score = 0

        for pat in POSITIVE_SIGNALS:
            if re.search(pat, text, re.IGNORECASE):
                score += 1

        for pat in NEGATIVE_SIGNALS:
            if re.search(pat, text, re.IGNORECASE):
                score -= 1

        if len(agent_message.split()) < 8:
            score -= 0.5
        if any(w in text for w in ["i understand", "i can see", "that must be", "frustrating"]):
            score += 0.5

        return int(round(score))

    def update(self, agent_message: str) -> EmotionState:
        raw_delta = self._score_agent_message(agent_message)

        patience_factor = (self.patience_level - 5) * 0.15
        persona_factor = self.persona_modifier * 0.1

        if raw_delta > 0:
            delta = -max(1, int(1 + raw_delta + patience_factor + persona_factor))
        elif raw_delta < 0:
            delta = max(1, int(1 - raw_delta - patience_factor - persona_factor))
        else:
            delta = 1 if self.state.intensity >= 6 else 0

        new_intensity = self.state.intensity + delta
        new_intensity = max(EMOTION_SCALE_MIN, min(EMOTION_SCALE_MAX, new_intensity))

        old_label = self.state.label
        new_label = EMOTION_LABELS[new_intensity]

        self.state.intensity = new_intensity
        self.state.label = new_label
        self.state.history.append(
            f"{old_label}({self.state.intensity - delta}) → {new_label}({new_intensity}) [Δ{delta:+d}]"
        )

        return self.state

    def force_set(self, intensity: int, reason: str = "manual") -> EmotionState:
        intensity = max(EMOTION_SCALE_MIN, min(EMOTION_SCALE_MAX, intensity))
        self.state.intensity = intensity
        self.state.label = EMOTION_LABELS[intensity]
        self.state.history.append(f"force → {intensity} ({self.state.label}) [{reason}]")
        return self.state