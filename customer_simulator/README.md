# 🎧 Customer Simulator Agent

An LLM-powered **Customer Simulator Agent** that simulates realistic
customer conversations with a support agent, generating customer
messages **turn-by-turn** based on a configurable persona, scenario,
emotion, issue severity, patience level and expected resolution.

---

## ✨ Features

| # | Requirement | Implementation |
|---|-------------|----------------|
| 1 | Configurable customer personas | `personas.py` – calm, confused, frustrated, angry, impatient, polite |
| 2 | Customer scenarios | `scenarios.py` – refund, delayed order, payment failure, account issue, cancellation |
| 3 | Turn-by-turn LLM generation | `simulator.py` + `llm_client.py` |
| 4 | Conversation context | Full history passed to the LLM each turn |
| 5 | Emotional progression | Frustration rises/falls based on the agent reply |
| 6 | Configurable parameters | initial emotion, issue severity, patience, expected resolution |
| 7 | Realistic, scenario-specific messages | Persona + scenario aware prompt; offline message bank fallback |
| 8 | API interface | FastAPI (`api.py`) – start session / send reply / get next message |
| 9 | Conversation logging | JSON log per session in `logs/` |
| 10 | Tests for different behaviours | `test_simulator.py` (24 tests) + `test_cases.py` |

---

## 🏗️ Architecture

```text
             ┌────────────────────┐
   config    │  personas  scenarios│
   (.env)    └─────────┬──────────┘
                       │
              ┌────────▼─────────┐      ┌──────────────┐
              │   simulator.py   │◄────►│ llm_client.py│──► Groq / OpenAI
              │ (turn-by-turn)   │      └──────────────┘
              └────┬────────┬────┘
                   │        │
        emotion_manager.py  logger.py  ──► logs/session_*.json
                   │
              ┌────▼─────┐
              │  api.py  │ ──► frontend/index.html
              └──────────┘
```

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
cd customer_simulator
pip install -r requirements.txt
```

### 2. Configure the API key

Create/edit `.env`:

```env
OPENAI_API_KEY=gsk_xxxxxxxxxxxxxxxx   # OpenAI or Groq key (gsk_ → Groq)
LLM_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0.9
MAX_TOKENS=250
USE_LLM=true
API_HOST=0.0.0.0
API_PORT=8000
```

> The simulator works **without** an API key too — it falls back to a
> rule-based message bank (`USE_LLM=false` or no key).

### 3. Run the web app (API + UI)

```bash
python api.py
```

Then open **http://localhost:8000** in your browser.

### 4. Run the automated tests

```bash
python test_simulator.py
```

### 5. Run the interactive terminal test

```bash
python test_run.py
```

### 6. Run the built-in self-test (all personas × scenarios × levels)

```bash
python simulator.py
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/` | Web UI |
| `GET`  | `/health` | Health check |
| `GET`  | `/config/options` | Personas, scenarios, emotions, resolutions |
| `POST` | `/session/start` | Start a simulated conversation |
| `POST` | `/session/respond` | Send the agent reply → get the next customer message |
| `PATCH`| `/session/{id}/frustration` | Manually set the frustration level |
| `GET`  | `/session/{id}` | Current session state |
| `GET`  | `/session/{id}/log` | Full conversation log |
| `GET`  | `/sessions` | List active sessions |
| `DELETE`| `/session/{id}` | End a session |
| `POST` | `/analyze` | Analyze a transcript for coaching |

### Example

```bash
# Start a session
curl -X POST http://localhost:8000/session/start \
  -H "Content-Type: application/json" \
  -d '{"persona":"angry","scenario":"refund_request","frustration_level":8,
       "initial_emotion":"angry","issue_severity":8,"patience_level":3,
       "expected_resolution":"full_refund"}'

# Respond as the agent
curl -X POST http://localhost:8000/session/respond \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<id>","message":"I understand, I have processed your refund within 2 business days."}'
```

---

## 🧠 Emotional Progression

Frustration is scored from the agent's reply:

* **Positive** – apology, empathy, ownership, concrete timeline → **calms**
* **Negative** – deflection, policy-only, "wait", "cannot" → **escalates**
* **Patience** amplifies negative replies; **issue severity** dampens calming.

Bands: `Calm (1-2) · Concerned (3-4) · Frustrated (5-6) · Angry (7-8) · Furious (9-10)`

Angry / furious personas are enforced to **never** use polite words
(*please, kindly, thank you, sorry, appreciate*).

---

## 📁 Project Structure

```text
customer_simulator/
├── api.py               # FastAPI server + UI host
├── simulator.py         # Core turn-by-turn simulation engine
├── personas.py          # Customer personas
├── scenarios.py         # Customer scenarios
├── emotion_manager.py   # Emotion / frustration state manager
├── llm_client.py        # OpenAI-compatible LLM client (Groq/OpenAI)
├── config.py            # Configuration (.env)
├── logger.py            # JSON conversation logging
├── frontend/
│   └── index.html       # Web UI
├── logs/                # Session logs
├── test_simulator.py    # Automated test suite (24 tests)
├── test_cases.py        # Positive / negative test-case catalogue
├── test_run.py          # Interactive terminal test
└── requirements.txt
```

---

## 📝 Sample Conversation Log

Each session writes `logs/session_<id>.json`:

```json
{
  "meta": {
    "session_id": "a1b2c3d4",
    "config": {
      "persona": "angry",
      "scenario": "refund_request",
      "frustration_level": 8,
      "issue_severity": 8,
      "patience_level": 3,
      "expected_resolution": "full_refund"
    },
    "final_emotion": { "label": "Angry", "frustration_level": 8 }
  },
  "conversation": [
    { "turn": 1, "role": "customer", "message": "This refund delay is unacceptable. I need a definite timeline now." },
    { "turn": 2, "role": "agent", "message": "I understand how frustrating this is..." },
    { "turn": 3, "role": "customer", "message": "..." }
  ]
}