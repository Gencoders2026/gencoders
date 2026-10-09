# Task 7 - Live Support Console & Conversation Replay

Interactive **three-panel Live Support Console** for support agents, with
real-time coaching and knowledge recommendations. It reuses the existing
Task 4/5/6 engines (`analysis_core.py`, `knowledge_bridge.py`,
`support_assist.py`) - nothing is re-implemented.

```text
Customer message
      |
      v
Intent & Sentiment   ->  Knowledge Recommendation  ->  Coaching & Response
Analysis Agent           Agent (RAG)                   Suggestion Agent
      |                                                  |
      +--------------------------------------------------+
                              |
                              v
                 Escalation Risk Monitor Agent
```

## The three panels

| Panel | What it shows |
| ----- | ------------- |
| **1 - Conversation window** | Customer/agent chat in chronological order, an input box for the agent's reply, and the live customer state: **intent**, **sentiment**, **frustration level (0-10 / emotion)** and **escalation risk** - all recalculated after every customer message. |
| **2 - Real-time coaching feed** | **Suggested response** (+ alternates and a follow-up question), **coaching feedback**, and **tone / empathy / clarity / professionalism** guidance with per-dimension scores, plus an **escalation-risk warning** with recommended actions when the risk threshold is reached. |
| **3 - Knowledge recommendation panel** | FAQs / support articles / policies / troubleshooting steps retrieved from the RAG knowledge base for the *current* message and conversation context, each with its source document, page and relevance. **Open full article** shows the complete content in a dialog. |

## Manual Mode

1. Type or paste the customer message and press **Add customer message**.
2. The backend analyses it (`POST /task7/analyze`) and every panel updates:
   intent, sentiment, frustration, suggested response, coaching feedback,
   knowledge recommendations and escalation risk.
3. Write the agent reply (or hit **Use suggested response**), optionally
   **Check my draft** to score it, then **Send reply**.
4. Repeat - the analysis is regenerated for every new customer message, and
   the whole conversation state is kept for the session.

The analysis is **message-dependent, not incremental**: the same three
messages from the brief produce three clearly different results.

| Customer message | Intent | Emotion / frustration | Sentiment | Escalation |
| --- | --- | --- | --- | --- |
| "My payment failed and I have been trying for two hours." | `payment_failure` | Calm, 3/10 | neutral | Low 0/100 |
| "This is ridiculous. Nobody is helping me and I need this fixed immediately." | `general_inquiry` | Furious, 9/10 | negative | High 53/100 |
| "Thank you, the issue is finally resolved." | `general_inquiry` | Calm, 3/10 | positive | Low 3/100 |

## Replay Mode

* **Upload a transcript** (.txt / .csv / .json) or pick a conversation the
  existing Task 3 simulator already recorded.
* The transcript is parsed into individual customer/agent messages
  (role markers, CSV role/message columns, or JSON message objects).
* Step through it with **Next**, **Previous**, **Play**, **Pause** and
  **Restart**.
* After every customer message the console regenerates coaching,
  knowledge recommendations, sentiment, frustration, intent and
  escalation risk for that exact point of the conversation.
* The **escalation-risk progression** chart shows the score after each
  analysed customer message, and a **replay/conversation summary** is
  shown when the replay completes.

## API

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| GET | `/task7/health` | Service + knowledge-base health |
| POST | `/task7/analyze` | Analyse one customer message (whole pipeline) |
| POST | `/task7/transcript/parse` | Upload and parse a transcript |
| GET | `/task7/sessions` | Recorded conversations |
| POST | `/task7/sessions` | Record a conversation (used by Task 8) |
| GET | `/task7/sessions/{id}` | One recorded conversation |
| DELETE | `/task7/sessions/{id}` | Delete a recorded conversation |
| GET | `/task7/simulator-sessions` | Task 3 conversations (read-only) |

## Run

The router is mounted by the Customer Simulator backend, so the console and
the earlier tasks share one origin:

```powershell
cd task3_customer_simulator_agent
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

* **Live Support Console** - <http://127.0.0.1:8000/task7>
* Manual Mode - <http://127.0.0.1:8000/task7?mode=manual>
* Replay Mode - <http://127.0.0.1:8000/task7?mode=replay>
* React dev server - <http://localhost:5173/task7>

Standalone API (optional):

```powershell
python task7_live_support_console/run.py     # http://127.0.0.1:8107
```

## Tests

```powershell
python -m pytest task7_live_support_console/test_task7.py -v
```

30 tests covering health, the Manual Mode dynamic analysis, all three
transcript formats, Replay stepping (Next/Previous/Restart), escalation
progression and conversation-state persistence.

## Files

| File | Purpose |
| ---- | ------- |
| `console_api.py` | FastAPI router (`/task7/...`) + standalone app |
| `transcript_parser.py` | .txt / .csv / .json transcript parsing |
| `session_store.py` | Recorded conversations + read-only Task 3 log access |
| `test_task7.py` | Test cases for Manual Mode and Replay Mode |
| `run.py` | Standalone server (port 8107) |
| `data/recorded_sessions.json` | Conversations recorded by the console |
