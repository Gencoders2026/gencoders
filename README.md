# Customer Simulator Agent

A rule-based **customer simulator for customer-support conversations**. Pick a
customer persona, a support scenario, and a frustration level (1-10), then chat
as the support agent: the simulator replies as the customer would - politely at
low frustration, angrily at high frustration - and its frustration rises or
falls depending on how helpful your replies are.

> Scope: this README covers ONLY the Customer Simulator Agent (backend in
> `task3_customer_simulator_agent/`, UI in `support_console_frontend/`). This
> repo also contains other task folders (RAG knowledge base, analysis/coaching
> agents, analytics); they are out of scope here and the simulator does NOT
> use RAG.

## Contents

1. Project overview
2. Objectives
3. Features (verified in code)
4. Technology stack
5. Project folder structure
6. System workflow
7. Installation and setup
8. How to run
9. How to use
10. Test cases
11. API documentation
12. Agile documentation
13. Limitations and future enhancements
14. Contributors
15. License

## 1. Project overview

Support-agent training and support-tool testing need realistic customers on
demand. This project simulates a customer during a customer-support
conversation: you configure WHO the customer is (persona = communication
style), WHAT the problem is (scenario = issue and goal), and HOW upset they
start (frustration level 1-10 = emotional intensity). The simulator then
generates the customer's opening message and every follow-up reply, reacting to
what the agent actually says (a request for details, a concrete timeline, an
apology with no action, or a vague stall) instead of repeating canned lines.

## 2. Objectives

- Simulate believable customers across common support situations (refunds,
  delayed orders, payment failures, account access, cancellations).
- Keep persona (communication style) and frustration level (emotional
  intensity) as separate, explicit controls.
- React to the agent's replies: helpful answers calm the customer, poor or
  evasive answers raise frustration, and a genuine resolution ends the chat.
- Provide a simple HTTP API plus a browser UI so beginners can run practice
  conversations and inspect turn-by-turn state.
- Persist every conversation as a JSON log for review and evaluation.

## 3. Features (verified in code)

Read directly from `task3_customer_simulator_agent/*.py`:

- 5 customer personas (`simulator.py` PERSONAS): polite, concerned,
  frustrated, angry, furious. Persona controls COMMUNICATION STYLE ONLY.
- 5 support scenarios (`simulator.py` SCENARIOS): refund_request,
  delayed_order, payment_failure, account_issue, cancellation.
- Frustration level 1-10 is the SINGLE control for emotional intensity
  (`get_band` / `get_emotion`): 1-2 Calm, 3-4 Concerned, 5-6 Frustrated,
  7-8 Angry, 9-10 Furious. Different levels give different messages.
- Contextual replies: the agent message is classified into 6 kinds
  (asks_for_info, asks_confirmation, gives_timeline, apology_only, vague,
  offers_help) and the customer answers THAT from `contextual_replies.py`,
  filtered to the current band.
- Evidence-based emotion change (`respond`): concrete commitments and empathy
  lower frustration proportionally (never a flat +-1); vague language (wait,
  soon, later, cannot help, policy, outside our control, no refund) raises it.
  A scenario-specific resolution phrase drops frustration sharply and, at
  level 4 or below, ends the chat with a band-appropriate closing message.
- No-repeat protection: unused lines preferred, previous line never repeated,
  persona prefixes cannot disguise a repeat (base lines in `used_bases`).
- Session backend (`api.py`): start/respond/frustration/state/log/end
  endpoints with per-session JSON logs in `logs/`.
- React Support Console (`support_console_frontend/`): configuration page,
  live conversation view, served production build in `dist/`.
- Checks: pytest suite `test_simulator_replies.py`, live script
  `verify_live.py`, interactive chat `test_run.py`.

NOT in this project: no RAG/retrieval, no embeddings. Patience level and
issue severity shown in the UI do NOT drive backend emotions - only
frustration level does.

## 4. Technology stack

- Language: Python 3.13 (backend), JavaScript/JSX (frontend)
- Backend: FastAPI 0.115.0, Uvicorn (standard) 0.30.6, Pydantic 2.9.2,
  python-dotenv 1.0.1, python-multipart 0.0.12
- Optional LLM hooks in requirements (openai 1.51.0, httpx, aiofiles, jinja2);
  simulator defaults to `use_llm=False` (rule-based, no key needed)
- Misc deps listed: requests 2.32.3, streamlit 1.38.0 (simulator runs on
  FastAPI, not Streamlit)
- Frontend: React 19, React Router 7, Vite 8, Axios
- Testing: pytest, plain-Python scripts, `scripts/` verification helpers
- Tools: Node.js + npm, uvicorn, Git/GitHub

