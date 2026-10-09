# Task 4 / 5 / 6 — Support Assistance Agents

Self-contained module for the support-assistance deliverables:

| Task | Agent | Class / functions | Purpose |
| ---- | ----- | ----------------- | ------- |
| **4** | **Intent & Sentiment Analysis Agent** | `analysis_core.py` | Detects customer intent, emotion, frustration (0–10), sentiment (positive/neutral/negative), tracks the satisfaction trend and escalation risk over the conversation. |
| **5** | **Knowledge Recommendation Agent** | `knowledge_bridge.py` | Intent-aware retrieval of the most relevant support articles / FAQs / policies / troubleshooting steps from the RAG knowledge base, with a source reference for every result and a graceful "no relevant information" fallback. |
| **6** | **Coaching & Response Suggestion Agent** | `CoachingResponseAgent` (`support_assist.py`) | Generates context-aware suggested replies (intent + sentiment + history + knowledge base), evaluates them for tone / clarity / empathy / professionalism and returns actionable coaching tips. |
| **6** | **Escalation Risk Monitor Agent** | `EscalationRiskMonitor` (`support_assist.py`) | Recalculates an escalation-risk score (0–100) after every **customer** message, lists the indicators, explains the reasoning, maps the risk to Low / Medium / High / Critical and raises a configurable alert with recommended actions. |

Everything these features need lives in **this folder only** — the
customer simulator (`../task3_customer_simulator_agent`) contains no
support-assistance code; it just mounts the router that is defined here.

---

## Files

```
task4_task5_task6_support_assist_agents/
├── analysis_core.py         # Task 4 - Intent & Sentiment Analysis core
├── knowledge_bridge.py      # Task 5 - Knowledge Recommendation (RAG) bridge
├── support_assist.py        # Task 6 - Coaching + Escalation Risk agents
├── support_api.py           # FastAPI router + standalone app
├── run.py                   # Runs this API on its own (port 8100)
├── test_support_assist.py   # 55 pytest checks (agents + API pipeline)
├── conftest.py              # makes the flat imports work from any cwd
├── requirements.txt         # dependencies of this module
└── README.md
```

## Pipeline

