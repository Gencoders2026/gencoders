"""
FastAPI server for Customer Simulator.
"""

import os
import json
import hashlib
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

# Task 6: Coaching, Response Suggestion & Escalation Risk Monitoring
from analysis_core import detect_intent, detect_emotion, detect_sentiment
from knowledge_bridge import knowledge_status, search_knowledge
from support_assist import (
    CoachingResponseAgent,
    EscalationRiskMonitor,
    clamp_score,
    risk_level_for_score,
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
# TASK 6 - SUPPORT ASSISTANCE AGENTS (singletons)
# ==========================================================
# Coaching & Response Suggestion Agent
COACHING_AGENT = CoachingResponseAgent()

# Escalation Risk Monitor Agent (configurable alert threshold)
ESCALATION_MONITOR = EscalationRiskMonitor()

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


class HistoryMessage(BaseModel):
    """One previous conversation message."""
    role: str = "customer"
    content: str = ""


class SupportAssistRequest(BaseModel):
    """
    Full support-assistance pipeline request (Task 6).

    Runs: Intent & Sentiment Analysis -> Knowledge Recommendation ->
    Coaching & Response Suggestion -> Escalation Risk Monitor.
    """
    query: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    persona_hint: Optional[str] = None
    scenario_hint: Optional[str] = None
    history: Optional[List[HistoryMessage]] = None
    threshold: Optional[int] = Field(default=None, ge=0, le=100)
    turn: Optional[int] = None
    # Who wrote `query`: "customer" (default) or "agent".
    # The escalation monitor ONLY ingests customer messages.
    sender: Optional[str] = "customer"


class EvaluateResponseRequest(BaseModel):
    """Evaluate an agent's drafted response for soft skills."""
    response: str = Field(..., min_length=1)
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    frustration_score: Optional[int] = Field(default=None, ge=1, le=10)


class ThresholdRequest(BaseModel):
    """Configure the high-escalation alert threshold."""
    threshold: int = Field(..., ge=0, le=100)


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
# MANUAL ANALYSIS – FULLY FIXED
# ==========================================================
@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    text = req.query
    text_lower = text.lower()

    # ------------------------------------------------------
    # INTENT & SENTIMENT ANALYSIS AGENT (shared core, Task 6)
    # ------------------------------------------------------
    intent = detect_intent(text_lower)
    emotion, score = detect_emotion(text_lower)
    sentiment = detect_sentiment(text_lower)

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
    # KNOWLEDGE RECOMMENDATION AGENT (Task 6 integration)
    # ------------------------------------------------------
    knowledge_results = search_knowledge(text, top_k=3)

    # ------------------------------------------------------
    # COACHING & RESPONSE SUGGESTION AGENT (Task 6)
    # ------------------------------------------------------
    suggestions = COACHING_AGENT.generate_suggestions(
        intent=intent,
        sentiment=sentiment["label"],
        emotion_label=emotion,
        frustration_score=score,
        customer_message=text,
        knowledge_results=knowledge_results,
    )
    response_evaluation = COACHING_AGENT.evaluate_response(
        suggestions["primary"],
        sentiment=sentiment["label"],
        frustration_score=score,
    )
    coaching_tips = COACHING_AGENT.generate_coaching_tips(
        intent=intent,
        sentiment=sentiment["label"],
        emotion_label=emotion,
        frustration_score=score,
        escalation_level=risk,
        evaluation=response_evaluation,
        knowledge_used=suggestions["knowledge_used"],
    )

    # ------------------------------------------------------
    # ESCALATION RISK (stateless mapping for this endpoint)
    # ------------------------------------------------------
    escalation_score = clamp_score(score * 10)

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

        # Sentiment (Task 6)
        "sentiment": sentiment["label"],
        "sentiment_score": sentiment["score"],
        "confidence": sentiment["confidence"],
        "satisfaction_trend": "unknown",

        # Risk
        "escalation_risk": risk,
        "escalation_score": escalation_score,
        "escalation_level": risk_level_for_score(escalation_score),

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

        # Task 6 additions
        "coaching_tips": coaching_tips,
        "knowledge_results": knowledge_results,
        "knowledge_available": knowledge_status()["available"],
        "suggested_response": suggestions["primary"],
        "suggested_responses": suggestions,
        "response_evaluation": response_evaluation,

        # Extra
        "intent": intent,
        "suggested_persona": req.persona_hint or ("angry" if score >= 7 else "frustrated"),
        "suggested_scenario": req.scenario_hint or intent,
        "query": req.query
    }


