"""
Task 5 - Knowledge Recommendation Agent (standalone HTTP API).
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
ENGINE_DIR = REPO_ROOT / "task4_task5_task6_support_assist_agents"

for candidate in (str(ENGINE_DIR), str(REPO_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from analysis_core import detect_intent
from knowledge_bridge import knowledge_status, search_knowledge


class KnowledgeRequest(BaseModel):
    query: Optional[str] = None
    text: Optional[str] = None
    intent: Optional[str] = None
    top_k: int = Field(default=3, ge=1, le=10)

    def resolved_text(self) -> str:
        return str(self.query or self.text or "").strip()


class KnowledgeResult(BaseModel):
    text: str
    score: float
    metadata: Dict


class KnowledgeResponse(BaseModel):
    query: str
    intent: str
    available: bool
    source: Optional[str] = None
    error: Optional[str] = None
    results: List[KnowledgeResult]
    message: str

_LANDING_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Task 5 - Knowledge Recommendation Agent</title>
    <style>
      body { margin:0; font-family: system-ui, sans-serif;
             background:#f5f7fb; color:#111827; }
      .wrap { max-width: 760px; margin: 0 auto; padding: 60px 24px; }
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
      <h1>Task 5 - Knowledge Recommendation Agent</h1>
      <p class="sub">
        Intent-aware retrieval from the support knowledge base. The engine is
        the existing <code>knowledge_bridge.py</code>; this page is only a
        thin launcher for the standalone Task 5 service.
      </p>
      <div class="card">
        <strong>Try the agent</strong>
        <ul>
          <li><code>POST /task5/recommend</code> with <code>{"query": "your customer text"}</code></li>
          <li><code>GET /task5/status</code> - retriever availability and source</li>
        </ul>
        <a class="btn" href="/docs">API documentation</a>
        <a class="btn secondary" href="/task5/status">Knowledge status</a>
      </div>
      <div class="card">
        <strong>Full console (all tasks together)</strong>
        <a class="btn" href="http://127.0.0.1:8000/">Support Console (port 8000)</a>
        <a class="btn secondary" href="http://localhost:5173/">React dev server (port 5173)</a>
        <a class="btn secondary" href="http://localhost:5173/task6">Task 6 screen</a>
      </div>
    </div>
  </body>
</html>
"""


app = FastAPI(
    title="Task 5 - Knowledge Recommendation Agent",
    description=(
        "Standalone Task 5 service. "
        "POST /task5/recommend retrieves relevant knowledge chunks with "
        "the existing knowledge_bridge engine."
    ),
    version="1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def landing() -> HTMLResponse:
    return HTMLResponse(_LANDING_PAGE)


@app.get("/task5/health")
def health() -> Dict:
    status = knowledge_status()
    return {
        "status": "ok",
        "service": "task5-knowledge-recommendation",
        "knowledge_available": status["available"],
    }


@app.get("/task5/status")
def status() -> Dict:
    return knowledge_status()


@app.post("/task5/recommend", response_model=KnowledgeResponse)
def recommend(req: KnowledgeRequest) -> KnowledgeResponse:
    text = req.resolved_text()
    if not text:
        raise HTTPException(
            status_code=422,
            detail="One of 'query' or 'text' must be provided and non-empty.",
        )

    intent = (req.intent or "").strip() or detect_intent(text.lower())
    status = knowledge_status()
    results = search_knowledge(text, top_k=req.top_k, intent=intent)

    if not status["available"]:
        message = (
            "Knowledge retrieval is unavailable in this environment; "
            "no relevant information was found."
        )
    elif not results:
        message = "No relevant information was found for this query."
    else:
        message = (
            f"Found {len(results)} relevant knowledge result(s) for intent "
            f"'{intent}'."
        )

    return KnowledgeResponse(
        query=text,
        intent=intent,
        available=status["available"],
        source=status.get("source"),
        error=status.get("error"),
        results=[
            KnowledgeResult(
                text=item.get("text", ""),
                score=float(item.get("score", 0.0)),
                metadata=dict(item.get("metadata", {})),
            )
            for item in results
        ],
        message=message,
    )

