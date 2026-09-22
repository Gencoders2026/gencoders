# Task 6 — Support Assistance Agents

Self-contained module for the Task 6 deliverables:

| Agent | Class / functions | Purpose |
| ----- | ----------------- | ------- |
| **Coaching & Response Suggestion Agent** | `CoachingResponseAgent` (`support_assist.py`) | Generates context-aware suggested replies (intent + sentiment + history + knowledge base), evaluates them for tone / clarity / empathy / professionalism and returns actionable coaching tips. |
| **Escalation Risk Monitor Agent** | `EscalationRiskMonitor` (`support_assist.py`) | Recalculates an escalation-risk score (0–100) after every **customer** message, lists the indicators, explains the reasoning, maps the risk to Low / Medium / High / Critical and raises a configurable alert with recommended actions. |
| **Intent & Sentiment Analysis core** | `analysis_core.py` | Shared intent / emotion / sentiment analysis used by the pipeline and by `/analyze`. |
| **Knowledge Recommendation bridge** | `knowledge_bridge.py` | Lazy, failure-tolerant bridge to the FAISS RAG retriever in `../rag`. |

Everything the Task 6 feature needs lives in **this folder only** — the
customer simulator (`../customer_simulator`) contains no Task 6 code
anymore; it just mounts the router that is defined here.

---

## Files

```
task6_support_assist/
├── analysis_core.py         # Intent & Sentiment Analysis core
├── knowledge_bridge.py      # Knowledge Recommendation (RAG) bridge
├── support_assist.py        # Coaching & Escalation Risk agents
├── support_api.py           # FastAPI router + standalone app
├── run.py                   # Runs the Task 6 API on its own (port 8100)
├── test_support_assist.py   # 37 pytest checks (agents + API pipeline)
├── conftest.py              # makes the flat imports work from any cwd
├── requirements.txt         # dependencies of this module
└── README.md
```

## Pipeline

```text
Customer message (latest CUSTOMER message only)
        ↓
Intent & Sentiment Analysis      analysis_core.py
        ↓
Knowledge Recommendation         knowledge_bridge.py → ../rag FAISS
        ↓
Coaching & Response Suggestion   support_assist.py (CoachingResponseAgent)
        ↓
Escalation Risk Monitor          support_assist.py (EscalationRiskMonitor)
        ↓
Combined payload → React Support Console
```

Agent/support replies are **never** analysed as customer state: they are
answered by `EscalationRiskMonitor.assess_non_customer_message()`, a pure
no-op that returns the previous customer assessment unchanged.

## Endpoints

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/support/analyze` | Full integrated pipeline (session-aware) |
| POST | `/coaching/evaluate` | Evaluate a drafted reply (tone/clarity/empathy/professionalism) |
| GET | `/escalation/threshold` | Current alert threshold + risk bands |
| POST | `/escalation/threshold` | Update the alert threshold (0–100) |
| GET | `/escalation/{session_id}` | Escalation-monitor state snapshot |
| POST | `/analyze` | Intent & sentiment analysis (+ Task 6 extras) |
| GET | `/support/health` | Service health (incl. knowledge-agent status) |

Risk levels: **Low** 0–24 · **Medium** 25–49 · **High** 50–74 ·
**Critical** 75–100. Alert threshold defaults to **70**
(`ESCALATION_ALERT_THRESHOLD`) and can be changed at runtime from the
Support Console or via `POST /escalation/threshold`.

Frustration bands returned by the analysis (kept in sync with the
escalation thresholds and the UI labels): Furious 9–10 · Angry 7–8 ·
Frustrated 5–6 · Calm 3.

## Running

**Option A — through the customer simulator backend (default, one port).**
`../customer_simulator/api.py` mounts this module's router, so the whole
app (simulator sessions + Task 6) is available on port 8000:

```bash
cd customer_simulator
python -m uvicorn api:app --host 127.0.0.1 --port 8000
# Support Console UI : http://localhost:5173
# API docs           : http://127.0.0.1:8000/docs
```

**Option B — Task 6 on its own (no customer simulator).**

```bash
cd task6_support_assist
python run.py
# Task 6 API docs : http://127.0.0.1:8100/docs
```

Optional environment variables: `TASK6_API_HOST` (default `127.0.0.1`),
`TASK6_API_PORT` (default `8100`), `ESCALATION_ALERT_THRESHOLD`
(default `70`).

## Tests

```bash
cd task6_support_assist
python -m pytest test_support_assist.py -v

# or from the repository root
python -m pytest task6_support_assist -v
```

The suite covers the intent/emotion/sentiment analysis, the coaching
agent (suggestions, evaluation, tips), the escalation monitor (bands,
repeat complaints, streaks, threshold override, idempotency, state
snapshot, agent-reply no-op) and the HTTP pipeline.

## Notes

* The Knowledge Recommendation agent needs the RAG dependencies
  (`../rag/requirements.txt`) and a built index (`python build_index.py`
  inside `../rag`). When they are missing, `search_knowledge()` returns an
  empty list and the rest of the pipeline keeps working.
* Response suggestions only ever **offer** to check/confirm something —
  they never claim an action that has not happened.
* Escalation state is keyed by `session_id` (falling back to a digest of
  the first customer message), so it survives frontend reloads.
