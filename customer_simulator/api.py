"""
FastAPI interface for the Customer Simulator Agent.

Frustration Level is the single control for customer emotional intensity.
Patience Level and Issue Severity are not used.
"""

import os
from typing import Optional, Dict
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


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FRONTEND_DIR = os.path.join(
    BASE_DIR,
    "frontend"
)

INDEX_PATH = os.path.join(
    FRONTEND_DIR,
    "index.html"
)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Customer Simulator Agent API",
    description=(
        "Simulate realistic customer conversations "
        "for support training and testing."
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ACTIVE SESSIONS
# ============================================================

SESSIONS: Dict[str, CustomerSimulator] = {}


# ============================================================
# REQUEST MODELS
# ============================================================

class SessionRequest(BaseModel):
    """
    Request used to start a customer simulation.

    Frustration level is the customer's initial
    emotional intensity from 1 to 10.
    """

    persona: str = Field(
        default="frustrated"
    )

    scenario: str = Field(
        default="refund_request"
    )

    frustration_level: int = Field(
        default=5,
        ge=1,
        le=10
    )

    expected_resolution: str = Field(
        default="full_refund"
    )

    use_llm: bool = Field(
        default=True
    )


class AgentMessageRequest(BaseModel):
    """
    Support agent's reply to the customer.
    """

    session_id: str

    message: str = Field(
        ...,
        min_length=1
    )


class ManualAnalyzeRequest(BaseModel):
    """
    Request for manual customer-message analysis.
    """

    query: str = Field(
        ...,
        min_length=1
    )

    persona_hint: Optional[str] = None

    scenario_hint: Optional[str] = None


# ============================================================
# FRONTEND
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
@app.get(
    "/ui",
    response_class=HTMLResponse
)
@app.get(
    "/ui/",
    response_class=HTMLResponse
)
async def serve_ui():

    if os.path.exists(INDEX_PATH):

        return FileResponse(
            INDEX_PATH
        )

    return HTMLResponse(
        "<h1>Error: frontend/index.html not found</h1>",
        status_code=404
    )


if os.path.exists(FRONTEND_DIR):

    app.mount(
        "/static",
        StaticFiles(
            directory=FRONTEND_DIR
        ),
        name="static"
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "customer-simulator"
    }


# ============================================================
# CONFIGURATION OPTIONS
# ============================================================

@app.get("/config/options")
def get_options():

    return {
        "personas": list_personas(),

        "scenarios": list_scenarios(),

        # Frustration is now the emotional control.
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


# ============================================================
# START SESSION
# ============================================================

@app.post("/session/start")
def start_session(req: SessionRequest):

    try:

        # ----------------------------------------------------
        # Create simulator
        # ----------------------------------------------------

        sim = create_simulator(

            persona=req.persona,

            scenario=req.scenario,

            # IMPORTANT:
            # Frustration level controls the customer's
            # initial emotional intensity.
            frustration_level=req.frustration_level,

            expected_resolution=req.expected_resolution,

            use_llm=req.use_llm
        )

        # ----------------------------------------------------
        # Start customer conversation
        # ----------------------------------------------------

        result = sim.start()

        # ----------------------------------------------------
        # Store active session
        # ----------------------------------------------------

        SESSIONS[sim.session_id] = sim

        return result

    except KeyError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except TypeError as e:

        raise HTTPException(
            status_code=500,
            detail=(
                "Simulator configuration mismatch. "
                "Make sure simulator.py uses "
                "'frustration_level'. "
                f"Details: {e}"
            )
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to start session: {e}"
            )
        )


# ============================================================
# CUSTOMER RESPONSE
# ============================================================

@app.post("/session/respond")
def respond_to_customer(
    req: AgentMessageRequest
):

    # --------------------------------------------------------
    # Find session
    # --------------------------------------------------------

    sim = SESSIONS.get(
        req.session_id
    )

    if not sim:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Session '{req.session_id}' "
                "not found"
            )
        )

    try:

        # ----------------------------------------------------
        # Generate next customer response
        # ----------------------------------------------------

        result = sim.respond(
            req.message
        )

        return result

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Respond failed: {e}"
            )
        )


# ============================================================
# GET SESSION STATE
# ============================================================

@app.get("/session/{session_id}")
def get_session(
    session_id: str
):

    sim = SESSIONS.get(
        session_id
    )

    if not sim:

        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    return sim.get_state()


# ============================================================
# GET SESSION LOG
# ============================================================

@app.get("/session/{session_id}/log")
def get_session_log(
    session_id: str
):

    sim = SESSIONS.get(
        session_id
    )

    # --------------------------------------------------------
    # Active session
    # --------------------------------------------------------

    if sim:

        return sim.logger.get_full_log()

    # --------------------------------------------------------
    # Try saved log
    # --------------------------------------------------------

    log_path = (
        Path(LOG_DIR)
        / f"session_{session_id}.json"
    )

    if log_path.exists():

        import json

        with open(
            log_path,
            encoding="utf-8"
        ) as f:

            return json.load(f)

    raise HTTPException(
        status_code=404,
        detail="Session not found"
    )


