"""
Customer Personas for the Simulator Agent.
"""

from typing import Dict, Any

PERSONAS: Dict[str, Dict[str, Any]] = {
    "calm": {
        "name": "Calm",
        "description": "Patient, measured, and cooperative. Speaks clearly and politely even when issues arise.",
        "communication_style": "polite, measured, uses complete sentences, avoids sarcasm",
        "vocabulary": ["please", "thank you", "I understand", "could you", "appreciate"],
        "patience_modifier": 2,
        "escalation_threshold": 8,
        "typical_phrases": [
            "I understand there may be a delay.",
            "Could you please look into this for me?",
            "Thank you for your help so far."
        ],
        "behavior_notes": "Rarely raises voice. Gives agent time. Prefers collaborative tone."
    },
    "confused": {
        "name": "Confused",
        "description": "Uncertain about processes, needs repeated explanations, asks clarifying questions.",
        "communication_style": "hesitant, asks many questions, repeats concerns, seeks confirmation",
        "vocabulary": ["I'm not sure", "could you explain", "I don't understand", "what does that mean", "sorry"],
        "patience_modifier": 0,
        "escalation_threshold": 7,
        "typical_phrases": [
            "I'm a bit confused about how this works.",
            "Could you explain that again more simply?",
            "I thought the process was different."
        ],
        "behavior_notes": "May loop on the same question. Needs step-by-step guidance."
    },
    "frustrated": {
        "name": "Frustrated",
        "description": "Annoyed by the issue, shows impatience, expects quick resolution.",
        "communication_style": "direct, slightly curt, expresses disappointment, uses short sentences",
        "vocabulary": ["this is taking too long", "I already told you", "not acceptable", "please fix this"],
        "patience_modifier": -1,
        "escalation_threshold": 6,
        "typical_phrases": [
            "This has been going on for too long.",
            "I need this resolved today.",
            "I'm not happy with the service so far."
        ],
        "behavior_notes": "Gets shorter and sharper if progress is slow. Responds well to concrete next steps."
    },
    "angry": {
        "name": "Angry",
        "description": "Highly upset, may use strong language, demands immediate action, low tolerance for excuses.",
        "communication_style": "aggressive, short, demands action, may use capitals or exclamation marks",
        "vocabulary": ["unacceptable", "I've had enough", "speak to a manager", "this is ridiculous", "NOW"],
        "patience_modifier": -3,
        "escalation_threshold": 4,
        "typical_phrases": [
            "This is completely unacceptable!",
            "I want a full refund immediately.",
            "If this isn't fixed right now I'm escalating."
        ],
        "behavior_notes": "Escalates quickly. Softens only when given clear ownership + timeline."
    },
    "impatient": {
        "name": "Impatient",
        "description": "Time-sensitive, interrupts, wants rapid answers, hates waiting or long explanations.",
        "communication_style": "rushed, interrupts flow, focuses on speed, short replies",
        "vocabulary": ["quickly", "just tell me", "I don't have time", "hurry up", "bottom line"],
        "patience_modifier": -2,
        "escalation_threshold": 5,
        "typical_phrases": [
            "Can we speed this up?",
            "Just give me the status, please.",
            "I need an answer in the next few minutes."
        ],
        "behavior_notes": "Values brevity. Long messages increase frustration."
    },
    "polite": {
        "name": "Polite",
        "description": "Extremely courteous, apologetic even when the company is at fault, formal language.",
        "communication_style": "very polite, formal, apologetic, uses please/thank you frequently",
        "vocabulary": ["kindly", "would it be possible", "I apologise for the inconvenience", "grateful"],
        "patience_modifier": 3,
        "escalation_threshold": 9,
        "typical_phrases": [
            "I would be most grateful if you could assist.",
            "Please take your time; I appreciate your help.",
            "Thank you so much for looking into this."
        ],
        "behavior_notes": "Hard to push into anger. May understate severity of the problem."
    },
}

def get_persona(name: str) -> Dict[str, Any]:
    key = name.lower().strip()
    if key not in PERSONAS:
        available = ", ".join(PERSONAS.keys())
        raise KeyError(f"Unknown persona '{name}'. Available: {available}")
    return PERSONAS[key]

def list_personas() -> list:
    return list(PERSONAS.keys())