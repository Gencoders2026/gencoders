import { BrowserRouter, Routes, Route } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import SessionAutoStart from "./pages/SessionAutoStart";
import SessionConfiguration from "./pages/SessionConfiguration";
import SupportConsole from "./pages/SupportConsole";
import SessionResult from "./pages/SessionResult";
import Analytics from "./pages/Analytics";
import Task6EscalationRiskMonitor from "./pages/Task6EscalationRiskMonitor";
import Task7LiveSupportConsole from "./pages/Task7LiveSupportConsole";
import Task8Analytics from "./pages/Task8Analytics";
import Task8Summary from "./pages/Task8Summary";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Main landing dashboard with "+ Start New Session", stats, and recent sessions */}
        <Route path="/" element={<Dashboard />} />
        <Route path="/dashboard" element={<Dashboard />} />

        {/* Full Customer Configuration screen (mode / persona / scenario / initial emotion / severity / resolution / frustration & patience sliders) */}
        <Route path="/session/new" element={<SessionConfiguration />} />

        {/* Auto-start convenience route */}
        <Route path="/auto" element={<SessionAutoStart />} />

        {/* Live Support Console with Task 6 AI Analysis, Coaching, Suggestions, Knowledge & Escalation Risk Monitor */}
        <Route path="/session/:sessionId" element={<SupportConsole />} />
        <Route path="/session/:sessionId/result" element={<SessionResult />} />

        {/* Analytics page */}
        <Route path="/analytics" element={<Analytics />} />

        {/* Dedicated Task 6 screen: Escalation Risk Monitor.
            Reachable from the console/dashboard "Task 6" button or
            directly at /task6. */}
        <Route
          path="/task6"
          element={<Task6EscalationRiskMonitor />}
        />

        {/* Task 7 - Live Support Console (three panels + Manual Mode +
            Replay Mode). The mode is a query parameter so both modes are
            directly linkable: /task7?mode=manual, /task7?mode=replay. */}
        <Route
          path="/task7"
          element={<Task7LiveSupportConsole />}
        />

        {/* Task 8 - Performance Analytics dashboard: multi-session
            insights (resolution/escalation frequency, sentiment,
            recurring issues, knowledge gaps). */}
        <Route
          path="/task8"
          element={<Task8Analytics />}
        />

        {/* Task 8 - Post-Interaction Summary: structured report for ONE
            conversation (recorded, simulator or demo). */}
        <Route
          path="/task8/summary"
          element={<Task8Summary />}
        />

      </Routes>
    </BrowserRouter>
  );
}

export default App;
