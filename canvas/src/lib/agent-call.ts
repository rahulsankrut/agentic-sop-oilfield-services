/**
 * agent-call.ts
 *
 * One-shot streaming client for a deployed Agent Engine that has an
 * `output_schema` (e.g. Forecast Review Agent, Capacity Planning Agent).
 *
 * Unlike `agent-stream.ts` (which drains `state_delta.canvas_events` from
 * Orchestrator workflow chunks for the cargo-plane scenario), this helper
 * consumes the SSE stream end-to-end and returns the final structured
 * response — the JSON-serialized Pydantic dump that an `LlmAgent`
 * configured with `output_schema=Foo` emits as its terminal message.
 *
 * Why a separate helper:
 *   - Cargo-plane is a long-running workflow whose value is the choreography
 *     of intermediate events. `AgentStream` is the right tool there.
 *   - P1 (forecast review) and P2 (buffer planning) are single-turn agents
 *     whose value is one structured response. The canvas just needs that
 *     payload reduced into static beat state.
 *
 * Both routes pass through the same `/api/orchestrator/stream` proxy — the
 * proxy is URL-allowlist generic (any `reasoningEngines/<id>:streamQuery`
 * URL works).
 */

interface AdkEventLike {
  /** Present on agent model-response events. */
  content?: {
    role?: string;
    parts?: Array<{ text?: string }>;
  };
}

export interface RunAgentCallOptions {
  /**
   * Full Vertex AI streamQuery URL for the target agent. Same shape the
   * proxy accepts (regex-allowlisted to
   * `<region>-aiplatform.googleapis.com/v1beta1/projects/<n>/locations/<region>/reasoningEngines/<id>:streamQuery`).
   */
  streamUrl: string;
  /** Same-origin proxy path. Default: `/api/orchestrator/stream`. */
  proxyPath?: string;
  /** Pre-seeded session id, or empty string to let AdkApp auto-create one. */
  sessionId?: string;
  /** Persona's memory-profile user id (drives `preload_memory`). */
  userId: string;
  /** The natural-language prompt that drives the single turn. */
  userMessage: string;
  /** Optional abort signal (caller-managed cancellation). */
  signal?: AbortSignal;
}

export interface RunAgentCallResult<T> {
  /** Parsed structured response, or null if no JSON could be extracted. */
  parsed: T | null;
  /** Raw text of the final model message (the last non-empty text part). */
  rawText: string;
  /** Every text chunk the stream produced, in order. Useful for debugging. */
  allTexts: string[];
}

/**
 * Open the proxy, consume the NDJSON stream, return the parsed final
 * structured output. Throws on transport error / bad HTTP status. A stream
 * that closes with no parseable JSON resolves with `parsed: null` — the
 * caller decides whether to fall back to static.
 */
export async function runAgentCall<T>(
  opts: RunAgentCallOptions,
): Promise<RunAgentCallResult<T>> {
  const proxyPath = opts.proxyPath ?? "/api/orchestrator/stream";

  const res = await fetch(proxyPath, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: opts.signal,
    body: JSON.stringify({
      streamUrl: opts.streamUrl,
      sessionId: opts.sessionId ?? "",
      userId: opts.userId,
      userMessage: opts.userMessage,
    }),
  });

  if (!res.ok || !res.body) {
    const errBody = await res.text().catch(() => "");
    throw new Error(
      `agent-call: HTTP ${res.status}${errBody ? ` — ${errBody.slice(0, 300)}` : ""}`,
    );
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  const allTexts: string[] = [];
  let buffered = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffered += value ?? "";

    const lines = buffered.split("\n");
    buffered = lines.pop() ?? "";

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;
      const json = line.startsWith("data:") ? line.slice(5).trim() : line;
      if (!json) continue;

      let evt: AdkEventLike;
      try {
        evt = JSON.parse(json) as AdkEventLike;
      } catch {
        continue;
      }

      const parts = evt.content?.parts;
      if (!Array.isArray(parts)) continue;
      for (const p of parts) {
        if (typeof p?.text === "string" && p.text.length > 0) {
          allTexts.push(p.text);
        }
      }
    }
  }

  const rawText = allTexts[allTexts.length - 1] ?? "";
  let parsed: T | null = null;
  if (rawText) {
    try {
      parsed = JSON.parse(rawText) as T;
    } catch {
      // The final text wasn't a JSON object on its own. Try concatenating
      // every text chunk (some agents stream a single JSON object in
      // pieces). Falls back to parsed=null if still unparseable.
      const joined = allTexts.join("");
      try {
        parsed = JSON.parse(joined) as T;
      } catch {
        parsed = null;
      }
    }
  }

  return { parsed, rawText, allTexts };
}
