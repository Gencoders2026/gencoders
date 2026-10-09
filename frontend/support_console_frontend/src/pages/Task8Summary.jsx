import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  getSummaryReport,
  listConversations,
  loadDemoData,
} from "../services/task8Service";
import { LineChart } from "../components/Charts";

/**
 * Task 8 - Post-Interaction Summary.
 *
 * Pick one conversation (recorded in the Task 7 console, produced by the
 * Task 3 simulator, or a labelled demo) and render the structured
 * post-interaction report:
 *
 *   - overall summary text and primary issue
 *   - resolution quality score with its 4 weighted factors
 *   - conversation statistics
 *   - sentiment timeline / journey and risk progression chart
 *   - escalation trigger counts
 *   - strengths, weaknesses and prioritised coaching recommendations
 *   - per-agent-turn quality scores and the conversation transcript
 */

function factorTone(score) {
  if (score >= 75) return "good";
  if (score >= 50) return "warn";
  return "bad";
}

function qualityTone(score) {
  if (score >= 75) return "good";
  if (score >= 50) return "warn";
  return "bad";
}

function titleCase(value) {
  if (!value) return "-";
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function sourceLabel(conversation) {
  if (conversation.is_demo) return "demo";
  return conversation.source;
}

export default function Task8Summary() {
  const navigate = useNavigate();

  const [conversations, setConversations] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const loadConversations = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await listConversations({ limit: 50, includeDemo: true });
      setConversations(payload.conversations || []);
      setSelectedId((current) => {
        if (current) return current;
        return payload.conversations?.[0]?.id || "";
      });
    } catch (requestError) {
      setError(
        requestError?.response?.data?.detail ||
          requestError?.message ||
          "Failed to load conversations."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const generate = useCallback(async (conversationId) => {
    if (!conversationId) return;
    setReportLoading(true);
    setError("");
    try {
      const conversation = conversations.find(
        (item) => item.id === conversationId
      );
      const payload =
        conversation?.source === "simulator"
          ? await getSummaryReport({ simulatorSessionId: conversationId })
          : await getSummaryReport({ conversationId });
      setReport(payload);
    } catch (requestError) {
      setReport(null);
      setError(
        requestError?.response?.data?.detail ||
          requestError?.message ||
          "Failed to build the summary."
      );
    } finally {
      setReportLoading(false);
    }
  }, [conversations]);

  useEffect(() => {
    if (selectedId && conversations.length > 0) {
      generate(selectedId);
    }
    // Re-generate only when the picker value changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, conversations.length]);

  async function handleLoadDemo() {
    try {
      const result = await loadDemoData();
      setNote(
        `${result.written} labelled demo conversation(s) loaded into the store.`
      );
      await loadConversations();
    } catch (requestError) {
      setNote(requestError?.response?.data?.detail || "Failed to load demos.");
    }
  }

  const factors = useMemo(() => {
    const raw = report?.resolution_quality?.factors;
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    return Object.entries(raw).map(([key, value]) => ({
      key,
      score: typeof value === "object" ? value.score : Number(value),
      label: (typeof value === "object" && value.label) || titleCase(key),
      weight:
        (typeof value === "object" && value.weight) ??
        report?.resolution_quality?.weights?.[key] ??
        null,
      detail: typeof value === "object" ? value.detail : null,
    }));
  }, [report]);

  const riskData = useMemo(
    () =>
      (report?.risk_progression || []).map((point) => ({
        label: point.label || `#${point.turn}`,
        value: point.value,
      })),
    [report]
  );

  const selected = conversations.find((item) => item.id === selectedId);

  return (
    <div className="t7-page">
      <header className="t7-topbar">
        <div>
          <h1 className="t7-title">Task 8 - Post-Interaction Summary</h1>
          <p className="t7-subtitle">
            Structured report for one conversation: resolution quality,
            sentiment journey, escalation triggers and prioritised coaching
            recommendations.
          </p>
        </div>
        <div className="t7-topbar-actions">
          <button
            type="button"
            className="t7-ghost-btn"
            onClick={() => navigate("/task8")}
          >
            Performance Analytics
          </button>
          <button
            type="button"
            className="t7-ghost-btn"
            onClick={() => navigate("/task7")}
          >
            Task 7 Console
          </button>
          <button
            type="button"
            className="t7-ghost-btn"
            onClick={() => navigate("/dashboard")}
          >
            Dashboard
          </button>
        </div>
      </header>

      <section className="t7-card t8-controls">
        <label className="t7-label">
          Conversation
          <select
            value={selectedId}
            onChange={(event) => setSelectedId(event.target.value)}
            disabled={loading}
          >
            {conversations.length === 0 && (
              <option value="">No conversations yet</option>
            )}
            {conversations.map((conversation) => (
              <option key={conversation.id} value={conversation.id}>
                {conversation.title || conversation.id} -{" "}
                {sourceLabel(conversation)} - {conversation.messages} msg
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="t7-primary-btn"
          onClick={() => generate(selectedId)}
          disabled={!selectedId || reportLoading}
        >
          {reportLoading ? "Building..." : "Regenerate report"}
        </button>

        <button
          type="button"
          className="t7-ghost-btn"
          onClick={handleLoadDemo}
        >
          Load demo data
        </button>

        <button
          type="button"
          className="t7-ghost-btn"
          onClick={loadConversations}
        >
          Refresh list
        </button>

        {note && <span className="t8-demo-note">{note}</span>}
      </section>

      {error && <div className="t7-notice error">{error}</div>}
      {!loading && conversations.length === 0 && (
        <div className="t7-empty">
          No conversations to summarise yet. Record one in the Task 7 Live
          Support Console, run a simulation, or load the demo data.
        </div>
      )}
      {reportLoading && <div className="t7-loading">Building the report...</div>}


      {report && (
        <>
          {/* ---------- report header ---------- */}
          <section className="t7-card t8-report-head">
            <div>
              <div className="t7-card-title">{report.title || "Conversation"}</div>
              <p className="t7-card-hint">
                {titleCase(report.mode)} mode - {report.persona || "unknown persona"}{" "}
                - {report.scenario || "unknown scenario"}
              </p>
              <p className="t7-card-hint">
                {report.conversation_id} - generated {report.generated_at}
                {report.completed_at ? ` - completed ${report.completed_at}` : ""}
              </p>
            </div>
            <div className="t8-report-tags">
              <span className="t7-chip">
                primary issue: {titleCase(report.primary_issue)}
              </span>
              <span
                className={`t7-chip sentiment ${
                  report.final_resolution?.customer_confirmed
                    ? "positive"
                    : report.final_resolution?.status === "resolved"
                    ? "positive"
                    : report.final_resolution?.status === "escalated"
                    ? "negative"
                    : "neutral"
                }`}
              >
                {report.final_resolution?.label || "Resolution not detected"}
              </span>
            </div>
          </section>

          {/* ---------- overall summary ---------- */}
          <section className="t7-card">
            <div className="t7-card-title">Overall summary</div>
            <p className="t8-summary-text">{report.summary}</p>
          </section>

          {/* ---------- resolution quality ---------- */}
          <section className="t8-two-col">
            <div className="t7-card">
              <div className="t7-card-title">Resolution quality</div>
              <div className={`t8-score ${qualityTone(report.resolution_quality?.score)}`}>
                <strong>{report.resolution_quality?.score}</strong>
                <span>/ 100</span>
                <em>{report.resolution_quality?.band}</em>
              </div>
              <ul className="t8-factors">
                {factors.map((factor) => (
                  <li key={factor.key || factor.label}>
                    <div className="t8-factor-head">
                      <span>{titleCase(factor.key || factor.label)}</span>
                      <strong className={factorTone(factor.score)}>
                        {factor.score}
                        {factor.weight != null ? ` (weight ${factor.weight})` : ""}
                      </strong>
                    </div>
                    <div className="t7-progress">
                      <div className="t7-progress-bar">
                        <div
                          className={`t7-progress-fill tone-${factorTone(
                            factor.score
                          )}`}
                          style={{
                            width: `${Math.max(
                              0,
                              Math.min(100, factor.score)
                            )}%`,
                          }}
                        />
                      </div>
                    </div>
                    {factor.detail && (
                      <p className="t7-card-hint">{factor.detail}</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <div className="t7-card">
              <div className="t7-card-title">Conversation statistics</div>
              <div className="t7-summary-grid">
                <div className="t7-state-item">
                  <span>Total messages</span>
                  <strong>{report.statistics?.total_messages}</strong>
                </div>
                <div className="t7-state-item">
                  <span>Customer messages</span>
                  <strong>{report.statistics?.customer_messages}</strong>
                </div>
                <div className="t7-state-item">
                  <span>Agent replies</span>
                  <strong>{report.statistics?.agent_messages}</strong>
                </div>
                <div className="t7-state-item">
                  <span>Avg response quality</span>
                  <strong>{report.statistics?.avg_response_quality}%</strong>
                </div>
                <div className="t7-state-item">
                  <span>Below-bar responses</span>
                  <strong>{report.statistics?.below_bar_responses}</strong>
                </div>
                <div className="t7-state-item">
                  <span>Alerts triggered</span>
                  <strong>{report.statistics?.alerts_triggered}</strong>
                </div>
                <div className="t7-state-item">
                  <span>Peak escalation</span>
                  <strong>
                    {report.statistics?.peak_escalation_score}/100 (
                    {report.statistics?.peak_escalation_level})
                  </strong>
                </div>
                <div className="t7-state-item">
                  <span>Frustration</span>
                  <strong>
                    {report.statistics?.frustration_start} -&gt;{" "}
                    {report.statistics?.frustration_end}
                  </strong>
                </div>
                <div className="t7-state-item">
                  <span>Sentiment</span>
                  <strong>
                    {report.statistics?.sentiment_start} -&gt;{" "}
                    {report.statistics?.sentiment_end}
                  </strong>
                </div>
              </div>
            </div>
          </section>


          {/* ---------- risk progression + sentiment ---------- */}
          <section className="t8-two-col">
            <div className="t7-card">
              <div className="t7-card-title">Escalation risk progression</div>
              <p className="t7-card-hint">
                Risk score (0-100) evaluated after every customer message.
              </p>
              <LineChart data={riskData} yMax={100} color="#dc2626" />
              <ul className="t8-list">
                {Object.entries(report.escalation_triggers || {}).map(
                  ([trigger, count]) => (
                    <li key={trigger}>
                      <span>{titleCase(trigger)}</span>
                      <strong>{count}x</strong>
                    </li>
                  )
                )}
                {Object.keys(report.escalation_triggers || {}).length === 0 && (
                  <li className="t7-empty">
                    No escalation triggers fired in this conversation.
                  </li>
                )}
              </ul>
            </div>

            <div className="t7-card">
              <div className="t7-card-title">Sentiment journey</div>
              <p className="t8-summary-text">
                {report.sentiment_journey?.narrative}
              </p>
              <div className="t7-summary-grid">
                <div className="t7-state-item">
                  <span>Start</span>
                  <strong>
                    {titleCase(report.sentiment_journey?.start?.label)} (
                    {report.sentiment_journey?.start?.frustration}/10)
                  </strong>
                </div>
                <div className="t7-state-item">
                  <span>End</span>
                  <strong>
                    {titleCase(report.sentiment_journey?.end?.label)} (
                    {report.sentiment_journey?.end?.frustration}/10)
                  </strong>
                </div>
                <div className="t7-state-item">
                  <span>Direction</span>
                  <strong>{titleCase(report.sentiment_journey?.direction)}</strong>
                </div>
                <div className="t7-state-item">
                  <span>Frustration delta</span>
                  <strong>
                    {report.sentiment_journey?.delta_frustration > 0 ? "+" : ""}
                    {report.sentiment_journey?.delta_frustration}
                  </strong>
                </div>
              </div>
            </div>
          </section>

          {/* ---------- strengths / weaknesses ---------- */}
          <section className="t8-two-col">
            <div className="t7-card">
              <div className="t7-card-title">Strengths</div>
              <ul className="t8-insight-list positive">
                {(report.strengths || []).map((strength, index) => (
                  <li key={`strength-${index}`}>
                    {typeof strength === "string" ? (
                      strength
                    ) : (
                      <>
                        <strong>{strength.title}</strong>{" "}
                        <span>{strength.detail}</span>
                      </>
                    )}
                  </li>
                ))}
                {(report.strengths || []).length === 0 && (
                  <li className="t7-empty">
                    No clear strengths recorded for this conversation.
                  </li>
                )}
              </ul>
            </div>

            <div className="t7-card">
              <div className="t7-card-title">Weaknesses</div>
              <ul className="t8-insight-list warning">
                {(report.weaknesses || []).map((weakness, index) => (
                  <li key={`weakness-${index}`}>
                    {typeof weakness === "string" ? (
                      weakness
                    ) : (
                      <>
                        <strong>{weakness.title}</strong>{" "}
                        <span>{weakness.detail}</span>
                      </>
                    )}
                  </li>
                ))}
                {(report.weaknesses || []).length === 0 && (
                  <li className="t7-empty">No weaknesses detected.</li>
                )}
              </ul>
            </div>
          </section>


          {/* ---------- coaching recommendations ---------- */}
          <section className="t7-card">
            <div className="t7-card-title">Coaching recommendations</div>
            <p className="t7-card-hint">
              Prioritised, personalised guidance for future interactions.
            </p>
            <div className="t8-rec-grid">
              {(report.coaching_recommendations || []).map(
                (recommendation, index) => (
                  <div
                    className="t7-card t8-rec-card"
                    key={`${recommendation.title}-${index}`}
                  >
                    <span
                      className={`t8-priority ${String(
                        recommendation.priority || "medium"
                      ).toLowerCase()}`}
                    >
                      {recommendation.priority} priority
                    </span>
                    <div className="t7-card-title">{recommendation.title}</div>
                    <p className="t7-card-hint">{recommendation.detail}</p>
                  </div>
                )
              )}
              {(report.coaching_recommendations || []).length === 0 && (
                <div className="t7-empty">No recommendations for this report.</div>
              )}
            </div>
          </section>

          {/* ---------- sentiment timeline ---------- */}
          <section className="t7-card">
            <div className="t7-card-title">Sentiment timeline</div>
            <p className="t7-card-hint">
              Customer state evaluated after every message (intent, emotion,
              frustration, escalation risk).
            </p>
            <div className="t8-timeline">
              {(report.sentiment_timeline || []).map((point) => (
                <div className="t8-timeline-row" key={`point-${point.turn}`}>
                  <span className="t8-timeline-turn">#{point.turn}</span>
                  <span className={`t7-chip sentiment ${point.label}`}>
                    {point.label}
                  </span>
                  <span className="t7-chip">{point.intent_label}</span>
                  <span className="t7-chip">{point.emotion}</span>
                  <span className="t7-chip">
                    frustration {point.frustration}/10
                  </span>
                  <span className={point.escalation_level === "High" || point.escalation_level === "Critical"
                    ? "t7-risk-badge high"
                    : "t7-risk-badge low"}
                  >
                    risk {point.escalation_score}/100
                  </span>
                  <span className="t8-timeline-message">{point.message}</span>
                </div>
              ))}
              {(report.sentiment_timeline || []).length === 0 && (
                <div className="t7-empty">No timeline points recorded.</div>
              )}
            </div>
          </section>

          {/* ---------- transcript ---------- */}
          <section className="t7-card">
            <div className="t7-card-title">Conversation transcript</div>
            <div className="t8-transcript">
              {(report.messages || []).map((message, index) => (
                <div
                  className={`t8-transcript-row role-${message.role}`}
                  key={`msg-${index}`}
                >
                  <span className="t8-transcript-role">{message.role}</span>
                  <span className="t8-transcript-content">{message.content}</span>
                </div>
              ))}
            </div>
          </section>

          <footer className="t8-foot">
            Session key {report.session_key} - generated {report.generated_at}
          </footer>
        </>
      )}
    </div>
  );
}

