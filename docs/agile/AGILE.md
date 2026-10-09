# Agile Documentation — Customer Simulator Agent

> Honest scope note: this file describes only what the repository history and
> code actually show. No formal Scrum ceremonies (named sprints, sprint
> planning meetings, stand-ups, retrospectives) are recorded in the repo, so
> none are claimed here.

## 1. Development approach (evidence-based)

Development was **iterative and incremental**, as shown by the git history
(`git log --oneline`): small, focused commits that each added or fixed one
thing — e.g. making the customer react to the agent's actual reply, fixing
escalation-risk behaviour, updating the session-configuration UI, syncing
built frontend assets, and adding verification scripts.

Work was organised **by task folder** (`task3_customer_simulator_agent/` for
the simulator backend, `support_console_frontend/` for the UI), so each
increment could be built, run, and tested independently before integration
through the single FastAPI backend on port 8000.

## 2. Task breakdown (what was actually built)

| # | Task | Where | Status |
|---|------|-------|--------|
| 1 | Persona catalogue (5 personas, communication styles) | `task3_customer_simulator_agent/simulator.py` (`PERSONAS`) + reference file `personas.py` | Done |
| 2 | Scenario catalogue (5 support scenarios) | `simulator.py` (`SCENARIOS`) + reference file `scenarios.py` | Done |
| 3 | Band-based message pools (calm → furious) | `simulator.py` (`message_sets`, `BAND_POOLS`) | Done |
| 4 | Contextual replies reacting to the agent's reply kind (6 kinds) | `contextual_replies.py` + `_agent_reply_kind()` | Done |
| 5 | Evidence-based frustration dynamics + resolution finish | `simulator.py` (`_assess_agent_response_quality()`, `_is_resolved()`, `respond()`) | Done |
| 6 | No-repeat protection + persona prefixes + closing messages | `simulator.py` (`_pick_unused()`, `PERSONA_PREFIXES`, `_closing_message()`) | Done |
| 7 | FastAPI session backend + JSON conversation logs | `api.py`, `logger.py`, `logs/` | Done |
| 8 | React Support Console (configuration + conversation UI) | `support_console_frontend/src/pages/`, `src/services/` | Done |
| 9 | Automated checks (pytest suite + live verification scripts) | `test_simulator_replies.py`, `verify_live.py`, `test_run.py`, `scripts/` | Done |

## 3. Testing performed

- **Automated (pytest):** `task3_customer_simulator_agent/test_simulator_replies.py`
  covers agent-reply classification, band-dependent messages, no-repeat
  behaviour (including with persona prefixes), pool exhaustion over long
  conversations, and all scenario/band combinations. Run:
  `cd task3_customer_simulator_agent` then
  `python -m pytest test_simulator_replies.py -v`.
- **Live behaviour script:** `verify_live.py` demonstrates frustration
  decreasing after helpful replies, increasing after poor replies,
  per-scenario resolution detection, and repetition checks.
- **Manual:** `test_run.py` (interactive console chat, no API key needed) and
  browser testing of the React console (`SessionConfiguration` →
  `SupportConsole`) against the backend on port 8000.
- **Reference cases:** `test_cases.py` lists sample positive/negative input
  cases (empty, blank, over-long, missing messages).

## 4. Iterative improvements (from commit history)

1. Customer replies changed from band-only selection to **reacting to the
   agent's actual reply** (commit `feat(customer-simulator): make the
   customer react to the agent's actual reply`).
2. Frustration movement made **evidence-based and proportional** instead of a
   fixed per-turn step, with scenario-specific resolution phrases.
3. **No-repeat protection** added so long conversations never repeat a line
   while unused lines remain.
4. Session-configuration UI updated (persona / scenario / frustration and
   patience sliders / expected resolution) with built assets synced so the
   backend can serve the UI directly.
5. Verification scripts added (`scripts/live_session_proof.py`,
   escalation-monitor audits) to prove end-to-end behaviour.

## 5. Known issues / backlog

- The current frontend sends the **Patience slider** value as
  `frustration_level` (`sessionService.js`), ignoring the Initial Frustration
  Level slider — set the Patience slider to the desired intensity, or call
  the API directly (see README § “How to Use”).
- `personas.py` / `scenarios.py` are richer reference files but the running
  backend uses the `PERSONAS` / `SCENARIOS` tables inside `simulator.py`.
- Duplicate synced copies (`customer_simulator/`, `task3_customer_simulator/`)
  should be consolidated by the team in a future cleanup (not done here to
  avoid breaking anything).
