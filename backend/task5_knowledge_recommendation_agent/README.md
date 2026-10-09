# Task 5 - Knowledge Recommendation Agent (standalone)

Standalone HTTP service for **Task 5 only**. It reuses the existing engine
(`task4_task5_task6_support_assist_agents/knowledge_bridge.py`) without
editing it.

## Run

```powershell
python task5_knowledge_recommendation_agent/run.py
```

Optional environment variables: `TASK5_API_HOST` (default `127.0.0.1`),
`TASK5_API_PORT` (default `8105`).

Set `TASK6_NO_RAG=1` to skip loading the heavy embedding model / FAISS
index (same flag the test suite uses); the service then responds honestly
with `available: false` instead of hanging on startup queries.

## Browser links

- Task 5 service: <http://127.0.0.1:8105/>
- Task 5 status: <http://127.0.0.1:8105/task5/status>
- Task 5 health: <http://127.0.0.1:8105/task5/health>
- Task 5 API docs: <http://127.0.0.1:8105/docs>
- `POST /task5/recommend` with `{"query": "customer text"}` returns the
  detected intent, availability and the relevant knowledge results.

## Full console (unchanged, all tasks together)

- Support Console: <http://127.0.0.1:8000/>
- React dev server: <http://localhost:5173/>
- Task 6 screen: <http://localhost:5173/task6>
