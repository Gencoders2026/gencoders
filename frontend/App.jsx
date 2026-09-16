import { BrowserRouter, Routes, Route } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import SessionConfiguration from "./pages/SessionConfiguration";
import SupportConsole from "./pages/SupportConsole";
import SessionResult from "./pages/SessionResult";
import Analytics from "./pages/Analytics";

function App() {
  return (
    <BrowserRouter>
      <Routes>

        <Route path="/" element={<Dashboard />} />

        <Route
          path="/session/new"
          element={<SessionConfiguration />}
        />

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