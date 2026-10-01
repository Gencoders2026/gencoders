import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  analyzeSupport,
  getEscalationThreshold,
  setEscalationThreshold,
} from "../services/supportAssistService";

/**
 * Dedicated Task 6 page - "Escalation Risk Monitor".
 *
 * It is a focused view of the Escalation Risk Monitor Agent and uses the
 * EXISTING Task 6 backend (`POST /support/analyze`, `GET|POST
 * /escalation/threshold`) through `supportAssistService`. Nothing here is
 * mocked: every score, level, emotion, sentiment, frustration value and
 * risk factor displayed comes from a real backend response.
 *
 * The risk is recomputed by the backend on every submitted customer reply
 * from that reply plus the whole conversation context, so submitting a
 * new reply updates the score immediately.
 */

// Quick scenarios used to demonstrate the required behaviours
// (normal / frustrated / angry+urgent / repeated complaint / calmer).
const SCENARIOS = [
  {
    key: "neutral",
    label: "A. Normal / neutral",
    message:
      "Hi, could you please tell me the status of my order? " +
      "My order number is 12345.",
    agent: "Of course. I am looking up order 12345 for you now.",
  },
  {
    key: "frustrated",
    label: "B. Negative / frustrated",
    message:
      "This is really frustrating. My order still has not arrived " +
      "and I have been waiting a long time.",
    agent: "I am sorry about the delay. I am checking the tracking now.",
  },
  {
    key: "angry",
    label: "C. Angry + urgent",
    message:
      "This is completely unacceptable! I demand a supervisor right now. " +
      "Fix it immediately or I am cancelling my account.",
    agent:
      "I understand your frustration. I am escalating this to my supervisor.",
  },
  {
    key: "repeat",
    label: "D. Repeated complaint",
    message:
      "I contacted support twice already and nobody has helped me. " +
      "My refund is still not resolved.",
    agent: "I am sorry about that. I am reviewing your previous contacts.",
  },
  {
    key: "calmer",
    label: "E. Calmer after angry",
    message: "Okay, I understand. Thank you for the update.",
    agent: "Thank you for your patience. Your refund has been processed.",
  },
];

const STORAGE_KEY = "task6.monitorSessionId";

function readOrCreateSessionId() {
  let id;

  try {
    id = window.sessionStorage.getItem(STORAGE_KEY);
  } catch {
    id = null;
  }

  if (!id) {
    id = `task6-monitor-${Date.now().toString(36)}`;

    try {
      window.sessionStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* storage unavailable - the in-memory id is used instead */
    }
  }

  return id;
}

function levelClass(level) {
  return String(level || "Low").toLowerCase();
}

/**
 * Dedicated Task 6 - Escalation Risk Monitor screen.
 *
 * Left  : the customer conversation (real replies, submitted to the real
 *         Task 6 backend).
 * Right : the escalation risk result produced by the Escalation Risk
 *         Monitor Agent for the LATEST customer reply.
 */
