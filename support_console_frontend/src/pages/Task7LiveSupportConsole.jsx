import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import {
  analyzeConsoleMessage,
  uploadTranscript,
  recordConversation,
  listSimulatorConversations,
  getSimulatorConversation,
} from "../services/task7Service";
import { evaluateResponse } from "../services/supportAssistService";
import { LineChart } from "../components/Charts";

/**
 * Task 7 - Live Support Console.
 *
 * One three-panel screen:
 *
 *   Panel 1  Conversation window  - chat, agent input, and the live
 *                                   customer state (intent, sentiment,
 *                                   frustration, emotion, risk).
 *   Panel 2  Real-time coaching   - suggested response, coaching tips and
 *                                   tone/empathy/clarity/professionalism
 *                                   guidance for the latest message.
 *   Panel 3  Knowledge            - FAQs / articles / policies /
 *                                   troubleshooting retrieved for the
 *                                   current message, openable in full.
 *
 * Both required modes live here:
 *
 *   Manual Mode  - the agent types/pastes each customer message.
 *   Replay Mode  - a .txt/.csv/.json transcript is uploaded and stepped
 *                  through with Next / Previous / Play / Pause / Restart.
 */

const MODES = [
  {
    id: "manual",
    label: "Manual Mode",
    hint: "Type or paste what the customer says; the console analyses it.",
  },
  {
    id: "replay",
    label: "Replay Mode",
    hint: "Upload a .txt / .csv / .json transcript and step through it.",
  },
];

const MODE_BY_ID = Object.fromEntries(MODES.map((mode) => [mode.id, mode]));

// Demo messages for Manual Mode, so the trainer can start instantly.
const EXAMPLE_MESSAGES = [
  "My payment failed and I have been trying for two hours.",
  "This is ridiculous. Nobody is helping me and I need this fixed immediately.",
  "I can still see the duplicate charge on my statement.",
  "Thank you, the issue is finally resolved.",
];

const REPLAY_SPEED_MS = 1800;

