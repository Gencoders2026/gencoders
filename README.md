# AI Customer Support Assistant — Task 1 → Task 6

An end-to-end **AI customer-support assistant**. Each deliverable of the
assignment lives in its own clearly-named folder, and the whole system runs
as one pipeline:

```text
Support documents ──► RAG knowledge base ──► semantic search
        (Task 1 & 2)              │
                                  ▼
Customer Simulator Agent ──► Intent & Sentiment Analysis Agent
        (Task 3)                      (Task 4)
                                          │
                                          ▼
                        Knowledge Recommendation Agent  (Task 5)
                                          │
                                          ▼
        Coaching & Response Suggestion  +  Escalation Risk Monitor
                                  (Task 6)
                                          │
                                          ▼
                   Live Support Console  (React web UI)
```

---

## 1. Repository layout (task → folder)

| Task | Folder | What is inside |
| ---- | ------ | -------------- |
| **1 & 2** | **`task1_task2_rag_knowledge_base/`** | Knowledge-base ingestion, text cleaning, chunking, embeddings, FAISS vector store, semantic search, and the Streamlit RAG assistant. |
| **3** | **`task3_customer_simulator_agent/`** | Configurable customer personas, support scenarios, emotion/patience state, turn-by-turn simulated customer replies, session logging and the FastAPI backend. |
| **4** | **`task4_task5_task6_support_assist_agents/analysis_core.py`** | Intent & Sentiment Analysis Agent: intent, emotion, frustration (0–10), sentiment, satisfaction trend, escalation risk. |
| **5** | **`task4_task5_task6_support_assist_agents/knowledge_bridge.py`** | Knowledge Recommendation Agent: intent-aware retrieval of articles / FAQs / policies / troubleshooting steps with source + page references. |
| **6** | **`task4_task5_task6_support_assist_agents/support_assist.py`** | Coaching & Response Suggestion Agent and Escalation Risk Monitor Agent (score, indicators, reasoning, risk bands, configurable alert). |
| **all** | **`support_console_frontend/`** | React + Vite web UI: conversation, AI analysis, knowledge used, suggested response, coaching tips and the Escalation Risk Monitor. |
| — | `scripts/` | Verification / demo scripts (endpoints, risk movement, console simulation). |
| — | `archive/` | Historical copies that are **not** part of the running app (`reference_copy_before_merge/`, `legacy_static_ui_prototype/`). |

```
gencoders/
├── task1_task2_rag_knowledge_base/          # Task 1 & 2 - RAG knowledge base
│   ├── data/knowledge_base/                 #   sample support documents
│   │   ├── policies/                        #   Refund / Cancellation / Privacy (PDF)
│   │   └── troubleshooting/                 #   login / payment / application issues (TXT)
│   ├── app.py            build_index.py      #   Streamlit UI / index builder
│   ├── document_loader.py  text_cleaner.py   #   extraction + cleaning
│   ├── chunker.py  embeddings.py             #   chunking + embeddings
│   ├── vector_store.py  retriever.py  llm.py #   FAISS store / search / LLM
│   └── vector_db/                           #   built FAISS index
├── task3_customer_simulator_agent/          # Task 3 - Customer Simulator Agent
│   ├── api.py                               #   FastAPI: sessions + mounts Task 4/5/6 router
│   ├── simulator.py  personas.py  scenarios.py  emotion_manager.py
│   ├── logger.py  config.py  verify_live.py
│   └── logs/                                #   saved conversations (JSON)
├── task4_task5_task6_support_assist_agents/ # Task 4 + 5 + 6 - the agents
│   ├── analysis_core.py  knowledge_bridge.py  support_assist.py
│   ├── support_api.py  run.py  test_support_assist.py
├── support_console_frontend/                # React Support Console (all tasks)
│   └── src/pages/SupportConsole.jsx         #   conversation + analysis + monitor
└── scripts/                                 # verification & demo scripts
```

---

## 2. Quick start (3 terminals) and browser links

