import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  getSession,
  getSessionLog,
  sendMessage,
  endSession,
  startSession,
  getConfigOptions,
  readStoredConfig,
  storeSessionId,
  clearStoredSessionId,
} from "../services/sessionService";

import {
  analyzeSupport,
  evaluateResponse,
  getEscalationThreshold,
  setEscalationThreshold,
} from "../services/supportAssistService";

// Fallback Customer Configuration choices. The backend's
// `GET /config/options` is preferred; these keep every dropdown usable if
// that request ever fails. The values must match the simulator's own keys.
const FALLBACK_CONFIG_OPTIONS = {
  personas: [
    { value: "polite", name: "Polite Customer" },
    { value: "concerned", name: "Concerned Customer" },
    { value: "frustrated", name: "Frustrated Customer" },
    { value: "angry", name: "Angry Customer" },
    { value: "furious", name: "Furious Customer" },
  ],
  scenarios: [
    { value: "refund_request", name: "Refund Request" },
    { value: "delayed_order", name: "Delayed Order" },
    { value: "payment_failure", name: "Payment Failure" },
    { value: "account_issue", name: "Account Access Issue" },
    { value: "cancellation", name: "Cancellation Request" },
  ],
};

const INITIAL_EMOTIONS = ["frustrated", "neutral", "angry", "worried"];
const SEVERITIES = ["low", "medium", "high"];

/**
 * Recalculate the customer state from the latest CUSTOMER message of a
 * conversation - the single source of truth for every displayed value
 * (intent, emotion, sentiment, frustration, satisfaction trend,
 * escalation risk, negative streak, risk score and risk reasoning).
 *
 * `history` must be the role-tagged conversation (customer + agent). The
 * full history is sent to the backend so repeat/streak signals and the
 * escalation risk are always evaluated against the previous conversation
 * and the current customer state - never against the agent's own wording.
 */
async function analyseConversation(history, sessionId, requestRef, actions) {
  const { setLoading, setResult, setError } = actions || {};

  const messages = (history || []).filter(
    (item) => item && item.role && String(item.content || "").trim()
  );

  const latestCustomerMessage = [...messages]
    .reverse()
    .find((item) => item.role === "customer");

  if (!latestCustomerMessage?.content) {
    if (setLoading) setLoading(false);
    return null;
  }

  const customerTurn =
    messages.filter((item) => item.role === "customer").length || 1;

  // Ignore out-of-order responses: only the newest request may write to
  // the displayed analysis, so the console can never show a stale state.
  const requestId = (requestRef.current || 0) + 1;
  requestRef.current = requestId;

  if (setLoading) setLoading(true);
  if (setError) setError("");

  try {
    const analysisData = await analyzeSupport(
      latestCustomerMessage.content,
      sessionId,
      customerTurn,
      null,
      messages.map((item) => ({
        role: item.role,
        content: item.content,
      }))
    );

    if (requestRef.current !== requestId) {
      return null;
    }

    if (setResult) setResult(analysisData);
    if (setError) setError("");
    return analysisData;
  } catch (analysisError) {
    console.error(
      "Failed to analyze the customer message:",
      analysisError
    );

    if (requestRef.current === requestId) {
      if (setResult) setResult(null);
      if (setError) {
        setError(
          analysisError.response?.data?.detail ||
            analysisError.message ||
            "The AI analysis request failed."
        );
      }
    }

    return null;
  } finally {
    if (requestRef.current === requestId && setLoading) {
      setLoading(false);
    }
  }
}

/**
 * Customer Configuration section of the Task 6 dashboard.
 *
 * Persona, scenario, initial emotion, severity and customer patience -
 * the same five controls as the dedicated configuration screen, embedded
 * in the dashboard so the whole interface is usable in one place.
 * Submitting starts a new conversation with the chosen customer.
 */
