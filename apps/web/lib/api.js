// The Studio talks to the engine only through the server-side proxy at
// /api/engine, which attaches the session token. Never call the engine's port
// directly from the browser.

async function call(path, method, body, options = {}) {
  const headers = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  if (options.idempotencyKey) headers["idempotency-key"] = options.idempotencyKey;

  const response = await fetch(`/api/engine${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = {};
  }
  if (!response.ok) {
    const error = new Error(data?.error?.message || response.statusText || "Request failed");
    error.code = data?.error?.code;
    error.status = response.status;
    throw error;
  }
  return data;
}

export const apiGet = (path) => call(path, "GET");
export const apiPost = (path, body, options) => call(path, "POST", body ?? {}, options);

export function idemKey() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `k_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

// Back-compat for the overview page.
export const getJson = apiGet;
