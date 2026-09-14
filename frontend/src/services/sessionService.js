import api from "./api";

export async function startSession(sessionData) {
  const response = await api.post("/start_session", {
    persona: sessionData.persona,
    scenario: sessionData.scenario,
    initial_emotion: sessionData.initial_emotion,
    severity: sessionData.severity,
    patience: Number(sessionData.patience),
  });

  return response.data;
}

export async function sendMessage(sessionId, agentResponse) {
  const response = await api.post("/send_message", {
    session_id: sessionId,
    agent_response: agentResponse,
  });

  return response.data;
}

export async function getSession(sessionId) {
  const response = await api.get(`/session/${sessionId}`);
  return response.data;
}

export async function endSession(sessionId) {
  const response = await api.post(`/end_session/${sessionId}`);
  return response.data;
}