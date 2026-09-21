import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  getSession,
  getSessionLog,
  sendMessage,
  endSession,
} from "../services/sessionService";

import {
  analyzeSupport,
  evaluateResponse,
  getEscalationThreshold,
  setEscalationThreshold,
} from "../services/supportAssistService";

function SupportConsole() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  // AI analysis + RAG results
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // Task 6: escalation threshold configuration
  const [threshold, setThreshold] = useState(null);
  const [thresholdInput, setThresholdInput] = useState("");
  const [thresholdSaving, setThresholdSaving] = useState(false);

  // Task 6: draft response evaluation
  const [draftEvaluation, setDraftEvaluation] = useState(null);
  const [checkingDraft, setCheckingDraft] = useState(false);

  // ==========================================================
  // LOAD CURRENT ESCALATION THRESHOLD
  // ==========================================================
  useEffect(() => {
    getEscalationThreshold()
      .then((data) => {
        setThreshold(data.threshold);
        setThresholdInput(String(data.threshold));
      })
      .catch(() => {
        /* threshold control is optional */
      });
  }, []);

  // ==========================================================
  // USE THE AI-SUGGESTED RESPONSE
  // ==========================================================
  const handleUseSuggestion = (text) => {
    setMessage(text);
    setDraftEvaluation(null);
  };

  // ==========================================================
  // EVALUATE THE AGENT'S DRAFT BEFORE SENDING
  // ==========================================================
  const handleCheckDraft = async () => {
    if (!message.trim() || checkingDraft) {
      return;
    }

    setCheckingDraft(true);
    setDraftEvaluation(null);

    try {
      const result = await evaluateResponse(message.trim());
      setDraftEvaluation(result);
    } catch (err) {
      console.error("Failed to evaluate draft:", err);
    } finally {
      setCheckingDraft(false);
    }
  };

  // ==========================================================
  // UPDATE THE ESCALATION ALERT THRESHOLD
  // ==========================================================
  const handleSaveThreshold = async () => {
    const value = Number(thresholdInput);

    if (Number.isNaN(value) || value < 0 || value > 100) {
      return;
    }

    setThresholdSaving(true);

    try {
      const result = await setEscalationThreshold(value);
      setThreshold(result.threshold);
    } catch (err) {
      console.error("Failed to update threshold:", err);
    } finally {
      setThresholdSaving(false);
    }
  };

  // ==========================================================
  // LOAD SESSION
  // ==========================================================
  useEffect(() => {
    async function loadSession() {
      try {
        const data = await getSession(sessionId);

        setSession(data);

        // If the backend says the session is already finished,
        // open the result page instead of keeping the user
        // inside the active support console.
        if (data.finished) {
          navigate(`/session/${sessionId}/result`, {
            replace: true,
          });
          return;
        }

        // Analyze the latest customer message when the session loads
        const history = data.history || [];

        const latestCustomerMessage = [...history]
          .reverse()
          .find((item) => item.role === "customer");

        if (latestCustomerMessage?.content) {
          try {
            setAnalysisLoading(true);

            // Task 6: full support-assistance pipeline
            // (intent/sentiment + knowledge + coaching + escalation).
            // `query` is ALWAYS the latest CUSTOMER message; the full
            // role-tagged history is passed so repeat/streak signals
            // use customer context only.
            const customerTurn =
              history.filter((item) => item.role === "customer").length ||
              1;

            const analysisData = await analyzeSupport(
              latestCustomerMessage.content,
              sessionId,
              customerTurn,
              null,
              history.map((item) => ({
                role: item.role,
                content: item.content,
              }))
            );

            setAnalysis(analysisData);
            // Mirror the analysed customer state into the console
            // status area: the UI always shows the latest CUSTOMER
            // analysis, never the agent draft or reply.
            setSession((previous) => ({
              ...previous,
              emotion: {
                label:
                  analysisData.emotion_label || analysisData.emotion,
                intensity:
                  analysisData.frustration_level ??
                  analysisData.frustration_score ??
                  null,
              },
            }));
          } catch (analysisError) {
            console.error(
              "Failed to analyze initial customer message:",
              analysisError
            );
          } finally {
            setAnalysisLoading(false);
          }
        }
      } catch (err) {
        console.error("Failed to load active session:", err);

        // ------------------------------------------------------
        // The active session may already be completed and removed
        // from the backend's in-memory SESSIONS dictionary.
        //
        // In that case, load the saved log instead.
        // ------------------------------------------------------
        try {
          const logData = await getSessionLog(sessionId);

          const history =
            logData.history ||
            (logData.conversation || []).map((item) => ({
              role: item.role,
              content: item.message || item.content || "",
              frustration_level:
                item.emotion?.frustration_level ?? null,
              emotion: item.emotion?.label || null,
            }));

          const completedSession = {
            ...logData,
            session_id: logData.session_id || sessionId,
            persona:
              logData.persona ||
              logData.meta?.config?.persona ||
              "",
            scenario:
              logData.scenario ||
              logData.meta?.config?.scenario ||
              "",
            frustration_level:
              logData.frustration_level ??
              logData.meta?.config?.frustration_level ??
              5,
            turn_count:
              logData.turn_count ??
              logData.meta?.turn_count ??
              history.length,
            emotion:
              logData.meta?.final_emotion
                ? {
                    label:
                      logData.meta.final_emotion.label ||
                      "Unknown",
                    intensity:
                      logData.meta.final_emotion.frustration_level ??
                      0,
                  }
                : null,
            finished: Boolean(
              logData.finished || logData.meta?.finished
            ),
            history,
          };

          setSession(completedSession);

          // If this is a completed saved session, show the result.
          if (completedSession.finished) {
            navigate(`/session/${sessionId}/result`, {
              replace: true,
            });
            return;
          }
        } catch (logError) {
          console.error(
            "Failed to load saved session log:",
            logError
          );

          setError("Unable to load this session.");
        }
      } finally {
        setLoading(false);
      }
    }

    loadSession();
  }, [sessionId, navigate]);

  // ==========================================================
  // SEND AGENT RESPONSE
  // ==========================================================
  const handleSend = async (event) => {
    event.preventDefault();

    if (!message.trim() || sending) {
      return;
    }

    const agentMessage = message.trim();

    setSending(true);
    setError("");

    try {
      // --------------------------------------------------
      // 1. Send agent response to Customer Simulator
      // --------------------------------------------------
      const data = await sendMessage(
        sessionId,
        agentMessage
      );

      // --------------------------------------------------
      // 2. Add agent response + customer response
      //    to the conversation
      // --------------------------------------------------
      setSession((previous) => ({
        ...previous,
        turn_count: data.turn,
        // IMPORTANT (Task 6 correction): `data.emotion` is the
        // simulator's post-reply customer state estimate, NOT the
        // analysed customer state. The UI always shows the
        // analysis state (emotion, frustration, sentiment, risk)
        // of the latest CUSTOMER message from `/support/analyze`
        // below, so keep the previous emotion here and let the
        // fresh customer analysis overwrite it.
        finished: data.finished,
        history: [
          ...(previous?.history || []),
          {
            role: "agent",
            content: agentMessage,
          },
          {
            role: "customer",
            content: data.customer_message,
            // NOTE (Task 6 correction): these per-message simulator
            // values are informational only. The displayed customer
            // analysis ALWAYS comes from `/support/analyze` applied
            // to the latest CUSTOMER message below — never from the
            // agent reply or the simulator's reply-time estimate.
            frustration_level:
              data.emotion?.intensity ??
              data.emotion?.frustration_level ??
              null,
            emotion:
              data.emotion?.label ||
              data.emotion?.emotion ||
              null,
          },
        ],
      }));

      setMessage("");

      // --------------------------------------------------
      // 3. IMPORTANT:
      // If the simulator has completed the conversation,
      // immediately go to the Session Result page.
      // --------------------------------------------------
      if (data.finished) {
        navigate(`/session/${sessionId}/result`, {
          replace: true,
        });

        return;
      }

      // --------------------------------------------------
      // 4. Run the Task 6 support-assistance pipeline on
      //    the CUSTOMER'S new message (escalation risk is
      //    recalculated after every customer message).
      //    NEVER send the agent's own reply here: the backend
      //    analyses only what the customer wrote.
      // --------------------------------------------------
      try {
        setAnalysisLoading(true);

        const customerTurnCount =
          (session?.history || []).filter(
            (item) => item.role === "customer"
          ).length + 1;

        const updatedHistory = [
          ...(session?.history || []),
          { role: "agent", content: agentMessage },
          { role: "customer", content: data.customer_message },
        ];

        const analysisData = await analyzeSupport(
          data.customer_message,
          sessionId,
          customerTurnCount,
          null,
          updatedHistory
        );

        // Only accept analyses that match the customer message we
        // asked about; stale async responses must not overwrite.
        setAnalysis((previous) => {
          if (
            previous &&
            previous.customer_message &&
            previous.customer_message !== data.customer_message &&
            (analysisData.customer_message || "") !==
              data.customer_message
          ) {
            return previous;
          }
          return analysisData;
        });
        setSession((previous) => ({
          ...previous,
          // Mirror the analysed customer state into the console
          // header/status: always the displayed customer state.
          emotion: {
            label: analysisData.emotion_label || analysisData.emotion,
            intensity:
              analysisData.frustration_level ??
              analysisData.frustration_score ??
              null,
          },
        }));
      } catch (analysisError) {
        console.error(
          "Failed to analyze customer message:",
          analysisError
        );

        // Conversation should continue even if analysis fails
        setAnalysis(null);
      } finally {
        setAnalysisLoading(false);
      }
    } catch (err) {
      console.error("Failed to send message:", err);

      setError(
        err.response?.data?.detail ||
          err.message ||
          "Unable to send your message."
      );
    } finally {
      setSending(false);
    }
  };

  // ==========================================================
  // MANUALLY END SESSION
  // ==========================================================
  const handleEndSession = async () => {
    try {
      await endSession(sessionId);

      navigate(`/session/${sessionId}/result`, {
        replace: true,
      });
    } catch (err) {
      console.error("Failed to end session:", err);

      setError("Unable to end the session.");
    }
  };

  // ==========================================================
  // LOADING
  // ==========================================================
  if (loading) {
    return (
      <div className="console-page">
        <div className="console-loading">
          Loading support session...
        </div>
      </div>
    );
  }

  // ==========================================================
  // ERROR
  // ==========================================================
  if (!session) {
    return (
      <div className="console-page">
        <div className="console-error">
          {error || "Session not found."}
        </div>
      </div>
    );
  }

  // ==========================================================
  // MAIN UI
  // ==========================================================
  return (
    <div className="console-page">

      {/* ==================================================
          HEADER
      ================================================== */}

      <header className="console-header">
        <div>
          <h1>SupportAI</h1>
          <p>Live Support Console</p>
        </div>

        <div className="console-header-actions">
          <span className="session-id">
            Session: {session.session_id}
          </span>

          <button onClick={handleEndSession}>
            End Session
          </button>
        </div>
      </header>

      <main className="console-content">

        {/* ==================================================
            PAGE TITLE
        ================================================== */}

        <div className="console-title">
          <div>
            <h2>Customer Support Session</h2>

            <p>
              Practice handling the customer conversation
              in real time.
            </p>
          </div>

          <div className="session-status">
            <span>
              Turn {session.turn_count}
            </span>

            <span>
              Emotion:{" "}
              {session.emotion?.label || "Unknown"}
            </span>

            <span>
              Intensity:{" "}
              {session.emotion?.intensity ?? "-"}
            </span>
          </div>
        </div>

        {/* ==================================================
            ERROR
        ================================================== */}

        {error && (
          <div className="console-error">
            {typeof error === "string"
              ? error
              : "Something went wrong."}
          </div>
        )}

        {/* ==================================================
            ESCALATION ALERT (Task 6)
        ================================================== */}

        {analysis?.alert?.triggered && (
          <div
            className={`alert-banner ${
              analysis.alert.level === "Critical"
                ? "critical"
                : "high"
            }`}
          >
            <div className="alert-banner-header">
              <strong>
                🚨 Escalation Alert —{" "}
                {analysis.alert.level} Risk (
                {analysis.escalation_score}/100)
              </strong>

              <span>
                Threshold: {analysis.alert.threshold}
              </span>
            </div>

            <p>{analysis.alert.message}</p>

            {analysis.recommended_actions?.length > 0 && (
              <div className="alert-actions">
                <strong>Recommended actions:</strong>

                <ul>
                  {analysis.recommended_actions.map(
                    (action, index) => (
                      <li key={index}>
                        {action}
                      </li>
                    )
                  )}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* ==================================================
            MAIN GRID
        ================================================== */}

        <section className="console-grid">

          {/* ==================================================
              CONVERSATION PANEL
          ================================================== */}

          <div className="conversation-panel">

            <div className="panel-header">
              <h3>Customer Conversation</h3>

              <span>
                {session.persona} · {session.scenario}
              </span>
            </div>

            <div className="conversation-messages">

              {session.history?.map((item, index) => (
                <div
                  className={`message ${
                    item.role === "customer"
                      ? "customer-message"
                      : "agent-message"
                  }`}
                  key={index}
                >

                  <div className="message-role">
                    {item.role === "customer"
                      ? "Customer"
                      : "You"}
                  </div>

                  <div className="message-content">
                    {item.content}
                  </div>

                </div>
              ))}

            </div>

            <form
              className="message-form"
              onSubmit={handleSend}
            >

              <textarea
                value={message}
                onChange={(event) =>
                  setMessage(event.target.value)
                }
                placeholder="Type your response to the customer..."
                disabled={
                  sending ||
                  session.finished
                }
                rows={4}
              />

              <div className="message-form-actions">
                <button
                  type="button"
                  className="check-draft-button"
                  onClick={handleCheckDraft}
                  disabled={
                    checkingDraft ||
                    !message.trim() ||
                    sending
                  }
                >
                  {checkingDraft
                    ? "Checking..."
                    : "Check my draft"}
                </button>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={
                    sending ||
                    !message.trim() ||
                    session.finished
                  }
                >
                  {sending
                    ? "Sending..."
                    : "Send Response"}
                </button>
              </div>

              {draftEvaluation && (
                <div
                  className={`draft-evaluation ${
                    draftEvaluation.meets_standard
                      ? "pass"
                      : "warn"
                  }`}
                >
                  <strong>
                    Draft check —{" "}
                    {draftEvaluation.overall}/100 ·{" "}
                    {draftEvaluation.summary}
                  </strong>

                  <div className="eval-grid">
                    {[
                      "tone",
                      "clarity",
                      "empathy",
                      "professionalism",
                    ].map((dimension) => {
                      const item =
                        draftEvaluation[dimension];

                      return (
                        <div
                          className="eval-item"
                          key={dimension}
                        >
                          <span className="eval-label">
                            {dimension}{" "}
                            {item?.score ?? "-"}
                          </span>

                          <div className="eval-bar">
                            <div
                              className={`eval-bar-fill ${
                                (item?.score ?? 0) >= 70
                                  ? "good"
                                  : "weak"
                              }`}
                              style={{
                                width: `${item?.score ?? 0}%`,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

            </form>

          </div>

          {/* ==================================================
              AI COACHING PANEL
          ================================================== */}

          <aside className="coaching-panel">

            <div className="panel-header">
              <h3>AI Coaching</h3>
              <span>Real-time feedback</span>
            </div>

            {/* Current Emotion */}

            <div className="coaching-card">
              <h4>Current Emotion</h4>

              <strong>
                {session.emotion?.label || "Unknown"}
              </strong>

              <p>
                Intensity:{" "}
                {session.emotion?.intensity ?? "-"} / 10
              </p>
            </div>

            {/* Conversation Status */}

            <div className="coaching-card">
              <h4>Conversation Status</h4>

              <p>
                {session.finished
                  ? "Session completed"
                  : "Conversation in progress"}
              </p>
            </div>

            {/* ==================================================
                AI ANALYSIS
            ================================================== */}

            <div className="coaching-card">
              <h4>AI Analysis</h4>

              {analysisLoading ? (
                <p>
                  Analyzing customer message...
                </p>
              ) : analysis ? (
                <>
                  {/* Intent */}

                  <p>
                    <strong>Intent:</strong>{" "}
                    {analysis.intent || "Unknown"}
                  </p>

                  {/* Emotion */}

                  <p>
                    <strong>Emotion:</strong>{" "}
                    {analysis.emotion_label ||
                      analysis.emotion ||
                      "Unknown"}
                  </p>

                  {/* Sentiment */}

                  <p>
                    <strong>Sentiment:</strong>{" "}
                    {analysis.sentiment || "Unknown"}
                  </p>

                  {/* Frustration */}

                  <p>
                    <strong>Frustration:</strong>{" "}
                    {analysis.frustration_level ??
                      analysis.emotion_score ??
                      "-"}{" "}
                    / 10
                  </p>

                  {/* Satisfaction Trend */}

                  <p>
                    <strong>
                      Satisfaction Trend:
                    </strong>{" "}
                    {analysis.satisfaction_trend ||
                      "Unknown"}
                  </p>

                  {/* Escalation Risk */}

                  <p>
                    <strong>
                      Escalation Risk:
                    </strong>{" "}
                    {analysis.escalation_risk ||
                      "Unknown"}
                  </p>

                  {/* Confidence */}

                  <p>
                    <strong>Confidence:</strong>{" "}
                    {analysis.confidence !== undefined
                      ? `${(
                          analysis.confidence * 100
                        ).toFixed(0)}%`
                      : "Unknown"}
                  </p>
                </>
              ) : (
                <p>
                  Analysis will appear after a customer
                  response.
                </p>
              )}
            </div>

            {/* ==================================================
                COACHING GUIDANCE
            ================================================== */}

            <div className="coaching-card">
              <h4>Coaching Focus</h4>

              {analysis?.coaching_guidance?.length > 0 ? (
                <ul>
                  {analysis.coaching_guidance.map(
                    (tip, index) => (
                      <li key={index}>
                        {tip}
                      </li>
                    )
                  )}
                </ul>
              ) : (
                <p>
                  Stay calm, acknowledge the customer's
                  concern, and provide a clear next step.
                </p>
              )}
            </div>

            {/* ==================================================
                SUGGESTED RESPONSE (Task 6)
            ================================================== */}

            <div className="coaching-card suggestion-card">
              <h4>Suggested Response</h4>

              {analysisLoading ? (
                <p>Generating suggestion...</p>
              ) : analysis?.suggested_response ? (
                <>
                  <div className="suggestion-text">
                    {analysis.suggested_response}
                  </div>

                  <div className="suggestion-actions">
                    <button
                      type="button"
                      className="use-suggestion-button"
                      onClick={() =>
                        handleUseSuggestion(
                          analysis.suggested_response
                        )
                      }
                    >
                      Use this response
                    </button>
                  </div>

                  {analysis.suggested_responses
                    ?.followup_question && (
                    <p className="suggestion-followup">
                      <strong>Ask next:</strong>{" "}
                      {
                        analysis.suggested_responses
                          .followup_question
                      }
                    </p>
                  )}

                  {analysis.response_evaluation && (
                    <div className="eval-grid">
                      <strong className="eval-title">
                        Quality check —{" "}
                        {analysis.response_evaluation.summary}
                      </strong>

                      {[
                        "tone",
                        "clarity",
                        "empathy",
                        "professionalism",
                      ].map((dimension) => {
                        const item =
                          analysis.response_evaluation[dimension];

                        return (
                          <div
                            className="eval-item"
                            key={dimension}
                          >
                            <span className="eval-label">
                              {dimension}{" "}
                              {item?.score ?? "-"}
                            </span>

                            <div className="eval-bar">
                              <div
                                className={`eval-bar-fill ${
                                  (item?.score ?? 0) >= 70
                                    ? "good"
                                    : "weak"
                                }`}
                                style={{
                                  width: `${item?.score ?? 0}%`,
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {analysis.suggested_responses?.knowledge_used
                    ?.length > 0 && (
                    <p className="suggestion-source">
                      Grounded in:{" "}
                      {analysis.suggested_responses.knowledge_used
                        .map((k) => k.source)
                        .join(", ")}
                    </p>
                  )}
                </>
              ) : (
                <p>
                  A context-aware reply suggestion will appear
                  after the customer responds.
                </p>
              )}
            </div>

          </aside>

          {/* ==================================================
              KNOWLEDGE + ESCALATION PANEL
          ================================================== */}

          <aside className="knowledge-panel">

            <div className="panel-header">
              <h3>Knowledge & Escalation</h3>
              <span>Support guidance</span>
            </div>

            {/* Scenario */}

            <div className="knowledge-card">
              <h4>Scenario</h4>

              <p>
                {session.scenario}
              </p>
            </div>

            {/* Customer Persona */}

            <div className="knowledge-card">
              <h4>Customer Persona</h4>

              <p>
                {session.persona}
              </p>
            </div>

            {/* ==================================================
                ESCALATION RISK MONITOR (Task 6)
            ================================================== */}

            <div className="knowledge-card escalation-card">

              <h4>Escalation Risk Monitor</h4>

              {analysisLoading ? (
                <p>Assessing escalation risk...</p>
              ) : (
                <>
                  <div className="risk-row">
                    <span
                      className={`risk-badge ${
                        (
                          analysis?.escalation_level || "Low"
                        ).toLowerCase()
                      }`}
                    >
                      {analysis?.escalation_level || "Low"}
                    </span>

                    <span className="risk-score">
                      {analysis?.escalation_score ?? 0}/100
                    </span>
                  </div>

                  <div className="risk-score-bar">
                    <div
                      className={`risk-score-fill ${
                        (
                          analysis?.escalation_level || "Low"
                        ).toLowerCase()
                      }`}
                      style={{
                        width: `${analysis?.escalation_score ?? 0}%`,
                      }}
                    />
                  </div>

                  <p className="risk-meta">
                    Trend: {analysis?.escalation_trend || "unknown"}{" "}
                    · Turn {analysis?.turn ?? 1} · Negative
                    streak: {analysis?.negative_streak ?? 0}
                  </p>

                  {analysis?.escalation_indicators?.length > 0 && (
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
                  )}

                  {analysis?.escalation_reasoning?.length > 0 && (
                    <div className="reasoning-list">
                      <strong>Why this score:</strong>

                      <ul>
                        {analysis.escalation_reasoning.map(
                          (reason, index) => (
                            <li key={index}>
                              {reason}
                            </li>
                          )
                        )}
                      </ul>
                    </div>
                  )}

                  <div className="threshold-control">
                    <label htmlFor="threshold-input">
                      Alert threshold
                    </label>

                    <div className="threshold-row">
                      <input
                        id="threshold-input"
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
                      Current: {threshold ?? "-"} (0-100). Alerts
                      fire when the risk score reaches this value.
                    </small>
                  </div>
                </>
              )}

            </div>

            {/* ==================================================
                RAG KNOWLEDGE RESULTS
            ================================================== */}

            <div className="knowledge-card">

              <h4>Relevant Knowledge</h4>

              {analysisLoading ? (
                <p>
                  Searching knowledge base...
                </p>
              ) : analysis?.knowledge_results?.length > 0 ? (

                <div className="rag-results">

                  {analysis.knowledge_results.map(
                    (result, index) => (
                      <div
                        className="rag-result"
                        key={index}
                      >

                        <div className="rag-result-header">

                          <strong>
                            {result.metadata?.source ||
                              "Knowledge Base"}
                          </strong>

                          <span>
                            {result.score !== undefined
                              ? `${(
                                  result.score * 100
                                ).toFixed(1)}%`
                              : ""}
                          </span>

                        </div>

                        <p>
                          {result.text}
                        </p>

                        {result.metadata?.page && (
                          <small>
                            Page {result.metadata.page}
                          </small>
                        )}

                      </div>
                    )
                  )}

                </div>

              ) : (
                <p>
                  No relevant knowledge found yet.
                </p>
              )}

            </div>

          </aside>

        </section>

      </main>

    </div>
  );
}

export default SupportConsole;