"""
FastAPI interface for the Customer Simulator Agent.

Provides:
- Health check
- Configuration options
- Session creation
- Customer response generation
- Session state retrieval
- Session logs
- Session listing
- Session deletion
- Manual customer-message analysis
- RAG knowledge retrieval
"""

from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pathlib import Path

from .config import (
    API_HOST,
    API_PORT,
    DEFAULT_PERSONA,
    DEFAULT_SCENARIO,
    DEFAULT_INITIAL_EMOTION,
    DEFAULT_ISSUE_SEVERITY,
    DEFAULT_PATIENCE_LEVEL,
    DEFAULT_EXPECTED_RESOLUTION,
)

from .personas import (
    list_personas,
)

from .scenarios import (
    list_scenarios,
)

from .simulator import CustomerSimulator

from rag.retriever import semantic_search


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="AI Customer Support Coaching Assistant",
    description=(
        "Backend API for customer support simulation, "
        "emotion analysis, coaching and RAG."
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SESSION STORAGE
# ============================================================

sessions: Dict[str, CustomerSimulator] = {}


# ============================================================
# REQUEST MODELS
# ============================================================


class StartSessionRequest(BaseModel):
    persona: str = DEFAULT_PERSONA

    scenario: str = DEFAULT_SCENARIO

    initial_emotion: Optional[str] = DEFAULT_INITIAL_EMOTION

    frustration_level: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    issue_severity: int = Field(
        default=DEFAULT_ISSUE_SEVERITY,
        ge=1,
        le=10,
    )

    patience_level: int = Field(
        default=DEFAULT_PATIENCE_LEVEL,
        ge=1,
        le=10,
    )

    expected_resolution: str = DEFAULT_EXPECTED_RESOLUTION

    use_llm: bool = False


class RespondRequest(BaseModel):
    session_id: str
    message: str


class ManualAnalyzeRequest(BaseModel):
    query: str

    persona_hint: Optional[str] = None

    scenario_hint: Optional[str] = None


# ============================================================
# HEALTH
# ============================================================


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "customer-simulator",
    }


# ============================================================
# CONFIGURATION OPTIONS
# ============================================================


@app.get("/config/options")
def config_options():

    return {
        "personas": list_personas(),
        "scenarios": list_scenarios(),
        "expected_resolutions": [
            "full_refund",
            "partial_refund",
            "replacement",
            "store_credit",
            "delivery_update",
            "technical_resolution",
            "account_recovery",
            "cancellation",
        ],
    }


# ============================================================
# START SESSION
# ============================================================


@app.post("/session/start")
def start_session(req: StartSessionRequest):

    try:

        simulator = CustomerSimulator(
            persona=req.persona,
            scenario=req.scenario,
            initial_emotion=req.initial_emotion,
            frustration_level=req.frustration_level,
            issue_severity=req.issue_severity,
            patience_level=req.patience_level,
            expected_resolution=req.expected_resolution,
            use_llm=req.use_llm,
        )

        result = simulator.start()

        session_id = result["session_id"]

        sessions[session_id] = simulator

        return result

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to start session: {exc}",
        )


# ============================================================
# RESPOND TO SESSION
# ============================================================


@app.post("/session/respond")
def respond_to_session(req: RespondRequest):

    simulator = sessions.get(req.session_id)

    if simulator is None:

        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    try:

        result = simulator.respond(req.message)

        return result

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to process response: {exc}",
        )


# ============================================================
# GET SESSION
# ============================================================


@app.get("/session/{session_id}")
def get_session(session_id: str):

    simulator = sessions.get(session_id)

    if simulator is None:

        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    try:

        return simulator.get_state()

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session: {exc}",
        )


# ============================================================
# GET SESSION LOG
# ============================================================


@app.get("/session/{session_id}/log")
def get_session_log(session_id: str):

    simulator = sessions.get(session_id)

    # If the session is still active, return its current log
    if simulator is not None:
        try:
            return simulator.get_state()
        except Exception:
            pass

    # If the session has ended, load the saved JSON log
    log_path = Path("customer_simulator") / "logs" / f"session_{session_id}.json"

    if log_path.exists():
        import json

        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise HTTPException(
        status_code=404,
        detail="Session not found",
    )

