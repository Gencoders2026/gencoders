"""
Customer Simulator Agent package.

A configurable, LLM-powered customer-simulator that generates realistic
customer messages turn-by-turn based on persona, scenario, emotion,
issue severity, patience, and expected resolution.
"""

from .simulator import (
    CustomerSimulator,
    create_simulator,
    get_band,
    get_emotion_label,
    run_self_test,
)
from .personas import PERSONAS, list_personas, get_persona
from .scenarios import SCENARIOS, list_scenarios, get_scenario
from .emotion_manager import EmotionManager, EmotionState
from .logger import ConversationLogger
from .llm_client import LLMClient

__version__ = "2.0"

__all__ = [
    "CustomerSimulator",
    "create_simulator",
    "get_band",
    "get_emotion_label",
    "run_self_test",
    "PERSONAS",
    "list_personas",
    "get_persona",
    "SCENARIOS",
    "list_scenarios",
    "get_scenario",
    "EmotionManager",
    "EmotionState",
    "ConversationLogger",
    "LLMClient",
]