# ==========================================================
# TASK 6 - SUPPORT ASSISTANCE PIPELINE
# ==========================================================
def _session_key(session_id: Optional[str], query: str) -> str:
    """Stable per-session key; falls back to a query digest."""
    if session_id:
        return session_id
    digest = hashlib.md5(
        query.lower()[:160].encode("utf-8")
    ).hexdigest()[:12]
    return f"adhoc-{digest}"


SATISFACTION_TREND_MAP = {
    "increasing": "declining",
    "decreasing": "improving",
    "stable": "steady",
    "first_message": "unknown",
}


@app.post("/support/analyze")
def support_analyze(req: SupportAssistRequest):
    """
    Full integrated support-assistance pipeline (Task 6):

        1. Intent & Sentiment Analysis Agent
        2. Knowledge Recommendation Agent (RAG)
        3. Coaching & Response Suggestion Agent
        4. Escalation Risk Monitor Agent (session-aware,
           recalculated after every customer message)
    """
    text = req.query.strip()
    text_lower = text.lower()
    query_sender = (req.sender or "customer").strip().lower()

    # ------------------------------------------------------
    # 1. INTENT & SENTIMENT ANALYSIS AGENT
    #    ALWAYS runs on the latest CUSTOMER message only.
    #    Agent/support replies are NEVER analysed as customer
    #    state: they would otherwise overwrite the customer's
    #    emotion / frustration / risk with agent politeness
    #    ("sorry", "thank you", ...).
    # ------------------------------------------------------
    history = [m.model_dump() for m in (req.history or [])]
    session_key = _session_key(req.session_id, text)

    if query_sender != "customer":
        # No-op pass-through: the monitor's last customer result is
        # returned unchanged so agent text can never move the
        # customer's risk or emotion state.
        risk, intent, emotion, frustration, sentiment = (
            ESCALATION_MONITOR.assess_non_customer_message(
                session_key, text, turn=req.turn,
            )
        )
        return _build_support_assist_response(
            req=req, text=text, intent=intent, emotion=emotion,
            frustration=frustration, sentiment=sentiment,
            knowledge_results=[], suggestions={
                "primary": "", "alternates": [],
                "followup_question": "",
                "knowledge_used": [],
                "basis": {"skipped": "agent message"},
            },
            response_evaluation=None, tips=[],
            risk=risk,
            monitor_state=ESCALATION_MONITOR.get_state(session_key),
            session_key=session_key, history=history,
        )

    intent = detect_intent(text_lower)
    emotion, frustration = detect_emotion(text_lower)
    sentiment = detect_sentiment(text_lower)

    # ------------------------------------------------------
    # 2. KNOWLEDGE RECOMMENDATION AGENT (RAG)
    # ------------------------------------------------------
    knowledge_results = search_knowledge(text, top_k=3)

    # ------------------------------------------------------
    # 4. ESCALATION RISK MONITOR AGENT
    #    (stateful - updated after every CUSTOMER message)
    # ------------------------------------------------------
    risk = ESCALATION_MONITOR.assess(
        session_key,
        text,
        intent=intent,
        sentiment=sentiment,
        emotion_label=emotion,
        frustration_score=frustration,
        turn=req.turn,
        threshold_override=req.threshold,
        customer_history=history,
    )

    # ------------------------------------------------------
    # 3. COACHING & RESPONSE SUGGESTION AGENT
    # ------------------------------------------------------
    suggestions = COACHING_AGENT.generate_suggestions(
        intent=intent,
        sentiment=sentiment["label"],
        emotion_label=emotion,
        frustration_score=frustration,
        customer_message=text,
        knowledge_results=knowledge_results,
        history=history,
    )

    response_evaluation = COACHING_AGENT.evaluate_response(
        suggestions["primary"],
        sentiment=sentiment["label"],
        frustration_score=frustration,
    )

    coaching_tips = COACHING_AGENT.generate_coaching_tips(
        intent=intent,
        sentiment=sentiment["label"],
        emotion_label=emotion,
        frustration_score=frustration,
        escalation_level=risk["escalation_level"],
        evaluation=response_evaluation,
        knowledge_used=suggestions["knowledge_used"],
    )

    monitor_state = ESCALATION_MONITOR.get_state(session_key)

    return _build_support_assist_response(
        req=req, text=text, intent=intent, emotion=emotion,
        frustration=frustration, sentiment=sentiment,
        knowledge_results=knowledge_results, suggestions=suggestions,
        response_evaluation=response_evaluation, tips=coaching_tips,
        risk=risk, monitor_state=monitor_state,
        session_key=session_key, history=history,
    )


