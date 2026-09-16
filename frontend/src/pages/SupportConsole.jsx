import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  getSession,
  getSessionLog,
  sendMessage,
  endSession,
} from "../services/sessionService";

import { analyzeMessage } from "../services/coachingService";

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

            const analysisData = await analyzeMessage(
              latestCustomerMessage.content,
              data.persona || "",
              data.scenario || ""
            );

            setAnalysis(analysisData);
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
        emotion: data.emotion,
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
      // 4. Analyze the CUSTOMER'S new message
      // --------------------------------------------------
      try {
        setAnalysisLoading(true);

        const analysisData = await analyzeMessage(
          data.customer_message,
          session?.persona || "",
          session?.scenario || ""
        );

        setAnalysis(analysisData);
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

            {/* Escalation Monitor */}

            <div className="knowledge-card">
              <h4>Escalation Monitor</h4>

              <p>
                {analysis?.escalation_risk
                  ? `Current risk: ${analysis.escalation_risk}`
                  : "Monitor customer emotion and conversation risk throughout the session."}
              </p>
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