function Task6EscalationRiskMonitor() {
  const navigate = useNavigate();

  const [sessionId] = useState(readOrCreateSessionId);
  const [history, setHistory] = useState([]);
  const [reply, setReply] = useState("");
  const [agentNote, setAgentNote] = useState("");

  const [analysis, setAnalysis] = useState(null);
  const [scoreTrail, setScoreTrail] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [threshold, setThreshold] = useState(null);
  const [thresholdInput, setThresholdInput] = useState("");
  const [thresholdSaving, setThresholdSaving] = useState(false);

  const requestRef = useRef(0);

  // Read the configurable alert threshold from the backend on mount.
  useEffect(() => {
    let cancelled = false;

    async function loadThreshold() {
      try {
        const data = await getEscalationThreshold();

        if (!cancelled) {
          setThreshold(data.threshold);
          setThresholdInput(String(data.threshold));
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err.response?.data?.detail ||
              err.message ||
              "Unable to reach the Task 6 backend."
          );
        }
      }
    }

    loadThreshold();

    return () => {
      cancelled = true;
    };
  }, []);

  /**
   * Submit a NEW customer reply to the real Task 6 pipeline.
   *
   * The backend recomputes the escalation risk from this reply plus the
   * full conversation context, so the displayed score/level/indicators
   * change on every submission - it is never a fixed value.
   */
  const submitReply = async (text) => {
    // `submitReply()` (the button) falls back to the typed reply; an
    // explicit argument (quick scenarios) still takes precedence. Reading
    // the argument alone made the button a no-op: the guard always saw "".
    const customerText = (text ?? reply).trim();

    if (!customerText) {
      setError("Type a customer reply first.");
      return;
    }

    const nextHistory = [
      ...history,
      { role: "customer", content: customerText },
    ];

    // The optional agent note is context only - the monitor never scores it.
    const nextHistoryWithAgent = agentNote.trim()
      ? [...nextHistory, { role: "agent", content: agentNote.trim() }]
      : nextHistory;

    const requestId = requestRef.current + 1;
    requestRef.current = requestId;

    setLoading(true);
    setError("");

    try {
      const data = await analyzeSupport(
        customerText,
        sessionId,
        nextHistory.filter((item) => item.role === "customer").length,
        null,
        nextHistoryWithAgent
      );

      // Ignore out-of-order responses so the UI never shows a stale score.
      if (requestRef.current !== requestId) {
        return;
      }

      setAnalysis(data);
      setHistory(nextHistoryWithAgent);
      setScoreTrail((trail) => [
        ...trail,
        {
          turn: data.turn,
          score: data.escalation_score,
          level: data.escalation_level,
          trend: data.escalation_trend,
          message: customerText,
        },
      ]);
      setReply("");
      setAgentNote("");
    } catch (err) {
      if (requestRef.current !== requestId) {
        return;
      }

      setError(
        err.response?.data?.detail ||
          err.message ||
          "Unable to assess the escalation risk."
      );
    } finally {
      if (requestRef.current === requestId) {
        setLoading(false);
      }
    }
  };

  const handleSaveThreshold = async () => {
    const value = Number(thresholdInput);

    if (Number.isNaN(value) || value < 0 || value > 100) {
      setError("The alert threshold must be a number between 0 and 100.");
      return;
    }

    setThresholdSaving(true);
    setError("");

    try {
      const data = await setEscalationThreshold(value);
      setThreshold(data.threshold);
      setThresholdInput(String(data.threshold));
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Unable to update the alert threshold."
      );
    } finally {
      setThresholdSaving(false);
    }
  };

  const handleReset = () => {
    requestRef.current += 1;
    setHistory([]);
    setScoreTrail([]);
    setAnalysis(null);
    setReply("");
    setAgentNote("");
    setError("");
  };

  const handleScenario = (scenario) => {
    setReply(scenario.message);
    setAgentNote(scenario.agent);
  };

  const riskLevel = analysis?.escalation_level || "Low";
  const riskScore = analysis?.escalation_score ?? 0;
  const isAlerting = Boolean(analysis?.alert?.triggered);


  return (
    <div className="task6-page">

      <header className="task6-header">
        <div>
          <h1>Task 6 - Escalation Risk Monitor</h1>
          <p>
            Live escalation-risk scoring from the real customer reply and
            conversation context (Escalation Risk Monitor Agent).
          </p>
        </div>

        <div className="task6-header-actions">
          <button type="button" onClick={() => navigate("/")}>
            Support Console
          </button>

          <button
            type="button"
            onClick={handleReset}
            disabled={history.length === 0}
          >
            Reset conversation
          </button>
        </div>
      </header>

      <main className="task6-content">

        {error && <div className="task6-error">{error}</div>}

        <div className="task6-grid">

          {/* ==============================================
              LEFT: CUSTOMER CONVERSATION
          ============================================== */}

          <section className="task6-panel">

            <h2>Customer conversation</h2>

            <p className="task6-hint">
              Submit the customer&apos;s ACTUAL reply. The escalation risk
              is recalculated from this text plus the conversation history
              on every submission.
            </p>

            <div className="task6-scenarios">
              {SCENARIOS.map((scenario) => (
                <button
                  type="button"
                  key={scenario.key}
                  onClick={() => handleScenario(scenario)}
                >
                  {scenario.label}
                </button>
              ))}
            </div>

            <div className="task6-transcript">
              {history.length === 0 ? (
                <p className="task6-empty">
                  No customer reply yet. The risk score appears after the
                  first reply.
                </p>
              ) : (
                history.map((item, index) => (
                  <div key={index} className={`task6-bubble ${item.role}`}>
                    <span className="task6-bubble-role">
                      {item.role === "customer" ? "Customer" : "Agent"}
                    </span>

                    <p>{item.content}</p>
                  </div>
                ))
              )}
            </div>

            <label className="task6-label" htmlFor="task6-reply">
              New customer reply
            </label>

            <textarea
              id="task6-reply"
              className="task6-textarea"
              rows={4}
              value={reply}
              placeholder={
                "e.g. This is completely unacceptable! " +
                "I demand a supervisor right now."
              }
              onChange={(event) => setReply(event.target.value)}
            />

            <label className="task6-label" htmlFor="task6-agent-note">
              Agent reply (optional, context only)
            </label>

            <input
              id="task6-agent-note"
              className="task6-input"
              type="text"
              value={agentNote}
              placeholder="e.g. I am checking this for you right now."
              onChange={(event) => setAgentNote(event.target.value)}
            />

            <div className="task6-actions">
              <button
                type="button"
                className="task6-primary"
                onClick={() => submitReply()}
                disabled={loading}
              >
                {loading ? "Assessing..." : "Assess escalation risk"}
              </button>
            </div>
          </section>


          {/* ==============================================
              RIGHT: ESCALATION RISK RESULT
          ============================================== */}

          <section className="task6-panel">

            <h2>Escalation risk</h2>

            {loading && !analysis ? (
              <p className="task6-empty">
                Assessing escalation risk...
              </p>
            ) : !analysis ? (
              <p className="task6-empty">
                No risk assessment yet. Submit a customer reply to run the
                Escalation Risk Monitor.
              </p>
            ) : (
              <>

                {isAlerting && analysis.alert && (
                  <div
                    className={`alert-banner ${
                      riskLevel === "Critical" ? "" : "high"
                    }`}
                  >
                    <div className="alert-banner-header">
                      <strong>Escalation alert</strong>

                      <span>Threshold: {analysis.alert_threshold}</span>
                    </div>

                    <p>{analysis.alert.message}</p>

                    {analysis.recommended_actions?.length > 0 && (
                      <div className="alert-actions">
                        <strong>Recommended actions:</strong>

                        <ul>
                          {analysis.recommended_actions.map(
                            (action, index) => (
                              <li key={index}>{action}</li>
                            )
                          )}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                <div className="knowledge-card escalation-card">
                  <div className="risk-row">
                    <span className={`risk-badge ${levelClass(riskLevel)}`}>
                      {riskLevel}
                    </span>

                    <span className="risk-score">{riskScore}/100</span>
                  </div>

                  <div className="risk-score-bar">
                    <div
                      className={`risk-score-fill ${levelClass(riskLevel)}`}
                      style={{ width: `${riskScore}%` }}
                    />
                  </div>

                  <p className="risk-meta">
                    Trend: {analysis.escalation_trend || "unknown"} · Turn{" "}
                    {analysis.turn ?? 1}
                  </p>

                  <p className="risk-meta">
                    Negative Streak: {analysis.negative_streak ?? 0}
                  </p>
                </div>

                <div className="task6-stats">
                  <div className="knowledge-card">
                    <h4>Emotion</h4>
                    <p>{analysis.emotion}</p>
                  </div>

                  <div className="knowledge-card">
                    <h4>Frustration</h4>
                    <p>{analysis.frustration_level}/10</p>
                  </div>

                  <div className="knowledge-card">
                    <h4>Sentiment</h4>
                    <p>{analysis.sentiment}</p>
                  </div>

                  <div className="knowledge-card">
                    <h4>Urgency</h4>
                    <p>
                      {analysis.unaddressed_pressure
                        ? "Urgent - issue still open"
                        : "No urgent pressure"}
                    </p>
                  </div>

                  <div className="knowledge-card">
                    <h4>Intent</h4>
                    <p>{analysis.intent}</p>
                  </div>

                  <div className="knowledge-card">
                    <h4>Satisfaction</h4>
                    <p>{analysis.satisfaction_trend}</p>
                  </div>
                </div>


                <div className="knowledge-card">
                  <h4>Risk factors</h4>

                  {analysis.escalation_indicators?.length > 0 ? (
                    <>
                      <div className="indicator-chips">
                        {analysis.escalation_indicators.map(
                          (indicator, index) => (
                            <span
                              className="indicator-chip"
                              key={index}
                              title={indicator.matched_phrase}
                            >
                              {indicator.name.replace(/_/g, " ")}{" "}
                              +{indicator.points}
                            </span>
                          )
                        )}
                      </div>

                      {analysis.escalation_reasoning?.length > 0 && (
                        <div className="reasoning-list">
                          <strong>Why this score:</strong>

                          <ul>
                            {analysis.escalation_reasoning.map(
                              (reason, index) => (
                                <li key={index}>{reason}</li>
                              )
                            )}
                          </ul>
                        </div>
                      )}
                    </>
                  ) : (
                    <p>No escalation indicators in this reply.</p>
                  )}
                </div>

                {analysis.suggested_response && (
                  <div className="knowledge-card suggestion-card">
                    <h4>Suggested response</h4>

                    <div className="suggestion-text">
                      {analysis.suggested_response}
                    </div>
                  </div>
                )}
              </>
            )}

            {scoreTrail.length > 1 && (
              <div className="knowledge-card">
                <h4>Risk movement per reply</h4>

                <ul className="task6-trail">
                  {scoreTrail.map((entry, index) => (
                    <li key={index}>
                      <span
                        className={`risk-badge ${levelClass(entry.level)}`}
                      >
                        {entry.level}
                      </span>

                      <span className="task6-trail-score">
                        {entry.score}/100
                      </span>

                      <span className="task6-trail-trend">
                        {entry.trend}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="knowledge-card threshold-control">
              <label htmlFor="task6-threshold">Alert threshold</label>

              <div className="threshold-row">
                <input
                  id="task6-threshold"
                  type="number"
                  min="0"
                  max="100"
                  value={thresholdInput}
                  onChange={(event) =>
                    setThresholdInput(event.target.value)
                  }
                />

                <button
                  type="button"
                  onClick={handleSaveThreshold}
                  disabled={thresholdSaving}
                >
                  {thresholdSaving ? "Saving..." : "Save"}
                </button>
              </div>

              <small>
                Current: {threshold ?? "-"} (0-100). Alerts fire when the
                risk score reaches this value.
              </small>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

export default Task6EscalationRiskMonitor;

