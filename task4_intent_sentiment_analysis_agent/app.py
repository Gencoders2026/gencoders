"""
Task 4 - Intent & Sentiment Analysis Agent (standalone HTTP API).
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

from analysis_core import detect_emotion, detect_intent, detect_sentiment


class AnalyzeRequest(BaseModel):
    """Customer text to analyse. Any of these field names is accepted."""

    query: Optional[str] = None
    transcript: Optional[str] = None
    conversation: Optional[str] = None
    text: Optional[str] = None

    def resolved_text(self) -> str:
        return str(
            self.query or self.transcript or self.conversation or self.text or ""
        ).strip()


class AnalyzeResponse(BaseModel):
    query: str
    intent: str
    emotion: str
    frustration_score: int = Field(ge=0, le=10)
    sentiment: str
    sentiment_score: float
    confidence: float
    escalation_risk: str
    analysis_steps: List[str]


def _risk_from_frustration(score: int) -> str:
    if score >= 8:
        return "High"
    if score >= 6:
        return "Medium"
    return "Low"


_LANDING_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Task 4 - Intent &amp; Sentiment Analysis Agent</title>
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
      <h1>Task 4 - Intent &amp; Sentiment Analysis Agent</h1>
      <p class="sub">
        Detects customer intent, emotion/frustration (0-10) and sentiment.
        The engine is the existing <code>analysis_core.py</code>; this page is
        only a thin launcher for the standalone Task 4 service.
      </p>
      <div class="card">
        <strong>Try the agent</strong>
        <ul>
          <li><code>POST /task4/analyze</code> with <code>{"query": "your customer text"}</code></li>
        </ul>
        <a class="btn" href="/docs">API documentation</a>
        <a class="btn secondary" href="/task4/health">Health check</a>
      </div>
      <div class="card">
        <strong>Full console (all tasks together)</strong>
        <ul>
          <li>Support Console (port 8000): configuration, conversation, AI Analysis, escalation monitor</li>
          <li>React dev server (port 5173): same console during development</li>
          <li>Task 6 screen (port 5173): live escalation risk scoring</li>
        </ul>
        <a class="btn" href="http://127.0.0.1:8000/">Support Console (port 8000)</a>
        <a class="btn secondary" href="http://localhost:5173/">React dev server (port 5173)</a>
        <a class="btn secondary" href="http://localhost:5173/task6">Task 6 screen</a>
      </div>
    </div>
  </body>
</html>
"""


app = FastAPI(
    title="Task 4 - Intent & Sentiment Analysis Agent",
    description=(
        "Standalone Task 4 service. "
        "POST /task4/analyze analyses customer text with the existing "
        "analysis_core engine."
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


@app.get("/task4/health")
def health() -> Dict:
    return {"status": "ok", "service": "task4-intent-sentiment-analysis"}


@app.post("/task4/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    text = req.resolved_text()
    if not text:
        raise HTTPException(
            status_code=422,
            detail="One of 'query', 'transcript', 'conversation' or 'text' must be provided and non-empty.",
        )

    text_lower = text.lower()
    intent = detect_intent(text_lower)
    emotion, frustration = detect_emotion(text_lower)
    sentiment = detect_sentiment(text_lower)

    return AnalyzeResponse(
        query=text,
        intent=intent,
        emotion=emotion,
        frustration_score=int(frustration),
        sentiment=sentiment["label"],
        sentiment_score=float(sentiment["score"]),
        confidence=float(sentiment["confidence"]),
        escalation_risk=_risk_from_frustration(int(frustration)),
        analysis_steps=[
            "detect customer intent",
            "detect customer emotion and frustration (0-10)",
            "detect sentiment (positive / neutral / negative)",
            "map frustration to a Low / Medium / High escalation risk",
        ],
    )
