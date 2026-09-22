"""
Run the Task 6 support-assistance API standalone.

    cd task6_support_assist
    python run.py            # -> http://127.0.0.1:8100/docs

The Customer Simulator backend (http://127.0.0.1:8000) mounts the very
same routes, so this script is only needed when you want to run and
demonstrate the Task 6 agents without the customer simulator.

Environment variables (all optional):

    TASK6_API_HOST                default 127.0.0.1
    TASK6_API_PORT                default 8100
    ESCALATION_ALERT_THRESHOLD    default 70
"""

import os
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent

if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

# Load .env (this folder or the repository root) BEFORE support_api is
# imported, so ESCALATION_ALERT_THRESHOLD is picked up at import time.
try:  # python-dotenv is optional
    from dotenv import load_dotenv

    for candidate in (MODULE_DIR / ".env", MODULE_DIR.parent / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
except Exception:  # pragma: no cover - dotenv is optional
    pass


HOST = os.getenv("TASK6_API_HOST", "127.0.0.1")
PORT = int(os.getenv("TASK6_API_PORT", "8100"))


def main() -> None:
    import uvicorn

    uvicorn.run("support_api:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
