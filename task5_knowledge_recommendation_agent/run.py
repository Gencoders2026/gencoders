"""
Task 5 - Knowledge Recommendation Agent (standalone server).

Only new launcher code; reuses the existing knowledge_bridge engine.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

for candidate in (
    REPO_ROOT / "task4_task5_task6_support_assist_agents",
    REPO_ROOT,
):
    candidate = str(candidate)
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

try:
    from dotenv import load_dotenv

    for candidate in (HERE / ".env", REPO_ROOT / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
except Exception:
    pass

HOST = os.getenv("TASK5_API_HOST", "127.0.0.1")
PORT = int(os.getenv("TASK5_API_PORT", "8105"))


def main() -> None:
    import uvicorn

    uvicorn.run("app:app", host=HOST, port=PORT, app_dir=str(HERE))


if __name__ == "__main__":
    main()
