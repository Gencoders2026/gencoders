# Task 4 - Intent & Sentiment Analysis Agent (standalone)

Standalone HTTP service for **Task 4 only**. It reuses the existing engine
(`task4_task5_task6_support_assist_agents/analysis_core.py`) without editing it.

## Run

```powershell
python task4_intent_sentiment_analysis_agent/run.py
```

Optional environment variables: `TASK4_API_HOST` (default `127.0.0.1`),
`TASK4_API_PORT` (default `8104`).

## Browser links

- Task 4 service: <http://127.0.0.1:8104/>
- Task 4 health: <http://127.0.0.1:8104/task4/health>
- Task 4 API docs: <http://127.0.0.1:8104/docs>
- `POST /task4/analyze` with `{"query": "customer text"}` returns
  intent, emotion/frustration (0-10), sentiment and escalation risk.

## Full console (unchanged, all tasks together)

- Support Console: <http://127.0.0.1:8000/>
- React dev server: <http://localhost:5173/>
- Task 6 screen: <http://localhost:5173/task6>
