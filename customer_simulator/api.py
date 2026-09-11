"""
FastAPI interface for the Customer Simulator Agent.
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from simulator import CustomerSimulator, create_simulator
from personas import list_personas
from scenarios import list_scenarios
from config import API_HOST, API_PORT, LOG_DIR

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
INDEX_PATH = os.path.join(FRONTEND_DIR, "index.html")

app = FastAPI(
    title="Customer Simulator Agent API",
    description="Simulate realistic customer conversations for support training & testing.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: Dict[str, CustomerSimulator] = {}


class SessionRequest(BaseModel):
    persona: str = Field("frustrated")
    scenario: str = Field("refund_request")
    initial_emotion: str = Field("angry")
    issue_severity: int = Field(7, ge=1, le=10)
    patience_level: int = Field(5, ge=1, le=10)
    expected_resolution: str = Field("full_refund")
    use_llm: bool = Field(True)


class AgentMessageRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1)


class ManualAnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1)
    persona_hint: Optional[str] = None
    scenario_hint: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse)
@app.get("/ui/", response_class=HTMLResponse)
async def serve_ui():
    if os.path.exists(INDEX_PATH):
        return FileResponse(INDEX_PATH)
    return HTMLResponse("<h1>Error: frontend/index.html not found</h1>", status_code=404)


if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "service": "customer-simulator"}


@app.get("/config/options")
def get_options():
    return {
        "personas": list_personas(),
        "scenarios": list_scenarios(),
        "emotions": ["calm", "confused", "frustrated", "angry", "impatient", "polite"],
        "resolutions": [
            "full_refund", "partial_refund", "replacement", "store_credit",
            "cancellation_confirmed", "account_restored", "new_delivery_date",
        ],
    }


@app.post("/session/start")
def start_session(req: SessionRequest):
    try:
        sim = create_simulator(
            persona=req.persona,
            scenario=req.scenario,
            initial_emotion=req.initial_emotion,
            issue_severity=req.issue_severity,
            patience_level=req.patience_level,
            expected_resolution=req.expected_resolution,
            use_llm=req.use_llm,
        )
        result = sim.start()
        SESSIONS[sim.session_id] = sim
        return result
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {e}")


@app.post("/session/respond")
def respond_to_customer(req: AgentMessageRequest):
    sim = SESSIONS.get(req.session_id)
    if not sim:
        raise HTTPException(status_code=404, detail=f"Session '{req.session_id}' not found")
    try:
        result = sim.respond(req.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Respond failed: {e}")


@app.get("/session/{session_id}")
def get_session(session_id: str):
    sim = SESSIONS.get(session_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Session not found")
    return sim.get_state()


@app.get("/session/{session_id}/log")
def get_session_log(session_id: str):
    sim = SESSIONS.get(session_id)
    if not sim:
        log_path = Path(LOG_DIR) / f"session_{session_id}.json"
        if log_path.exists():
            import json
            with open(log_path, encoding="utf-8") as f:
                return json.load(f)
        raise HTTPException(status_code=404, detail="Session not found")
    return sim.logger.get_full_log()


@app.delete("/session/{session_id}")
def end_session(session_id: str):
    sim = SESSIONS.pop(session_id, None)
    if sim:
        sim.logger.finalize(sim.emotion_mgr.get_state().to_dict())
        return {"status": "ended", "session_id": session_id, "log_path": sim.logger.get_log_path()}
    return {"status": "not_found", "session_id": session_id}


@app.get("/sessions")
def list_sessions():
    return {
        "active": list(SESSIONS.keys()),
        "count": len(SESSIONS),
    }


@app.post("/analyze")
def analyze_customer_message(req: ManualAnalyzeRequest):
    text = req.query.lower()

    intent = "general_inquiry"
    if any(w in text for w in ["refund", "money back", "return"]):
        intent = "refund_request"
    elif any(w in text for w in ["late", "delayed", "not arrived", "tracking"]):
        intent = "delayed_order"
    elif any(w in text for w in ["payment", "charged", "declined", "card"]):
        intent = "payment_failure"
    elif any(w in text for w in ["login", "password", "locked", "account"]):
        intent = "account_issue"
    elif any(w in text for w in ["cancel", "unsubscribe", "stop billing"]):
        intent = "cancellation"

    emotion_score = 5
    if any(w in text for w in ["furious", "ridiculous", "unacceptable", "now!", "manager"]):
        emotion_score = 9
    elif any(w in text for w in ["angry", "frustrated", "upset", "not happy"]):
        emotion_score = 7
    elif any(w in text for w in ["please", "thank", "appreciate", "kindly"]):
        emotion_score = 3

    escalation_risk = "low"
    if emotion_score >= 8:
        escalation_risk = "high"
    elif emotion_score >= 6:
        escalation_risk = "medium"

    coaching = []
    if emotion_score >= 7:
        coaching.append("Acknowledge the customer's frustration first.")
        coaching.append("Offer a concrete next step and timeline.")
    if intent == "refund_request":
        coaching.append("Confirm order details and state the refund policy clearly.")
    if escalation_risk == "high":
        coaching.append("Consider offering escalation to a supervisor early.")

    return {
        "query": req.query,
        "intent": intent,
        "emotion_score": emotion_score,
        "emotion_label": "angry" if emotion_score >= 7 else ("frustrated" if emotion_score >= 5 else "calm"),
        "escalation_risk": escalation_risk,
        "coaching_guidance": coaching,
        "suggested_persona": req.persona_hint or ("angry" if emotion_score >= 7 else "frustrated"),
        "suggested_scenario": req.scenario_hint or intent,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host=API_HOST, port=API_PORT, reload=True)