# ============================================================
# DELETE / END SESSION
# ============================================================


@app.delete("/session/{session_id}")
def end_session(session_id: str):
    simulator = sessions.get(session_id)

    if simulator is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    try:
        # Get the current state before removing the session
        state = simulator.get_state()

        # Finalize the saved conversation log
        simulator.logger.finalize(
            simulator.emotion_mgr.get_state().to_dict()
        )

        # Remove the active session from memory
        sessions.pop(session_id, None)

        return {
            "session_id": session_id,
            "status": "ended",
            "state": state,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to end session: {exc}",
        )


# ============================================================
# LIST SESSIONS
# ============================================================


@app.get("/sessions")
def list_sessions():

    results = []

    for session_id, simulator in sessions.items():

        try:

            state = simulator.get_state()

            results.append(state)

        except Exception:

            continue

    return {
        "sessions": results,
        "count": len(results),
    }


# ============================================================
# CUSTOMER MESSAGE ANALYSIS
# ============================================================


@app.post("/analyze")
def analyze_customer_message(
    req: ManualAnalyzeRequest,
):

    text = req.query.lower().strip()

    scenario_hint = (
        req.scenario_hint or ""
    ).lower().strip()

    persona_hint = (
        req.persona_hint or ""
    ).lower().strip()

    # ========================================================
    # 1. INTENT DETECTION
    # ========================================================

    intent = "general_inquiry"

    if any(
        phrase in text
        for phrase in [
            "refund",
            "money back",
            "return my money",
            "refund me",
        ]
    ):
        intent = "refund_request"

    elif any(
        phrase in text
        for phrase in [
            "cancel",
            "cancellation",
            "unsubscribe",
            "stop billing",
        ]
    ):
        intent = "cancellation"

    elif any(
        phrase in text
        for phrase in [
            "late",
            "delayed",
            "not arrived",
            "tracking",
            "delivery",
            "shipment",
            "where is my order",
            "still waiting",
            "hasn't arrived",
            "has not arrived",
            "delivery date",
        ]
    ):
        intent = "delayed_order"

    elif any(
        phrase in text
        for phrase in [
            "payment",
            "charged",
            "declined",
            "card",
            "transaction",
        ]
    ):
        intent = "payment_failure"

    elif any(
        phrase in text
        for phrase in [
            "login",
            "password",
            "locked",
            "account",
            "sign in",
        ]
    ):
        intent = "account_issue"

    elif any(
        phrase in text
        for phrase in [
            "return",
            "exchange",
            "replace",
            "replacement",
        ]
    ):
        intent = "return_exchange"

    elif any(
        phrase in text
        for phrase in [
            "complaint",
            "complain",
            "terrible service",
            "bad service",
        ]
    ):
        intent = "complaint"

    # ========================================================
    # 2. SCENARIO HINT CAN OVERRIDE GENERIC INTENT
    # ========================================================

    scenario_aliases = {
        "delayed order": "delayed_order",
        "delivery issue": "delayed_order",
        "delivery": "delayed_order",
        "refund": "refund_request",
        "refund request": "refund_request",
        "payment": "payment_failure",
        "payment issue": "payment_failure",
        "account": "account_issue",
        "account issue": "account_issue",
        "login": "account_issue",
        "return": "return_exchange",
        "exchange": "return_exchange",
        "cancellation": "cancellation",
        "cancel": "cancellation",
    }

    normalized_scenario = scenario_aliases.get(
        scenario_hint,
        scenario_hint.replace(" ", "_"),
    )

    if normalized_scenario in [
        "delayed_order",
        "refund_request",
        "payment_failure",
        "account_issue",
        "return_exchange",
        "cancellation",
    ]:
        intent = normalized_scenario

    # ========================================================
    # 3. EMOTION + FRUSTRATION
    # ========================================================

    # Start from neutral/mild concern.
    emotion_score = 5

    severe_negative_phrases = [
        "furious",
        "ridiculous",
        "unacceptable",
        "immediately",
        "manager",
        "escalating",
        "escalate",
        "worst",
        "horrible",
        "terrible",
        "this is ridiculous",
        "this is unacceptable",
        "fed up",
        "sick of",
        "waste of time",
        "lawsuit",
        "legal action",
        "enough is enough",
    ]

    frustrated_phrases = [
        "angry",
        "frustrated",
        "upset",
        "annoyed",
        "not happy",
        "disappointed",
        "already explained",
        "explained the problem",
        "already told you",
        "keep waiting",
        "still waiting",
        "what is going on",
        "what's going on",
        "give me a clear answer",
        "clear next step",
        "need a clear answer",
        "need an answer",
        "no update",
        "still no update",
        "no response",
        "why is this taking",
        "how long",
        "timeline",
        "when will",
        "when can",
        "taking too long",
        "taking so long",
        "please fix this",
    ]

    worried_phrases = [
        "confused",
        "don't understand",
        "do not understand",
        "not sure",
        "unclear",
        "worried",
        "concerned",
        "concern",
    ]

    positive_phrases = [
        "thank you",
        "thanks",
        "appreciate it",
        "appreciate your help",
        "great help",
        "problem solved",
        "that works",
        "perfect",
        "excellent",
        "resolved",
    ]

    # IMPORTANT:
    # Negative phrases are checked before positive/polite words.
    #
    # "Please give me a clear answer" is NOT positive.
    # "Please fix this" is NOT positive.
    #
    # Politeness must not override frustration.

    if any(
        phrase in text
        for phrase in severe_negative_phrases
    ):

        emotion_score = 9

    elif any(
        phrase in text
        for phrase in frustrated_phrases
    ):

        emotion_score = 7

    elif any(
        phrase in text
        for phrase in worried_phrases
    ):

        emotion_score = 6

    elif any(
        phrase in text
        for phrase in positive_phrases
    ):

        emotion_score = 3

    # ========================================================
    # 4. SCENARIO-AWARE EMOTION
    # ========================================================

    if normalized_scenario == "delayed_order":

        delayed_order_phrases = [
            "where is my order",
            "still waiting",
            "not arrived",
            "late",
            "delayed",
            "no update",
            "timeline",
            "when will",
            "already explained",
            "clear next step",
            "tracking",
            "delivery",
        ]

        if any(
            phrase in text
            for phrase in delayed_order_phrases
        ):

            emotion_score = max(
                emotion_score,
                7,
            )

    # Explicit persona hint provides additional context.
    if persona_hint in [
        "frustrated",
        "angry",
    ]:

        emotion_score = max(
            emotion_score,
            7,
        )

    # ========================================================
    # 5. EMOTION LABEL
    # ========================================================

    if emotion_score >= 9:

        emotion_label = "angry"

    elif emotion_score >= 7:

        emotion_label = "frustrated"

    elif emotion_score == 6:

        emotion_label = "worried"

    elif emotion_score <= 3:

        emotion_label = "happy"

    else:

        emotion_label = "neutral"

    # ========================================================
    # 6. SENTIMENT
    # ========================================================

    if emotion_score >= 6:

        sentiment = "Negative"

    elif emotion_score <= 3:

        sentiment = "Positive"

    else:

        sentiment = "Neutral"

    # ========================================================
    # 7. FRUSTRATION LEVEL
    # ========================================================

    frustration_level = emotion_score

    # ========================================================
    # 8. ESCALATION RISK
    # ========================================================

    escalation_risk = "low"

    if emotion_score >= 8:

        escalation_risk = "high"

    elif emotion_score >= 6:

        escalation_risk = "medium"

    if any(
        phrase in text
        for phrase in [
            "manager",
            "escalating",
            "escalate",
            "supervisor",
            "legal action",
            "lawsuit",
        ]
    ):

        escalation_risk = "high"

    # ========================================================
    # 9. SATISFACTION TREND
    # ========================================================

    if emotion_score >= 7:

        satisfaction_trend = "Declining"

    elif emotion_score <= 3:

        satisfaction_trend = "Improving"

    else:

        satisfaction_trend = "Stable"

    # ========================================================
    # 10. CONFIDENCE
    # ========================================================

    confidence = 0.85

    if intent == "general_inquiry":

        confidence = 0.65

    if scenario_hint:

        confidence = max(
            confidence,
            0.85,
        )

    if escalation_risk == "high":

        confidence = max(
            confidence,
            0.90,
        )

    # ========================================================
    # 11. COACHING GUIDANCE
    # ========================================================

    coaching = []

    if emotion_score >= 7:

        coaching.append(
            "Acknowledge the customer's frustration first."
        )

        coaching.append(
            "Offer a concrete next step and timeline."
        )

    elif emotion_score >= 5:

        coaching.append(
            "Acknowledge the customer's concern."
        )

        coaching.append(
            "Provide a clear next step."
        )

    else:

        coaching.append(
            "Maintain a friendly and helpful tone."
        )

    if intent == "refund_request":

        coaching.append(
            "Confirm order details and state the refund policy clearly."
        )

    if intent == "delayed_order":

        coaching.append(
            "Check the latest tracking information and provide a realistic delivery update."
        )

    if intent == "payment_failure":

        coaching.append(
            "Verify the payment status and explain the next resolution step."
        )

    if intent == "account_issue":

        coaching.append(
            "Verify the account issue and guide the customer through the recovery steps."
        )

    if intent == "return_exchange":

        coaching.append(
            "Confirm the return or exchange eligibility and explain the required steps."
        )

    if intent == "cancellation":

        coaching.append(
            "Confirm cancellation, stop future billing, and explain any applicable refund policy."
        )

    if escalation_risk == "high":

        coaching.append(
            "Consider offering escalation to a supervisor early."
        )

    # ========================================================
    # 12. RAG WITH SCENARIO CONTEXT
    # ========================================================

    scenario_context = {

        "delayed_order": (
            "delayed order delivery shipment tracking "
            "late package missing delivery promised date "
            "carrier in transit"
        ),

        "refund_request": (
            "refund money back refund processing "
            "refund policy damaged product return"
        ),

        "payment_failure": (
            "payment failed card declined transaction "
            "billing payment error subscription"
        ),

        "account_issue": (
            "login password account locked sign in "
            "account recovery subscription account"
        ),

        "return_exchange": (
            "return exchange replacement returned product "
            "damaged product return window"
        ),

        "cancellation": (
            "cancel cancellation subscription billing "
            "unsubscribe stop future charges"
        ),

        "complaint": (
            "complaint bad service poor service "
            "customer complaint service issue"
        ),
    }

    context = scenario_context.get(
        intent,
        intent.replace("_", " "),
    )

    rag_query = (
        f"{context} {req.query}"
    ).strip()

    try:

        rag_results = semantic_search(
            rag_query,
            top_k=3,
        )

    except FileNotFoundError:

        rag_results = []

    except Exception:

        rag_results = []

    # ========================================================
    # 13. SUGGESTED PERSONA
    # ========================================================

    if req.persona_hint:

        suggested_persona = req.persona_hint

    elif emotion_score >= 9:

        suggested_persona = "angry"

    elif emotion_score >= 7:

        suggested_persona = "frustrated"

    elif emotion_score >= 6:

        suggested_persona = "confused"

    else:

        suggested_persona = "polite"

    # ========================================================
    # 14. FINAL RESPONSE
    # ========================================================

    return {

        "query": req.query,

        "intent": intent,

        "emotion": emotion_label,

        "emotion_label": emotion_label,

        "sentiment": sentiment,

        "emotion_score": emotion_score,

        "frustration_level": frustration_level,

        "satisfaction_trend": satisfaction_trend,

        "escalation_risk": escalation_risk,

        "confidence": confidence,

        "coaching_guidance": coaching,

        "suggested_persona": suggested_persona,

        "suggested_scenario": (
            req.scenario_hint
            or intent
        ),

        "knowledge_results": rag_results,
    }


# ============================================================
# UI / SERVICE ROUTES
# ============================================================


@app.get("/")
def root():

    return {
        "service": "AI Customer Support Coaching Assistant",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/ui")
def ui_root():

    return {
        "service": "AI Customer Support Coaching Assistant",
        "status": "running",
        "message": "Frontend is served separately by Vite.",
    }


@app.get("/ui/")
def ui_slash():

    return {
        "service": "AI Customer Support Coaching Assistant",
        "status": "running",
        "message": "Frontend is served separately by Vite.",
    }


# ============================================================
# MAIN
# ============================================================


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "customer_simulator.api:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
    )