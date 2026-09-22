"""
FastAPI server for Customer Simulator.

Task 6 note: the Coaching & Response Suggestion Agent and the
Escalation Risk Monitor Agent live in their own module folder
(`task6_support_assist/`) and expose a shared FastAPI router. That
router is mounted below, so the React Support Console keeps talking to
a single backend on port 8000.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from simulator import (
    CustomerSimulator,
    create_simulator,
    PERSONAS,
    SCENARIOS
)


BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = BASE_DIR.parent
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_PATH = FRONTEND_DIR / "index.html"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ==========================================================
# TASK 6 - SUPPORT ASSISTANCE MODULE (separate folder)
# ==========================================================
# task6_support_assist/support_api.py exposes the shared router with
# /support/analyze, /coaching/evaluate, /escalation/... and /analyze.
TASK6_DIR = ROOT_DIR / "task6_support_assist"
task6_router = None

if TASK6_DIR.exists():
    if str(TASK6_DIR) not in sys.path:
        # Position 0: the Task 6 modules must win over any same-named
        # legacy module left in this folder (import precedence).
        sys.path.insert(0, str(TASK6_DIR))

    from support_api import router as task6_router  # noqa: E402


app = FastAPI(
    title="Customer Simulator Agent",
    version="2.0"
)

# Mount the Task 6 support-assistance endpoints on this backend too, so
# the Support Console UI can use one base URL (http://127.0.0.1:8000).
# The Task 6 service can also run on its own: task6_support_assist/run.py
if task6_router is not None:
    app.include_router(task6_router)


# ==========================================================
# CORS
# ==========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ==========================================================
# ACTIVE SESSIONS
# ==========================================================
SESSIONS: Dict[str, CustomerSimulator] = {}

# ==========================================================
# REQUEST MODELS
# ==========================================================
class SessionRequest(BaseModel):
    persona: str = "frustrated"
    scenario: str = "refund_request"
    frustration_level: int = Field(default=5, ge=1, le=10)
    expected_resolution: str = "full_refund"


class AgentMessageRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1)
    frustration_level: Optional[int] = Field(default=None, ge=1, le=10)


class FrustrationRequest(BaseModel):
    frustration_level: int = Field(..., ge=1, le=10)


# ==========================================================
# FRONTEND
# ==========================================================
@app.get("/")
@app.get("/ui")
@app.get("/ui/")
async def home():
    if INDEX_PATH.exists():
        return FileResponse(INDEX_PATH)
    return HTMLResponse(
        "<h1>frontend/index.html not found</h1>",
        status_code=404
    )


if FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static"
    )


# ==========================================================
# HEALTH
# ==========================================================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "customer-simulator"
    }


# ==========================================================
# OPTIONS
# ==========================================================
@app.get("/config/options")
def options():
    return {
        "personas": [
            {
                "value": key,
                "name": value["name"],
                "style": value["style"]
            }
            for key, value in PERSONAS.items()
        ],
        "scenarios": [
            {
                "value": key,
                "name": value["name"]
            }
            for key, value in SCENARIOS.items()
        ],
        "frustration_levels": list(range(1, 11)),
        "resolutions": [
            "full_refund",
            "partial_refund",
            "replacement",
            "store_credit",
            "cancellation_confirmed",
            "account_restored",
            "new_delivery_date"
        ]
    }


# ==========================================================
# START SESSION
# ==========================================================
@app.post("/session/start")
def start_session(req: SessionRequest):
    try:
        sim = create_simulator(
            persona=req.persona,
            scenario=req.scenario,
            frustration_level=req.frustration_level,
            expected_resolution=req.expected_resolution
        )
        result = sim.start()
        SESSIONS[sim.session_id] = sim
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start session: {e}"
        )


# ==========================================================
# CUSTOMER RESPONSE
# ==========================================================
@app.post("/session/respond")
def respond_to_customer(req: AgentMessageRequest):
    sim = SESSIONS.get(req.session_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        if req.frustration_level is not None:
            sim.set_frustration_level(req.frustration_level)

        result = sim.respond(req.message)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Respond failed: {e}"
        )


# ==========================================================
# UPDATE FRUSTRATION
# ==========================================================
@app.patch("/session/{session_id}/frustration")
def update_frustration(session_id: str, req: FrustrationRequest):
    sim = SESSIONS.get(session_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Session not found")

    level = sim.set_frustration_level(req.frustration_level)
    return {
        "session_id": session_id,
        "frustration_level": level,
        "emotion": sim._build_response("")["emotion"]
    }


# ==========================================================
# SESSION STATE
# ==========================================================
@app.get("/session/{session_id}")
def get_session(session_id: str):
    sim = SESSIONS.get(session_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Session not found")
    return sim.get_state()


# ==========================================================
# SESSION LOG
# ==========================================================
@app.get("/session/{session_id}/log")
def get_log(session_id: str):
    sim = SESSIONS.get(session_id)

    if sim:
        path = Path(sim.log_path)
    else:
        path = LOG_DIR / f"session_{session_id}.json"

    if not path.exists():
        raise HTTPException(status_code=404, detail="Log not found")

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


# ==========================================================
# END SESSION
# ==========================================================
@app.delete("/session/{session_id}")
def end_session(session_id: str):
    sim = SESSIONS.pop(session_id, None)
    if sim:
        return {
            "status": "ended",
            "session_id": session_id,
            "log_path": str(sim.log_path)
        }
    return {
        "status": "not_found",
        "session_id": session_id
    }


# ==========================================================
# ACTIVE SESSIONS
# ==========================================================
@app.get("/sessions")
def sessions():
    return {
        "active": list(SESSIONS.keys()),
        "count": len(SESSIONS)
    }


# ==========================================================
# RUN
# ==========================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
