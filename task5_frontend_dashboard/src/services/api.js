import axios from "axios";

/**
 * Base URL of the Task 6 backend.
 *
 * The React app can be served in two ways:
 *
 *   1. by the Vite dev server (port 5173) - the API lives on port 8000;
 *   2. by the FastAPI backend itself (port 8000/8100, which serves the
 *      built `frontend/dist`) - the API is then on the SAME origin, so a
 *      same-origin base URL is used. That keeps the interface working even
 *      when the project is opened from another host (e.g. 192.168.x.x:8000).
 *
 * `VITE_API_BASE_URL` overrides both.
 */
function resolveBaseUrl() {
  const configured = import.meta.env?.VITE_API_BASE_URL;

  if (configured) {
    return configured;
  }

  if (typeof window !== "undefined") {
    const { protocol, port } = window.location;

    if ((protocol === "http:" || protocol === "https:") && (port === "8080" || port === "8100")) {
      return window.location.origin;
    }
  }

  return "http://127.0.0.1:8080";
}

const api = axios.create({
  baseURL: resolveBaseUrl(),
  headers: {
    "Content-Type": "application/json",
    // Never let the backend mistake an API call for a browser navigation:
    // the backend serves the SPA only to `Accept: text/html` requests.
    Accept: "application/json",
  },
});

export default api;