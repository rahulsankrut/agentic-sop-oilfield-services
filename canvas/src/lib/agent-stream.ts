/**
 * agent-stream.ts
 *
 * SSE client for the Capacity Orchestrator's A2A `message:stream` endpoint.
 *
 * The browser's built-in `EventSource` API can't carry an `Authorization`
 * Bearer header (per TASK-10 spec §Common pitfalls), so we use `fetch` +
 * `ReadableStream` + `TextDecoderStream` and parse the SSE wire format
 * ourselves: messages separated by `\n\n`, each block contains one or more
 * lines, lines starting with `data:` carry the JSON payload.
 *
 * No reconnect logic: A2A `message/stream` is per-request on Agent Engine
 * (one POST → one stream). The caller decides whether to fire another
 * `connect()` after a `close`/`error` transition.
 */

import type { CanvasEvent } from "./canvas-events";

export type ConnectionState =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error";

export interface AgentStreamOptions {
  /**
   * The A2A `message:stream` endpoint, e.g.
   * `https://us-central1-aiplatform.googleapis.com/v1beta1/projects/<n>/locations/us-central1/reasoningEngines/<id>/a2a/v1/message:stream`
   */
  url: string;
  sessionId: string;
  userId: string;
  /**
   * OAuth Bearer token. The class does not refresh tokens — re-issue
   * `connect()` after refreshing.
   */
  authToken: string;
  /** Initial user message that kicks off the workflow. */
  userMessage: string;
  onEvent: (event: CanvasEvent) => void;
  onStateChange?: (state: ConnectionState) => void;
}

/**
 * Open and consume a single A2A SSE stream. `connect()` resolves when the
 * server closes the stream (or `close()` is called). Wire each instance to a
 * single React effect; create a new one for each reconnect.
 */
export class AgentStream {
  private abort: AbortController | null = null;
  private readonly opts: AgentStreamOptions;
  private state: ConnectionState = "idle";

  constructor(opts: AgentStreamOptions) {
    this.opts = opts;
  }

  async connect(): Promise<void> {
    if (this.abort) return;
    this.setState("connecting");
    this.abort = new AbortController();

    const body = {
      message: {
        role: "user",
        parts: [{ kind: "text", text: this.opts.userMessage }],
      },
      configuration: { accepted_output_modes: ["text"] },
      metadata: {
        context_id: this.opts.sessionId,
        user_id: this.opts.userId,
      },
    };

    try {
      const res = await fetch(this.opts.url, {
        method: "POST",
        signal: this.abort.signal,
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          Authorization: `Bearer ${this.opts.authToken}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok || !res.body) {
        throw new Error(`Stream open failed: HTTP ${res.status}`);
      }
      this.setState("open");

      const reader = res.body
        .pipeThrough(new TextDecoderStream())
        .getReader();

      let buffered = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffered += value ?? "";

        // SSE messages are separated by blank lines; lines beginning with
        // `data:` carry the JSON payload. There can be multiple `data:`
        // lines per block (the SSE spec says to concatenate with `\n`);
        // we take the first one because the orchestrator emits a single
        // JSON object per event.
        const blocks = buffered.split("\n\n");
        buffered = blocks.pop() ?? "";
        for (const block of blocks) {
          const dataLines = block
            .split("\n")
            .filter((l) => l.startsWith("data:"))
            .map((l) => l.slice(5).trimStart());
          if (dataLines.length === 0) continue;
          const json = dataLines.join("\n").trim();
          if (!json) continue;
          try {
            const evt = JSON.parse(json) as CanvasEvent;
            this.opts.onEvent(evt);
          } catch (err) {
            // eslint-disable-next-line no-console
            console.warn("agent-stream: failed to parse SSE event", json, err);
          }
        }
      }
      this.setState("closed");
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        // Caller-initiated; do not transition to error.
        return;
      }
      // eslint-disable-next-line no-console
      console.error("agent-stream: SSE error", err);
      this.setState("error");
    } finally {
      this.abort = null;
    }
  }

  close(): void {
    if (!this.abort) return;
    this.abort.abort();
    this.abort = null;
    this.setState("closed");
  }

  getState(): ConnectionState {
    return this.state;
  }

  private setState(s: ConnectionState): void {
    this.state = s;
    this.opts.onStateChange?.(s);
  }
}