```bash
# T1 - RAG knowledge base  (Task 1 & 2)          -> http://localhost:8501
cd task1_task2_rag_knowledge_base
pip install -r requirements.txt
python build_index.py          # only needed if vector_db/ is missing
streamlit run app.py --server.port 8501

# T2 - backend: simulator + support-assistance   -> http://127.0.0.1:8000
cd task3_customer_simulator_agent
python -m uvicorn api:app --host 127.0.0.1 --port 8000

# T3 - React Support Console                     -> http://localhost:5173
cd support_console_frontend
npm install
npm run dev
```

| What | Browser link |
| ---- | ------------ |
| **Task 3 + 4 + 5 + 6 - Live Support Console** (single UI for everything) | **http://127.0.0.1:8000/** (built UI served by the backend) |
| Same UI from the Vite dev server (hot reload) | http://localhost:5173/ |
| **Task 1 & 2 - RAG Knowledge Base assistant** (Streamlit) | http://localhost:8501/ |
| Task 3 - Customer Simulator API docs / try-it-out | http://127.0.0.1:8000/docs |
| Task 4 & 5 & 6 - support-assistance API (standalone, optional) | http://127.0.0.1:8100/docs (start with `cd task4_task5_task6_support_assist_agents && python run.py`) |
| Task 4 - Intent & Sentiment analysis endpoint | http://127.0.0.1:8000/docs#/default/analyze_analyze_post |
| Task 5 - Knowledge agent status | http://127.0.0.1:8000/support/health |
| Task 6 - Escalation monitor state for a session | http://127.0.0.1:8000/escalation/{session_id} |

> The backend serves the **built** React app at `/`, so http://127.0.0.1:8000/
> works without the dev server. Rebuild it after UI changes with
> `cd support_console_frontend && npm run build`.

---

## 3. Task 1 & 2 — Support Knowledge Base Ingestion & RAG Pipeline

`task1_task2_rag_knowledge_base/`

```text
Documents → loading → cleaning → chunking (500 / 100 overlap)
          → embeddings (all-MiniLM-L6-v2) → FAISS vector store
          → semantic search → relevant context → LLM answer
```

* **Upload / ingest** FAQ, support and policy documents — PDF and TXT
  (`data/knowledge_base/policies/*.pdf`, `.../troubleshooting/*.txt`).
  Drop more files in those folders and re-run `python build_index.py`.
* **Extract & clean** the text per document (`document_loader.py`,
  `text_cleaner.py`).
* **Chunk** it into meaningful, overlapping pieces (`chunker.py`).
* **Embed** every chunk and **store** it in FAISS (`embeddings.py`,
  `vector_store.py`).
* **Semantic search** for the most relevant chunks (`retriever.py`) and
  answer with the LLM (`llm.py`, Groq `openai/gpt-oss-20b`).
* **Document- and page-level metadata** is kept with every chunk, so each
  result always shows its `source` (file name) and `page` — this is what
  the Task 5 recommendations display.

Sample support documents/PDFs are the ones committed under
`task1_task2_rag_knowledge_base/data/knowledge_base/`.

## 4. Task 3 — Customer Simulator Agent

`task3_customer_simulator_agent/`

* **Configurable personas**: calm, polite, concerned, frustrated, angry,
  furious (`personas.py`).
* **Scenarios**: refund request, delayed order, payment failure, account
  / login issue, cancellation (`scenarios.py`).
* **Turn-by-turn generation** with conversation context and **emotional
  progression** — the customer's emotion rises or falls with the agent's
  replies (`simulator.py`, `emotion_manager.py`).
* **Configurable parameters**: persona, scenario, initial emotion
  (frustration level), issue severity, patience level, expected
  resolution.
