import api from "./api";

/**
 * Task 7 - Live Support Console service.
 *
 * Talks to the Task 7 router (`task7_live_support_console/console_api.py`)
 * which is mounted on the same backend as the Task 1-6 endpoints, so there
 * is still only ONE base URL for the whole application.
 */

/** Analyse one customer message (Manual + Replay mode, every exchange). */
export async function analyzeConsoleMessage({
  query,
  sessionId = null,
  turn = null,
  history = null,
  threshold = null,
}) {
  const payload = { query, session_id: sessionId, turn, threshold };

  if (history?.length) {
    payload.history = history.map((item) => ({
      role: item.role,
      content: item.content,
    }));
  }

  const response = await api.post("/task7/analyze", payload);
  return response.data;
}

/**
 * Upload a conversation transcript for Replay Mode.
 * Accepts .txt, .csv and .json files and returns the parsed, role-tagged
 * messages plus any parse warnings.
 */
export async function uploadTranscript(file) {
  const form = new FormData();
  form.append("file", file);

  const response = await api.post("/task7/transcript/parse", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
}

/** Save a finished conversation so Task 8 can analyse it. */
export async function recordConversation({
  mode,
  title,
  persona,
  scenario,
  sourceFile,
  messages,
  knowledgeSearches,
  meta,
}) {
  const response = await api.post("/task7/sessions", {
    mode,
    title,
    persona: persona || null,
    scenario: scenario || null,
    source_file: sourceFile || null,
    messages: (messages || []).map((item) => ({
      role: item.role,
      content: item.content,
      timestamp: item.timestamp || null,
      turn: item.turn ?? null,
    })),
    knowledge_searches: (knowledgeSearches || []).map((item) => ({
      turn: item.turn ?? null,
      query: item.query || "",
      results: item.results ?? 0,
      sources: item.sources || [],
    })),
    meta: meta || {},
  });

  return response.data;
}

/** Recorded conversations (newest first). */
export async function listRecordedConversations({
  includeDemo = true,
  includeMessages = false,
  limit = null,
} = {}) {
  const response = await api.get("/task7/sessions", {
    params: {
      include_demo: includeDemo,
      include_messages: includeMessages,
      ...(limit ? { limit } : {}),
    },
  });
  return response.data;
}

export async function getRecordedConversation(sessionId) {
  const response = await api.get(`/task7/sessions/${sessionId}`);
  return response.data;
}

export async function deleteRecordedConversation(sessionId) {
  const response = await api.delete(`/task7/sessions/${sessionId}`);
  return response.data;
}

/** Conversations produced by the existing Task 3 simulator (read-only). */
export async function listSimulatorConversations(limit = 20) {
  const response = await api.get("/task7/simulator-sessions", {
    params: { limit },
  });
  return response.data;
}

export async function getSimulatorConversation(sessionId) {
  const response = await api.get(`/task7/simulator-sessions/${sessionId}`);
  return response.data;
}
