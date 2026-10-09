# Task 6 - Coaching & Escalation Agents (standalone)

Standalone HTTP service for **Task 6 only**. It reuses the existing engine
(`task4_task5_task6_support_assist_agents/support_assist.py`,
`knowledge_bridge.py`, `analysis_core.py`) without editing it.

## Run

```powershell
python task6_coaching_escalation_agents/run.py
```

Optional environment variables: `TASK6_API_HOST` (default `127.0.0.1`),
`TASK6_API_PORT` (default `8106`).

## Browser links

- Task 6 service: <http://127.0.0.1:8106/>
- Task 6 health: <http://127.0.0.1:8106/task6/health>
- Task 6 API docs: <http://127.0.0.1:8106/docs>
- `POST /task6/assist` with `{"query": "customer text"}` runs the
  coaching + escalation pipeline.
- `POST /task6/coaching/evaluate` evaluates a drafted agent reply.
- `GET /task6/escalation/threshold` shows the alert threshold.

## Dedicated Task 6 screen (unchanged React console)

- Task 6 - Escalation Risk Monitor: <http://localhost:5173/task6>
- Support Console: <http://127.0.0.1:8000/>
- React dev server: <http://localhost:5173/>
