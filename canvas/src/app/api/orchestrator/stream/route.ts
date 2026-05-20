/**
 * Server-side proxy for the deployed Capacity Orchestrator's
 * ``streamQuery`` endpoint on Vertex AI Reasoning Engine.
 *
 * Why a proxy instead of calling Vertex AI directly from the browser:
 * - Vertex AI requires a Google Cloud OAuth Bearer token. The cleanest
 *   way to acquire one is via Application Default Credentials (ADC) on
 *   the server, which means we need Node runtime here.
 * - Tokens expire (~1 hour); a server-side proxy refreshes them
 *   automatically per request via ``google-auth-library``.
 * - Keeps the GCP project's identity off the browser. The user agent
 *   talks only to its own origin.
 *
 * Request: POST {streamUrl, sessionId, userId, userMessage}
 * Response: ``application/x-ndjson`` — one ADK Event dict per line.
 *
 * Local development: ADC comes from ``gcloud auth application-default
 * login``. Cloud Run deployment: ADC comes from the attached service
 * account (canvas runtime needs ``roles/aiplatform.user`` on the project
 * hosting the Orchestrator).
 */

import { GoogleAuth } from "google-auth-library";

// Force Node runtime — google-auth-library uses Node APIs (fs, crypto)
// not available on the edge runtime.
export const runtime = "nodejs";

const auth = new GoogleAuth({
  scopes: ["https://www.googleapis.com/auth/cloud-platform"],
});

interface ProxyRequestBody {
  streamUrl: string;
  sessionId: string;
  userId: string;
  userMessage: string;
}

export async function POST(req: Request): Promise<Response> {
  let body: ProxyRequestBody;
  try {
    body = (await req.json()) as ProxyRequestBody;
  } catch {
    return new Response("Invalid JSON body", { status: 400 });
  }

  if (!body.streamUrl || !body.sessionId || !body.userId || !body.userMessage) {
    return new Response(
      "Missing required field: streamUrl, sessionId, userId, userMessage",
      { status: 400 },
    );
  }

  // Acquire an OAuth Bearer token from ADC. The auth library caches the
  // token and refreshes it before expiry; we only pay the auth cost once
  // per cold start of the server.
  let token: string | null | undefined;
  try {
    const client = await auth.getClient();
    const tokenResponse = await client.getAccessToken();
    token = tokenResponse.token;
  } catch (err) {
    return new Response(
      `Failed to acquire ADC token: ${(err as Error).message}`,
      { status: 500 },
    );
  }
  if (!token) {
    return new Response("ADC returned empty token", { status: 500 });
  }

  // Forward to streamQuery. The body shape is the AdkApp class_method
  // dispatch format that vertexai/_genai/reasoning_engines expects.
  //
  // The `?alt=sse` query param is REQUIRED for the endpoint to actually
  // stream — without it Vertex AI returns a single JSON envelope and
  // closes the connection (the SDK appends this automatically; we have
  // to do it manually here).
  const upstreamUrl = body.streamUrl.includes("alt=sse")
    ? body.streamUrl
    : body.streamUrl + (body.streamUrl.includes("?") ? "&" : "?") + "alt=sse";
  const upstream = await fetch(upstreamUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      class_method: "async_stream_query",
      input: {
        message: { role: "user", parts: [{ text: body.userMessage }] },
        user_id: body.userId,
        session_id: body.sessionId,
      },
    }),
  });

  if (!upstream.ok || !upstream.body) {
    const errText = await upstream.text().catch(() => "");
    return new Response(
      `streamQuery upstream error: HTTP ${upstream.status} ${errText.slice(0, 500)}`,
      { status: upstream.status || 500 },
    );
  }

  // Pipe the upstream stream straight through to the browser. The browser
  // sees the same NDJSON bytes as if it had hit Vertex AI directly.
  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/x-ndjson",
      "Cache-Control": "no-store",
      "X-Accel-Buffering": "no",
    },
  });
}
