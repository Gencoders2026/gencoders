import api from "./api";

/**
 * Task 8 - Insights & Performance Analytics service.
 *
 * Talks to the Task 8 router (`task8_insights_analytics/insights_api.py`)
 * which is mounted on the same backend as the Tasks 1-7 endpoints, so the
 * dashboard still uses ONE base URL.
 */

/** Service health + data availability. */
export async function getTask8Health() {
  const response = await api.get("/task8/health");
  return response.data;
}

/**
 * Conversations available to analyse (recorded Task 7 conversations,
 * Task 3 simulator conversations and the labelled demo conversations).
 */
export async function listConversations({ limit = 50, includeDemo = true } = {}) {
  const response = await api.get("/task8/conversations", {
    params: { limit, include_demo: includeDemo },
  });
  return response.data;
}

/**
 * Post-Interaction Summary report for ONE conversation.
 * `source` may be "recorded" | "simulator"; the caller passes the id in the
 * matching field, or an inline message list.
 */
export async function getSummaryReport({
  conversationId = null,
  simulatorSessionId = null,
  messages = null,
  meta = {},
} = {}) {
  const payload = { meta };

  if (conversationId) payload.conversation_id = conversationId;
  if (simulatorSessionId) payload.simulator_session_id = simulatorSessionId;
  if (messages) payload.messages = messages;

  const response = await api.post("/task8/summary", payload);
  return response.data;
}

/** Multi-session performance analytics for the dashboard. */
export async function getAnalytics({
  limit = 25,
  simulatorLimit = 20,
  includeDemo = true,
} = {}) {
  const response = await api.get("/task8/analytics", {
    params: {
      limit,
      simulator_limit: simulatorLimit,
      include_demo: includeDemo,
    },
  });
  return response.data;
}

/** (Re)load the labelled demo conversations into the Task 7 store. */
export async function loadDemoData() {
  const response = await api.post("/task8/demo-data");
  return response.data;
}

/** Turn-based analysis for one recorded conversation. */
export async function getConversationAnalysis(conversationId) {
  const response = await api.get(
    `/task8/conversations/${conversationId}/analysis`
  );
  return response.data;
}
