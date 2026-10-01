"""
Task 8 - Insights & Performance Analytics API.

Exposes the post-interaction summary and the performance-analytics
dashboard:

    GET  /task8/health                service health + data availability
    GET  /task8/conversations         conversations available to analyse
    POST /task8/summary               post-interaction report for ONE
                                      conversation (recorded, simulator,
                                      or an inline conversation)
    GET  /task8/analytics             multi-session performance analytics
    POST /task8/demo-data             (re)load the labelled demo sessions

Mounted by the Customer Simulator backend so the React dashboard talks to
the same origin as Tasks 1-7, and runnable standalone via ``run.py`` on
http://127.0.0.1:8108.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent

for _candidate in (
    str(_MODULE_DIR),
    str(_REPO_ROOT / "task7_live_support_console"),
    str(_REPO_ROOT / "task4_task5_task6_support_assist_agents"),
    str(_REPO_ROOT),
):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import analytics_agent  # noqa: E402
import conversation_analysis  # noqa: E402
import demo_sessions  # noqa: E402
import session_store  # noqa: E402
import summary_agent  # noqa: E402

router = APIRouter(tags=["task8-insights-analytics"])


# ==========================================================
# REQUEST MODELS
# ==========================================================
class ConversationMessage(BaseModel):
    role: str = "customer"
    content: str = ""
    timestamp: Optional[str] = None


class SummaryRequest(BaseModel):
    """Which conversation to summarise.

    Exactly one source should be provided:
      * ``conversation_id``   - a conversation recorded by Task 7,
      * ``simulator_session_id`` - a Task 3 simulator conversation,
      * ``messages``          - an inline conversation.
    """

    conversation_id: Optional[str] = None
    simulator_session_id: Optional[str] = None
    messages: Optional[List[ConversationMessage]] = None
    meta: Dict = {}


# ==========================================================
# HEALTH
# ==========================================================
@router.get("/task8/health")
def health() -> Dict:
    recorded = session_store.list_sessions(
        include_messages=False, include_demo=False
    )
    simulator = session_store.list_simulator_conversations(limit=200)
    return {
        "status": "ok",
        "service": "task8-insights-analytics",
        "recorded_conversations": len(recorded),
        "simulator_conversations_available": len(simulator),
        "demo_conversations_available": len(demo_sessions.demo_conversations()),
    }


# ==========================================================
# AVAILABLE CONVERSATIONS (summary picker)
# ==========================================================
@router.get("/task8/conversations")
def list_conversations(
    limit: int = Query(default=25, ge=1, le=200),
    include_demo: bool = Query(default=True),
) -> Dict:
    """Every conversation Task 8 can analyse, newest first.

    Real (recorded + labelled demo) conversations are listed before the
    Task 3 simulator logs so the picker always shows them, no matter how
    many simulator sessions exist.
    """
    recorded_items: List[Dict] = []

    for record in session_store.list_sessions(
        include_messages=False, include_demo=include_demo
    ):
        recorded_items.append({
            "id": record["id"],
            "source": "recorded",
            "title": record["title"],
            "mode": record["mode"],
            "created_at": record["created_at"],
            "messages": record["message_count"],
            "scenario": record.get("scenario"),
            "is_demo": record["is_demo"],
        })

    simulator_items: List[Dict] = []
    for conversation in session_store.list_simulator_conversations(limit=limit):
        simulator_items.append({
            "id": conversation["id"],
            "source": "simulator",
            "title": conversation["title"],
            "mode": "simulator",
            "created_at": conversation.get("created_at"),
            "messages": len(conversation.get("messages") or []),
            "scenario": conversation.get("scenario"),
            "is_demo": False,
        })

    recorded_items.sort(
        key=lambda item: item.get("created_at") or "", reverse=True
    )
    simulator_items.sort(
        key=lambda item: item.get("created_at") or "", reverse=True
    )

    items = recorded_items + simulator_items

    return {"count": len(items), "conversations": items[:limit]}


# ==========================================================
# POST-INTERACTION SUMMARY
# ==========================================================
def _resolve_conversation(req: SummaryRequest):
    """Find the conversation to summarise and its metadata."""
    if req.conversation_id:
        record = session_store.get_session(
            req.conversation_id, include_messages=True
        )
        if not record:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No conversation '{req.conversation_id}' was found. "
                    "Record one in the Task 7 Live Support Console first."
                ),
            )
        messages = record.get("messages") or []
        meta = {
            "id": record.get("id"),
            "title": record.get("title"),
            "mode": record.get("mode"),
            "persona": record.get("persona"),
            "scenario": record.get("scenario"),
            "created_at": record.get("created_at"),
            "completed_at": record.get("completed_at"),
            "is_demo": record.get("is_demo"),
            **(req.meta or {}),
        }
        return messages, meta

    if req.simulator_session_id:
        session_id = str(req.simulator_session_id).replace("sim-", "", 1)
        conversation = session_store.get_simulator_conversation(session_id)
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No Task 3 simulator conversation '{req.simulator_session_id}' "
                    "was found."
                ),
            )
        meta = {
            "id": conversation.get("id"),
            "title": conversation.get("title"),
            "mode": conversation.get("mode"),
            "persona": conversation.get("persona"),
            "scenario": conversation.get("scenario"),
            "created_at": conversation.get("created_at"),
            **(req.meta or {}),
        }
        return conversation.get("messages") or [], meta

    if req.messages:
        return (
            [message.model_dump() for message in req.messages],
            {"mode": "inline", **(req.meta or {})},
        )

    raise HTTPException(
        status_code=422,
        detail=(
            "Provide 'conversation_id', 'simulator_session_id' or 'messages' "
            "to generate a post-interaction summary."
        ),
    )


@router.post("/task8/summary")
def post_interaction_summary(req: SummaryRequest) -> Dict:
    """Generate the structured post-interaction report."""
    messages, meta = _resolve_conversation(req)

    try:
        return summary_agent.build_report(
            messages,
            meta=meta,
            session_key=f"task8-summary-{meta.get('id') or 'inline'}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ==========================================================
# PERFORMANCE ANALYTICS
# ==========================================================
@router.get("/task8/analytics")
def performance_analytics(
    limit: int = Query(default=25, ge=1, le=200),
    simulator_limit: int = Query(default=20, ge=0, le=200),
    include_demo: bool = Query(default=True),
) -> Dict:
    """Multi-session performance analytics for the dashboard."""
    return analytics_agent.build_analytics(
        limit=limit,
        include_demo=include_demo,
        simulator_limit=simulator_limit,
    )


@router.post("/task8/demo-data")
def load_demo_data() -> Dict:
    """(Re)load the clearly-labelled realistic demo conversations."""
    written = demo_sessions.seed_demo_conversations(session_store)
    return {
        "status": "loaded",
        "written": written,
        "note": (
            "Demo conversations are stored with is_demo = True and are always "
            "reported separately from real sessions."
        ),
    }


# ==========================================================
# SINGLE-CONVERSATION ANALYSIS (used by the summary screen)
# ==========================================================
@router.get("/task8/conversations/{conversation_id}/analysis")
def conversation_analysis_endpoint(conversation_id: str) -> Dict:
    record = session_store.get_session(conversation_id, include_messages=True)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No conversation '{conversation_id}' was found.",
        )
    return conversation_analysis.analyse_conversation(
        record.get("messages") or [],
        session_key=f"task8-analysis-{conversation_id}",
    )



# ==========================================================
# STANDALONE APPLICATION (run.py, port 8108)
# ==========================================================
_LANDING_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Task 8 - Insights &amp; Performance Analytics API</title>
    <style>
      body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
             background:#f5f7fb; color:#111827; }
      .wrap { max-width: 800px; margin: 0 auto; padding: 60px 24px; }
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
      <h1>Task 8 - Insights &amp; Performance Analytics</h1>
      <p class="sub">
        Post-Interaction Summary Agent and the multi-session Performance
        Analytics module. This service is running in
        <strong>standalone API mode</strong>.
      </p>
      <div class="card">
        <strong>Endpoints on this service</strong>
        <ul>
          <li><code>POST /task8/summary</code> - post-interaction report</li>
          <li><code>GET /task8/analytics</code> - performance analytics</li>
          <li><code>GET /task8/conversations</code> - analysable sessions</li>
          <li><code>POST /task8/demo-data</code> - load labelled demo data</li>
        </ul>
        <a class="btn" href="/docs">API documentation</a>
        <a class="btn secondary" href="/task8/health">Health check</a>
      </div>
      <div class="card">
        <strong>Open the Task 8 dashboard</strong>
        <p>Start the main backend, which serves the React application:</p>
        <p><code>cd task3_customer_simulator_agent &amp;&amp; python -m uvicorn api:app --host 127.0.0.1 --port 8000</code></p>
        <a class="btn" href="http://127.0.0.1:8000/task8/summary">Post-Interaction Summary</a>
        <a class="btn secondary" href="http://127.0.0.1:8000/task8/analytics">Performance Analytics</a>
      </div>
    </div>
  </body>
</html>
"""


def create_app():
    """Standalone Task 8 application (used by run.py)."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse

    application = FastAPI(
        title="Task 8 - Insights & Performance Analytics",
        description=(
            "Post-Interaction Summary Agent and the multi-session "
            "Performance Analytics module."
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

