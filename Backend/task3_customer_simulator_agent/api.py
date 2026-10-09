"""
FastAPI server for the Customer Simulator Agent (Task 3).

Task 4/5/6 note: the Intent & Sentiment Analysis Agent, the Knowledge
Recommendation Agent, the Coaching & Response Suggestion Agent and the
Escalation Risk Monitor Agent live in their own module folder
(`task4_task5_task6_support_assist_agents/`) and expose a shared FastAPI
router. That router is mounted below, so the React Support Console keeps
talking to a single backend on port 8000.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Make sibling modules (simulator, personas, scenarios, ...) importable
# regardless of how uvicorn is launched (e.g. `uvicorn customer_simulator.api`).
_BASE_DIR = Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

from simulator import (
    CustomerSimulator,
    create_simulator,
    PERSONAS,
    SCENARIOS
)


BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = BASE_DIR.parent
# The React Support Console (Task 3 + 4 + 5 + 6 UI) is built into
# `support_console_frontend/dist`. Serve THAT as the root page so the
# browser gets the working Support Console (with the escalation risk
# monitor, coaching panel, emotion/frustration state, etc.) instead of
# the legacy static HTML prototype (now archived under
# `archive/legacy_static_ui_prototype/`).
REACT_DIST_DIR = ROOT_DIR / "support_console_frontend" / "dist"
INDEX_PATH = REACT_DIST_DIR / "index.html"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ==========================================================
# TASK 4 / 5 / 6 - SUPPORT ASSISTANCE MODULE (separate folder)
# ==========================================================
# task4_task5_task6_support_assist_agents/support_api.py exposes the
# shared router with /support/analyze, /coaching/evaluate,
# /escalation/... and /analyze.
TASK6_DIR = ROOT_DIR / "task4_task5_task6_support_assist_agents"
task6_router = None

if TASK6_DIR.exists():
    if str(TASK6_DIR) not in sys.path:
        # Position 0: the Task 6 modules must win over any same-named
        # legacy module left in this folder (import precedence).
        sys.path.insert(0, str(TASK6_DIR))

    from support_api import router as task6_router  # noqa: E402


# ==========================================================
# TASK 7 - LIVE SUPPORT CONSOLE MODULE (separate folder)
# ==========================================================
# task7_live_support_console/console_api.py exposes the shared router with
# /task7/analyze, /task7/transcript/parse and /task7/sessions... so the
# three-panel console (Manual Mode + Replay Mode) talks to this same
# backend.
TASK7_DIR = ROOT_DIR / "task7_live_support_console"
task7_router = None

if TASK7_DIR.exists():
    if str(TASK7_DIR) not in sys.path:
        sys.path.insert(0, str(TASK7_DIR))

    from console_api import router as task7_router  # noqa: E402


# ==========================================================
# TASK 8 - POST-INTERACTION SUMMARY + PERFORMANCE ANALYTICS
# ==========================================================
# task8_insights_analytics/insights_api.py exposes /task8/summary,
# /task8/analytics, /task8/conversations and /task8/demo-data.
TASK8_DIR = ROOT_DIR / "task8_insights_analytics"
task8_router = None

if TASK8_DIR.exists():
    if str(TASK8_DIR) not in sys.path:
        sys.path.insert(0, str(TASK8_DIR))

    from insights_api import router as task8_router  # noqa: E402


app = FastAPI(
    title="Customer Simulator Agent",
    version="2.0"
)

# Mount the Task 4/5/6 support-assistance endpoints on this backend too,
# so the Support Console UI can use one base URL
# (http://127.0.0.1:8000). The support-assistance service can also run on
# its own: task4_task5_task6_support_assist_agents/run.py
if task6_router is not None:
    app.include_router(task6_router)

# Task 7 - Live Support Console endpoints (/task7/...)
if task7_router is not None:
    app.include_router(task7_router)

# Task 8 - Post-Interaction Summary + Performance Analytics (/task8/...)
if task8_router is not None:
    app.include_router(task8_router)


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
# FRONTEND (React Task 6 UI)
# ==========================================================
# The React app is built into `frontend/dist`. The root page serves the
# built `index.html` and the `/assets/*` bundle is served from the same
# `dist` folder. A catch-all route is added below so the React Router's
# client-side routes (e.g. `/session/<id>`) keep working after a browser
# refresh instead of hitting a 404.
def wants_html(request: Request) -> bool:
    """True for a real browser navigation (SPA route), not an API call.

    Browsers send `Accept: text/html,application/xhtml+xml,...`, while
    `fetch`/`axios`/`requests`/`urllib` clients send `application/json` or
    `*/*`. This distinction is what lets `/session/<id>` serve the React
    app to the browser and JSON to the API.
    """
    accept = (request.headers.get("accept") or "").lower()
    return "text/html" in accept


def spa_index() -> FileResponse:
    """Serve the built React Support Console (SPA entry point)."""
    if INDEX_PATH.exists():
        return FileResponse(INDEX_PATH)
    raise HTTPException(
        status_code=404,
        detail=(
            "Support Console UI not built. Run `npm run build` inside the "
            "`support_console_frontend` folder."
        ),
    )


@app.get("/")
@app.get("/ui")
@app.get("/ui/")
async def home():
    return spa_index()



# Serve the built JS/CSS bundle from the dist folder. Mounting at
# /assets keeps it from shadowing the API routes.
if REACT_DIST_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(REACT_DIST_DIR / "assets")),
        name="react-assets"
    )

    # Serve root-level static files referenced by the built index.html
    # (favicon.svg, icons.svg) without shadowing the API routes.
    for static_name in ("favicon.svg", "icons.svg"):
        static_path = REACT_DIST_DIR / static_name
        if static_path.exists():
            app.get(f"/{static_name}")(
                lambda p=static_path: FileResponse(p)
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
# `/session/new` is a React route (session configuration), NOT a real
# session id. It must serve the SPA, so it is registered BEFORE the
# `/session/{session_id}` route below (which would otherwise capture
# "new" as a session id and 404).
@app.get("/session/new")
async def session_new():
    return spa_index()


@app.get("/session/{session_id}")
def get_session(session_id: str, request: Request):
    # ------------------------------------------------------
    # IMPORTANT (Task 6 UI routing)
    # ------------------------------------------------------
    # `/session/<id>` is BOTH an API endpoint and a React Router
    # client-side route (the Support Console / Task 6 conversation
    # interface). A browser navigation - opening the URL directly or
    # hitting refresh - must receive the built React app, otherwise the
    # user sees a raw JSON dump instead of the interface (which looked
    # like a "code screen"/broken page).
    #
    # Browsers send `Accept: text/html,...`; API clients (axios, requests,
    # urllib) send `application/json` or `*/*`. So the SPA is served only
    # for real browser navigations and the JSON state is kept for the API.
    if wants_html(request):
        return spa_index()

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
# SPA CATCH-ALL (React Router client-side routes)
# ==========================================================
# The React app uses client-side routing (`/session/<id>`, `/session/<id>/result`,
# `/analytics`, ...). After a browser refresh those URLs are NOT handled by
# React Router, so Starlette would return 404. This catch-all serves the
# built `index.html` for any non-API GET request, letting React take over.
# It is registered LAST so every real API route is matched first.
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # Serve the React SPA for any GET request that is NOT an explicit
    # API / static route. This is what makes client-side routing work
    # after a browser refresh (e.g. `/session/<id>`, `/analytics`,
    # `/session/new`). Real API endpoints (defined above this
    # catch-all) are matched first by Starlette, so they are never
    # intercepted here.
    return spa_index()


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
