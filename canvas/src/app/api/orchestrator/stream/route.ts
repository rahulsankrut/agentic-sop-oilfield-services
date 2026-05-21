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

/**
 * SSRF guard — the proxy attaches an ADC OAuth token before forwarding,
 * so we MUST validate that ``streamUrl`` points at a legitimate Vertex AI
 * Reasoning Engine endpoint. Without this, any caller can post an
 * attacker-controlled URL and we'd leak the token to it.
 *
 * Allowed:
 *   https://<region>-aiplatform.googleapis.com/v1beta1/
 *     projects/<numeric-id>/locations/<region>/reasoningEngines/<id>:streamQuery
 *   (optionally with ?alt=sse query string)
 */
const STREAM_URL_ALLOWLIST_REGEX =
  /^https:\/\/[a-z0-9-]+-aiplatform\.googleapis\.com\/v1beta1\/projects\/\d+\/locations\/[a-z0-9-]+\/reasoningEngines\/\d+:streamQuery(\?[a-zA-Z0-9_=&-]*)?$/;

function isAllowedStreamUrl(url: string): boolean {
  return STREAM_URL_ALLOWLIST_REGEX.test(url);
}

interface ProxyRequestBody {
  streamUrl: string;
  /**
   * Optional. When omitted (or empty), AdkApp auto-creates a fresh
   * session per stream. Pre-seeded session IDs require the seeding
   * script to use the same ``app_name`` the deployed AdkApp uses
   * (which is the numeric engine id from
   * ``GOOGLE_CLOUD_AGENT_ENGINE_ID``). Until TASK-07's seeder is
   * updated to match, the canvas leaves this blank and accepts a
   * fresh session per Live-mode trigger.
   */
  sessionId?: string;
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

  if (!body.streamUrl || !body.userId || !body.userMessage) {
    return new Response(
      "Missing required field: streamUrl, userId, userMessage",
      { status: 400 },
    );
  }

  // SSRF: refuse to attach our ADC token to arbitrary URLs. Only forward
  // to the Vertex AI Reasoning Engine streamQuery endpoint pattern.
  if (!isAllowedStreamUrl(body.streamUrl)) {
    return new Response(
      `streamUrl rejected by allowlist: ${body.streamUrl}`,
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
        // session_id intentionally omitted when empty/missing — AdkApp
        // auto-creates a fresh session. Passing a non-existent ID
        // raises SessionNotFoundError and closes the stream.
        ...(body.sessionId ? { session_id: body.sessionId } : {}),
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
