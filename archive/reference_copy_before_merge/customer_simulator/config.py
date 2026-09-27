"""
Configuration for the Customer Simulator Agent.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI / LLM settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.85"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "250"))

# Simulator defaults
DEFAULT_PERSONA = "frustrated"
DEFAULT_SCENARIO = "refund_request"
DEFAULT_INITIAL_EMOTION = "angry"
DEFAULT_ISSUE_SEVERITY = 7          # 1-10
DEFAULT_PATIENCE_LEVEL = 5          # 1-10 (lower = less patient)
DEFAULT_EXPECTED_RESOLUTION = "full_refund"

# Emotion thresholds
EMOTION_SCALE_MIN = 1
EMOTION_SCALE_MAX = 10

# Logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))