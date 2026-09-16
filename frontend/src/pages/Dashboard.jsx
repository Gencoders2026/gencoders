import { useNavigate } from "react-router-dom";

function Dashboard() {
  const navigate = useNavigate();

  return (
    <div className="dashboard">

      {/* Header */}
      <header className="dashboard-header">
        <div className="brand">
          <h2>SupportAI</h2>
          <span>Customer Support Coach</span>
        </div>

        <nav>
          <button onClick={() => navigate("/")}>
            Dashboard
          </button>

          <button onClick={() => navigate("/analytics")}>
            Analytics
          </button>
        </nav>
      </header>

      {/* Main Content */}
      <main className="dashboard-content">

        {/* Welcome Section */}
        <section className="welcome-section">
          <div>
            <h1>Welcome to SupportAI</h1>

            <p>
              Improve your customer support conversations with
              real-time AI coaching, knowledge recommendations,
              and escalation monitoring.
            </p>
          </div>

          <button
            className="primary-button"
            onClick={() => navigate("/session/new")}
          >
            + Start New Session
          </button>
        </section>

        {/* Statistics */}
        <section className="stats-grid">

          <div className="stat-card">
            <span className="stat-label">
              Total Sessions
            </span>

            <strong>24</strong>

            <span className="stat-description">
              Sessions completed
            </span>
          </div>

          <div className="stat-card">
            <span className="stat-label">
              Average Score
            </span>

            <strong>87%</strong>

            <span className="stat-description">
              Overall coaching score
            </span>
          </div>

          <div className="stat-card">
            <span className="stat-label">
              Escalations
            </span>

            <strong>3</strong>

            <span className="stat-description">
              High-risk conversations
            </span>
          </div>

          <div className="stat-card">
            <span className="stat-label">
              Improvement
            </span>

            <strong>+12%</strong>

            <span className="stat-description">
              Compared with previous sessions
            </span>
          </div>

        </section>

        {/* Recent Sessions */}
        <section className="recent-section">

          <div className="section-heading">
            <div>
              <h2>Recent Sessions</h2>

              <p>
                Review your latest customer support sessions.
              </p>
            </div>

            <button
              className="secondary-button"
              onClick={() => navigate("/analytics")}
            >
              View Analytics
            </button>
          </div>

          <div className="session-table">

            <div className="table-header">
              <span>Scenario</span>
              <span>Mode</span>
              <span>Score</span>
              <span>Status</span>
            </div>

            <div className="table-row">
              <span>Delayed Order</span>
              <span>Simulator</span>
              <span>92%</span>
              <span className="status completed">
                Completed
              </span>
            </div>

            <div className="table-row">
              <span>Refund Request</span>
              <span>Manual</span>
              <span>84%</span>
              <span className="status completed">
                Completed
              </span>
            </div>

            <div className="table-row">
              <span>Payment Issue</span>
              <span>Simulator</span>
              <span>76%</span>
              <span className="status completed">
                Completed
              </span>
            </div>

            <div className="table-row">
              <span>Account Login</span>
              <span>Replay</span>
              <span>89%</span>
              <span className="status completed">
                Completed
              </span>
            </div>

          </div>

        </section>

      </main>

    </div>
  );
}

export default Dashboard;