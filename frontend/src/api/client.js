const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001/api/v1";

function normalizeError(payload, fallback) {
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => item.msg ?? JSON.stringify(item)).join("; ");
  }
  if (typeof payload?.detail === "string") return payload.detail;
  if (typeof payload?.message === "string") return payload.message;
  return fallback;
}

export async function apiRequest(path, options = {}) {
  const token = window.localStorage.getItem("telecom360_token");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(normalizeError(error, `Request failed with status ${response.status}`));
  }
  if (response.status === 204) return null;
  return response.json();
}
