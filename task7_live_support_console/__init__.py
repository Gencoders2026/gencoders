"""
Task 7 - Live Support Console (backend package).

Deliverables covered here:

* three-panel Live Support Console (the React screens in
  ``support_console_frontend``), reached at ``/task7``;
* **Manual Mode** - the agent types/pastes every customer message and the
  system analyses each one through the existing Task 4/5/6 pipeline;
* **Replay Mode** - a previously recorded conversation is uploaded
  (.txt / .csv / .json), parsed, and stepped through message by message;
* conversation state that survives the session (``session_store.py``).

The intent/sentiment analysis, knowledge recommendation, coaching and
escalation-risk engines are the SAME modules Task 4/5/6 already uses
(``task4_task5_task6_support_assist_agents/``), so the console shows
exactly the numbers the rest of the application produces.
"""

__all__ = [
    "transcript_parser",
    "session_store",
    "console_api",
]
