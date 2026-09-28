import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  startSession,
  readStoredConfig,
  getConfigOptions,
} from "../services/sessionService";

const FALLBACK_CONFIG_OPTIONS = {
  personas: [
    { value: "polite", name: "Polite Customer" },
    { value: "concerned", name: "Concerned Customer" },
    { value: "frustrated", name: "Frustrated Customer" },
    { value: "angry", name: "Angry Customer" },
    { value: "furious", name: "Furious Customer" },
  ],
  scenarios: [
    { value: "delayed_order", name: "Delayed Order" },
    { value: "refund_request", name: "Refund Request" },
    { value: "payment_failure", name: "Payment Failure" },
    { value: "account_issue", name: "Account Access Issue" },
    { value: "cancellation", name: "Cancellation Request" },
  ],
  resolutions: [
    { value: "full_refund", name: "Full Refund" },
    { value: "partial_refund", name: "Partial Refund" },
    { value: "replacement", name: "Replacement" },
    { value: "store_credit", name: "Store Credit" },
    { value: "cancellation_confirmed", name: "Cancellation Confirmed" },
    { value: "account_restored", name: "Account Restored" },
    { value: "new_delivery_date", name: "New Delivery Date" },
  ],
};

function SessionConfiguration() {
  const navigate = useNavigate();

  const [form, setForm] = useState(() => {
    const stored = readStoredConfig();
    return {
      mode: stored?.mode || "simulator",
      persona: stored?.persona || "frustrated",
      scenario: stored?.scenario || "delayed_order",
      initial_emotion: stored?.initial_emotion || "frustrated",
      severity: stored?.severity || "medium",
      expected_resolution: stored?.expected_resolution || "full_refund",
      frustration_level: stored?.frustration_level !== undefined ? stored.frustration_level : 5,
      patience: stored?.patience !== undefined ? stored.patience : 5,
    };
  });

  const [configOptions, setConfigOptions] = useState(FALLBACK_CONFIG_OPTIONS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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
        resolutions: options.resolutions?.length
          ? options.resolutions.map((r) =>
              typeof r === "string"
                ? {
                    value: r,
                    name: r
                      .split("_")
                      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                      .join(" "),
                  }
                : r
            )
          : FALLBACK_CONFIG_OPTIONS.resolutions,
      });
    });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleChange = (event) => {
    const { name, value, type } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: type === "range" || name === "patience" || name === "frustration_level" ? Number(value) : value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    setLoading(true);
    setError("");

    try {
      const data = await startSession(form);

      navigate(`/session/${data.session_id}`, {
        state: {
          customerMessage: data.customer_message,
          currentEmotion: data.current_emotion,
          intensity: data.intensity,
          sessionData: form,
        },
      });
    } catch (err) {
      console.error("Failed to start session:", err);

      const errorMessage =
        err.response?.data?.detail ||
        "Unable to start session. Please make sure the backend is running.";

      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="config-page">
      {/* ================= HEADER ================= */}
      <header className="config-header">
        <div>
          <h2>SupportAI</h2>
          <span>Customer Support Coach</span>
        </div>

        <button onClick={() => navigate("/")}>
          Back to Dashboard
        </button>
      </header>

      {/* ================= MAIN CONTENT ================= */}
      <main className="config-content">
        <div className="config-title">
          <h1>Create New Session</h1>
          <p>
            Configure the customer interaction before starting your support training session.
          </p>
        </div>

        {/* ================= CONFIGURATION FORM ================= */}
        <form onSubmit={handleSubmit} className="config-card">
          {/* ================= INTERACTION MODE ================= */}
          <div className="form-section">
            <h2>Interaction Mode</h2>

            <div className="mode-grid">
              {/* Simulator */}
              <label className={`mode-option ${form.mode === "simulator" ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="mode"
                  value="simulator"
                  checked={form.mode === "simulator"}
                  onChange={handleChange}
                />
                <div>
                  <strong>Simulator</strong>
                  <p>Practice with an AI-generated customer.</p>
                </div>
              </label>

              {/* Manual */}
              <label className={`mode-option ${form.mode === "manual" ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="mode"
                  value="manual"
                  checked={form.mode === "manual"}
                  onChange={handleChange}
                />
                <div>
                  <strong>Manual</strong>
                  <p>Practice using manually controlled interactions.</p>
                </div>
              </label>

              {/* Replay */}
              <label className={`mode-option ${form.mode === "replay" ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="mode"
                  value="replay"
                  checked={form.mode === "replay"}
                  onChange={handleChange}
                />
                <div>
                  <strong>Replay</strong>
                  <p>Review a previous customer interaction.</p>
                </div>
              </label>
            </div>
          </div>

          {/* ================= CUSTOMER CONFIGURATION ================= */}
          <div className="form-section">
            <h2>Customer Configuration</h2>

            <div className="form-grid">
              {/* Persona */}
              <div className="form-group">
                <label>Customer Persona</label>
                <select name="persona" value={form.persona} onChange={handleChange}>
                  {configOptions.personas.map((persona) => (
                    <option key={persona.value} value={persona.value}>
                      {persona.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Scenario */}
              <div className="form-group">
                <label>Scenario</label>
                <select name="scenario" value={form.scenario} onChange={handleChange}>
                  {configOptions.scenarios.map((scenario) => (
                    <option key={scenario.value} value={scenario.value}>
                      {scenario.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Initial Emotion */}
              <div className="form-group">
                <label>Initial Emotion</label>
                <select name="initial_emotion" value={form.initial_emotion} onChange={handleChange}>
                  <option value="frustrated">Moderately Frustrated</option>
                  <option value="calm">Calm</option>
                  <option value="neutral">Neutral</option>
                  <option value="worried">Worried</option>
                  <option value="angry">Angry</option>
                  <option value="furious">Furious</option>
                </select>
              </div>

              {/* Severity */}
              <div className="form-group">
                <label>Issue Severity</label>
                <select name="severity" value={form.severity} onChange={handleChange}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>

              {/* Expected Resolution */}
              <div className="form-group">
                <label>Expected Resolution</label>
                <select
                  name="expected_resolution"
                  value={form.expected_resolution}
                  onChange={handleChange}
                >
                  {configOptions.resolutions.map((res) => (
                    <option key={res.value} value={res.value}>
                      {res.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* ================= INITIAL FRUSTRATION LEVEL ================= */}
          <div className="form-section">
            <div className="patience-heading">
              <div>
                <h2>Initial Frustration Level</h2>
                <p>Sets the customer's starting frustration on a 1–10 scale.</p>
              </div>
              <strong>{form.frustration_level || 5}/10</strong>
            </div>

            <input
              className="patience-slider"
              type="range"
              name="frustration_level"
              min="1"
              max="10"
              value={form.frustration_level || 5}
              onChange={handleChange}
            />

            <div className="slider-labels">
              <span>1 (Very Calm)</span>
              <span>10 (Extremely Angry)</span>
            </div>
          </div>

          {/* ================= CUSTOMER PATIENCE LEVEL ================= */}
          <div className="form-section">
            <div className="patience-heading">
              <div>
                <h2>Customer Patience Level</h2>
                <p>Controls how quickly the customer loses patience with slow responses.</p>
              </div>
              <strong>{form.patience || 5}/10</strong>
            </div>

            <input
              className="patience-slider"
              type="range"
              name="patience"
              min="1"
              max="10"
              value={form.patience || 5}
              onChange={handleChange}
            />

            <div className="slider-labels">
              <span>1 (Very Patient)</span>
              <span>10 (Very Impatient)</span>
            </div>
          </div>

          {/* ================= ERROR MESSAGE ================= */}
          {error && <div className="error-message">{error}</div>}

          {/* ================= ACTION BUTTONS ================= */}
          <div className="config-actions">
            <button
              type="button"
              className="cancel-button"
              onClick={() => navigate("/")}
              disabled={loading}
            >
              Cancel
            </button>

            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? "Starting Session..." : "Start Session"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}

export default SessionConfiguration;