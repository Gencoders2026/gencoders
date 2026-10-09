"""
Task 8 - Insights & Performance Analytics package.

Two deliverables live here, in their own folder, separate from Task 7:

    summary_agent.py     Post-Interaction Summary Agent
    analytics_agent.py   Performance Analytics module

Both are driven by the REAL conversations the application produces:

    * conversations recorded by the Task 7 Live Support Console
      (``task7_live_support_console/session_store.py``), and
    * the conversation logs the existing Task 3 Customer Simulator writes
      (``task3_customer_simulator_agent/logs/``), read read-only.

The agent engines are the SAME modules Tasks 4/5/6 use, so the reports and
analytics agree with every other screen of the application.
"""

__all__ = [
    "conversation_analysis",
    "summary_agent",
    "analytics_agent",
    "demo_sessions",
    "insights_api",
]