def _build_support_assist_response(
    *,
    req, text, intent, emotion, frustration, sentiment,
    knowledge_results, suggestions, response_evaluation, tips,
    risk, monitor_state, session_key, history,
) -> Dict:
    """Assemble the combined Task 6 support-assistance payload."""
    escalation_level = risk["escalation_level"]

    return {
        # ---- Meta ----
        "session_id": req.session_id,
        "session_key": session_key,
        "turn": risk["turn"],
        "message_count": risk["message_count"],
        "query": text,
        # The message this analysis belongs to (used by the UI to
        # avoid displaying stale analyses).
        "customer_message": risk.get("customer_message", text),
        "analyzed_customer_message": risk.get(
            "analyzed_customer_message", True
        ),
        "history_turns": len(history),

        # ---- Intent & Sentiment Analysis Agent ----
        # ALWAYS the latest CUSTOMER message analysis.
        "intent": intent,
        "emotion": emotion,
        "emotion_label": emotion,
        "overall_emotion": emotion,
        "customer_emotion": emotion,
        "frustration_level": frustration,
        "frustration_score": frustration,
        "sentiment": sentiment["label"],
        "sentiment_score": sentiment["score"],
        "confidence": sentiment["confidence"],
        "satisfaction_trend": SATISFACTION_TREND_MAP.get(
            risk["trend"], "unknown"
        ),

        # ---- Escalation Risk Monitor Agent ----
        "escalation_risk": escalation_level,
        "escalation_level": escalation_level,
        "escalation_score": risk["escalation_score"],
        "risk_score": risk["risk_score"],
        "escalation_trend": risk["trend"],
        "escalation_indicators": risk["indicators"],
        "escalation_reasoning": risk["reasoning"],
        "negative_streak": risk["negative_streak"],
        "alert_threshold": risk["alert"]["threshold"],
        "alert": risk["alert"],
        "alerts_raised": monitor_state.get("alerts", []),
        "recommended_actions": risk["recommended_actions"],
        "assessed_at": risk["assessed_at"],

        # ---- Knowledge Recommendation Agent ----
        "knowledge_results": knowledge_results,
        "knowledge_available": knowledge_status()["available"],

        # ---- Coaching & Response Suggestion Agent ----
        "suggested_response": suggestions.get("primary", "") if isinstance(suggestions, dict) else "",
        "suggested_responses": suggestions,
        "response_evaluation": response_evaluation,
        "coaching_tips": tips,
        "coaching_guidance": tips,
        "recommendations": tips,
        "suggested_persona": req.persona_hint or (
            "angry" if frustration >= 7 else "frustrated"
        ),
        "suggested_scenario": req.scenario_hint or intent,
    }


# ==========================================================
# TASK 6 - COACHING RESPONSE EVALUATION
# ==========================================================
@app.post("/coaching/evaluate")
def coaching_evaluate(req: EvaluateResponseRequest):
    """
    Evaluate a drafted agent response for tone, clarity, empathy
    and professionalism (0-100 scores with notes).
    """
    result = COACHING_AGENT.evaluate_response(
        req.response,
        sentiment=req.sentiment or "neutral",
        frustration_score=req.frustration_score or 5,
    )
    result["intent"] = req.intent
    return result


# ==========================================================
# TASK 6 - ESCALATION ALERT THRESHOLD (configurable)
# ==========================================================
@app.get("/escalation/threshold")
def get_escalation_threshold():
    return {
        "threshold": ESCALATION_MONITOR.get_threshold(),
        "bands": {
            "Low": "0-24",
            "Medium": "25-49",
            "High": "50-74",
            "Critical": "75-100",
        },
    }


@app.post("/escalation/threshold")
def set_escalation_threshold(req: ThresholdRequest):
    value = ESCALATION_MONITOR.set_threshold(req.threshold)
    return {
        "status": "updated",
        "threshold": value,
    }


# ==========================================================
# TASK 6 - ESCALATION MONITOR STATE
# ==========================================================
@app.get("/escalation/{session_id}")
def escalation_state(session_id: str):
    """Full escalation-monitor state snapshot for a session."""
    state = ESCALATION_MONITOR.get_state(session_id)
    if not state.get("message_count"):
        raise HTTPException(
            status_code=404,
            detail="No escalation state found for this session."
        )
    return state


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