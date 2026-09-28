import { BrowserRouter, Routes, Route } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import SessionAutoStart from "./pages/SessionAutoStart";
import SessionConfiguration from "./pages/SessionConfiguration";
import SupportConsole from "./pages/SupportConsole";
import SessionResult from "./pages/SessionResult";
import Analytics from "./pages/Analytics";

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
      </Routes>
    </BrowserRouter>
  );
}

export default App;
