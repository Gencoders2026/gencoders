"""
Task 4 - Intent & Sentiment Analysis Agent (standalone server).

Do not edit any existing engine code. This launcher only puts the
existing repository folders on ``sys.path`` and starts the existing
FastAPI engine.

    python task4_intent_sentiment_analysis_agent/run.py

Environment variables (all optional):

    TASK4_API_HOST    default 127.0.0.1
    TASK4_API_PORT    default 8104
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

for candidate in (REPO_ROOT / "task4_task5_task6_support_assist_agents", REPO_ROOT):
    candidate = str(candidate)
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

# Load .env (this folder or the repository root) BEFORE the engine is
# imported, so thresholds are picked up at import time.
try:  # python-dotenv is optional
    from dotenv import load_dotenv

    for candidate in (HERE / ".env", REPO_ROOT / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
except Exception:  # pragma: no cover - dotenv is optional
    pass


HOST = os.getenv("TASK4_API_HOST", "127.0.0.1")
PORT = int(os.getenv("TASK4_API_PORT", "8104"))


def main() -> None:
    import uvicorn

    uvicorn.run("app:app", host=HOST, port=PORT, app_dir=str(HERE))


if __name__ == "__main__":
    main()