## 5. Project folder structure

```text
gencoders/
  README.md                        # this file (Customer Simulator Agent docs)
  LICENSE                          # MIT License (root level)
  AGILE.md                           # Agile documentation for this project
  task3_customer_simulator_agent/    # BACKEND (FastAPI + simulator)
    api.py                           # session endpoints, serves React build
    simulator.py                     # CustomerSimulator, PERSONAS, SCENARIOS
    contextual_replies.py            # scenario x agent-kind reply tables
    emotion_manager.py               # reference emotion-state helper module
    personas.py                      # richer persona reference catalogue
    scenarios.py                     # richer scenario reference catalogue
    config.py                        # env defaults, ports, emotion scale 1-10
    logger.py                        # ConversationLogger helper
    requirements.txt                 # backend dependencies
    test_simulator_replies.py        # pytest suite
    test_cases.py                    # sample positive/negative input cases
    test_run.py                      # interactive console chat (no key)
    verify_live.py                   # live frustration/resolution demo
    logs/                            # per-session JSON conversation logs
  support_console_frontend/          # FRONTEND (React + Vite)
    src/pages/SessionConfiguration.jsx  # persona/scenario/level form
    src/pages/SupportConsole.jsx        # live conversation view
    src/services/sessionService.js      # start/respond/session API calls
    src/services/api.js                 # base URL (port 8000 default)
    package.json                        # react, router, vite, axios
    dist/                               # built UI served by the backend
  scripts/                           # verification/demo helpers
    live_session_proof.py               # end-to-end session flow proof
  logs/                              # root-level run/session logs
```

Notes: `emotion_manager.py`, `personas.py`, `scenarios.py` are reference
modules - the running backend uses the PERSONAS/SCENARIOS tables inside
`simulator.py`. Extra task folders and duplicate synced copies
(`customer_simulator/`, `task3_customer_simulator/`) exist in this shared repo
but are out of scope for this README.

## 6. System workflow

```text
1. Configure   persona + scenario + frustration_level (1-10) + expected_resolution
       |
2. POST /session/start  ->  opening customer message for that band + session_id
       |
3. Agent replies (typed in UI or POST /session/respond)
       |
4. Simulator classifies reply kind (info request / confirmation / timeline /
   apology-only / vague stall / generic) AND scores helpfulness from evidence
       |
5. Frustration moves: helpful -> down (proportional); vague/poor -> up;
   scenario resolution phrase -> big drop; <=4 with resolution -> finished
       |
6. Next customer message chosen from matching contextual pool, else band pool;
   persona wording applied; repeats avoided; state + JSON log updated
       |
7. Repeat 3-6 until resolved (closing message) or session ended/deleted.
```

## 7. Installation and setup

Prerequisites: Python 3.10+ (3.13 used here), Node.js 18+ with npm.

Backend:

```bash
cd task3_customer_simulator_agent
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
```

Optional: copy env example if you ever enable LLM mode (NOT needed by
default - the simulator is rule-based with `use_llm=False`):

```bash
# copy your own env; never commit secrets
# OPENAI_API_KEY=... (only if you modify code to use the LLM path)
```

Frontend (only needed for development; the backend already serves the built
UI in `support_console_frontend/dist/`):

```bash
cd support_console_frontend
npm install
```

## 8. How to run

Terminal 1 - backend (from repo root):

