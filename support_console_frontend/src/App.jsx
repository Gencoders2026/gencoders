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

        {/* Opening the project lands directly on the Task 6 interface.
            `SessionAutoStart` resumes the conversation of this tab when
            there is one, otherwise it creates a session automatically
            (with the last Customer Configuration) and opens the console -
            no internal URL or session id has to be typed. */}
        <Route path="/" element={<SessionAutoStart />} />

        <Route path="/dashboard" element={<Dashboard />} />

        {/* Full Customer Configuration screen (persona / scenario /
            initial emotion / severity / patience). */}
        <Route
          path="/session/new"
          element={<SessionConfiguration />}
        />

        {/* Task 6 conversation interface + AI Analysis + Escalation Risk
            Monitor. The configuration panel lives inside this screen too,
            so the whole dashboard is visible at once. */}
        <Route
          path="/session/:sessionId"
          element={<SupportConsole />}
        />

        <Route
          path="/session/:sessionId/result"
          element={<SessionResult />}
        />

        <Route
          path="/analytics"
          element={<Analytics />}
        />

      </Routes>
    </BrowserRouter>
  );
}

export default App;
