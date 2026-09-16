import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

function Analytics() {
  const navigate = useNavigate();

  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    const storedSessions = [];

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);

      if (key && key.startsWith("supportai_session_")) {
        try {
          const session = JSON.parse(
            localStorage.getItem(key)
          );

          if (session) {
            storedSessions.push(session);
          }
        } catch (error) {
          console.error(
            "Unable to read stored session:",
            error
          );
        }
      }
    }

    setSessions(storedSessions);
  }, []);

  const getMeta = (session) => session?.meta || {};

  const getConfig = (session) =>
    getMeta(session)?.config || {};

  const getEmotion = (session) =>
    getMeta(session)?.final_emotion || {};

  const getConversation = (session) =>
    session?.conversation || [];

  const getTurnCount = (session) =>
    getMeta(session)?.turn_count ??
    getConversation(session).length ??
    0;

  const getFrustration = (session) =>
    getEmotion(session)?.intensity ?? 0;

  const getPersona = (session) =>
    getConfig(session)?.persona || "Unknown";

  const getScenario = (session) =>
    getConfig(session)?.scenario || "Unknown";

  const formatLabel = (value) => {
    if (!value) {
      return "Unknown";
    }

    return String(value)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) =>
        char.toUpperCase()
      );
  };

  const totalSessions = sessions.length;

  const completedSessions = sessions.filter(
    (session) =>
      Boolean(getMeta(session)?.ended_at)
  ).length;

  const averageFrustration =
    totalSessions > 0
      ? (
          sessions.reduce(
            (total, session) =>
              total + getFrustration(session),
            0
          ) / totalSessions
        ).toFixed(1)
      : "0.0";

  const averageTurns =
    totalSessions > 0
      ? (
          sessions.reduce(
            (total, session) =>
              total + getTurnCount(session),
            0
          ) / totalSessions
        ).toFixed(1)
      : "0.0";

  const getPerformanceLabel = (frustration) => {
    if (frustration <= 3) {
      return "Excellent";
    }

    if (frustration <= 5) {
      return "Good";
    }

    if (frustration <= 7) {
      return "Needs Improvement";
    }

    return "High Escalation Risk";
  };

  return (
    <div className="analytics-page">
      <div className="analytics-container">

        {/* Header */}
        <div className="analytics-header">
          <div>
            <h1>Performance Analytics</h1>

            <p>
              Review customer interactions,
              emotional trends, and session performance.
            </p>
          </div>

          <button
            className="analytics-back-button"
            onClick={() => navigate("/")}
          >
            Dashboard
          </button>
        </div>

        {/* Summary Cards */}
        <div className="analytics-stats">

          <div className="analytics-stat-card">
            <span>Total Sessions</span>
            <strong>{totalSessions}</strong>
            <small>
              Completed sessions recorded
            </small>
          </div>

          <div className="analytics-stat-card">
            <span>Completed</span>
            <strong>{completedSessions}</strong>
            <small>
              Successfully finished sessions
            </small>
          </div>

          <div className="analytics-stat-card">
            <span>Avg. Frustration</span>
            <strong>
              {averageFrustration}/10
            </strong>
            <small>
              Final customer frustration
            </small>
          </div>

          <div className="analytics-stat-card">
            <span>Avg. Turns</span>
            <strong>{averageTurns}</strong>
            <small>
              Conversation turns per session
            </small>
          </div>

        </div>

        {/* Performance Overview */}
        <div className="analytics-card">

          <h2>Performance Overview</h2>

          {sessions.length === 0 ? (
            <div className="analytics-empty">
              <h3>No completed sessions yet</h3>

              <p>
                Complete a support session to see
                real performance analytics here.
              </p>

              <button
                onClick={() =>
                  navigate("/session/new")
                }
              >
                Start New Session
              </button>
            </div>
          ) : (
            <div className="performance-list">

              {sessions.map((session, index) => {
                const frustration =
                  getFrustration(session);

                return (
                  <div
                    className="performance-item"
                    key={
                      getMeta(session)?.session_id ||
                      index
                    }
                  >

                    <div className="performance-info">

                      <strong>
                        {formatLabel(
                          getScenario(session)
                        )}
                      </strong>

                      <span>
                        {formatLabel(
                          getPersona(session)
                        )}
                      </span>

                    </div>

                    <div className="performance-bar-container">

                      <div
                        className="performance-bar"
                        style={{
                          width: `${Math.max(
                            5,
                            100 -
                              frustration * 10
                          )}%`,
                        }}
                      />

                    </div>

                    <div className="performance-score">
                      {getPerformanceLabel(
                        frustration
                      )}
                    </div>

                  </div>
                );
              })}

            </div>
          )}

        </div>

        {/* Session History */}
        <div className="analytics-card">

          <div className="analytics-section-header">
            <div>
              <h2>Session History</h2>

              <p>
                Recent customer support training sessions.
              </p>
            </div>

            <button
              onClick={() =>
                navigate("/session/new")
              }
            >
              + New Session
            </button>
          </div>

          {sessions.length === 0 ? (
            <div className="analytics-empty-small">
              No session history available.
            </div>
          ) : (
            <div className="analytics-table">

              <div className="analytics-table-header">
                <span>Scenario</span>
                <span>Persona</span>
                <span>Turns</span>
                <span>Emotion</span>
                <span>Status</span>
              </div>

              {sessions.map((session, index) => {

                const emotion =
                  getEmotion(session);

                return (
                  <div
                    className="analytics-table-row"
                    key={
                      getMeta(session)?.session_id ||
                      index
                    }
                  >

                    <span>
                      {formatLabel(
                        getScenario(session)
                      )}
                    </span>

                    <span>
                      {formatLabel(
                        getPersona(session)
                      )}
                    </span>

                    <span>
                      {getTurnCount(session)}
                    </span>

                    <span>
                      {formatLabel(
                        emotion?.label
                      )}{" "}
                      ({emotion?.intensity ?? 0}/10)
                    </span>

                    <span className="status-completed">
                      Completed
                    </span>

                  </div>
                );
              })}

            </div>
          )}

        </div>

        {/* Insights */}
        {sessions.length > 0 && (
          <div className="analytics-card">

            <h2>AI Coaching Insights</h2>

            <div className="insight-grid">

              <div className="insight-item">
                <strong>
                  Customer Handling
                </strong>

                <p>
                  Monitor customer frustration
                  throughout the conversation and
                  use empathy before providing
                  resolution steps.
                </p>
              </div>

              <div className="insight-item">
                <strong>
                  Resolution Focus
                </strong>

                <p>
                  Customers with higher frustration
                  levels benefit from clear next
                  steps and realistic timelines.
                </p>
              </div>

              <div className="insight-item">
                <strong>
                  Conversation Quality
                </strong>

                <p>
                  Keep responses concise, acknowledge
                  concerns, and provide actionable
                  information.
                </p>
              </div>

            </div>

          </div>
        )}

      </div>
    </div>
  );
}

export default Analytics;