```bash
cd task3_customer_simulator_agent
uvicorn api:app --host 127.0.0.1 --port 8000 --reload
# or: python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

Backend health/docs:

- UI served at: http://127.0.0.1:8000/ (built React console)
- API docs: http://127.0.0.1:8000/docs
- Config: http://127.0.0.1:8000/config/options

Terminal 2 - frontend dev server (optional, for developing the UI):

```bash
cd support_console_frontend
npm run dev
# open http://localhost:5173 (expects backend on port 8000; see
# src/services/api.js or set VITE_API_BASE_URL)
```

Rebuild the served UI after frontend changes:

```bash
cd support_console_frontend
npm run build
# output dist/ is committed on purpose and served by api.py
```

Run the automated simulator checks:

```bash
cd task3_customer_simulator_agent
python -m pytest test_simulator_replies.py -v
python verify_live.py
python test_run.py   # interactive chat; type quit to exit
```

## 9. How to use

1. Open http://127.0.0.1:8000/ (backend-served console) or
   http://localhost:5173 (vite dev server).
2. On Session Configuration choose Persona (e.g. polite), Scenario (e.g.
   Refund Request), Expected Resolution, Initial Frustration Level (1-10),
   plus Patience (see note) and Severity/Issue fields.
3. Click Start Session. The simulator posts its opening customer message with
   the current emotion and frustration (e.g. `2/10 Calm`).
4. Type as the support agent and send. Helpful replies (concrete timeline,
   confirmed refund, empathy) lower frustration; vague stalls raise it.
5. Resolve with the scenario phrase (e.g. refund_request:
   "Your refund has been processed ... full refund ... confirmed") until the
   customer closes the chat.

IMPORTANT UI NOTE (verified in `src/services/sessionService.js` line 170):
the frontend currently sends the PATIENCE slider value as `frustration_level`
and ignores the Initial Frustration slider. So set PATIENCE to the intensity
you want (e.g. 2 for calm, 9 for furious), or call the API directly with the
exact `frustration_level`.

## 10. Test cases

From `contextual_replies.py`, `simulator.py` band pools, and `verify_live.py`
(rule-based mode, exact pool rotation may vary but band/intensity behaviour is
as shown):

| # | Setup | Agent reply | Expected simulator behaviour |
|---|-------|-------------|------------------------------|
| 1 | persona=polite, scenario=refund_request, level=2 (Calm) | (start) | Polite calm opener, e.g. "Hi, I received a damaged product in my order. Could you please help me with a refund?" level stays 2, emotion Calm |
| 2 | persona=furious, scenario=refund_request, level=9 (Furious) | (start) | Furious opener, e.g. "This is completely unacceptable. I need my refund resolved immediately." level 9, emotion Furious |
| 3 | persona=frustrated, scenario=delayed_order, level=5 | "Could you please provide your order number?" (asks_for_info) | Customer supplies details from the asks_for_info pool (e.g. order/tracking info), band stays Frustrated |
| 4 | persona=frustrated, scenario=refund_request, level=9 start | "Your full refund has been processed and confirmed. It will arrive within 3 business days. Sorry for the inconvenience - I understand this is frustrating." | Frustration DROPS sharply (proportional release), reply acknowledges the timeline; repeated resolutions finish the chat at level <=4 |
| 5 | persona=polite, scenario=delayed_order, level=2 start | "I cannot help with that right now, please wait, maybe later. Unfortunately policy says outside our control." | Frustration RISES (poor/evasive signals), next message pushes back and asks for a real timeline |
| 6 | any persona/scenario, mid-chat | "Thanks for reaching out, we will look into this for you." (vague) | Customer pushes back (vague pool), e.g. refund_request angry: "Stop saying you will check. Tell me exactly when the refund happens." |
| 7 | any, mid-chat | "We will process this within 24 hours and email you." (gives_timeline) | Customer acknowledges the commitment in-band (calm thanks / furious says still too slow) |

Edge cases listed in `test_cases.py`: empty string, spaces-only, very long
(100x repeated), missing/None message, unknown emotion/intensity - the API
validates `message` (min length 1) and `frustration_level` (1-10) via Pydantic
and the simulator falls back to `frustrated`/`refund_request` on unknown keys.

## 11. API documentation

Base URL: `http://127.0.0.1:8000`. Interactive docs: `/docs`.
All endpoints verified in `task3_customer_simulator_agent/api.py`.

### GET /config/options

Lists valid personas, scenarios, levels, resolutions.

```json
{
  "personas": [{"value": "polite", "name": "Polite Customer"}],
  "scenarios": [{"value": "refund_request", "name": "Refund Request"}],
  "frustration_levels": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "resolutions": ["full_refund", "partial_refund", "replacement",
    "store_credit", "cancellation_confirmed", "account_restored",
    "new_delivery_date"]
}
```

### POST /session/start

Fields: `persona` (default frustrated), `scenario` (default refund_request),
`frustration_level` 1-10 (default 5), `expected_resolution`
(default full_refund).

```bash
curl -X POST http://127.0.0.1:8000/session/start \
  -H "Content-Type: application/json" \
  -d '{"persona":"polite","scenario":"refund_request","frustration_level":2,"expected_resolution":"full_refund"}'
```

Response shape: `session_id`, `customer_message` (opening line for that
band), `persona`, `persona_name`, `scenario`, `scenario_name`,
`frustration_level`, `emotion` (`label` + `intensity`), `finished`,
`turn_count`, `history` (role/content/frustration/emotion per turn),
`log_path` (JSON log under `logs/`).

### POST /session/respond

Fields: `session_id` (required), `message` (required, min length 1),
`frustration_level` (optional override 1-10 applied before scoring).

