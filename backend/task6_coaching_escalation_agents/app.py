import sys
from pathlib import Path
from typing import Dict, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
ENGINE_DIR = REPO_ROOT / "task4_task5_task6_support_assist_agents"
for candidate in (str(ENGINE_DIR), str(REPO_ROOT)):
    p = str(candidate)
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from analysis_core import detect_intent
from knowledge_bridge import knowledge_status, search_knowledge
from support_assist import CoachingResponseAgent, EscalationRiskMonitor

COACH = CoachingResponseAgent()
MONITOR = EscalationRiskMonitor()

class AssistRequest(BaseModel):
    query: Optional[str] = None
    text: Optional[str] = None
    session_id: Optional[str] = None
    threshold: Optional[int] = Field(default=None, ge=0, le=100)
    def resolved_text(self) -> str:
        v = self.query or self.text or ""
        return str(v).strip()

class EvaluateRequest(BaseModel):
    response: str = Field(min_length=1)
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    frustration_score: Optional[int] = Field(default=None, ge=1, le=10)

class ThresholdRequest(BaseModel):
    threshold: int = Field(ge=0, le=100)

app = FastAPI(title="Task 6 Coaching Escalation", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PAGE = "<html><body><h1>Task 6 Coaching Escalation</h1></body></html>"

@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def landing():
    return HTMLResponse(PAGE)

@app.get("/task6/health")
def task6_health() -> Dict:
    s = knowledge_status()
    return {"status": "ok", "service": "task6", "knowledge_available": s["available"]}


@app.get("/task6/escalation/threshold")
def get_thr() -> Dict:
    return {"threshold": MONITOR.get_threshold()}

@app.post("/task6/escalation/threshold")
def set_thr(req: ThresholdRequest) -> Dict:
    v = MONITOR.set_threshold(req.threshold)
    return {"status": "updated", "threshold": v}

@app.get("/task6/escalation/check")
def check_thr() -> Dict:
    return {"service": "task6", "threshold": MONITOR.get_threshold()}

@app.post("/task6/assist")
def assist(req: AssistRequest) -> Dict:
    text = req.resolved_text()
    if not text:
        raise HTTPException(status_code=422, detail="empty query")
    import hashlib
    sid = req.session_id or ("adhoc-" + hashlib.md5(text.lower()[:160].encode("utf-8")).hexdigest()[:12])
    risk = MONITOR.assess(sid, text, threshold_override=req.threshold)
    intent = risk.get("intent", detect_intent(text.lower()))
    emotion = risk.get("emotion", "")
    frust = risk.get("frustration", 5)
    sent = risk.get("sentiment", {"label": "neutral", "score": 0.0, "confidence": 0.4})
    know = search_knowledge(text, top_k=3, intent=intent)
    sugg = COACH.generate_suggestions(intent=intent, sentiment=sent["label"], emotion_label=emotion, frustration_score=frust, customer_message=text, knowledge_results=know)
    ev = COACH.evaluate_response(sugg["primary"], sentiment=sent["label"], frustration_score=frust)
    tips = COACH.generate_coaching_tips(intent=intent, sentiment=sent["label"], emotion_label=emotion, frustration_score=frust, escalation_level=risk["escalation_level"], evaluation=ev, knowledge_used=sugg["knowledge_used"])
    st = MONITOR.get_state(sid)
    return {"query": text, "session_id": req.session_id, "session_key": sid, "intent": intent, "emotion": emotion, "frustration_score": frust, "sentiment": sent["label"], "escalation_level": risk["escalation_level"], "escalation_score": risk["escalation_score"], "knowledge_results": know, "knowledge_available": knowledge_status()["available"], "suggested_response": sugg.get("primary", ""), "response_evaluation": ev, "coaching_tips": tips, "alert": risk["alert"], "recommended_actions": risk["recommended_actions"], "assessed_at": risk["assessed_at"], "state_alerts": st.get("alerts", [])}

@app.post("/task6/coaching/evaluate")
def coaching_evaluate(req: EvaluateRequest) -> Dict:
    r = COACH.evaluate_response(req.response, sentiment=req.sentiment or "neutral", frustration_score=req.frustration_score or 5)
    r["intent"] = req.intent
    return r
