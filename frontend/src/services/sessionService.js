import api from "./api";

export async function startSession(sessionData) {
  const severityMap = {
    low: 3,
    medium: 5,
    high: 8,
  };

  const resolutionMap = {
    delayed_order: "delivery_update",
    refund_request: "full_refund",
    payment_issue: "payment_resolution",
    account_login: "account_access",
  };

  try {
    const response = await api.post("/session/start", {
      persona: sessionData.persona,
      scenario: sessionData.scenario,
      initial_emotion: sessionData.initial_emotion,
      issue_severity: severityMap[sessionData.severity] || 5,
      patience_level: Number(sessionData.patience) || 5,
      expected_resolution:
        resolutionMap[sessionData.scenario] || "resolve_issue",
      use_llm: true,
    });

    return response.data;
  } catch (error) {
    const detail = error.response?.data?.detail;

    if (Array.isArray(detail)) {
      const message = detail
        .map((item) => item.msg || "Invalid request")
        .join(", ");

      throw new Error(message);
    }

    if (typeof detail === "string") {
      throw new Error(detail);
    }

    throw new Error(
      "Unable to start session. Please check that the backend is running."
    );
  }
}

export async function sendMessage(sessionId, message) {
  const response = await api.post("/session/respond", {
    session_id: sessionId,
    message,
  });

  return response.data;
}

export async function getSession(sessionId) {
  const response = await api.get(`/session/${sessionId}`);
  return response.data;
}

export async function endSession(sessionId) {
  const response = await api.delete(`/session/${sessionId}`);
  return response.data;
}

export async function getSessions() {
  const response = await api.get("/sessions");
  return response.data;
}