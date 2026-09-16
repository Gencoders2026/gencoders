import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  getSession,
  getSessionLog,
} from "../services/sessionService";

function SessionResult() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadSession() {
      try {
        setLoading(true);
        setError("");

        let data;

        // First try the active session endpoint.
        try {
          data = await getSession(sessionId);
        } catch (sessionError) {
          // Completed sessions are removed from active memory.
          // Therefore, load the persisted session log.
          console.log(
            "Active session not found. Loading saved session log..."
          );

          data = await getSessionLog(sessionId);
        }

        setSession(data);
        localStorage.setItem(
        `supportai_session_${sessionId}`,
        JSON.stringify(data)
        );
      } catch (err) {
        console.error("Failed to load session result:", err);

        setError(
          err.response?.data?.detail ||
            "Unable to load the session result."
        );
      } finally {
        setLoading(false);
      }
    }

    if (sessionId) {
      loadSession();
    }
  }, [sessionId]);

  // Loading state
  if (loading) {
    return (
      <div className="result-page">
        <div className="result-container">
          <h1>Session Result</h1>
          <p>Loading session results...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="result-page">
        <div className="result-container">
          <h1>Session Result</h1>

          <div className="result-error">
            {error}
          </div>

          <button onClick={() => navigate("/")}>
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  /*
   * The backend returns saved logs in this structure:
   *
   * {
   *   meta: {
   *     session_id,
   *     started_at,
   *     ended_at,
   *     config: {...},
   *     final_emotion: {...},
   *     turn_count
   *   },
   *   conversation: [...]
   * }
   */

  const meta = session?.meta || {};
  const config = meta?.config || {};
  const emotion = meta?.final_emotion || {};
  const conversation = session?.conversation || [];

  const persona = config?.persona || session?.persona || "N/A";
  const scenario = config?.scenario || session?.scenario || "N/A";

  const turnCount =
    meta?.turn_count ??
    session?.turn_count ??
    conversation.length ??
    0;

  const frustrationLevel =
    emotion?.intensity ??
    session?.frustration_level ??
    0;

  const emotionLabel =
    emotion?.label || "Unknown";

  const sessionFinished =
    Boolean(meta?.ended_at) ||
    Boolean(session?.finished);

  // Format scenario/persona labels
  const formatLabel = (value) => {
    if (!value || value === "N/A") {
      return "N/A";
    }

    return value
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  // Format timestamp
  const formatDateTime = (value) => {
    if (!value) {
      return "N/A";
    }

    try {
      return new Date(value).toLocaleString();
    } catch {
      return value;
    }
  };

  return (
    <div className="result-page">
      <div className="result-container">

        {/* ================= HEADER ================= */}

        <div className="result-header">
          <div>
            <h1>Session Result</h1>
            <p>
              Post-interaction performance report
            </p>
          </div>

          <div className="result-status">
            {sessionFinished
              ? "Completed"
              : "In Progress"}
          </div>
        </div>

        {/* ================= SESSION DETAILS ================= */}

        <div className="result-grid">

          <div className="result-card">
            <h3>Session Details</h3>

            <div className="result-row">
              <span>Session ID</span>

              <strong>
                {meta?.session_id || sessionId}
              </strong>
            </div>

            <div className="result-row">
              <span>Customer Persona</span>

              <strong>
                {formatLabel(persona)}
              </strong>
            </div>

            <div className="result-row">
              <span>Scenario</span>

              <strong>
                {formatLabel(scenario)}
              </strong>
            </div>

            <div className="result-row">
              <span>Total Turns</span>

              <strong>
                {turnCount}
              </strong>
            </div>

            <div className="result-row">
              <span>Started At</span>

              <strong>
                {formatDateTime(meta?.started_at)}
              </strong>
            </div>

            <div className="result-row">
              <span>Ended At</span>

              <strong>
                {formatDateTime(meta?.ended_at)}
              </strong>
            </div>
          </div>

          {/* ================= CUSTOMER EMOTION ================= */}

          <div className="result-card">
            <h3>Customer Emotion</h3>

            <div className="emotion-value">
              {formatLabel(emotionLabel)}
            </div>

            <div className="result-row">
              <span>Final Intensity</span>

              <strong>
                {frustrationLevel} / 10
              </strong>
            </div>

            <div className="result-row">
              <span>Frustration Level</span>

              <strong>
                {frustrationLevel} / 10
              </strong>
            </div>

            <div className="result-row">
              <span>Expected Resolution</span>

              <strong>
                {formatLabel(
                  config?.expected_resolution
                )}
              </strong>
            </div>

            <div className="result-row">
              <span>Issue Severity</span>

              <strong>
                {config?.issue_severity ?? "N/A"}
              </strong>
            </div>
          </div>
        </div>

        {/* ================= CONVERSATION ================= */}

        <div className="result-card conversation-card">
          <h3>Conversation Summary</h3>

          {conversation.length === 0 ? (
            <p>
              No conversation history available.
            </p>
          ) : (
            <div className="conversation-history">

              {conversation.map((message, index) => {

                const isAgent =
                  message?.role === "agent";

                return (
                  <div
                    key={`${message?.turn || index}-${index}`}
                    className={`history-message ${
                      isAgent
                        ? "agent-message"
                        : "customer-message"
                    }`}
                  >

                    <div className="history-role">
                      {isAgent
                        ? "You"
                        : "Customer"}
                    </div>

                    <div className="history-text">
                      {message?.message || ""}
                    </div>

                    {message?.timestamp && (
                      <div
                        style={{
                          marginTop: "6px",
                          fontSize: "12px",
                          opacity: 0.6,
                        }}
                      >
                        {formatDateTime(
                          message.timestamp
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

            </div>
          )}
        </div>

        {/* ================= EMOTION HISTORY ================= */}

        {emotion?.history?.length > 0 && (
          <div className="result-card">
            <h3>Emotion Progression</h3>

            <div className="conversation-history">

              {emotion.history.map(
                (item, index) => (
                  <div
                    key={index}
                    className="history-message"
                  >
                    {item}
                  </div>
                )
              )}

            </div>
          </div>
        )}

        {/* ================= ACTIONS ================= */}

        <div className="result-actions">

          <button
            onClick={() =>
              navigate("/session/new")
            }
          >
            Start New Session
          </button>

          <button
            className="secondary-button"
            onClick={() =>
              navigate("/analytics")
            }
          >
            View Analytics
          </button>

          <button
            className="secondary-button"
            onClick={() =>
              navigate("/")
            }
          >
            Dashboard
          </button>

        </div>

      </div>
    </div>
  );
}

export default SessionResult;