# ============================================================
# END SESSION
# ============================================================

@app.delete("/session/{session_id}")
def end_session(
    session_id: str
):

    sim = SESSIONS.pop(
        session_id,
        None
    )

    if sim:

        sim.logger.finalize(
            sim.emotion_mgr
            .get_state()
            .to_dict()
        )

        return {
            "status": "ended",

            "session_id": session_id,

            "log_path": (
                sim.logger.get_log_path()
            )
        }

    return {
        "status": "not_found",
        "session_id": session_id
    }


# ============================================================
# LIST ACTIVE SESSIONS
# ============================================================

@app.get("/sessions")
def list_sessions():

    return {
        "active": list(
            SESSIONS.keys()
        ),

        "count": len(
            SESSIONS
        )
    }


# ============================================================
# MANUAL CUSTOMER MESSAGE ANALYSIS
# ============================================================

@app.post("/analyze")
def analyze_customer_message(
    req: ManualAnalyzeRequest
):

    text = req.query.lower()

    # ========================================================
    # INTENT DETECTION
    # ========================================================

    intent = "general_inquiry"

    if any(
        word in text
        for word in [
            "refund",
            "money back",
            "return"
        ]
    ):

        intent = "refund_request"

    elif any(
        word in text
        for word in [
            "late",
            "delayed",
            "not arrived",
            "tracking"
        ]
    ):

        intent = "delayed_order"

    elif any(
        word in text
        for word in [
            "payment",
            "charged",
            "declined",
            "card"
        ]
    ):

        intent = "payment_failure"

    elif any(
        word in text
        for word in [
            "login",
            "password",
            "locked",
            "account"
        ]
    ):

        intent = "account_issue"

    elif any(
        word in text
        for word in [
            "cancel",
            "unsubscribe",
            "stop billing"
        ]
    ):

        intent = "cancellation"

    # ========================================================
    # FRUSTRATION DETECTION
    # ========================================================

    frustration_score = 5

    # Very high frustration
    if any(
        word in text
        for word in [
            "furious",
            "ridiculous",
            "unacceptable",
            "immediately",
            "now!",
            "manager",
            "worst",
            "terrible"
        ]
    ):

        frustration_score = 9

    # High frustration
    elif any(
        word in text
        for word in [
            "angry",
            "frustrated",
            "upset",
            "not happy",
            "annoyed"
        ]
    ):

        frustration_score = 7

    # Low frustration / polite
    elif any(
        word in text
        for word in [
            "please",
            "thank",
            "appreciate",
            "kindly"
        ]
    ):

        frustration_score = 3

    # ========================================================
    # FRUSTRATION LABEL
    # ========================================================

    if frustration_score <= 2:

        frustration_label = "calm"

    elif frustration_score <= 4:

        frustration_label = "concerned"

    elif frustration_score <= 6:

        frustration_label = "frustrated"

    elif frustration_score <= 8:

        frustration_label = "angry"

    else:

        frustration_label = "furious"

    # ========================================================
    # ESCALATION RISK
    # ========================================================

    escalation_risk = "low"

    if frustration_score >= 8:

        escalation_risk = "high"

    elif frustration_score >= 6:

        escalation_risk = "medium"

    # ========================================================
    # COACHING
    # ========================================================

    coaching = []

    if frustration_score >= 7:

        coaching.append(
            "Acknowledge the customer's frustration first."
        )

        coaching.append(
            "Offer a concrete next step and timeline."
        )

    if intent == "refund_request":

        coaching.append(
            "Confirm order details and explain "
            "the refund process clearly."
        )

    if escalation_risk == "high":

        coaching.append(
            "Consider offering escalation "
            "to a supervisor early."
        )

    # ========================================================
    # RETURN ANALYSIS
    # ========================================================

    return {

        "query": req.query,

        "intent": intent,

        # New terminology
        "frustration_score": frustration_score,

        "frustration_level": frustration_score,

        "frustration_label": frustration_label,

        # Compatibility with existing frontend/code
        "emotion_score": frustration_score,

        "emotion_label": frustration_label,

        "escalation_risk": escalation_risk,

        "coaching_guidance": coaching,

        "suggested_persona": (
            req.persona_hint
            or (
                "angry"
                if frustration_score >= 7
                else "frustrated"
            )
        ),

        "suggested_scenario": (
            req.scenario_hint
            or intent
        )
    }


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "api:app",
        host=API_HOST,
        port=API_PORT,
        reload=True
    )