function titleCase(value) {
  if (!value) return "Unknown";
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function riskClass(level) {
  return `t7-risk-badge ${String(level || "low").toLowerCase()}`;
}

function sentimentClass(label) {
  return `t7-chip sentiment ${String(label || "neutral").toLowerCase()}`;
}

/** Knowledge chunks the backend marks with source + page metadata. */
function knowledgeId(result, index) {
  const meta = result?.metadata || {};
  return `${meta.source || "doc"}-${meta.page || 0}-${index}`;
}

function timingLabel(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return String(timestamp);
  return date.toLocaleTimeString();
}

function Task7LiveSupportConsole() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const requestedMode = searchParams.get("mode");
  const [mode, setMode] = useState(
    requestedMode === "replay" ? "replay" : "manual"
  );

  // ---- shared conversation state (kept for the whole session) ----
  const [messages, setMessages] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [openKnowledge, setOpenKnowledge] = useState(null);
  const [saving, setSaving] = useState(false);

  // ---- manual mode ----
  const [customerDraft, setCustomerDraft] = useState("");
  const [agentDraft, setAgentDraft] = useState("");
  const [draftEvaluation, setDraftEvaluation] = useState(null);
  const [checkingDraft, setCheckingDraft] = useState(false);

  // ---- replay mode ----
  const [transcript, setTranscript] = useState(null);
  const [replayIndex, setReplayIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analysisMap, setAnalysisMap] = useState({});
  const [simulatorSessions, setSimulatorSessions] = useState([]);
  const [loadingSimulator, setLoadingSimulator] = useState(false);
  const [simulatorId, setSimulatorId] = useState("");

  const conversationRef = useRef(null);
  const knowledgeSearchesRef = useRef([]);
  const fileInputRef = useRef(null);

  const isReplay = mode === "replay";
  const activeMode = MODE_BY_ID[mode] || MODES[0];

  // Analysis shown in the panels: the manual analysis, or the replay
  // analysis of the newest customer message reached so far.
  const latestAnalysisIndex = useMemo(() => {
    const keys = Object.keys(analysisMap)
      .map((key) => Number(key))
      .filter((key) => key < replayIndex)
      .sort((a, b) => a - b);
    return keys.length ? keys[keys.length - 1] : null;
  }, [analysisMap, replayIndex]);

  const displayAnalysis = isReplay
    ? latestAnalysisIndex !== null
      ? analysisMap[latestAnalysisIndex]
      : null
    : analysis;

  // Escalation-risk progression over the customer messages.
  const riskTimeline = useMemo(() => {
    const entries = Object.entries(analysisMap)
      .map(([index, value]) => ({ index: Number(index), analysis: value }))
      .filter((entry) => !isReplay || entry.index < replayIndex)
      .sort((a, b) => a.index - b.index);

    return entries.map((entry, position) => ({
      label: `#${position + 1}`,
      value: entry.analysis?.escalation_score ?? 0,
      level: entry.analysis?.escalation_level || "Low",
      frustration: entry.analysis?.frustration_level ?? 0,
      sentiment: entry.analysis?.sentiment || "neutral",
      intent: entry.analysis?.intent || "general_inquiry",
      message: entry.analysis?.customer_message || "",
    }));
  }, [analysisMap, isReplay, replayIndex]);

  // Auto-scroll the conversation to the newest message.
  useEffect(() => {
    const node = conversationRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [messages.length, replayIndex]);

  // Remember the requested mode in the URL so a refresh keeps it.
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (next.get("mode") !== mode) {
      next.set("mode", mode);
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const resetConversation = useCallback(() => {
    setMessages([]);
    setAnalysis(null);
    setAnalysisMap({});
    setReplayIndex(0);
    setPlaying(false);
    setError("");
    setNotice("");
    setDraftEvaluation(null);
    setAgentDraft("");
    knowledgeSearchesRef.current = [];
  }, []);

  // ==========================================================
  // CORE ANALYSIS (used by BOTH modes after every exchange)
  // ==========================================================
  const runAnalysis = useCallback(
    async (conversation, turn) => {
      const history = conversation
        .filter((item) => item.role && item.content)
        .map((item) => ({ role: item.role, content: item.content }));

      const latestCustomer = [...history]
        .reverse()
        .find((item) => item.role === "customer");

      if (!latestCustomer) {
        return null;
      }

      const result = await analyzeConsoleMessage({
        query: latestCustomer.content,
        sessionId: `task7-${mode}-session`,
        turn,
        history,
      });

      knowledgeSearchesRef.current.push({
        turn,
        query: latestCustomer.content,
        results: (result.knowledge_results || []).length,
        sources: (result.knowledge_results || [])
          .map((item) => item?.metadata?.source)
          .filter(Boolean),
      });

      return result;
    },
    [mode]
  );

  // ==========================================================
  // MANUAL MODE
  // ==========================================================
  const handleAddCustomerMessage = useCallback(
    async (rawText) => {
      const text = (rawText ?? customerDraft).trim();

      if (!text) {
        setError("Enter the customer message first.");
        return;
      }

      const nextMessage = {
        role: "customer",
        content: text,
        timestamp: new Date().toISOString(),
      };
      const conversation = [...messages, nextMessage];
      const turnNumber =
        conversation.filter((item) => item.role === "customer").length;

      setMessages(conversation);
      setCustomerDraft("");
      setError("");
      setAnalyzing(true);

      try {
        const result = await runAnalysis(conversation, turnNumber);
        setAnalysis(result);
        setNotice("");
      } catch (err) {
        console.error("Task 7 analysis failed:", err);
        setError(
          err.response?.data?.detail ||
            err.message ||
            "The analysis request failed. Check that the backend is running."
        );
      } finally {
        setAnalyzing(false);
      }
    },
    [customerDraft, messages, runAnalysis]
  );

  const handleSendAgentReply = useCallback(() => {
    const text = agentDraft.trim();

    if (!text) {
      setError("Write your reply before sending it.");
      return;
    }

    setMessages((previous) => [
      ...previous,
      {
        role: "agent",
        content: text,
        timestamp: new Date().toISOString(),
      },
    ]);
    setAgentDraft("");
    setDraftEvaluation(null);
    setError("");
    setNotice("Reply added to the conversation.");
  }, [agentDraft]);

  const handleUseSuggestion = useCallback(() => {
    const suggestion =
      displayAnalysis?.suggested_response ||
      displayAnalysis?.suggested_responses?.primary ||
      "";
    if (!suggestion) return;
    setAgentDraft(suggestion);
    setNotice("Suggested response copied into the reply box.");
  }, [displayAnalysis]);

  const handleCheckDraft = useCallback(async () => {
    const text = agentDraft.trim();
    if (!text) {
      setError("Write a draft reply to evaluate.");
      return;
    }

    setCheckingDraft(true);
    setError("");

    try {
      const result = await evaluateResponse(
        text,
        displayAnalysis?.intent || null
      );
      setDraftEvaluation(result);
    } catch (err) {
      console.error("Draft evaluation failed:", err);
      setError(
        err.response?.data?.detail ||
          "Could not evaluate the draft reply right now."
      );
    } finally {
      setCheckingDraft(false);
    }
  }, [agentDraft, displayAnalysis]);


  // ==========================================================
  // REPLAY MODE
  // ==========================================================
  const applyTranscript = useCallback((parsed, sourceLabel) => {
    const parsedMessages = (parsed.messages || []).map((item, index) => ({
      role: item.role,
      content: item.content,
      timestamp: item.timestamp || null,
      turn: index + 1,
    }));

    setTranscript({
      filename: sourceLabel,
      format: parsed.format,
      counts: parsed.counts,
      warnings: parsed.warnings || [],
      messages: parsedMessages,
    });
    setMessages([]);
    setAnalysisMap({});
    setAnalysis(null);
    setReplayIndex(0);
    setPlaying(false);
    setError("");
    setNotice(
      `Loaded ${parsedMessages.length} messages from a ${String(
        parsed.format
      ).toUpperCase()} source. Press Next to begin the replay.`
    );
    knowledgeSearchesRef.current = [];
  }, []);

  const handleTranscriptFile = useCallback(
    async (file) => {
      if (!file) return;

      setUploading(true);
      setError("");

      try {
        const parsed = await uploadTranscript(file);
        applyTranscript(parsed, file.name);
      } catch (err) {
        console.error("Transcript upload failed:", err);
        setError(
          err.response?.data?.detail ||
            err.message ||
            "The transcript could not be parsed. Upload a .txt, .csv or .json file."
        );
      } finally {
        setUploading(false);
      }
    },
    [applyTranscript]
  );

  const handleFileInput = useCallback(
    (event) => {
      const file = event.target.files?.[0];
      handleTranscriptFile(file);
      event.target.value = "";
    },
    [handleTranscriptFile]
  );

  const handleDrop = useCallback(
    (event) => {
      event.preventDefault();
      const file = event.dataTransfer?.files?.[0];
      handleTranscriptFile(file);
    },
    [handleTranscriptFile]
  );

  // Load a conversation the existing Task 3 simulator already produced.
  const loadSimulatorSessions = useCallback(async () => {
    setLoadingSimulator(true);
    try {
      const data = await listSimulatorConversations(25);
      setSimulatorSessions(data.sessions || []);
    } catch (err) {
      console.error("Could not load simulator conversations:", err);
      setSimulatorSessions([]);
    } finally {
      setLoadingSimulator(false);
    }
  }, []);

  useEffect(() => {
    if (isReplay && simulatorSessions.length === 0 && !loadingSimulator) {
      loadSimulatorSessions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isReplay]);

  const handleLoadSimulatorConversation = useCallback(
    async (sessionId) => {
      if (!sessionId) return;

      setUploading(true);
      setError("");

      try {
        const conversation = await getSimulatorConversation(sessionId);
        const items = conversation.messages || [];
        applyTranscript(
          {
            messages: items,
            format: "simulator",
            counts: {
              messages: items.length,
              customer_messages: items.filter(
                (item) => item.role === "customer"
              ).length,
              agent_messages: items.filter((item) => item.role === "agent")
                .length,
            },
            warnings: [],
          },
          conversation.title || `${sessionId}.json`
        );
      } catch (err) {
        console.error("Could not load the simulator conversation:", err);
        setError(
          err.response?.data?.detail ||
            "That simulator conversation could not be loaded."
        );
      } finally {
        setUploading(false);
      }
    },
    [applyTranscript]
  );


  /**
   * Reveal messages up to (and including) `count` and make sure the newest
   * revealed customer message has been analysed. Results are cached per
   * revealed position so stepping backwards is instant and always shows the
   * analysis that belongs to that point in the conversation.
   */
  const revealUpTo = useCallback(
    async (count) => {
      if (!transcript) return;

      const safeCount = Math.max(
        0,
        Math.min(count, transcript.messages.length)
      );
      const revealed = transcript.messages.slice(0, safeCount);

      setReplayIndex(safeCount);
      setMessages(revealed);

      const lastCustomerIndex = [...revealed]
        .map((item, index) => ({ item, index }))
        .filter((entry) => entry.item.role === "customer")
        .map((entry) => entry.index)
        .pop();

      if (lastCustomerIndex === undefined) {
        setAnalysis(null);
        return;
      }

      if (analysisMap[lastCustomerIndex]) {
        return; // already analysed - instant step back / forward
      }

      setAnalyzing(true);

      try {
        const turnNumber = revealed
          .slice(0, lastCustomerIndex + 1)
          .filter((item) => item.role === "customer").length;

        const result = await runAnalysis(
          transcript.messages.slice(0, lastCustomerIndex + 1),
          turnNumber
        );

        if (result) {
          setAnalysisMap((previous) => ({
            ...previous,
            [lastCustomerIndex]: result,
          }));
        }
      } catch (err) {
        console.error("Replay analysis failed:", err);
        setError(
          err.response?.data?.detail ||
            "The analysis for this message could not be generated."
        );
      } finally {
        setAnalyzing(false);
      }
    },
    [transcript, analysisMap, runAnalysis]
  );

  const handleNext = useCallback(() => {
    if (!transcript) return;
    if (replayIndex >= transcript.messages.length) {
      setPlaying(false);
      return;
    }
    revealUpTo(replayIndex + 1);
  }, [transcript, replayIndex, revealUpTo]);

  const handlePrevious = useCallback(() => {
    if (!transcript) return;
    setPlaying(false);
    revealUpTo(replayIndex - 1);
  }, [transcript, replayIndex, revealUpTo]);

  const handleRestart = useCallback(() => {
    if (!transcript) return;
    setPlaying(false);
    revealUpTo(0);
    setNotice("Replay restarted - press Play or Next to run it again.");
  }, [transcript, revealUpTo]);

  const handlePlayPause = useCallback(() => {
    if (!transcript) return;

    if (replayIndex >= transcript.messages.length) {
      setPlaying(false);
      return;
    }

    setPlaying((value) => !value);
  }, [transcript, replayIndex]);

  // Play / pause timer: one message at a time, stopping at the end.
  useEffect(() => {
    if (!playing || !transcript) return undefined;

    if (replayIndex >= transcript.messages.length) {
      setPlaying(false);
      return undefined;
    }

    const timer = setTimeout(() => {
      revealUpTo(replayIndex + 1);
    }, REPLAY_SPEED_MS);

    return () => clearTimeout(timer);
  }, [playing, replayIndex, transcript, revealUpTo]);

  const replayFinished =
    isReplay &&
    transcript !== null &&
    transcript.messages.length > 0 &&
    replayIndex >= transcript.messages.length;


  // ==========================================================
  // CONVERSATION / REPLAY SUMMARY
  // ==========================================================
  const conversationSummary = useMemo(() => {
    const customerMessages = messages.filter(
      (item) => item.role === "customer"
    );
    const agentMessages = messages.filter((item) => item.role === "agent");
    const scores = riskTimeline.map((point) => point.value);
    const peakIndex = scores.length
      ? scores.indexOf(Math.max(...scores))
      : -1;

    return {
      totalMessages: messages.length,
      customerMessages: customerMessages.length,
      agentMessages: agentMessages.length,
      peakRisk: scores.length ? Math.max(...scores) : null,
      peakLevel:
        peakIndex >= 0 ? riskTimeline[peakIndex]?.level || "Low" : null,
      startRisk: scores.length ? scores[0] : null,
      endRisk: scores.length ? scores[scores.length - 1] : null,
      firstSentiment: riskTimeline[0]?.sentiment || null,
      lastSentiment: riskTimeline[riskTimeline.length - 1]?.sentiment || null,
      firstFrustration: riskTimeline[0]?.frustration ?? null,
      lastFrustration:
        riskTimeline.length > 0
          ? riskTimeline[riskTimeline.length - 1].frustration
          : null,
      intents: Array.from(
        new Set(riskTimeline.map((point) => point.intent).filter(Boolean))
      ),
      hasAnalysis: riskTimeline.length > 0,
    };
  }, [messages, riskTimeline]);

  const canSave = messages.length >= 2;

  const handleSaveAndOpenSummary = useCallback(async () => {
    if (!canSave) {
      setError(
        "Add at least one customer message and one agent reply before generating the summary."
      );
      return;
    }

    setSaving(true);
    setError("");

    try {
      const stored = await recordConversation({
        mode,
        title: isReplay
          ? `Replay - ${transcript?.filename || "transcript"}`
          : "Manual support conversation",
        persona: isReplay ? null : "manual",
        scenario: conversationSummary.intents[0] || null,
        sourceFile: isReplay ? transcript?.filename || null : null,
        messages,
        knowledgeSearches: knowledgeSearchesRef.current,
        meta: {
          escalation_timeline: riskTimeline,
          summary: conversationSummary,
          transcript_format: transcript?.format || null,
          transcript_warnings: transcript?.warnings || [],
        },
      });

      setSaving(false);
      setNotice("Conversation saved. Opening the post-interaction summary...");
      navigate(
        `/task8/summary?conversationId=${encodeURIComponent(
          stored.session.id
        )}`
      );
    } catch (err) {
      console.error("Could not record the conversation:", err);
      setSaving(false);
      setError(
        err.response?.data?.detail ||
          "The conversation could not be saved for analytics."
      );
    }
  }, [
    canSave,
    mode,
    isReplay,
    transcript,
    messages,
    riskTimeline,
    conversationSummary,
    navigate,
  ]);

  // ==========================================================
  // RENDERING HELPERS
  // ==========================================================
  const renderEmptyPanels = (panel) => (
    <div className="t7-empty">
      {panel === "coaching" ? (
        <p>
          Coaching appears as soon as the first customer message is analysed -
          a suggested reply, tone/empathy/clarity/professionalism guidance and
          an escalation warning when it is needed.
        </p>
      ) : (
        <p>
          Knowledge recommendations are retrieved from the RAG knowledge base
          for each customer message, with their source document and page.
        </p>
      )}
    </div>
  );


  const evaluation =
    displayAnalysis?.response_evaluation || draftEvaluation || null;

  // ==========================================================
  // MAIN UI
  // ==========================================================
  return (
    <div className="console-page t7-page">
      <header className="console-header">
        <div>
          <h1>SupportAI</h1>
          <p>Task 7 - Live Support Console</p>
        </div>

        <div className="console-header-actions">
          <button onClick={() => navigate("/dashboard")}>Dashboard</button>
          <button onClick={() => navigate("/task8/summary")}>
            Task 8 - Summary
          </button>
          <button onClick={() => navigate("/task8/analytics")}>
            Task 8 - Analytics
          </button>
        </div>
      </header>

      <main className="console-content">
        <div className="console-title">
          <div>
            <h2>Live Support Console</h2>
            <p>{activeMode.hint}</p>
          </div>

          <div className="session-status">
            <span>Mode: {isReplay ? "Replay" : "Manual"}</span>
            <span>Messages: {messages.length}</span>
            <span>Analysed messages: {riskTimeline.length}</span>
          </div>
        </div>

        {/* ============ MODE TABS ============ */}
        <div className="t7-mode-tabs" role="tablist">
          {MODES.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={mode === item.id}
              className={`t7-mode-tab ${mode === item.id ? "active" : ""}`}
              onClick={() => {
                setMode(item.id);
                setError("");
                setNotice("");
              }}
            >
              <strong>{item.label}</strong>
              <span>{item.hint}</span>
            </button>
          ))}

          <button
            type="button"
            className="t7-mode-tab t7-mode-tab-link"
            onClick={() => navigate("/")}
          >
            <strong>Simulator Mode (Task 3-6)</strong>
            <span>Open the existing live customer-simulator console</span>
          </button>
        </div>

        {/* ============ STATUS / ERRORS ============ */}
        {error && <div className="console-error">{error}</div>}
        {notice && !error && <div className="t7-notice">{notice}</div>}
        {analyzing && (
          <div className="t7-loading">
            Analysing the latest customer message (intent, sentiment,
            frustration, coaching, knowledge, escalation risk)...
          </div>
        )}


        {/* ============ THREE PANELS ============ */}
        <section className="console-grid">
          {/* PANEL 1 - CONVERSATION WINDOW */}
          <div className="conversation-panel">
            <div className="panel-header">
              <h3>Conversation</h3>
              <span>
                {isReplay
                  ? `Replay: ${replayIndex}/${
                      transcript?.messages.length ?? 0
                    } messages`
                  : "Manual mode - enter the customer messages"}
              </span>
            </div>

            <div className="t7-state">
              <div className="t7-state-item">
                <span>Intent</span>
                <strong>
                  {displayAnalysis
                    ? titleCase(displayAnalysis.intent)
                    : "Waiting for a customer message"}
                </strong>
              </div>
              <div className="t7-state-item">
                <span>Sentiment</span>
                <strong className={sentimentClass(displayAnalysis?.sentiment)}>
                  {titleCase(displayAnalysis?.sentiment || "unknown")}
                </strong>
              </div>
              <div className="t7-state-item">
                <span>Frustration</span>
                <strong>
                  {displayAnalysis?.frustration_level ?? "-"}/10 (
                  {displayAnalysis?.emotion_label || "unknown"})
                </strong>
              </div>
              <div className="t7-state-item">
                <span>Escalation risk</span>
                <strong
                  className={riskClass(displayAnalysis?.escalation_level)}
                >
                  {displayAnalysis
                    ? `${displayAnalysis.escalation_level} (${
                        displayAnalysis.escalation_score
                      }/100, ${displayAnalysis.escalation_trend})`
                    : "-"}
                </strong>
              </div>
            </div>

            <div className="conversation-messages" ref={conversationRef}>
              {messages.length === 0 ? (
                <div className="t7-empty">
                  <p>
                    {isReplay
                      ? "Upload a transcript below, or pick one of the recorded simulator conversations."
                      : "The conversation starts when you add the first customer message."}
                  </p>
                </div>
              ) : (
                messages.map((item, index) => (
                  <div
                    key={`${item.role}-${index}`}
                    className={`message ${
                      item.role === "customer"
                        ? "customer-message"
                        : "agent-message"
                    }`}
                  >
                    <div className="message-role">
                      {item.role === "customer" ? "Customer" : "You (agent)"}
                      {item.turn ? ` - turn ${item.turn}` : ""}
                      {item.timestamp
                        ? ` - ${timingLabel(item.timestamp)}`
                        : ""}
                    </div>
                    <div className="message-content">{item.content}</div>
                  </div>
                ))
              )}
            </div>


            {/* ---------- MANUAL MODE INPUTS ---------- */}
            {!isReplay && (
              <div className="message-form t7-inputs">
                <label className="t7-label" htmlFor="t7-customer-input">
                  Customer message (type or paste what the customer says)
                </label>
                <textarea
                  id="t7-customer-input"
                  value={customerDraft}
                  onChange={(event) => setCustomerDraft(event.target.value)}
                  placeholder="e.g. My payment failed and I have been trying for two hours."
                />

                <div className="t7-examples">
                  <span>Quick examples:</span>
                  {EXAMPLE_MESSAGES.map((example) => (
                    <button
                      key={example}
                      type="button"
                      className="t7-example"
                      onClick={() => setCustomerDraft(example)}
                    >
                      {example.length > 48
                        ? `${example.slice(0, 48)}...`
                        : example}
                    </button>
                  ))}
                </div>

                <button
                  type="button"
                  className="primary-button"
                  disabled={analyzing}
                  onClick={() => handleAddCustomerMessage()}
                >
                  {analyzing ? "Analysing..." : "Add customer message"}
                </button>

                <label className="t7-label" htmlFor="t7-agent-input">
                  Your reply (support agent)
                </label>
                <textarea
                  id="t7-agent-input"
                  value={agentDraft}
                  onChange={(event) => setAgentDraft(event.target.value)}
                  placeholder="Write the reply you would send to the customer."
                />

                <div className="message-form-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={handleUseSuggestion}
                    disabled={!displayAnalysis?.suggested_response}
                  >
                    Use suggested response
                  </button>
                  <button
                    type="button"
                    className="check-draft-button"
                    onClick={handleCheckDraft}
                    disabled={checkingDraft || !agentDraft.trim()}
                  >
                    {checkingDraft ? "Checking..." : "Check my draft"}
                  </button>
                  <button
                    type="button"
                    className="primary-button"
                    onClick={handleSendAgentReply}
                    disabled={!agentDraft.trim()}
                  >
                    Send reply
                  </button>
                </div>

                {draftEvaluation && (
                  <div
                    className={`draft-evaluation ${
                      draftEvaluation.meets_standard ? "pass" : "warn"
                    }`}
                  >
                    <strong>
                      Draft score: {draftEvaluation.overall}/100
                    </strong>
                    <p>{draftEvaluation.summary}</p>
                  </div>
                )}
              </div>
            )}


            {/* ---------- REPLAY MODE CONTROLS ---------- */}
            {isReplay && (
              <div className="message-form t7-inputs">
                <label className="t7-label" htmlFor="t7-transcript">
                  Upload conversation transcript (.txt, .csv, .json)
                </label>
                <input
                  id="t7-transcript"
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.csv,.json,text/plain,text/csv,application/json"
                  onChange={handleFileInput}
                  disabled={uploading}
                />
                <div
                  className="t7-dropzone"
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={handleDrop}
                >
                  {uploading
                    ? "Uploading and parsing the transcript..."
                    : "Drag a transcript file here, or use the picker above."}
                </div>

                <label className="t7-label" htmlFor="t7-simulator">
                  ...or replay a conversation already recorded by the Task 3
                  simulator
                </label>
                <div className="t7-inline">
                  <select
                    id="t7-simulator"
                    value={simulatorId}
                    onChange={(event) => setSimulatorId(event.target.value)}
                  >
                    <option value="">
                      {loadingSimulator
                        ? "Loading simulator conversations..."
                        : `Select a recorded conversation (${simulatorSessions.length} available)`}
                    </option>
                    {simulatorSessions.map((session) => (
                      <option key={session.id} value={session.id}>
                        {titleCase(session.scenario)} -{" "}
                        {session.message_count} messages
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={!simulatorId || uploading}
                    onClick={() => handleLoadSimulatorConversation(simulatorId)}
                  >
                    Load
                  </button>
                </div>

                {transcript && (
                  <>
                    <div className="t7-transcript-info">
                      <strong>{transcript.filename}</strong>
                      <span>
                        {String(transcript.format).toUpperCase()} -{" "}
                        {transcript.counts?.messages ?? 0} messages (
                        {transcript.counts?.customer_messages ?? 0} customer /{" "}
                        {transcript.counts?.agent_messages ?? 0} agent)
                      </span>
                    </div>

                    {transcript.warnings?.length > 0 && (
                      <ul className="t7-warnings">
                        {transcript.warnings.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    )}

                    <div className="t7-replay-controls">
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handlePrevious}
                        disabled={replayIndex <= 0}
                      >
                        Previous
                      </button>
                      <button
                        type="button"
                        className="primary-button"
                        onClick={handlePlayPause}
                        disabled={replayFinished && !playing}
                      >
                        {playing ? "Pause" : "Play"}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleNext}
                        disabled={replayIndex >= transcript.messages.length}
                      >
                        Next
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={handleRestart}
                      >
                        Restart
                      </button>
                    </div>

                    <div className="t7-progress">
                      <div className="t7-progress-bar">
                        <div
                          className="t7-progress-fill"
                          style={{
                            width: `${
                              transcript.messages.length
                                ? Math.round(
                                    (replayIndex /
                                      transcript.messages.length) *
                                      100
                                  )
                                : 0
                            }%`,
                          }}
                        />
                      </div>
                      <small>
                        Step {replayIndex} of {transcript.messages.length}
                        {replayFinished ? " - replay complete" : ""}
                      </small>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>


          {/* PANEL 2 - REAL-TIME COACHING FEED */}
          <div className="coaching-panel">
            <div className="panel-header">
              <h3>Real-Time Coaching</h3>
              <span>Updates after every customer message</span>
            </div>

            {!displayAnalysis ? (
              renderEmptyPanels("coaching")
            ) : (
              <>
                {/* Escalation-risk warning (only when needed) */}
                {displayAnalysis.alert?.triggered && (
                  <div
                    className={`alert-banner ${
                      displayAnalysis.alert.level === "Critical"
                        ? "critical"
                        : "high"
                    }`}
                  >
                    <div className="alert-banner-header">
                      <strong>
                        Escalation warning - {displayAnalysis.alert.level} risk
                        ({displayAnalysis.escalation_score}/100)
                      </strong>
                      <span>Threshold: {displayAnalysis.alert.threshold}</span>
                    </div>
                    <p>{displayAnalysis.alert.message}</p>
                    {displayAnalysis.recommended_actions?.length > 0 && (
                      <div className="alert-actions">
                        <strong>Recommended actions:</strong>
                        <ul>
                          {displayAnalysis.recommended_actions.map(
                            (action) => (
                              <li key={action}>{action}</li>
                            )
                          )}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Suggested response */}
                <div className="coaching-card suggestion-card">
                  <h4>Suggested response</h4>
                  <p className="suggestion-text">
                    {displayAnalysis.suggested_response ||
                      "No suggestion available for this message."}
                  </p>

                  {displayAnalysis.suggested_responses?.followup_question && (
                    <p className="suggestion-followup">
                      Follow-up:{" "}
                      {displayAnalysis.suggested_responses.followup_question}
                    </p>
                  )}

                  {!isReplay && (
                    <div className="suggestion-actions">
                      <button
                        type="button"
                        className="use-suggestion-button"
                        onClick={handleUseSuggestion}
                      >
                        Use this reply
                      </button>
                    </div>
                  )}

                  {displayAnalysis.suggested_responses?.alternates?.length >
                    0 && (
                    <div className="t7-alternates">
                      <strong>Alternative wording:</strong>
                      <ul>
                        {displayAnalysis.suggested_responses.alternates.map(
                          (alternate) => (
                            <li key={alternate}>{alternate}</li>
                          )
                        )}
                      </ul>
                    </div>
                  )}
                </div>


                {/* Tone / empathy / clarity / professionalism */}
                {evaluation && (
                  <div className="coaching-card">
                    <h4>Response quality ({evaluation.overall}/100)</h4>
                    <div className="eval-grid">
                      {["tone", "empathy", "clarity", "professionalism"].map(
                        (dimension) => {
                          const item = evaluation[dimension];
                          if (!item) return null;
                          return (
                            <div className="eval-item" key={dimension}>
                              <div className="eval-label">
                                <span>{titleCase(dimension)}</span>
                                <strong>{item.score}/100</strong>
                              </div>
                              <div className="eval-bar">
                                <div
                                  className={`eval-bar-fill ${
                                    item.score >= 70 ? "good" : "weak"
                                  }`}
                                  style={{
                                    width: `${Math.max(
                                      4,
                                      Math.min(100, item.score)
                                    )}%`,
                                  }}
                                />
                              </div>
                              <p>{item.notes}</p>
                            </div>
                          );
                        }
                      )}
                    </div>
                    <p className="t7-eval-summary">{evaluation.summary}</p>
                  </div>
                )}

                {/* Coaching feedback */}
                <div className="coaching-card">
                  <h4>Coaching feedback</h4>
                  {displayAnalysis.coaching_tips?.length ? (
                    <ul className="t7-tips">
                      {displayAnalysis.coaching_tips.map((tip) => (
                        <li key={tip}>{tip}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>No coaching issues detected for this message.</p>
                  )}
                </div>

                {/* Escalation reasoning */}
                <div className="coaching-card escalation-card">
                  <h4>Escalation risk detail</h4>
                  <div className="risk-row">
                    <span
                      className={`risk-badge ${String(
                        displayAnalysis.escalation_level || "low"
                      ).toLowerCase()}`}
                    >
                      {displayAnalysis.escalation_level}
                    </span>
                    <span className="risk-meta">
                      Trend: {displayAnalysis.escalation_trend} - Turn{" "}
                      {displayAnalysis.turn} - Negative streak:{" "}
                      {displayAnalysis.negative_streak}
                    </span>
                  </div>

                  {displayAnalysis.escalation_indicators?.length > 0 && (
                    <div className="indicator-chips">
                      {displayAnalysis.escalation_indicators.map(
                        (indicator) => (
                          <span className="indicator-chip" key={indicator.name}>
                            {titleCase(indicator.name)} (+{indicator.points})
                          </span>
                        )
                      )}
                    </div>
                  )}

                  {displayAnalysis.escalation_reasoning?.length > 0 && (
                    <div className="reasoning-list">
                      <strong>Why this score:</strong>
                      <ul>
                        {displayAnalysis.escalation_reasoning
                          .slice(0, 5)
                          .map((line) => (
                            <li key={line}>{line}</li>
                          ))}
                      </ul>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>


          {/* PANEL 3 - KNOWLEDGE RECOMMENDATIONS */}
          <div className="knowledge-panel">
            <div className="panel-header">
              <h3>Knowledge Recommendations</h3>
              <span>
                Retrieved for the current customer message and conversation
              </span>
            </div>

            {!displayAnalysis?.knowledge_results?.length ? (
              renderEmptyPanels("knowledge")
            ) : (
              <div className="rag-results">
                {displayAnalysis.knowledge_results.map((result, index) => {
                  const meta = result.metadata || {};
                  const score = Math.round((result.score || 0) * 100);
                  return (
                    <div className="rag-result" key={knowledgeId(result, index)}>
                      <div className="rag-result-header">
                        <strong>
                          {meta.source
                            ? String(meta.source).replace(/_/g, " ")
                            : "Support knowledge"}
                        </strong>
                        <span>
                          Relevance {score}%
                          {meta.page ? ` - page ${meta.page}` : ""}
                        </span>
                      </div>

                      <p>{result.text}</p>

                      <button
                        type="button"
                        className="use-suggestion-button"
                        onClick={() =>
                          setOpenKnowledge({ ...result, relevance: score })
                        }
                      >
                        Open full article
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {displayAnalysis && (
              <div className="knowledge-card">
                <h4>Knowledge coverage</h4>
                <p>
                  {displayAnalysis.knowledge_available === false
                    ? "The knowledge base is currently unavailable, so recommendations could not be retrieved."
                    : displayAnalysis.knowledge_results?.length
                    ? `${displayAnalysis.knowledge_results.length} relevant source(s) found for this message.`
                    : "No matching knowledge-base article was found for this message - flag it as a knowledge gap."}
                </p>
              </div>
            )}
          </div>
        </section>


        {/* ============ ESCALATION PROGRESSION + SUMMARY ============ */}
        <section className="t7-bottom-grid">
          <div className="t7-card">
            <h3>Escalation-risk progression</h3>
            <p className="t7-card-hint">
              Risk score (0-100) after each analysed customer message.
            </p>
            <LineChart
              data={riskTimeline.map((point) => ({
                label: point.label,
                value: point.value,
              }))}
              yMax={100}
              height={200}
              emptyLabel="Analyse at least one customer message to see the escalation-risk progression."
            />
          </div>

          <div className="t7-card">
            <h3>{isReplay ? "Replay summary" : "Conversation summary"}</h3>

            {!conversationSummary.hasAnalysis ? (
              <p className="t7-card-hint">
                A summary of the conversation appears once the first customer
                message has been analysed.
              </p>
            ) : (
              <>
                <div className="t7-summary-grid">
                  <div>
                    <span>Messages</span>
                    <strong>{conversationSummary.totalMessages}</strong>
                  </div>
                  <div>
                    <span>Customer</span>
                    <strong>{conversationSummary.customerMessages}</strong>
                  </div>
                  <div>
                    <span>Agent</span>
                    <strong>{conversationSummary.agentMessages}</strong>
                  </div>
                  <div>
                    <span>Peak risk</span>
                    <strong>{conversationSummary.peakRisk}/100</strong>
                  </div>
                  <div>
                    <span>Risk start</span>
                    <strong>{conversationSummary.startRisk}/100</strong>
                  </div>
                  <div>
                    <span>Risk end</span>
                    <strong>{conversationSummary.endRisk}/100</strong>
                  </div>
                  <div>
                    <span>Frustration</span>
                    <strong>
                      {conversationSummary.firstFrustration} to{" "}
                      {conversationSummary.lastFrustration}
                    </strong>
                  </div>
                  <div>
                    <span>Sentiment</span>
                    <strong>
                      {titleCase(conversationSummary.firstSentiment)} to{" "}
                      {titleCase(conversationSummary.lastSentiment)}
                    </strong>
                  </div>
                </div>

                <p className="t7-card-hint">
                  Intents seen:{" "}
                  {conversationSummary.intents.length
                    ? conversationSummary.intents
                        .map((intent) => titleCase(intent))
                        .join(", ")
                    : "none detected"}
                </p>

                {replayFinished && (
                  <p className="t7-card-hint">
                    Replay complete - all {conversationSummary.totalMessages}{" "}
                    messages of the transcript were replayed and analysed.
                  </p>
                )}

                <button
                  type="button"
                  className="primary-button"
                  onClick={handleSaveAndOpenSummary}
                  disabled={saving || !canSave}
                >
                  {saving
                    ? "Saving conversation..."
                    : "End conversation and open Task 8 summary"}
                </button>
              </>
            )}
          </div>
        </section>

      </main>

      {/* ============ KNOWLEDGE CONTENT VIEWER ============ */}
      {openKnowledge && (
        <div
          className="t7-modal-backdrop"
          role="dialog"
          aria-modal="true"
          onClick={() => setOpenKnowledge(null)}
        >
          <div
            className="t7-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="t7-modal-header">
              <div>
                <h3>
                  {openKnowledge.metadata?.source
                    ? String(openKnowledge.metadata.source).replace(/_/g, " ")
                    : "Knowledge article"}
                </h3>
                <span>
                  {openKnowledge.metadata?.page
                    ? `Page ${openKnowledge.metadata.page} - `
                    : ""}
                  Relevance {openKnowledge.relevance}%
                </span>
              </div>
              <button
                type="button"
                className="secondary-button"
                onClick={() => setOpenKnowledge(null)}
              >
                Close
              </button>
            </div>

            <div className="t7-modal-body">
              <p>{openKnowledge.text}</p>
            </div>

            {!isReplay && (
              <div className="t7-modal-footer">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    setAgentDraft(openKnowledge.text);
                    setOpenKnowledge(null);
                    setNotice(
                      "Article content copied into the reply box - edit it into your own words before sending."
                    );
                  }}
                >
                  Insert into reply
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default Task7LiveSupportConsole;

