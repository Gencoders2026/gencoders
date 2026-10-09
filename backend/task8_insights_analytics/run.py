"""
Task 8 - Insights & Performance Analytics (standalone server).

    python task8_insights_analytics/run.py

Serves the Task 8 API on http://127.0.0.1:8108. In the normal workflow the
router is mounted by the Customer Simulator backend instead, so the React
dashboard talks to a single origin (http://127.0.0.1:8000).

Environment variables (all optional):

    TASK8_API_HOST   default 127.0.0.1
    TASK8_API_PORT   default 8108
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

for candidate in (
    HERE,
    REPO_ROOT / "task7_live_support_console",
    REPO_ROOT / "task4_task5_task6_support_assist_agents",
    REPO_ROOT,
):
    candidate = str(candidate)
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

try:  # python-dotenv is optional
    from dotenv import load_dotenv

    for candidate in (HERE / ".env", REPO_ROOT / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
except Exception:  # pragma: no cover - dotenv is optional
    pass


HOST = os.getenv("TASK8_API_HOST", "127.0.0.1")
PORT = int(os.getenv("TASK8_API_PORT", "8108"))


def main() -> None:
    import uvicorn

    uvicorn.run("insights_api:create_app", host=HOST, port=PORT,
                app_dir=str(HERE), factory=True)


if __name__ == "__main__":
    main()
