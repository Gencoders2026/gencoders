import api from "./api";

/**
 * Task 6 - session/configuration service.
 *
 * Also owns the small amount of browser-side state that makes the app
 * open directly on a working Task 6 conversation:
 *
 *   - `task6.sessionConfig` - the last Customer Configuration used
 *     (persona / scenario / initial emotion / severity / patience) so a
 *     session can be created automatically without the user filling the
 *     form again.
 *   - `task6.sessionId`     - the live session of THIS tab, so a browser
 *     refresh (or returning to "/") resumes the same conversation
 *     instead of creating a new one / showing a broken page.
 *
 * Both are stored in sessionStorage (per tab) and mirrored in memory so
 * they still work if storage is unavailable (private mode, etc.).
 */

export const DEFAULT_SESSION_CONFIG = {
  mode: "simulator",
  persona: "frustrated",
  scenario: "delayed_order",
  initial_emotion: "frustrated",
  severity: "medium",
  patience: 5,
};

const CONFIG_KEY = "task6.sessionConfig";
const SESSION_KEY = "task6.sessionId";

let memoryConfig = null;
let memorySessionId = null;

function readStorage(key) {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    if (value === null) {
      window.sessionStorage.removeItem(key);
    } else {
      window.sessionStorage.setItem(key, value);
    }
  } catch {
    /* storage unavailable - the in-memory mirror is used instead */
  }
}

/** Remember the Customer Configuration for the next automatic start. */
export function storeConfig(config) {
  const merged = { ...DEFAULT_SESSION_CONFIG, ...(config || {}) };
  memoryConfig = merged;
  writeStorage(CONFIG_KEY, JSON.stringify(merged));
  return merged;
}

/** Read the last Customer Configuration (defaults on first run). */
export function readStoredConfig() {
  if (memoryConfig) {
    return memoryConfig;
  }

  const raw = readStorage(CONFIG_KEY);

  if (raw) {
    try {
      memoryConfig = { ...DEFAULT_SESSION_CONFIG, ...JSON.parse(raw) };
      return memoryConfig;
    } catch {
      /* corrupted value - fall back to the defaults */
    }
  }

  memoryConfig = { ...DEFAULT_SESSION_CONFIG };
  return memoryConfig;
}

/** Remember the live session id of this tab. */
export function storeSessionId(sessionId) {
  memorySessionId = sessionId || null;
  writeStorage(SESSION_KEY, sessionId || null);
  return memorySessionId;
}

/** Live session id of this tab (null when there is none). */
export function readStoredSessionId() {
  if (memorySessionId) {
    return memorySessionId;
  }

  const raw = readStorage(SESSION_KEY);
  memorySessionId = raw || null;
  return memorySessionId;
}

/** Forget the live session id (used when a session ends/finishes). */
export function clearStoredSessionId() {
  memorySessionId = null;
  writeStorage(SESSION_KEY, null);
}

/** True when the backend still knows this session. */
export async function isSessionAlive(sessionId) {
  if (!sessionId) {
    return false;
  }

  try {
    await getSession(sessionId);
    return true;
  } catch {
    return false;
  }
}

/** Customer Configuration choices offered by the backend. */
export async function getConfigOptions() {
  try {
    const response = await api.get("/config/options");
    return response.data;
  } catch (error) {
    console.warn(
      "Could not load the Customer Configuration options:",
      error.message
    );
    return null;
  }
}

/**
 * Scenario name -> (simulator scenario, expected resolution).
 *
 * Accepts BOTH naming conventions: the short labels used by the React
 * configuration screens (`payment_issue`, `account_login`) and the
 * simulator's own keys returned by `GET /config/options`
 * (`payment_failure`, `account_issue`).
 */
const SCENARIO_MAP = {
  delayed_order: { scenario: "delayed_order", resolution: "delivery_update" },
  refund_request: { scenario: "refund_request", resolution: "full_refund" },
  payment_issue: { scenario: "payment_failure", resolution: "full_refund" },
  payment_failure: { scenario: "payment_failure", resolution: "full_refund" },
  account_login: { scenario: "account_issue", resolution: "account_recovery" },
  account_issue: { scenario: "account_issue", resolution: "account_recovery" },
  cancellation: { scenario: "cancellation", resolution: "cancellation" },
};

export async function startSession(sessionData) {
  const config = storeConfig(sessionData);

  const selected =
    SCENARIO_MAP[config.scenario] || {
      scenario: config.scenario,
      resolution: "full_refund",
    };

  try {
    const response = await api.post("/session/start", {
      persona: config.persona,

      scenario: selected.scenario,

      frustration_level: Number(config.patience) || 5,

      expected_resolution: selected.resolution,
    });

    // Remember which conversation this tab is in so a refresh resumes it.
    if (response.data?.session_id) {
      storeSessionId(response.data.session_id);
    }

    return response.data;
  } catch (error) {
    const detail = error.response?.data?.detail;

    if (Array.isArray(detail)) {
      const message = detail
        .map((item) => item.msg || "Invalid request")
        .join(", ");

      throw new Error(message, { cause: error });
    }

    if (typeof detail === "string") {
      throw new Error(detail, { cause: error });
    }

    throw new Error(
      "Unable to start session. Please check that the backend is running.",
      { cause: error }
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
  try {
    const response = await api.delete(`/session/${sessionId}`);
    return response.data;
  } finally {
    clearStoredSessionId();
  }
}

export async function getSessions() {
  const response = await api.get("/sessions");

  return response.data;
}

export async function getSessionLog(sessionId) {
  const response = await api.get(
    `/session/${sessionId}/log`
  );

  return response.data;
}