function CustomerConfigurationCard({
  config,
  options,
  onChange,
  onSubmit,
  saving,
  error,
  currentSession,
}) {
  return (
    <form className="customer-config-card" onSubmit={onSubmit}>

      <div className="customer-config-header">
        <div>
          <h3>Customer Configuration</h3>

          <p>
            Configure the customer, then start a new Task 6
            conversation with these settings.
          </p>
        </div>

        {currentSession?.scenario_name && (
          <span className="customer-config-active">
            Active: {currentSession.persona_name} ·{" "}
            {currentSession.scenario_name}
          </span>
        )}
      </div>

      <div className="customer-config-grid">

        <label className="customer-config-field">
          <span>Customer Persona</span>

          <select
            name="persona"
            value={config.persona}
            onChange={onChange}
          >
            {options.personas.map((persona) => (
              <option key={persona.value} value={persona.value}>
                {persona.name}
              </option>
            ))}
          </select>
        </label>

        <label className="customer-config-field">
          <span>Scenario</span>

          <select
            name="scenario"
            value={config.scenario}
            onChange={onChange}
          >
            {options.scenarios.map((scenario) => (
              <option key={scenario.value} value={scenario.value}>
                {scenario.name}
              </option>
            ))}
          </select>
        </label>

        <label className="customer-config-field">
          <span>Initial Emotion</span>

          <select
            name="initial_emotion"
            value={config.initial_emotion}
            onChange={onChange}
          >
            {INITIAL_EMOTIONS.map((emotion) => (
              <option key={emotion} value={emotion}>
                {emotion.charAt(0).toUpperCase() + emotion.slice(1)}
              </option>
            ))}
          </select>
        </label>

        <label className="customer-config-field">
          <span>Severity</span>

          <select
            name="severity"
            value={config.severity}
            onChange={onChange}
          >
            {SEVERITIES.map((severity) => (
              <option key={severity} value={severity}>
                {severity.charAt(0).toUpperCase() + severity.slice(1)}
              </option>
            ))}
          </select>
        </label>

        <div className="customer-config-field customer-config-patience">
          <span>
            Customer Patience: <strong>{config.patience}</strong> / 10
          </span>

          <input
            type="range"
            name="patience"
            min="1"
            max="10"
            value={config.patience}
            onChange={onChange}
          />

          <span className="slider-labels">
            <span>Impatient</span>
            <span>Patient</span>
          </span>
        </div>

        <div className="customer-config-field customer-config-submit">
          <button
            type="submit"
            className="primary-button"
            disabled={saving}
          >
            {saving ? "Starting session..." : "Start configured session"}
          </button>
        </div>

      </div>

      {error && <div className="error-message">{error}</div>}

    </form>
  );
}

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
  const [analysisError, setAnalysisError] = useState("");

  // Guards against out-of-order analysis responses: only the newest
  // request may write to `analysis`, so the console can never display a
  // stale customer state.
  const analysisRequestRef = useRef(0);

  // Task 6: escalation threshold configuration
  const [threshold, setThreshold] = useState(null);
  const [thresholdInput, setThresholdInput] = useState("");
  const [thresholdSaving, setThresholdSaving] = useState(false);

  // Task 6: draft response evaluation
  const [draftEvaluation, setDraftEvaluation] = useState(null);
  const [checkingDraft, setCheckingDraft] = useState(false);

  // Task 6: Customer Configuration (persona / scenario / initial emotion /
  // severity / patience) shown on the dashboard itself, so a session can be
  // (re)started with a different customer without leaving the screen.
  const [config, setConfig] = useState(() => readStoredConfig());
  const [configOptions, setConfigOptions] = useState(
    FALLBACK_CONFIG_OPTIONS
  );
  const [startingSession, setStartingSession] = useState(false);
  const [configError, setConfigError] = useState("");

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
  // LOAD THE CUSTOMER CONFIGURATION CHOICES
  // ==========================================================
  // Personas / scenarios come from the backend so the Customer
  // Configuration panel always offers what the simulator supports; the
  // local fallback keeps every dropdown usable if the call fails.
  useEffect(() => {
    let cancelled = false;

    getConfigOptions().then((options) => {
      if (cancelled || !options) {
        return;
      }

      setConfigOptions({
        personas: options.personas?.length
          ? options.personas
          : FALLBACK_CONFIG_OPTIONS.personas,
        scenarios: options.scenarios?.length
          ? options.scenarios
          : FALLBACK_CONFIG_OPTIONS.scenarios,
      });
    });

    return () => {
      cancelled = true;
    };
  }, []);

  // ==========================================================
  // CUSTOMER CONFIGURATION (start a session with new settings)
  // ==========================================================
  const handleConfigChange = (event) => {
    const { name, value } = event.target;

    setConfig((previous) => ({
      ...previous,
      [name]: name === "patience" ? Number(value) : value,
    }));
  };

  const handleStartConfiguredSession = async (event) => {
    event.preventDefault();

    if (startingSession) {
      return;
    }

    setStartingSession(true);
    setConfigError("");

    try {
      // `startSession` validates, remembers the configuration and the new
      // session id, and creates the customer conversation on the backend.
      const data = await startSession(config);

      if (!data?.session_id) {
        throw new Error("The backend did not return a session id.");
      }

      // Mount the new conversation. Keyed by `sessionId`, so the console
      // reloads its state, analysis and risk monitor for the new session.
      navigate(`/session/${data.session_id}`, { replace: true });
    } catch (err) {
      console.error("Failed to start the configured session:", err);

      setConfigError(
        err.response?.data?.detail ||
          err.message ||
          "Unable to start a session with this configuration."
      );
    } finally {
      setStartingSession(false);
    }
  };

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
    // Recalculate the customer state from the latest CUSTOMER message of
    // the conversation (shared with the post-reply analysis, so the
    // initial view and every submitted reply use the exact same pipeline).
    async function analyseLatestCustomerMessage(history) {
      await analyseConversation(
        history,
        sessionId,
        analysisRequestRef,
        {
          setLoading: setAnalysisLoading,
          setResult: setAnalysis,
          setError: setAnalysisError,
        }
      );
    }

    async function loadSession() {
      try {
        const data = await getSession(sessionId);

        setSession(data);

        // This tab now owns this conversation: returning to "/" (or
        // refreshing) resumes it instead of creating a new session.
        storeSessionId(sessionId);

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
        await analyseLatestCustomerMessage(data.history || []);
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

          // Restored (not finished) conversation: still show the
          // recalculated customer state for its latest message.
          await analyseLatestCustomerMessage(history);
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

    // The displayed customer state is recalculated from the customer's
    // NEXT message, so nothing from the previous message may stay on
    // screen while that happens.
    setAnalysis(null);
    setAnalysisError("");
    setAnalysisLoading(true);

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
        // The simulator returns `turn_count` (there is no `turn` key);
        // keeping the previous value avoids an "undefined" turn display.
        turn_count: data.turn_count ?? previous?.turn_count,
        // NOTE (Task 6): `data.emotion` is the simulator's own
        // post-reply estimate and is intentionally NOT displayed. The
        // console always shows the Task 6 analysis (emotion,
        // frustration, sentiment, risk) of the latest CUSTOMER message.
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
        setAnalysisLoading(false);

        clearStoredSessionId();

        navigate(`/session/${sessionId}/result`, {
          replace: true,
        });

        return;
      }

      // --------------------------------------------------
      // 4. Run the Task 6 support-assistance pipeline again so the AI
      //    Analysis and the Escalation Risk Monitor reflect the LATEST
      //    conversation state after EVERY submitted reply.
      //
      //    The analysed text is always the newest CUSTOMER message
      //    (never the agent's own reply); the full role-tagged history is
      //    sent so repeat pressure, negative streaks and satisfaction are
      //    evaluated against the previous conversation. If the simulator
      //    produced no new customer text, the latest customer message is
      //    re-analysed with the updated history, so the monitor still
      //    reflects the newest state instead of a stale value.
      // --------------------------------------------------
      const updatedHistory = [
        ...(session?.history || []),
        { role: "agent", content: agentMessage },
        { role: "customer", content: data.customer_message || "" },
      ];

      await analyseConversation(
        updatedHistory,
        sessionId,
        analysisRequestRef,
        {
          setLoading: setAnalysisLoading,
          setResult: setAnalysis,
          setError: setAnalysisError,
        }
      );
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
  // RETRY THE AI ANALYSIS / ESCALATION RISK ASSESSMENT
  // ==========================================================
  // Used when the analysis request failed (backend hiccup, knowledge
  // service unavailable, ...). It re-runs the same pipeline against the
  // current conversation state, so the Escalation Risk Monitor never has
  // to fall back to made-up values.
  const handleRetryAnalysis = () => {
    analyseConversation(
      session?.history || [],
      sessionId,
      analysisRequestRef,
      {
        setLoading: setAnalysisLoading,
        setResult: setAnalysis,
        setError: setAnalysisError,
      }
    );
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
          Loading Task 6 support session...
        </div>
      </div>
    );
  }

  // ==========================================================
  // SESSION UNAVAILABLE (complete recovery screen, never a dead end)
  // ==========================================================
  // The backend keeps sessions in memory, so a backend restart (or an
  // expired conversation) makes an existing session id unknown. Instead
  // of a bare error page the dashboard stays fully usable: the Customer
  // Configuration is shown and a new conversation can be started in one
  // click - without typing any internal URL or session id.
  if (!session) {
    return (
      <div className="console-page">

        <header className="console-header">
          <div>
            <h1>SupportAI</h1>
            <p>Live Support Console</p>
          </div>

          <div className="console-header-actions">
            <span className="session-id">
              Session: {sessionId}
            </span>
          </div>
        </header>

        <main className="console-content">

          <div className="console-title">
            <div>
              <h2>Customer Support Session</h2>

              <p>
                This conversation is no longer available. Start a new
                Task 6 session below.
              </p>
            </div>
          </div>

          <div className="console-error">
            {error || "Session not found."}
          </div>

          <CustomerConfigurationCard
            config={config}
            options={configOptions}
            onChange={handleConfigChange}
            onSubmit={handleStartConfiguredSession}
            saving={startingSession}
            error={configError}
            currentSession={null}
          />

          <div className="config-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() => navigate("/")}
            >
              Create a Task 6 session automatically
            </button>
          </div>

        </main>
      </div>
    );
  }

  // ==========================================================
  // DISPLAYED CUSTOMER STATE (single source of truth)
  // ==========================================================
  // Emotion, intensity, frustration, sentiment, satisfaction and
  // escalation risk ALL come from the same `/support/analyze` result
  // for the latest customer message, so they can never disagree or go
  // stale. The simulator's own emotion estimate is never displayed.
  const customerEmotion =
    analysis?.emotion_label || analysis?.emotion || "Unknown";
  const customerIntensity =
    analysis?.frustration_level ??
    analysis?.frustration_score ??
    "-";

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
              {customerEmotion}
            </span>

            <span>
              Intensity:{" "}
              {customerIntensity}
            </span>
          </div>
        </div>

        {/* ==================================================
            CUSTOMER CONFIGURATION (Task 6)
        ================================================== */}

        <CustomerConfigurationCard
          config={config}
          options={configOptions}
          onChange={handleConfigChange}
          onSubmit={handleStartConfiguredSession}
          saving={startingSession}
          error={configError}
          currentSession={session}
        />

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
                {customerEmotion}
              </strong>

              <p>
                Intensity:{" "}
                {customerIntensity} / 10
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
                      "Unknown"}{" "}
                    {analysis.escalation_score !== undefined
                      ? `(${analysis.escalation_score}/100 · ${
                          analysis.escalation_trend || "stable"
                        })`
                      : ""}
                  </p>

                  {/* Negative Streak */}

                  <p>
                    <strong>
                      Negative Streak:
                    </strong>{" "}
                    {analysis.negative_streak ?? 0}{" "}
                    consecutive negative customer message(s)
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
                  {analysisError ? (
                    <>
                      The AI analysis is unavailable: {analysisError}{" "}
                      <button
                        type="button"
                        className="retry-analysis-button"
                        onClick={handleRetryAnalysis}
                      >
                        Retry analysis
                      </button>
                    </>
                  ) : (
                    "Analysis will appear after a customer response."
                  )}
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
              ) : analysis ? (
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
              ) : (
                // No risk values are guessed when the assessment is
                // missing: the monitor states that it has no data and
                // offers to run the analysis again.
                <div className="analysis-unavailable">
                  <p>
                    The escalation risk assessment is
                    unavailable
                    {analysisError ? `: ${analysisError}` : "."}
                  </p>

                  <p className="analysis-unavailable-note">
                    No score is displayed instead of a guessed
                    value.
                  </p>

                  <button
                    type="button"
                    className="retry-analysis-button"
                    onClick={handleRetryAnalysis}
                  >
                    Retry assessment
                  </button>
                </div>
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