```bash
curl -X POST http://127.0.0.1:8000/session/respond \
  -H "Content-Type: application/json" \
  -d '{"session_id":"a1b2c3d4","message":"Your refund has been processed and the full refund is confirmed within 3 business days."}'
```

Returns the same shape with the next `customer_message` and updated
frustration/emotion. When a scenario resolution brings frustration to 4 or
below, returns `finished: true` plus `status: "resolved"` and a closing
message. Replying after finishing returns `status: "already_finished"`.

### PATCH /session/{session_id}/frustration

Field: `frustration_level` 1-10 (required). Manual intensity override.

```bash
curl -X PATCH http://127.0.0.1:8000/session/a1b2c3d4/frustration \
  -H "Content-Type: application/json" \
  -d '{"frustration_level": 8}'
```

### GET /session/{session_id} (JSON for API clients)

Returns the session state. Note: browser navigations (Accept: text/html) get
the React app; API clients send `Accept: application/json` (axios preset).

### GET /session/{session_id}/log

Returns the saved JSON log (`meta` + `conversation` entries).

### GET /sessions

```json
{"active": ["a1b2c3d4"], "count": 1}
```

### DELETE /session/{session_id}

Ends a session. Returns `status: ended` with `session_id` and `log_path`.

### Resolution phrases (verified in `_is_resolved`)

- refund_request: "refund has been processed" / "refund processed" /
  "full refund" / "refund completed"
- delayed_order: "delivery date" / "order has arrived" / "order delivered" /
  "delivered"
- payment_failure: "payment is successful" / "payment succeeded" /
  "payment fixed" / "payment completed"
- account_issue: "access restored" / "account restored" / "account is
  unlocked" / "unlocked" / "restored" / "logged in" / "log in now" /
  "login successful" / "access is restored" / "account access is working"
- cancellation: "cancelled" / "cancellation confirmed" /
  "subscription cancelled"

## 12. Agile documentation

Full file: `AGILE.md`. Summary (no invented ceremonies):

- Approach: iterative and incremental - small commits (reactive replies,
  evidence-based frustration, no-repeat protection, UI updates, verification
  scripts), organised by task folder, integrated via one FastAPI backend.
- Tasks: persona/scenario catalogues, band pools, contextual replies, emotion
  dynamics + resolution finish, no-repeat/prefixes/closings, session API +
  logs, React console, automated + live checks - all Done.
- Testing: `python -m pytest test_simulator_replies.py -v` (from
  `task3_customer_simulator_agent/`), `python verify_live.py`,
  `python test_run.py`, browser testing, `scripts/live_session_proof.py`.
- History shows: band-only replies became agent-reactive; frustration became
  evidence-proportional; repeats eliminated; UI + built assets synced.

## 13. Limitations and future enhancements

Limitations (from the code):

- Rule-based finite pools; very long chats eventually reuse lines (never
  back-to-back).
- Regex scoring can misread sarcasm or multi-issue messages.
- Resolution detection is phrase-based, not true understanding.
- Reference modules (`personas.py`, `scenarios.py`, `emotion_manager.py`) are
  richer than the tables the backend actually uses.
- UI quirk: Patience slider is sent as `frustration_level`; Initial
  Frustration slider is ignored (see section 9).
- Duplicate copies (`customer_simulator/`, `task3_customer_simulator/`) need
  team cleanup; sessions live in memory (restart clears them, logs remain).

Future work: one canonical backend folder; fix the slider mapping; optional
guardrailed LLM paraphrase behind `use_llm`; persistent store; more languages;
exportable transcripts; frustration-vs-turn chart.

## 14. Contributors

From `git shortlog -sne --all` (2026-10-09): bhanu-y-2007 (92 commits),
Manasa Kodi (26), ValarmathiSankar, Anubhi Jain / promptmuse,
pragna19177-prog. Teammates: add missing names + contributions here before
submission (no other names found in project files).

## 15. License

MIT License - see `LICENSE` at the repo root (full MIT text, copyright:
Gencoders2026 contributors, 2026).

---

## Submission checklist (team repo `Gencoders2026/gencoders`)

- [x] Frontend (`support_console_frontend/` incl. served `dist/`)
- [x] Backend (`task3_customer_simulator_agent/` incl. API, tests, logs)
- [x] Agile documentation (`AGILE.md` + section 12)
- [x] MIT License (root `LICENSE` + section 15)
- [x] Complete source + README (this file, simulator scope only)

Do NOT create a per-member repo. Do NOT commit/push without permission. No
secrets included (local untracked `.env` is gitignored - keep it off GitHub).
