import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  isSessionAlive,
  readStoredConfig,
  readStoredSessionId,
  clearStoredSessionId,
  startSession,
} from "../services/sessionService";

/**
 * Entry point of the Task 6 dashboard (`/`).
 *
 * Opening the project must land on a WORKING Task 6 conversation without
 * the user typing any internal URL or session id:
 *
 *   1. if this tab already has a live session, resume it (so a browser
 *      refresh or navigating back to `/` never creates a duplicate);
 *   2. otherwise create a session automatically with the last Customer
 *      Configuration (defaults on first run);
 *   3. while that happens a proper loading screen is shown, and if the
 *      backend cannot be reached a complete recovery screen is shown -
 *      never a blank/white page.
 */

// Module level so React StrictMode's double effect invocation (dev only)
// creates exactly one session.
let pendingStart = null;

function SessionAutoStart() {
  const navigate = useNavigate();

  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState("Starting your Task 6 session...");

  useEffect(() => {
    let cancelled = false;

    async function openTask6Session() {
      setError("");

      // 1. Resume the conversation this tab is already in.
      const stored = readStoredSessionId();

      if (stored) {
        setStatus("Restoring your Task 6 conversation...");

        if (await isSessionAlive(stored)) {
          if (!cancelled) {
            navigate(`/session/${stored}`, { replace: true });
          }
          return;
        }

        // The backend no longer knows it (restarted/expired).
        clearStoredSessionId();
      }

      // 2. Create a new conversation from the saved configuration.
      setStatus("Creating a new customer conversation...");

      if (!pendingStart) {
        pendingStart = startSession(readStoredConfig()).finally(() => {
          pendingStart = null;
        });
      }

      const data = await pendingStart;

      if (cancelled) {
        return;
      }

      if (!data?.session_id) {
        throw new Error(
          "The backend did not return a session id for the new conversation."
        );
      }

      navigate(`/session/${data.session_id}`, { replace: true });
    }

    openTask6Session().catch((err) => {
      if (cancelled) {
        return;
      }

      console.error("Unable to open a Task 6 session:", err);

      setError(
        err.response?.data?.detail ||
          err.message ||
          "Unable to start a Task 6 session."
      );
    });

    return () => {
      cancelled = true;
    };
  }, [navigate, attempt]);

  if (error) {
    return (
      <div className="config-page">
        <header className="config-header">
          <div>
            <h2>SupportAI</h2>
            <span>Task 6 - Customer Support Simulator</span>
          </div>
        </header>

        <main className="config-content">
          <div className="config-title">
            <h1>Task 6 is not reachable</h1>
            <p>
              The customer-simulator backend did not answer, so a customer
              conversation could not be created.
            </p>
          </div>

          <div className="config-card">
            <div className="error-message">{error}</div>

            <p className="setup-hint">
              Start the backend and try again:
            </p>

            <pre className="setup-command">
              cd customer_simulator{"\n"}
              python -m uvicorn api:app --host 127.0.0.1 --port 8000
            </pre>

            <div className="config-actions">
              <button
                type="button"
                className="cancel-button"
                onClick={() => navigate("/session/new")}
              >
                Open configuration
              </button>

              <button
                type="button"
                className="primary-button"
                onClick={() => setAttempt((value) => value + 1)}
              >
                Try again
              </button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="config-page">
      <header className="config-header">
        <div>
          <h2>SupportAI</h2>
          <span>Task 6 - Customer Support Simulator</span>
        </div>
      </header>

      <main className="config-content">
        <div className="console-loading">
          <strong>{status}</strong>
          <p>Preparing the Customer Configuration, AI Analysis and
            Escalation Risk Monitor...</p>
        </div>
      </main>
    </div>
  );
}

export default SessionAutoStart;