* **API**: `POST /session/start`, `POST /session/{id}/respond`,
  `GET /session/{id}`, `DELETE /session/{id}`, `GET /sessions`
  (see http://127.0.0.1:8000/docs).
* **Conversation logging**: every session is written to
  `task3_customer_simulator_agent/logs/session_<id>.json`.


## 5. Task 4 — Intent & Sentiment Analysis Agent

`task4_task5_task6_support_assist_agents/analysis_core.py`
(exposed by `POST /analyze` and inside `POST /support/analyze`)

For **every customer message** it returns structured information:

```json
{
  "intent": "refund_status",
  "emotion": "Frustrated",
  "frustration_level": 8,
  "sentiment": "negative",
  "satisfaction_trend": "declining",
  "escalation_risk": "high",
  "confidence": 0.94
}
```

* **Intent** — refund request / status, cancellation, delivery issue,
  payment issue, account issue, complaint, return & exchange, general
  inquiry (keyword + phrase evidence).
* **Emotion** — Calm, Neutral, Concerned, Frustrated, Angry, Furious.
* **Frustration level** — 0–10, built from the customer's language,
  repeated complaints, unresolved issues and tone drift.
* **Sentiment** — Positive / Neutral / Negative with a polarity score and
  a dynamic confidence value.
* **Satisfaction trend** — Improving / Declining / Stable, derived from
  the conversation history (never from the turn number).
* **Conversation context** — the analysis always uses previous customer
  messages, and agent/support replies can never overwrite the customer's
  state.
* **Escalation risk** — Low / Medium / High (Critical) with the reasons.

## 6. Task 5 — Knowledge Recommendation Agent

`task4_task5_task6_support_assist_agents/knowledge_bridge.py`

* Connected to the RAG knowledge base built in Task 1 & 2 (FAISS +
  `all-MiniLM-L6-v2` embeddings).
* Analyses the customer's **current message together with the
  conversation context** and the detected intent.
* Retrieves support articles, FAQs, troubleshooting steps and policies,
  and **ranks** them by relevance.
* Returns the **top 3–5 recommendations**, each with its **source
  reference** (`source` file name + `page` when available).
* Content-level filtering guarantees that unrelated policies are never
  quoted (e.g. a delayed-order conversation never gets a payment policy).
* When nothing relevant exists it degrades gracefully: an empty result
  list + `knowledge_available: false`, and the rest of the pipeline keeps
  working.


## 7. Task 6 — Coaching, Response Suggestion & Escalation Risk Monitoring

`task4_task5_task6_support_assist_agents/support_assist.py`

### 7.1 Coaching & Response Suggestion Agent
* **Context-aware suggestions**: uses intent, customer sentiment, conversation history and knowledge-base search results.
* **Suggested replies never fabricate actions** — they offer to verify, look up status, or guide through next steps.
* **Response evaluation** across four key dimensions:
  * **Tone** (0–100)
  * **Clarity** (0–100)
  * **Empathy** (0–100)
  * **Professionalism** (0–100)
  * Overall score + `meets_standard` flag (threshold 70).
* **Actionable communication tips**: guides the support agent on de-escalation, next steps, and policy grounding.
* **"Check my draft"** feature in the Support Console: agents can evaluate their own typed responses before sending.

### 7.2 Escalation Risk Monitor Agent
* **Continuous re-assessment**: calculates an escalation-risk score (0–100) after **every customer message**.
* **Key indicators detected**:
  * Repeated complaints (compounding repeat-pressure curve)
  * Elevated / extreme customer frustration (6–10)
  * Consecutive negative sentiment streaks
  * Unresolved issues (`still`, `again`, `no help`, `nothing happened`)
  * Urgency pressure (`immediately`, `asap`, `right now`)
  * Explicit supervisor / manager demands (+35 points)
  * Legal or bank dispute threats (+20 points)
  * Public reputation / social media threats (+15 points)
* **Risk classification bands**:
  * **Low**: 0–24 · **Medium**: 25–49 · **High**: 50–74 · **Critical**: 75–100
* **Detailed reasoning**: lists every driver and point breakdown explaining why the score was assigned.
* **Configurable threshold & alerts**: default alert threshold is **70** (configurable via API or live in the console); triggers an alert banner with recommended actions.
* **Role contract**: agent replies route through a no-op path (`assess_non_customer_message`) and **never** lower customer frustration or risk on their own.

### 7.3 Responsive Escalation Dynamics (Both Directions)
The monitor recalculates the score on every turn so it actively responds to the customer's replies:
* **Immediate rise** when new escalation signals, complaints, or negative wording appear.
* **Proportional easing** when customer replies become calmer:
  * Confirmed resolution (`resolved`, `fixed`, `all good`) → full release to 0.
  * Strong calming / appreciation language (`thank you`, `I understand`) → releases 40–50% of the gap.
  * Milder, pressure-free replies from a high emotional state → releases 30% of the gap.
  * Persistent complaints / unresolved wording (`still no update`, `nobody helped`) → holds running risk.
* **Score never falls below what fresh evidence justifies** (`score >= fresh_evidence`).
* **Trend & Satisfaction**: `escalation_trend` reports `increasing`, `decreasing`, or `stable` (±1 point noise band), and `satisfaction_trend` dynamically moves in lockstep (`declining`, `improving`, `steady`).


## 8. Frontend — Live Support Console

`support_console_frontend/` (React 19 + React Router 7 + Vite 8)

The frontend integrates all tasks into a single interactive console:
* **Customer Configuration Card**: select persona, scenario, frustration level (1–10), and expected resolution.
* **Live Chat View**: turn-by-turn messages between the simulated customer and the support agent.
* **AI Analysis Card** (Task 4): intent badge, emotion badge, frustration gauge, sentiment pill, confidence meter, and satisfaction trend.
* **Knowledge Recommendations Card** (Task 5): retrieved policy snippets, source PDF/TXT names, and page references.
* **Response Suggestion Card** (Task 6): AI recommended answer, quality scores (tone, clarity, empathy, professionalism), and coaching tips.
* **Escalation Risk Monitor Card** (Task 6): live 0–100 gauge, risk level pill, indicators chips, reasoning list, and runtime alert threshold slider.
* **Escalation Alert Banner** (Task 6): warning overlay displayed when the score crosses the alert threshold.

---

## 9. Verification & Demo Scripts

All verification scripts are organized in the `scripts/` directory:

```bash
# 1. Run unit test suite (52 tests across Task 4, 5, 6 agents)
python -m pytest task4_task5_task6_support_assist_agents -v

# 2. Verify all live API endpoints (run while backend is active on port 8000)
python scripts/verify_support_assist_endpoints.py

# 3. Demo escalation risk movement turn-by-turn (both directions: furious -> mild -> calm -> furious)
python scripts/demo_escalation_risk_movement.py

# 4. Simulate a complete multi-turn console conversation
python scripts/simulate_console_conversation.py
```

---

## 10. Deliverables Checklist

### Task 1 & 2 Deliverables:
- [x] Working source code (`task1_task2_rag_knowledge_base/`)
- [x] GitHub repository (`https://github.com/Gencoders2026/gencoders`)
- [x] Sample support documents/PDFs (`task1_task2_rag_knowledge_base/data/knowledge_base/`)
- [x] Test results & built vector index (`vector_db/index.faiss`)
- [x] Streamlit web application (`app.py` on port 8501)

### Task 3 Deliverables:
- [x] Customer Simulator Agent (`simulator.py`)
- [x] Persona & scenario configuration (`personas.py`, `scenarios.py`)
- [x] Emotion & state management (`emotion_manager.py`)
- [x] Turn-by-turn generation & API integration (`api.py` on port 8000)
- [x] Sample conversation logs (`task3_customer_simulator_agent/logs/`)
- [x] Test cases covering customer behaviors (`test_cases.py`)

### Task 4 Deliverables:
- [x] Intent and emotion classification module (`analysis_core.py`)
- [x] Sentiment analysis module with polarity & dynamic confidence
- [x] Frustration scoring mechanism (0–10 scale)
- [x] Satisfaction trend tracker (`improving`, `declining`, `steady`)
- [x] Escalation-risk detection with reason tracking
- [x] Conversation history & role management
- [x] API endpoint for analysis (`POST /analyze` and `/support/analyze`)

### Task 5 Deliverables:
- [x] Working Knowledge Recommendation Agent (`knowledge_bridge.py`)
- [x] Integration with RAG pipeline (FAISS vector store)
- [x] Intent-aware filtering and relevance ranking (top 3–5 recommendations)
- [x] Document and page-level metadata source tracking
- [x] Fallback handling when no information is available

### Task 6 Deliverables:
- [x] Coaching and Response Suggestion Agent (`support_assist.py`)
- [x] Response evaluation across tone, clarity, empathy, and professionalism
- [x] Actionable communication tips
- [x] Escalation Risk Monitor Agent with indicator detection & reasoning
- [x] Escalation alerts with configurable threshold and recommended actions
- [x] End-to-end integration into the React Support Console