```text
Customer message (latest CUSTOMER message only)
        ↓
Intent & Sentiment Analysis      analysis_core.py                  [Task 4]
        ↓
Knowledge Recommendation         knowledge_bridge.py → ../task1_task2_rag_knowledge_base FAISS  [Task 5]
        ↓
Coaching & Response Suggestion   support_assist.py (CoachingResponseAgent)        [Task 6]
        ↓
Escalation Risk Monitor          support_assist.py (EscalationRiskMonitor)        [Task 6]
        ↓
Combined payload → React Support Console (../support_console_frontend)
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

### How the risk score moves

`EscalationRiskMonitor` recomputes the score from the latest **customer**
message plus the customer-only conversation context on every reply
(`assess_non_customer_message()` ignores agent messages entirely). The
score therefore moves in **both directions** as the conversation
develops — it is never a ratchet that freezes at the highest value
reached so far:

* **Rise is immediate.** Any new escalation evidence in the customer's
  reply (negative wording, `still` / `again` / `when will`, a supervisor
  or manager demand, urgency, complaint language, a growing negative
  streak) raises the score in that same turn.
* **Repeat pressure grows with every raising of the same issue**
  (`18` → `24` → `26` → `28` → `30` for complaint wording, `6 / 9 / 12
  / …` capped at `20` for a repeat without complaint wording), so a long
  unresolved conversation never freezes on one value.
* **Release is proportional to the evidence in that reply.** When the
  fresh evidence is lighter than the running state, the score releases a
  share of the gap:
  | Tier | Evidence in the latest customer message | Released |
  | ---- | --------------------------------------- | -------- |
  | strong | resolution confirmed, or clearly positive and pressure-free | the whole gap (score = fresh evidence) |
  | calming | explicit calming language (“okay, I understand”, “thank you”, positive words) and no new pressure | 40–50 % of the gap |
  | milder | no calming words, but **no** unresolved / repeat / escalation / urgency wording either, while the customer was at a high emotional level | 30 % of the gap |
  | pressing | the reply still presses the same issue (`still`, `again`, `when will`, a manager demand, urgency) | nothing — the score is held |
* **A demand is not a confirmation.** “When will this be fixed?”, “I need
  this resolved” and “tell me how you will sort this out” contain a
  resolution keyword but are the *opposite* of a confirmation — the issue
  is still open and the customer is pressing for it. They are matched
  through `_DEMANDS_A_RESOLUTION_RE` and never release frustration or
  risk (`test_demand_for_a_resolution_is_not_a_resolution`).
* **Repeat pressure needs pressure in the current message.** The
  repeat-pressure indicator is gated on `latest_pressure` (markers in
  *this* reply), never on the conversation-level `unaddressed_pressure`.
  Otherwise it fired on every follow-up turn — because the same intent
  is always somewhere in the history — and the score could only ever
  climb, even after the customer had visibly calmed down
  (`test_neutral_repeat_does_not_inflate_risk`).
* **A furious customer on an open issue is never “Low”.** Very high
  frustration combined with a negative tone on an unresolved issue adds
  `high_frustration_open_issue` (+12), so an escalating conversation
  reaches the Medium/High bands and the configurable alert can fire even
  when the customer has not yet said “supervisor”
  (`test_furious_customer_on_open_issue_is_never_low_risk`).
* **The release never below the fresh evidence.** `score >= fresh_score`
  always, so a calmer reply can lower the risk but can never make the
  conversation look safer than the message itself justifies.
* **`escalation_trend`** reports any change above ±1 point as
  `increasing` / `decreasing`, so the UI direction always matches the
  numeric movement; the satisfaction trend is derived from the very same
  evidence (`increasing` → `declining`, `decreasing` → `improving`).
* The customer's emotion / frustration level is held while the wording is
  still negative, so the console never shows a calm customer together
  with an unresolved, negative complaint.

Examples measured live (`scripts/demo_escalation_risk_movement.py`):

```text
furious demand  → 58  High      first_message
mildly annoyed  → 49  Medium    decreasing
neutral info    → 37  Medium    decreasing
appreciative    →  0  Low       decreasing
resolved        →  0  Low       stable
furious again   → 79  Critical  increasing
```

## Running

**Option A — through the customer simulator backend (default, one port).**
`../task3_customer_simulator_agent/api.py` mounts this module's router, so
the whole app (simulator sessions + support assistance) is available on
port 8000:

```bash
cd task3_customer_simulator_agent
python -m uvicorn api:app --host 127.0.0.1 --port 8000
# Support Console UI : http://127.0.0.1:8000/
# API docs           : http://127.0.0.1:8000/docs
```

**Option B — this module on its own (no customer simulator).**

```bash
cd task4_task5_task6_support_assist_agents
python run.py
# API docs : http://127.0.0.1:8100/docs
```

Optional environment variables: `TASK6_API_HOST` (default `127.0.0.1`),
`TASK6_API_PORT` (default `8100`), `ESCALATION_ALERT_THRESHOLD`
(default `70`).

## Tests

```bash
cd task4_task5_task6_support_assist_agents
python -m pytest test_support_assist.py -v

# or from the repository root
python -m pytest task4_task5_task6_support_assist_agents -v
```

The suite covers the intent/emotion/sentiment analysis, the coaching
agent (suggestions, evaluation, tips), the escalation monitor (bands,
repeat complaints, streaks, threshold override, idempotency, state
snapshot, agent-reply no-op, risk moving in both directions) and the HTTP
pipeline.

## Notes

* The Knowledge Recommendation agent needs the RAG dependencies
  (`../task1_task2_rag_knowledge_base/requirements.txt`) and a built index
  (`python build_index.py` inside `../task1_task2_rag_knowledge_base`).
  When they are missing, `search_knowledge()` returns an empty list and
  the rest of the pipeline keeps working.
* Response suggestions only ever **offer** to check/confirm something —
  they never claim an action that has not happened.
* Escalation state is keyed by `session_id` (falling back to a digest of
  the first customer message), so it survives UI reloads.
