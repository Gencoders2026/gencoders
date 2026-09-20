"""
Configuration for the Customer Simulator Agent.

Reads settings from environment variables (.env) and exposes
provider-agnostic LLM settings. Supports any OpenAI-compatible
endpoint (OpenAI, Groq, etc.).
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# LLM SETTINGS
# ============================================================

_raw_api_key = os.getenv("OPENAI_API_KEY", "") or os.getenv("GROQ_API_KEY", "")

# A Groq key (gsk_...) is OpenAI-API compatible, so we can reuse the
# openai SDK against the Groq base URL.
if _raw_api_key.startswith("gsk_"):
    _default_base_url = "https://api.groq.com/openai/v1"
else:
    _default_base_url = os.getenv("LLM_BASE_URL", "") or None

OPENAI_API_KEY = _raw_api_key
LLM_BASE_URL = _default_base_url
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.9"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "250"))

USE_LLM = os.getenv("USE_LLM", "true").strip().lower() in ("1", "true", "yes", "on")


# ============================================================
# SIMULATOR DEFAULTS
# ============================================================

DEFAULT_PERSONA = os.getenv("DEFAULT_PERSONA", "frustrated")
DEFAULT_SCENARIO = os.getenv("DEFAULT_SCENARIO", "refund_request")
DEFAULT_INITIAL_EMOTION = os.getenv("DEFAULT_INITIAL_EMOTION", "frustrated")
DEFAULT_ISSUE_SEVERITY = int(os.getenv("DEFAULT_ISSUE_SEVERITY", "7"))   # 1-10
DEFAULT_PATIENCE_LEVEL = int(os.getenv("DEFAULT_PATIENCE_LEVEL", "5"))   # 1-10 (lower = less patient)
DEFAULT_EXPECTED_RESOLUTION = os.getenv("DEFAULT_EXPECTED_RESOLUTION", "full_refund")


# ============================================================
# EMOTION SCALE
# ============================================================

EMOTION_SCALE_MIN = 1
EMOTION_SCALE_MAX = 10


# ============================================================
# LOGGING
# ============================================================

LOG_DIR = os.getenv(
    "LOG_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"),
)
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# API
# ============================================================

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))