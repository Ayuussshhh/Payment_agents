import { createAuth } from "../../../../lib/auth";

// Server-side proxy to the Mandate engine. The browser never holds a Bearer
// token: this reads the Better Auth session on the server and attaches the
// session token the engine expects. Public engine routes work without one.
const API = process.env.MANDATE_API_URL || "http://127.0.0.1:8001";

async function sessionToken(request) {
  try {
    const auth = await createAuth();
    const session = await auth.api.getSession({ headers: request.headers });
    return session?.session?.token || "";
  } catch {
    return "";
  }
}

async function forward(request, pathParts) {
  const path = "/" + (pathParts || []).join("/");
  const search = new URL(request.url).search;
  const headers = { "content-type": "application/json" };
  const token = await sessionToken(request);
  if (token) headers["authorization"] = `Bearer ${token}`;
  const idempotency = request.headers.get("idempotency-key");
  if (idempotency) headers["idempotency-key"] = idempotency;

  const init = { method: request.method, headers };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  let response;
  try {
    response = await fetch(`${API}${path}${search}`, init);
  } catch {
    return Response.json(
      { error: { code: "engine_unreachable", message: `The engine is not reachable at ${API}.` } },
      { status: 502 },
    );
  }
  const contentType = response.headers.get("content-type") || "application/json";
  if (contentType.startsWith("audio/")) {
    return new Response(await response.arrayBuffer(), {
      status: response.status,
      headers: { "content-type": contentType, "cache-control": "no-store" },
    });
  }
  const body = await response.text();
  return new Response(body, {
    status: response.status,
    headers: { "content-type": contentType },
  });
}

export async function GET(request, ctx) {
  const { path } = await ctx.params;
  return forward(request, path);
}

export async function POST(request, ctx) {
  const { path } = await ctx.params;
  return forward(request, path);
}

export async function PUT(request, ctx) {
  const { path } = await ctx.params;
  return forward(request, path);
}

export async function DELETE(request, ctx) {
  const { path } = await ctx.params;
  return forward(request, path);
}
