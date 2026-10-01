import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getAnalytics, loadDemoData } from "../services/task8Service";
import { BarChart, DonutChart, LineChart } from "../components/Charts";

/**
 * Task 8 - Performance Analytics dashboard.
 *
 * Six sections: metric header, charts, frequent issues, escalation
 * reasons, knowledge gaps / repeated searches / incorrect responses /
 * unresolved queries, and the insights + recommendations feed.
 *
 * The Post-Interaction Summary lives on /task8/summary.
 */

const LIMITS = [10, 15, 25, 50, 100];

function Metric({ label, value, hint, tone }) {
  return (
    <div className={`t8-metric ${tone ? `tone-${tone}` : ""}`}>
      <span className="t8-metric-label">{label}</span>
      <strong className="t8-metric-value">{value}</strong>
      {hint && <span className="t8-metric-hint">{hint}</span>}
    </div>
  );
}

function ChartCard({ title, hint, children }) {
  return (
    <div className="t7-card t8-chart-card">
      <div className="t7-card-title">{title}</div>
      {hint && <p className="t7-card-hint">{hint}</p>}
      {children}
    </div>
  );
}

function priorityClass(priority) {
  return `t8-priority ${String(priority || "medium").toLowerCase()}`;
}

/** Split a multi-series trend into single-series chart data. */
function series(rows, key, fallbackKey = "value") {
  return (rows || []).map((row) => ({
    label: row.label,
    value: row[key] ?? row[fallbackKey] ?? 0,
  }));
}

