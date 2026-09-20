import api from "./api";

/**
 * Task 6 - Support Assistance service.
 *
 * Talks to the integrated pipeline endpoint:
 *   Intent & Sentiment -> Knowledge Recommendation ->
 *   Coaching & Response Suggestion -> Escalation Risk Monitor
 */
export async function analyzeSupport(
  query,
  sessionId = null,
  turn = null,
  threshold = null
) {
  const response = await api.post("/support/analyze", {
    query,
    session_id: sessionId,
    turn,
    threshold,
  });

  return response.data;
}

/** Evaluate a drafted agent response (tone/clarity/empathy/professionalism). */
export async function evaluateResponse(response, intent = null) {
  const result = await api.post("/coaching/evaluate", {
    response,
    intent,
  });

  return result.data;
}

/** Get the current configurable escalation alert threshold. */
export async function getEscalationThreshold() {
  const result = await api.get("/escalation/threshold");
  return result.data;
}

/** Update the configurable escalation alert threshold. */
export async function setEscalationThreshold(threshold) {
  const result = await api.post("/escalation/threshold", { threshold });
  return result.data;
}
