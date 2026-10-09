# Task 8 - Insights & Performance Analytics

Two connected deliverables on top of every conversation produced earlier in
the project (Task 3 simulator runs, Task 6/7 conversations, transcripts):

```text
                    conversations (Task 3 / Task 6 / Task 7 / demo)
                                     |
                                     v
              +---------------- conversation_analysis ----------------+
              |  timeline, intents, sentiment, frustration,           |
              |  escalation risk, resolution state, agent-turn scores |
              +------------------------------------------------------+
                        |                                  |
                        v                                  v
        Post-Interaction Summary Agent        Performance Analytics Agent
        (ONE conversation report)             (multi-session aggregation)
                        |                                  |
                        v                                  v
                 /task8/summary                      /task8/analytics
```

Both engines **reuse the existing Task 4/5/6 engines**
(`support_assist.py`, `analysis_core.py`, knowledge bridge) - nothing is
re-implemented.

## 1. Post-Interaction Summary (`/task8/summary`)

A structured report for ONE conversation:

| Block | Content |
| ----- | ------- |
| **Overall summary** | One paragraph describing what happened: issue, message counts, how the customer felt at the start/end, peak escalation and the final resolution. |
| **Resolution quality** | Score / 100 with a band, built from four weighted factors: issue resolution, communication quality, sentiment improvement, guideline adherence (weights sum to 1.0). Each factor is shown with its score and a progress bar. |
| **Conversation statistics** | Total/customer/agent messages, average response quality, below-bar responses, alerts triggered, peak escalation, frustration and sentiment start/end. |
| **Sentiment timeline** | One point per customer message: intent, emotion, frustration (0-10), sentiment, escalation score/level and the message itself. |
| **Sentiment journey** | Start/end state, direction (improved / steady / declined), frustration delta and a narrative. |
| **Escalation risk progression** | Line chart of the risk score after every customer message + counts of every escalation trigger that fired. |
| **Strengths / weaknesses** | Title + detail per observation, derived from the agent's scored turns. |
| **Coaching recommendations** | Prioritised (High / Medium / Low) with title, detail and the metric that triggered them. |
| **Final resolution** | Status (resolved / offered / open / unknown), label, evidence words and whether the CUSTOMER confirmed the fix in their last message. |

Sources: an explicit `conversation_id`, a `simulator_session_id`, or an
inline `messages` list (useful for one-off reports).

## 2. Performance Analytics (`/task8/analytics`)

Aggregated over many sessions - the dashboard shows six sections:

1. **Metric header** - sessions analysed, resolution rate (+ customer
   confirmed), escalation frequency, average response quality, sentiment
   improvement and the average frustration trend.
2. **Charts** - resolution/escalation trend, frustration curve,
   interaction trend, issue distribution donut, resolution breakdown donut,
   escalation triggers, response quality per dimension and knowledge
   coverage (red bars = gaps).
3. **Frequent issues** - primary issue per session with counts/rates, plus
   recurring issues that keep coming back.
4. **Escalation reasons** - how often each escalation trigger fired.
5. **Knowledge gaps & unresolved work** - missed topics (retrieved vs
   requested), repeated knowledge searches (same question/topic searched
   again), incorrect agent responses (below the quality bar) and
   unresolved queries.
6. **Insights** - overall insight sentences, prioritised recommendation
   cards and per-session insight tiles.

### Demo data is always labelled

The `demo_sessions.py` seeder keeps clearly-labelled **test** conversations
(`is_demo = True`). They are:

* reported separately in `data_sources` (`recorded_conversations`,
  `simulator_conversations`, `demo_conversations`, `total_analysed`),
* tagged `demo` in the session tiles and the conversation picker,
* excluded whenever `include_demo=false`.

Real data is never mixed into demo counts and vice versa.

## API

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| GET | `/task8/health` | Service + data availability |
| GET | `/task8/conversations` | Conversations available to analyse (`recorded` incl. labelled demo first, then Task 3 simulator logs) |
| POST | `/task8/summary` | Post-Interaction Summary for one conversation |
| GET | `/task8/analytics` | Multi-session Performance Analytics |
| GET | `/task8/conversations/{id}/analysis` | Turn-by-turn analysis (timeline + scored agent turns) |
| POST | `/task8/demo-data` | (Re)load the labelled demo conversations |

## Run

### Combined origin (normal workflow)

The router is mounted by the Customer Simulator backend, so everything runs
on one origin:

```bash
python task3_customer_simulator_agent/api.py          # http://127.0.0.1:8000
cd support_console_frontend && npm run dev            # http://localhost:5173
```

Frontend pages:

| URL | Screen |
| --- | ------ |
| `/task8` | Performance Analytics dashboard (six sections) |
| `/task8/summary` | Post-Interaction Summary (conversation picker + report) |

Both are also reachable from the Dashboard nav (**Task 8 - Performance
Analytics**, **Task 8 - Summary Report**) and from each other's header.

### Standalone API (optional)

```bash
python task8_insights_analytics/run.py                # http://127.0.0.1:8108
```

`TASK8_API_HOST` / `TASK8_API_PORT` override the bind address.

## Tests

```bash
python -m pytest task8_insights_analytics/test_task8.py -v
```

32 tests covering health, the conversation picker (including demo
labelling/exclusion), the full summary contract (quality factors and
weights, statistics, sentiment timeline/journey, risk progression, final
resolution, coaching priorities), every analytics section and chart,
`data_sources` demo separation, and the turn-by-turn analysis endpoint.

## Files

| File | Purpose |
| ---- | ------- |
| `insights_api.py` | FastAPI router (`/task8/...`) + standalone landing page |
| `summary_agent.py` | Post-Interaction Summary Agent |
| `analytics_agent.py` | Performance Analytics agent (multi-session) |
| `conversation_analysis.py` | Per-conversation timeline/intents/resolution/agent-turn scoring |
| `demo_sessions.py` | Clearly-labelled demo conversations (`is_demo = True`) |
| `run.py` | Standalone uvicorn server (port 8108) |
| `test_task8.py` | Pytest suite |

