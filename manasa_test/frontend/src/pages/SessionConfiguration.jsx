import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { startSession } from "../services/sessionService";

function SessionConfiguration() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    mode: "simulator",
    persona: "frustrated",
    scenario: "delayed_order",
    initial_emotion: "frustrated",
    severity: "medium",
    patience: 5,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (event) => {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    setLoading(true);
    setError("");

    try {
      console.log("Starting session with configuration:", form);

      const data = await startSession(form);

      console.log("Backend response:", data);

      /*
        Backend response:
        {
          session_id: "...",
          customer_message: "...",
          current_emotion: "...",
          intensity: ...
        }
      */

      navigate(`/session/${data.session_id}`, {
        state: {
          customerMessage: data.customer_message,
          currentEmotion: data.current_emotion,
          intensity: data.intensity,
          sessionData: form,
        },
      });
    } catch (error) {
      console.error("Failed to start session:", error);

      const errorMessage =
        error.response?.data?.detail ||
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
            Configure the customer interaction before starting
            your support training session.
          </p>

        </div>


        {/* ================= CONFIGURATION FORM ================= */}

        <form
          onSubmit={handleSubmit}
          className="config-card"
        >


          {/* ================= INTERACTION MODE ================= */}

          <div className="form-section">

            <h2>Interaction Mode</h2>

            <div className="mode-grid">


              {/* Simulator */}

              <label
                className={`mode-option ${
                  form.mode === "simulator" ? "selected" : ""
                }`}
              >

                <input
                  type="radio"
                  name="mode"
                  value="simulator"
                  checked={form.mode === "simulator"}
                  onChange={handleChange}
                />

                <div>
                  <strong>Simulator</strong>

                  <p>
                    Practice with an AI-generated customer.
                  </p>
                </div>

              </label>


              {/* Manual */}

              <label
                className={`mode-option ${
                  form.mode === "manual" ? "selected" : ""
                }`}
              >

                <input
                  type="radio"
                  name="mode"
                  value="manual"
                  checked={form.mode === "manual"}
                  onChange={handleChange}
                />

                <div>
                  <strong>Manual</strong>

                  <p>
                    Practice using manually controlled interactions.
                  </p>
                </div>

              </label>


              {/* Replay */}

              <label
                className={`mode-option ${
                  form.mode === "replay" ? "selected" : ""
                }`}
              >

                <input
                  type="radio"
                  name="mode"
                  value="replay"
                  checked={form.mode === "replay"}
                  onChange={handleChange}
                />

                <div>
                  <strong>Replay</strong>

                  <p>
                    Review a previous customer interaction.
                  </p>
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

                <select
                  name="persona"
                  value={form.persona}
                  onChange={handleChange}
                >

                  <option value="frustrated">
                    Frustrated Customer
                  </option>

                  <option value="calm">
                    Calm Customer
                  </option>

                  <option value="impatient">
                    Impatient Customer
                  </option>

                  <option value="angry">
                    Angry Customer
                  </option>

                </select>

              </div>


              {/* Scenario */}

              <div className="form-group">

                <label>Scenario</label>

                <select
                  name="scenario"
                  value={form.scenario}
                  onChange={handleChange}
                >

                  <option value="delayed_order">
                    Delayed Order
                  </option>

                  <option value="refund_request">
                    Refund Request
                  </option>

                  <option value="payment_issue">
                    Payment Issue
                  </option>

                  <option value="account_login">
                    Account Login
                  </option>

                </select>

              </div>


              {/* Initial Emotion */}

              <div className="form-group">

                <label>Initial Emotion</label>

                <select
                  name="initial_emotion"
                  value={form.initial_emotion}
                  onChange={handleChange}
                >

                  <option value="frustrated">
                    Frustrated
                  </option>

                  <option value="neutral">
                    Neutral
                  </option>

                  <option value="angry">
                    Angry
                  </option>

                  <option value="worried">
                    Worried
                  </option>

                </select>

              </div>


              {/* Severity */}

              <div className="form-group">

                <label>Severity</label>

                <select
                  name="severity"
                  value={form.severity}
                  onChange={handleChange}
                >

                  <option value="low">
                    Low
                  </option>

                  <option value="medium">
                    Medium
                  </option>

                  <option value="high">
                    High
                  </option>

                </select>

              </div>

            </div>

          </div>


          {/* ================= CUSTOMER PATIENCE ================= */}

          <div className="form-section">

            <div className="patience-heading">

              <div>

                <h2>Customer Patience</h2>

                <p>
                  Controls how quickly the customer's patience decreases.
                </p>

              </div>

              <strong>
                {form.patience}
              </strong>

            </div>


            <input
              className="patience-slider"
              type="range"
              name="patience"
              min="1"
              max="10"
              value={form.patience}
              onChange={handleChange}
            />


            <div className="slider-labels">

              <span>Impatient</span>

              <span>Patient</span>

            </div>

          </div>


          {/* ================= ERROR MESSAGE ================= */}

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}


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


            <button
              type="submit"
              className="primary-button"
              disabled={loading}
            >

              {loading
                ? "Starting Session..."
                : "Start Session"}

            </button>

          </div>

        </form>

      </main>

    </div>
  );
}

export default SessionConfiguration;