export default function Task8Analytics() {
  const navigate = useNavigate();

  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [limit, setLimit] = useState(25);
  const [simulatorLimit, setSimulatorLimit] = useState(20);
  const [includeDemo, setIncludeDemo] = useState(true);
  const [demoNote, setDemoNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await getAnalytics({
        limit,
        simulatorLimit,
        includeDemo,
      });
      setAnalytics(payload);
    } catch (requestError) {
      setError(
        requestError?.response?.data?.detail ||
          requestError?.message ||
          "Failed to load analytics."
      );
    } finally {
      setLoading(false);
    }
  }, [limit, simulatorLimit, includeDemo]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleLoadDemo() {
    try {
      const result = await loadDemoData();
      setDemoNote(
        `${result.written} labelled demo conversation(s) loaded into the store.`
      );
      await load();
    } catch (requestError) {
      setDemoNote(
        requestError?.response?.data?.detail || "Failed to load demo data."
      );
    }
  }

  const summary = analytics?.summary || null;
  const charts = analytics?.charts || {};
  const sources = analytics?.data_sources || {};

  const issueDonut = useMemo(
    () =>
      (charts.issue_distribution || []).map((row, index) => ({
        label: row.label,
        value: row.value,
        color: ["#2563eb", "#dc2626", "#f59e0b", "#16a34a", "#7c3aed", "#0891b2"][
          index % 6
        ],
      })),
    [charts.issue_distribution]
  );

  const resolutionDonut = useMemo(
    () =>
      (charts.resolution_breakdown || []).map((row, index) => ({
        label: row.label,
        value: row.value,
        color: ["#16a34a", "#dc2626", "#f59e0b", "#6b7280", "#2563eb"][index % 5],
      })),
    [charts.resolution_breakdown]
  );

  return (
    <div className="t7-page">
      <header className="t7-topbar">
        <div>
          <h1 className="t7-title">Task 8 - Performance Analytics</h1>
          <p className="t7-subtitle">
            Multi-session insights: resolution and escalation frequency,
            customer sentiment, recurring issues, knowledge gaps and agent
            response quality.
          </p>
        </div>
        <div className="t7-topbar-actions">
          <button
            type="button"
            className="t7-ghost-btn"
            onClick={() => navigate("/task8/summary")}
          >
            Post-Interaction Summary
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
          Conversations analysed
          <select
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          >
            {LIMITS.map((option) => (
              <option key={option} value={option}>
                last {option}
              </option>
            ))}
          </select>
        </label>

        <label className="t7-label">
          Simulator sessions
          <select
            value={simulatorLimit}
            onChange={(event) => setSimulatorLimit(Number(event.target.value))}
          >
            {[0, 5, 10, 20, 50, 100].map((option) => (
              <option key={option} value={option}>
                {option === 0 ? "none" : `last ${option}`}
              </option>
            ))}
          </select>
        </label>

        <label className="t7-label t8-checkbox">
          <input
            type="checkbox"
            checked={includeDemo}
            onChange={(event) => setIncludeDemo(event.target.checked)}
          />
          Include labelled demo conversations
        </label>

        <button
          type="button"
          className="t7-primary-btn"
          onClick={load}
          disabled={loading}
        >
          {loading ? "Loading..." : "Refresh"}
        </button>

        <button type="button" className="t7-ghost-btn" onClick={handleLoadDemo}>
          Load demo data
        </button>

        {demoNote && <span className="t8-demo-note">{demoNote}</span>}
      </section>

      {error && <div className="t7-notice error">{error}</div>}
      {loading && !analytics && (
        <div className="t7-loading">Crunching the conversation data...</div>
      )}

      {analytics && !loading && (
        <>
          {/* ---------------- 1. metric header ---------------- */}
          <section className="t8-metrics">
            <Metric
              label="Sessions analysed"
              value={summary?.sessions_analysed ?? 0}
              hint={`${sources.recorded_conversations || 0} recorded + ${
                sources.simulator_conversations || 0
              } simulator + ${sources.demo_conversations || 0} demo`}
            />
            <Metric
              label="Resolution rate"
              value={`${summary?.resolution_rate ?? 0}%`}
              hint={`${summary?.confirmed_resolution_rate ?? 0}% customer-confirmed`}
              tone={(summary?.resolution_rate ?? 0) >= 60 ? "good" : "warn"}
            />
            <Metric
              label="Escalation frequency"
              value={`${summary?.escalation_frequency ?? 0}%`}
              hint={`${summary?.escalated_sessions ?? 0} of ${
                summary?.sessions_analysed ?? 0
              } sessions escalated`}
              tone={(summary?.escalation_frequency ?? 0) > 40 ? "bad" : "good"}
            />
            <Metric
              label="Avg response quality"
              value={`${summary?.avg_response_quality ?? 0}%`}
              hint={`${summary?.weak_responses ?? 0} below-bar responses`}
              tone={(summary?.avg_response_quality ?? 0) >= 70 ? "good" : "warn"}
            />
            <Metric
              label="Sentiment improvement"
              value={`${summary?.sentiment_improved ?? 0} / ${
                summary?.sessions_analysed ?? 0
              }`}
              hint={`${summary?.sentiment_steady ?? 0} steady, ${
                summary?.sentiment_declined ?? 0
              } declined`}
            />
            <Metric
              label="Frustration trend"
              value={`${summary?.frustration_start ?? 0} -> ${
                summary?.frustration_end ?? 0
              }`}
              hint="avg start -> avg end (0-10)"
              tone={
                (summary?.frustration_end ?? 0) <=
                (summary?.frustration_start ?? 0)
                  ? "good"
                  : "bad"
              }
            />
          </section>


          {/* ---------------- 2. charts ---------------- */}
          <section className="t8-chart-grid">
            <ChartCard
              title="Resolution trend over sessions"
              hint="Blocks of conversations: resolution %, escalation %."
            >
              <LineChart
                data={series(charts.resolution_trend, "resolution_rate")}
                valueSuffix="%"
                emptyLabel="Not enough sessions yet."
              />
              <LineChart
                data={series(charts.resolution_trend, "escalation_rate")}
                color="#dc2626"
                valueSuffix="%"
                emptyLabel="Not enough sessions yet."
              />
            </ChartCard>

            <ChartCard
              title="Frustration / escalation curve"
              hint="Peak escalation score (0-100) recorded per session."
            >
              <LineChart
                data={charts.frustration_curve}
                yMax={100}
                color="#f59e0b"
                emptyLabel="No sessions yet."
              />
            </ChartCard>

            <ChartCard
              title="Interaction trend"
              hint="Message volume across conversation blocks."
            >
              <LineChart
                data={charts.interaction_trend}
                color="#2563eb"
                emptyLabel="No sessions yet."
              />
            </ChartCard>

            <ChartCard
              title="Issue distribution"
              hint="Primary issue of every analysed conversation."
            >
              <DonutChart
                data={issueDonut}
                centerLabel="sessions"
                emptyLabel="No issues detected yet."
              />
            </ChartCard>

            <ChartCard
              title="Resolution breakdown"
              hint="Resolved / unresolved / escalated / customer-confirmed."
            >
              <DonutChart
                data={resolutionDonut}
                centerLabel="sessions"
                emptyLabel="No resolution data yet."
              />
            </ChartCard>

            <ChartCard
              title="Top escalation triggers"
              hint="What pushed customers toward escalation."
            >
              <BarChart
                data={charts.escalation_triggers}
                color="#dc2626"
                emptyLabel="No escalation triggers recorded."
              />
            </ChartCard>

            <ChartCard
              title="Agent response quality"
              hint="Average score per quality dimension."
            >
              <BarChart
                data={charts.response_quality}
                color="#2563eb"
                emptyLabel="No agent responses scored yet."
              />
            </ChartCard>

            <ChartCard
              title="Knowledge coverage"
              hint="Retrieved knowledge per topic; red bars are gaps."
            >
              <BarChart
                data={(charts.knowledge_coverage || []).map((row) => ({
                  label: row.label,
                  value: row.value,
                  color: row.gap ? "#dc2626" : "#16a34a",
                }))}
                emptyLabel="No knowledge searches yet."
              />
            </ChartCard>
          </section>


          {/* ---------------- 3. frequent issues ---------------- */}
          <section className="t8-two-col">
            <div className="t7-card">
              <div className="t7-card-title">Frequent customer issues</div>
              <ul className="t8-list">
                {(analytics.issues || []).map((issue) => (
                  <li key={issue.intent}>
                    <span>{issue.label}</span>
                    <strong>
                      {issue.sessions} ({issue.rate}%)
                    </strong>
                  </li>
                ))}
                {(analytics.issues || []).length === 0 && (
                  <li className="t7-empty">No issues detected yet.</li>
                )}
              </ul>
            </div>

            <div className="t7-card">
              <div className="t7-card-title">Recurring issues</div>
              <p className="t7-card-hint">
                Topics that keep coming back across sessions and deserve a
                proactive fix.
              </p>
              <ul className="t8-list">
                {(analytics.recurring_issues || []).map((issue, index) => (
                  <li key={issue.intent || `${issue.label}-${index}`}>
                    <span>{issue.label}</span>
                    <strong>
                      {issue.sessions} session(s)
                      {issue.share ? ` - ${issue.share}%` : ""}
                    </strong>
                  </li>
                ))}
                {(analytics.recurring_issues || []).length === 0 && (
                  <li className="t7-empty">No recurring issues yet.</li>
                )}
              </ul>
            </div>
          </section>

          {/* ---------------- 4. escalation reasons ---------------- */}
          <section className="t7-card">
            <div className="t7-card-title">Escalation reasons</div>
            <p className="t7-card-hint">
              Frequency of the patterns that raise escalation risk across all
              analysed conversations.
            </p>
            <ul className="t8-list">
              {(charts.escalation_triggers || []).map((trigger) => (
                <li key={trigger.label}>
                  <span>{trigger.label}</span>
                  <strong>{trigger.value}x</strong>
                </li>
              ))}
              {(charts.escalation_triggers || []).length === 0 && (
                <li className="t7-empty">No escalation triggers recorded.</li>
              )}
            </ul>
          </section>

          {/* ---------------- 5. knowledge gaps ---------------- */}
          <section className="t8-two-col">
            <div className="t7-card">
              <div className="t7-card-title">Knowledge gaps</div>
              <p className="t7-card-hint">
                Topics customers asked about that the knowledge base could not
                cover.
              </p>
              <ul className="t8-list">
                {(analytics.knowledge_gaps || []).map((gap, index) => (
                  <li key={gap.intent || `${gap.label}-${index}`}>
                    <span>{gap.label}</span>
                    <strong>
                      {gap.retrieved ?? 0} retrieved
                      {gap.requested ? ` / ${gap.requested} requested` : ""}
                    </strong>
                  </li>
                ))}
                {(analytics.knowledge_gaps || []).length === 0 && (
                  <li className="t7-empty">
                    No knowledge gaps detected - every topic returned results.
                  </li>
                )}
              </ul>
            </div>

            <div className="t7-card">
              <div className="t7-card-title">Repeated knowledge searches</div>
              <p className="t7-card-hint">
                The same question (or topic) searched again because the first
                answer was not enough.
              </p>
              <ul className="t8-list">
                {(analytics.repeated_searches || []).map((search) => (
                  <li key={`q-${search.query}`}>
                    <span>{search.query}</span>
                    <strong>{search.searches}x</strong>
                  </li>
                ))}
                {(analytics.repeated_search_topics || []).map((topic) => (
                  <li key={`t-${topic.intent}`}>
                    <span>{topic.label} (topic)</span>
                    <strong>
                      {topic.searches}x / {topic.sessions} session(s)
                    </strong>
                  </li>
                ))}
                {(analytics.repeated_searches || []).length === 0 &&
                  (analytics.repeated_search_topics || []).length === 0 && (
                    <li className="t7-empty">
                      No repeated searches - first answers landed.
                    </li>
                  )}
              </ul>
            </div>
          </section>


          <section className="t8-two-col">
            <div className="t7-card">
              <div className="t7-card-title">Incorrect agent responses</div>
              <p className="t7-card-hint">
                Responses scored below the quality bar with the customer
                message that triggered them.
              </p>
              <ul className="t8-list t8-list-block">
                {(analytics.incorrect_responses || []).map((item, index) => (
                  <li key={`${item.session_id || "x"}-${index}`}>
                    <span className="t8-quote">"{item.message}"</span>
                    <strong>
                      quality {item.score ?? "?"}%
                      {item.session_id ? ` - ${item.session_id}` : ""}
                    </strong>
                  </li>
                ))}
                {(analytics.incorrect_responses || []).length === 0 && (
                  <li className="t7-empty">
                    No below-bar responses recorded.
                  </li>
                )}
              </ul>
            </div>

            <div className="t7-card">
              <div className="t7-card-title">Unresolved queries</div>
              <p className="t7-card-hint">
                Conversations that never reached a resolution, with the primary
                issue.
              </p>
              <ul className="t8-list t8-list-block">
                {(analytics.unresolved_queries || []).map((item) => (
                  <li key={item.id || item.session_id}>
                    <span className="t8-quote">
                      {item.title || item.session_id}
                    </span>
                    <strong>
                      {item.primary_issue_label || item.primary_issue}
                    </strong>
                  </li>
                ))}
                {(analytics.unresolved_queries || []).length === 0 && (
                  <li className="t7-empty">
                    Every analysed conversation reached a resolution.
                  </li>
                )}
              </ul>
            </div>
          </section>

          {/* ---------------- 6. insights ---------------- */}
          <section className="t7-card">
            <div className="t7-card-title">Overall insights</div>
            <ul className="t8-insight-list">
              {(analytics.overall_insights || []).map((insight, index) => (
                <li key={`insight-${index}`}>{insight}</li>
              ))}
              {(analytics.overall_insights || []).length === 0 && (
                <li className="t7-empty">
                  Analyse more conversations to generate insights.
                </li>
              )}
            </ul>
          </section>

          <section className="t8-rec-grid">
            {(analytics.recommendations || []).map((recommendation, index) => (
              <div
                className="t7-card t8-rec-card"
                key={`${recommendation.title}-${index}`}
              >
                <span className={priorityClass(recommendation.priority)}>
                  {recommendation.priority} priority
                </span>
                <div className="t7-card-title">{recommendation.title}</div>
                <p className="t7-card-hint">{recommendation.detail}</p>
              </div>
            ))}
          </section>

          <section className="t7-card">
            <div className="t7-card-title">Session insights</div>
            <div className="t8-session-grid">
              {(analytics.session_insights || []).map((session, index) => (
                <div className="t8-session-card" key={session.id || index}>
                  <div className="t8-session-head">
                    <span className="t8-session-title">{session.title}</span>
                    <span
                      className={
                        session.resolved
                          ? "t7-chip sentiment positive"
                          : "t7-chip sentiment negative"
                      }
                    >
                      {session.resolution_status || "unknown"}
                    </span>
                  </div>
                  <p className="t7-card-hint">
                    {session.primary_issue_label} - {session.turns} turn(s) -
                    peak risk {session.peak_escalation_score}/100 (
                    {session.peak_escalation_level})
                  </p>
                  {session.insight && (
                    <p className="t8-session-insight">{session.insight}</p>
                  )}
                  <div className="t8-session-foot">
                    <span>{session.mode}</span>
                    {session.is_demo && (
                      <span className="t8-demo-tag">demo</span>
                    )}
                  </div>
                </div>
              ))}
              {(analytics.session_insights || []).length === 0 && (
                <div className="t7-empty">No sessions to inspect yet.</div>
              )}
            </div>
          </section>

          <footer className="t8-foot">
            Generated at {analytics.generated_at || "-"} - demo conversations
            are clearly labelled and reported separately in data_sources.
          </footer>
        </>
      )}
    </div>
  );
}

