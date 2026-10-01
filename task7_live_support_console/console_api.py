"""
Task 7 - Live Support Console API.

Exposes the HTTP surface used by the React console at ``/task7``:

    GET    /task7/health                 service + engine health
    POST   /task7/analyze                one customer message through the
                                         full Task 4/5/6 pipeline
                                         (intent, sentiment, frustration,
                                          escalation risk, coaching,
                                          knowledge recommendations)
    POST   /task7/transcript/parse       upload .txt/.csv/.json transcript
    GET    /task7/sessions               recorded conversations
    POST   /task7/sessions               record a conversation
    GET    /task7/sessions/{id}          one recorded conversation
    DELETE /task7/sessions/{id}          delete a recorded conversation
    GET    /task7/simulator-sessions     Task 3 conversations (read-only,
                                         used as replay sources)

The router is mounted by the Customer Simulator backend
(``task3_customer_simulator_agent/api.py``) so the console talks to a
single origin, and can also be served standalone by ``run.py`` on
http://127.0.0.1:8107.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Reuse the EXISTING Task 4/5/6 engines - nothing is re-implemented here.
# ---------------------------------------------------------------------------
_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent
_ENGINE_DIR = _REPO_ROOT / "task4_task5_task6_support_assist_agents"

for _candidate in (str(_MODULE_DIR), str(_ENGINE_DIR)):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from knowledge_bridge import knowledge_status, search_knowledge  # noqa: E402
from support_assist import (  # noqa: E402
    CoachingResponseAgent,
    EscalationRiskMonitor,
)

import session_store  # noqa: E402
import transcript_parser  # noqa: E402

COACHING_AGENT = CoachingResponseAgent()
ESCALATION_MONITOR = EscalationRiskMonitor()

router = APIRouter(tags=["task7-live-support-console"])

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB is plenty for a transcript


# ==========================================================
# REQUEST MODELS
# ==========================================================
class ConsoleMessage(BaseModel):
    role: str = "customer"
    content: str = ""
    timestamp: Optional[str] = None
    turn: Optional[int] = None


class AnalyzeMessageRequest(BaseModel):
    """One customer message to analyse for the live console."""

    query: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    turn: Optional[int] = None
    history: Optional[List[ConsoleMessage]] = None
    threshold: Optional[int] = Field(default=None, ge=0, le=100)


class KnowledgeSearch(BaseModel):
    turn: Optional[int] = None
    query: str = ""
    results: int = 0
    sources: List[str] = []


class RecordSessionRequest(BaseModel):
    """A conversation handled in the console."""

    id: Optional[str] = None
    mode: str = "manual"
    title: Optional[str] = None
    persona: Optional[str] = None
    scenario: Optional[str] = None
    source_file: Optional[str] = None
    is_demo: bool = False
    tags: List[str] = []
    messages: List[ConsoleMessage] = []
    knowledge_searches: List[KnowledgeSearch] = []
    meta: Dict = {}


# ==========================================================
# HEALTH
# ==========================================================
@router.get("/task7/health")
def health() -> Dict:
    status = knowledge_status()
    return {
        "status": "ok",
        "service": "task7-live-support-console",
        "knowledge_available": status.get("available", False),
        "recorded_sessions": session_store.count_sessions(),
        "simulator_sessions_available": len(
            session_store.list_simulator_conversations(limit=200)
        ),
    }


# ==========================================================
# LIVE ANALYSIS (Manual + Replay mode, after every exchange)
# ==========================================================
def _history_payload(history) -> List[Dict]:
    return [
        {"role": message.role, "content": message.content}
        for message in (history or [])
        if (message.content or "").strip()
    ]


@router.post("/task7/analyze")
def analyze_message(req: AnalyzeMessageRequest) -> Dict:
    """
    Analyse the latest CUSTOMER message with the existing Task 4/5/6
    pipeline and return everything the three panels of the console need:

      * Panel 1 - intent, emotion, sentiment, frustration level
      * Panel 2 - suggested response, coaching tips, response
                  evaluation, escalation risk + recommended actions
      * Panel 3 - knowledge recommendations with source/page metadata
    """
    text = (req.query or "").strip()

    if not text:
        raise HTTPException(status_code=422, detail="The message is empty.")

    history = _history_payload(req.history)
    session_key = req.session_id or f"task7-{abs(hash(text)) % 10**10}"

    # ---- 1. Intent & Sentiment + 2. Escalation Risk (single source) ----
    risk = ESCALATION_MONITOR.assess(
        session_key,
        text,
        turn=req.turn,
        threshold_override=req.threshold,
        customer_history=history,
    )

    intent = risk["intent"]
    emotion = risk["emotion_label"]
    frustration = risk["frustration"]
    sentiment = risk["sentiment"]

    # ---- 3. Knowledge Recommendation Agent (RAG) ----
    knowledge_results = search_knowledge(text, top_k=3, intent=intent)

    # ---- 4. Coaching & Response Suggestion Agent ----
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

    return {
        # ---- meta ----
        "session_id": req.session_id,
        "session_key": session_key,
        "turn": risk["turn"],
        "message_count": risk["message_count"],
        "query": text,
        "customer_message": risk.get("customer_message", text),
        "history_turns": len(history),
        # ---- Panel 1: customer state ----
        "intent": intent,
        "emotion": emotion,
        "emotion_label": emotion,
        "frustration_level": frustration,
        "frustration_score": frustration,
        "sentiment": sentiment["label"],
        "sentiment_score": sentiment["score"],
        "confidence": sentiment["confidence"],
        "satisfaction_trend": risk.get("satisfaction_trend", "unknown"),
        "state_drivers": risk.get("state_drivers", []),
        "negative_streak": risk["negative_streak"],
        # ---- Panel 2: escalation risk + coaching ----
        "escalation_risk": risk["escalation_level"],
        "escalation_level": risk["escalation_level"],
        "escalation_score": risk["escalation_score"],
        "escalation_trend": risk["trend"],
        "escalation_indicators": risk["indicators"],
        "escalation_reasoning": risk["reasoning"],
        "alert_threshold": risk["alert"]["threshold"],
        "alert": risk["alert"],
        "recommended_actions": risk["recommended_actions"],
        "resolution_status": risk.get("resolution_status", "unknown"),
        "de_escalation": risk.get("de_escalation", "none"),
        "suggested_response": suggestions.get("primary", ""),
        "suggested_responses": suggestions,
        "response_evaluation": response_evaluation,
        "coaching_tips": coaching_tips,
        "coaching_guidance": coaching_tips,
        # ---- Panel 3: knowledge recommendations ----
        "knowledge_results": knowledge_results,
        "knowledge_available": knowledge_status().get("available", False),
        "assessed_at": risk.get("assessed_at"),
    }



# ==========================================================
# REPLAY MODE - TRANSCRIPT UPLOAD (.txt / .csv / .json)
# ==========================================================
@router.post("/task7/transcript/parse")
async def parse_transcript(file: UploadFile = File(...)) -> Dict:
    """
    Parse an uploaded conversation transcript for Replay Mode.

    Returns the separated customer/agent messages in chronological order
    plus any parse warnings, so the console can replay them one by one.
    """
    filename = file.filename or "transcript"

    if not filename.lower().endswith((".txt", ".csv", ".json")):
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type. Upload a .txt, .csv or .json "
                "conversation transcript."
            ),
        )

    try:
        raw = await file.read()
    except Exception as exc:  # pragma: no cover - upload failure
        raise HTTPException(
            status_code=400, detail=f"Could not read the uploaded file: {exc}"
        ) from exc

    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="The transcript is larger than 2 MB. Please upload a "
                   "shorter conversation.",
        )

    try:
        return transcript_parser.parse_transcript(filename, raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ==========================================================
# RECORDED CONVERSATIONS (conversation state persistence)
# ==========================================================
@router.get("/task7/sessions")
def list_recorded_sessions(
    include_demo: bool = Query(default=True),
    include_messages: bool = Query(default=False),
    limit: Optional[int] = Query(default=None, ge=1, le=500),
) -> Dict:
    sessions = session_store.list_sessions(
        include_messages=include_messages,
        include_demo=include_demo,
        limit=limit,
    )
    return {"count": len(sessions), "sessions": sessions}


@router.post("/task7/sessions")
def create_recorded_session(req: RecordSessionRequest) -> Dict:
    if len(req.messages) < 2:
        raise HTTPException(
            status_code=422,
            detail="A conversation needs at least two messages to be recorded.",
        )

    record = {
        "id": req.id,
        "mode": req.mode,
        "title": req.title or f"{req.mode.title()} support conversation",
        "persona": req.persona,
        "scenario": req.scenario,
        "source_file": req.source_file,
        "is_demo": req.is_demo,
        "tags": req.tags,
        "messages": [message.model_dump() for message in req.messages],
        "knowledge_searches": [
            search.model_dump() for search in req.knowledge_searches
        ],
        "meta": req.meta,
    }

    stored = session_store.record_session(record)

    return {"status": "recorded", "session": stored}



@router.get("/task7/sessions/{session_id}")
def get_recorded_session(session_id: str) -> Dict:
    session = session_store.get_session(session_id, include_messages=True)
    if not session:
        raise HTTPException(
            status_code=404, detail=f"No recorded conversation '{session_id}'."
        )
    return session


@router.delete("/task7/sessions/{session_id}")
def delete_recorded_session(session_id: str) -> Dict:
    removed = session_store.delete_session(session_id)
    if not removed:
        raise HTTPException(
            status_code=404, detail=f"No recorded conversation '{session_id}'."
        )
    return {"status": "deleted", "session_id": session_id}


# ==========================================================
# TASK 3 SIMULATOR CONVERSATIONS (read-only replay sources)
# ==========================================================
@router.get("/task7/simulator-sessions")
def list_simulator_sessions(
    limit: int = Query(default=25, ge=1, le=200),
) -> Dict:
    """Conversations produced by the existing Task 3 simulator."""
    sessions = session_store.list_simulator_conversations(limit=limit)
    return {
        "count": len(sessions),
        "sessions": [
            {
                "id": item["id"],
                "title": item["title"],
                "scenario": item.get("scenario"),
                "persona": item.get("persona"),
                "created_at": item.get("created_at"),
                "message_count": len(item.get("messages") or []),
            }
            for item in sessions
        ],
    }


@router.get("/task7/simulator-sessions/{session_id}")
def get_simulator_session(session_id: str) -> Dict:
    clean_id = str(session_id).replace("sim-", "", 1)
    conversation = session_store.get_simulator_conversation(clean_id)
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"No simulator conversation '{session_id}'.",
        )
    return conversation


# ==========================================================
# STANDALONE APPLICATION (run.py, port 8107)
# ==========================================================
_LANDING_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Task 7 - Live Support Console API</title>
    <style>
      body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
             background:#f5f7fb; color:#111827; }
      .wrap { max-width: 780px; margin: 0 auto; padding: 60px 24px; }
      h1 { margin:0 0 6px; color:#2563eb; }
      .sub { color:#6b7280; margin:0 0 28px; }
      .card { background:#fff; border:1px solid #e5e7eb; border-radius:14px;
              padding:22px; margin-bottom:18px; }
      a.btn { display:inline-block; margin:6px 10px 0 0; padding:10px 16px;
              border-radius:8px; background:#2563eb; color:#fff;
              text-decoration:none; font-size:14px; }
      a.btn.secondary { background:#fff; color:#2563eb; border:1px solid #2563eb; }
      code { background:#f3f4f6; padding:2px 6px; border-radius:6px; font-size:13px; }
      ul { margin:8px 0 0; padding-left:20px; color:#374151; }
      li { margin-bottom:6px; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>Task 7 - Live Support Console</h1>
      <p class="sub">
        Three-panel support console with Manual Mode and Replay Mode.
        This service is running in <strong>standalone API mode</strong>.
      </p>
      <div class="card">
        <strong>Endpoints on this service</strong>
        <ul>
          <li><code>POST /task7/analyze</code> - analyse one customer message</li>
          <li><code>POST /task7/transcript/parse</code> - upload .txt/.csv/.json</li>
          <li><code>GET/POST /task7/sessions</code> - recorded conversations</li>
          <li><code>GET /task7/simulator-sessions</code> - Task 3 conversations</li>
        </ul>
        <a class="btn" href="/docs">API documentation</a>
        <a class="btn secondary" href="/task7/health">Health check</a>
      </div>
      <div class="card">
        <strong>Open the Live Support Console UI</strong>
        <p>Start the main backend, which serves the React application:</p>
        <p><code>cd task3_customer_simulator_agent &amp;&amp; python -m uvicorn api:app --host 127.0.0.1 --port 8000</code></p>
        <a class="btn" href="http://127.0.0.1:8000/task7">Task 7 - Live Support Console</a>
        <a class="btn secondary" href="http://localhost:5173/task7">React dev server</a>
      </div>
    </div>
  </body>
</html>
"""


def create_app():
    """Standalone Task 7 application (used by run.py)."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse

    application = FastAPI(
        title="Task 7 - Live Support Console",
        description=(
            "Manual Mode, Replay Mode, message-by-message analysis, "
            "real-time coaching and knowledge recommendations."
        ),
        version="1.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    application.get("/", include_in_schema=False, response_class=HTMLResponse)(
        lambda: HTMLResponse(_LANDING_PAGE)
    )
    return application

