"""
FastAPI server for Customer Simulator.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from simulator import (
    CustomerSimulator,
    create_simulator,
    PERSONAS,
    SCENARIOS
)


BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_PATH = FRONTEND_DIR / "index.html"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


app = FastAPI(
    title="Customer Simulator Agent",
    version="2.0"
)

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


class AnalyzeRequest(BaseModel):
    """
    Accepts any of these field names for the conversation text:
    - query
    - transcript
    - conversation
    - text
    """
    query: Optional[str] = None
    transcript: Optional[str] = None
    conversation: Optional[str] = None
    text: Optional[str] = None
    persona_hint: Optional[str] = None
    scenario_hint: Optional[str] = None

    @model_validator(mode="after")
    def ensure_text_present(self):
        content = (
            self.query
            or self.transcript
            or self.conversation
            or self.text
        )
        if not content or not str(content).strip():
            raise ValueError(
                "One of the fields 'query', 'transcript', 'conversation' or 'text' must be provided and non-empty."
            )
        self.query = str(content).strip()
        return self


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
        data = json.load(file)

    # ------------------------------------------------------
    # NEW LOG FORMAT
    # If the log already contains meta + conversation,
    # return it directly.
    # ------------------------------------------------------
    if "meta" in data and "conversation" in data:
        return data

    # ------------------------------------------------------
    # OLD LOG FORMAT
    # Convert:
    #   history
    # into:
    #   meta + conversation
    #
    # This keeps old session logs compatible with the
    # current React frontend.
    # ------------------------------------------------------
    history = data.get("history", [])

    conversation = []

    for index, item in enumerate(history, start=1):
        role = item.get("role", "unknown")

        emotion_data = None

        if item.get("emotion") is not None:
            emotion_data = {
                "label": item.get("emotion", "Unknown"),
                "frustration_level": item.get("frustration_level")
            }

        conversation.append({
            "turn": index,
            "timestamp": None,
            "role": role,
            "message": item.get("content", ""),
            "emotion": emotion_data
        })

    # ------------------------------------------------------
    # DETERMINE WHETHER THE SESSION WAS COMPLETED
    # ------------------------------------------------------
    finished = False

    if history:
        last_message = str(
            history[-1].get("content", "")
        ).lower()

        completion_phrases = [
            "thank you for resolving",
            "thank you for your help",
            "i appreciate your help",
            "thanks for resolving",
            "problem is resolved",
            "issue is resolved",
            "that resolves",
            "resolved"
        ]

        finished = any(
            phrase in last_message
            for phrase in completion_phrases
        )

    # ------------------------------------------------------
    # BUILD META INFORMATION
    # ------------------------------------------------------
    meta = {
        "session_id": data.get("session_id", session_id),
        "started_at": None,
        "ended_at": None,
        "config": {
            "persona": data.get("persona"),
            "scenario": data.get("scenario"),
            "frustration_level": data.get("frustration_level")
        },
        "final_emotion": None,
        "turn_count": len(history),
        "finished": finished
    }

    # ------------------------------------------------------
    # GET FINAL CUSTOMER EMOTION
    # ------------------------------------------------------
    customer_messages = [
        item
        for item in history
        if item.get("role") == "customer"
    ]

    if customer_messages:
        final_customer = customer_messages[-1]

        meta["final_emotion"] = {
            "label": final_customer.get(
                "emotion",
                "Unknown"
            ),
            "frustration_level": final_customer.get(
                "frustration_level"
            )
        }

    # ------------------------------------------------------
    # RETURN NORMALIZED SESSION DATA
    # ------------------------------------------------------
    return {
        "session_id": data.get(
            "session_id",
            session_id
        ),
        "persona": data.get("persona"),
        "scenario": data.get("scenario"),
        "frustration_level": data.get(
            "frustration_level"
        ),
        "finished": finished,
        "meta": meta,
        "conversation": conversation,

        # Keep history for backward compatibility.
        "history": history
    }

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
# MANUAL ANALYSIS – FULLY FIXED
# ==========================================================
@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    text = req.query
    text_lower = text.lower()

    # ------------------------------------------------------
    # INTENT DETECTION
    # ------------------------------------------------------
    if any(w in text_lower for w in ["refund", "money back", "return"]):
        intent = "refund_request"
    elif any(w in text_lower for w in ["late", "delay", "delayed", "tracking", "not arrived", "hasn't arrived", "hasnt arrived"]):
        intent = "delayed_order"
    elif any(w in text_lower for w in ["payment", "charged", "declined", "card"]):
        intent = "payment_failure"
    elif any(w in text_lower for w in ["login", "password", "locked", "account"]):
        intent = "account_issue"
    elif any(w in text_lower for w in ["cancel", "unsubscribe", "stop billing"]):
        intent = "cancellation"
    else:
        intent = "general_inquiry"

    # ------------------------------------------------------
    # FRUSTRATION / EMOTION
    # ------------------------------------------------------
    if any(w in text_lower for w in [
        "furious", "unacceptable", "ridiculous", "manager",
        "worst", "immediately", "urgent", "urgently", "this is ridiculous"
    ]):
        score = 9
        emotion = "Furious"
    elif any(w in text_lower for w in [
        "angry", "frustrated", "upset", "annoyed", "not happy"
    ]):
        score = 7
        emotion = "Angry"
    elif any(w in text_lower for w in ["please", "thank", "appreciate", "thanks"]):
        score = 3
        emotion = "Calm"
    else:
        score = 5
        emotion = "Frustrated"

    risk = "High" if score >= 8 else "Medium" if score >= 6 else "Low"

    # ------------------------------------------------------
    # WHAT THE AGENT DID WELL
    # ------------------------------------------------------
    strengths = []
    if "sorry" in text_lower or "apologize" in text_lower:
        strengths.append("Agent apologized / showed empathy early.")
    if "understand" in text_lower or "frustration" in text_lower:
        strengths.append("Agent acknowledged the customer's frustration.")
    if "check" in text_lower or "looking into" in text_lower or "let me" in text_lower:
        strengths.append("Agent took ownership and started investigating.")
    if "thank you for contacting" in text_lower:
        strengths.append("Agent used a professional greeting.")

    if not strengths:
        strengths.append("No clear strengths detected in this short transcript.")

    # ------------------------------------------------------
    # AREAS FOR IMPROVEMENT
    # ------------------------------------------------------
    weaknesses = []
    if score >= 7 and "sorry" not in text_lower and "apologize" not in text_lower:
        weaknesses.append("Agent did not clearly apologize for the inconvenience.")
    if "urgently" in text_lower or "urgent" in text_lower:
        if "priority" not in text_lower and "escalate" not in text_lower and "immediately" not in text_lower:
            weaknesses.append("Customer expressed urgency but agent did not explicitly prioritize or escalate.")
    if "looking into it now" in text_lower or "let me check" in text_lower:
        weaknesses.append("Agent started investigating but did not give a concrete next step or timeline.")
    if len(text.splitlines()) < 6:
        weaknesses.append("Conversation is very short – more probing questions would help.")

    if not weaknesses:
        weaknesses.append("No major weaknesses identified.")

    # ------------------------------------------------------
    # COACHING SUGGESTIONS
    # ------------------------------------------------------
    coaching = []

    if score >= 7:
        coaching.append("Start by acknowledging the emotion: “I completely understand how frustrating this must be after 10 days.”")
    
    coaching.append("Give a clear next step + timeline (e.g. “I’m checking the tracking now and will have an update for you within 2 minutes.”)")

    if intent == "delayed_order":
        coaching.append("Proactively offer options: expedited reshipment, partial refund, or full refund.")
        coaching.append("Share the tracking number and expected delivery date if available.")
    elif intent == "refund_request":
        coaching.append("Confirm refund eligibility and exact processing time (e.g. 3–5 business days).")

    coaching.append("End with a reassurance statement and ask if there’s anything else you can help with.")

    # ------------------------------------------------------
    # FINAL RESPONSE – covers all possible keys the frontend may use
    # ------------------------------------------------------
    return {
        # Emotion (all possible names)
        "overall_emotion": emotion,
        "emotion": emotion,
        "emotion_label": emotion,
        "customer_emotion": emotion,
        "overall_customer_emotion": emotion,

        # Frustration
        "frustration_score": score,
        "frustration_level": score,
        "frustration": score,

        # Risk
        "escalation_risk": risk,

        # Strengths
        "strengths": strengths,
        "what_agent_did_well": strengths,
        "agent_strengths": strengths,

        # Weaknesses
        "weaknesses": weaknesses,
        "areas_for_improvement": weaknesses,
        "improvement_areas": weaknesses,

        # Coaching (all possible names)
        "coaching_suggestions": coaching,
        "coaching_guidance": coaching,
        "suggestions": coaching,
        "coaching": coaching,
        "improvement_suggestions": coaching,
        "recommendations": coaching,

        # Extra
        "intent": intent,
        "suggested_persona": req.persona_hint or ("angry" if score >= 7 else "frustrated"),
        "suggested_scenario": req.scenario_hint or intent,
        "query": req.query
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