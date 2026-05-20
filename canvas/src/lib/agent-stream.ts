/**
 * agent-stream.ts
 *
 * Streaming client for the deployed Capacity Orchestrator's
 * ``streamQuery`` REST endpoint on Vertex AI Reasoning Engine.
 *
 * The endpoint accepts a POST with a chat-style payload and streams the
 * ADK ``Event`` JSON objects emitted by the underlying ``Runner.run_async``
 * loop (one JSON object per HTTP chunk, NDJSON-style). Each ADK event
 * carries the workflow node's state delta — including the
 * ``canvas_events`` list our nodes append to via
 * ``src.orchestrator_agent.events.emit``. The client drains new canvas
 * events out of each chunk and forwards them through ``onEvent``.
 *
 * The browser's built-in ``EventSource`` API can't carry an
 * ``Authorization`` Bearer header, so we use ``fetch`` +
 * ``ReadableStream`` + ``TextDecoderStream`` and parse the wire format
 * ourselves. The streamQuery endpoint emits newline-delimited JSON
 * objects (NOT the ``data:``-prefixed SSE wire format), so we split on
 * newline rather than blank-line.
 *
 * No reconnect logic: streamQuery is per-request (one POST → one
 * stream). The caller decides whether to fire another ``connect()``
 * after a ``close`` / ``error`` transition.
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
   * The ``streamQuery`` endpoint, e.g.
   * ``https://us-central1-aiplatform.googleapis.com/v1beta1/projects/<n>/locations/us-central1/reasoningEngines/<id>:streamQuery``
   */
  url: string;
  sessionId: string;
  userId: string;
  /**
   * OAuth Bearer token. The class does not refresh tokens — re-issue
   * ``connect()`` after refreshing.
   */
  authToken: string;
  /** Initial user message that kicks off the workflow. */
  userMessage: string;
  /**
   * Called for every canvas event drained out of the stream. May be
   * called zero, one, or many times per ADK chunk depending on how many
   * canvas events the node appended to the state delta.
   */
  onEvent: (event: CanvasEvent) => void;
  onStateChange?: (state: ConnectionState) => void;
}

/**
 * Subset of the ADK Event shape we read. Only the bits we need; ADK's
 * full shape has many more fields we ignore.
 */
interface AdkEventLike {
  actions?: {
    state_delta?: {
      canvas_events?: unknown[];
    };
  };
}

/**
 * Open and consume a single streamQuery response. ``connect()`` resolves
 * when the server closes the stream (or ``close()`` is called). Create
 * a new instance for each reconnect.
 */
export class AgentStream {
  private abort: AbortController | null = null;
  private readonly opts: AgentStreamOptions;
  private state: ConnectionState = "idle";
  /**
   * The ``emit()`` helper on the backend returns the full cumulative
   * ``canvas_events`` list every time (so every ADK event's state_delta
   * carries everything-so-far). We track how many entries we've already
   * forwarded and only dispatch new ones — otherwise the reducer would
   * see every event repeated N times for N chunks.
   */
  private lastEmittedCount = 0;

  constructor(opts: AgentStreamOptions) {
    this.opts = opts;
  }

  async connect(): Promise<void> {
    if (this.abort) return;
    this.setState("connecting");
    this.abort = new AbortController();

    // streamQuery body shape: { class_method: "async_stream_query", input: {...} }
    // ``message`` can be a string or a Content dict; we send Content so the
    // runtime parses parts uniformly.
    const body = {
      class_method: "async_stream_query",
      input: {
        message: {
          role: "user",
          parts: [{ text: this.opts.userMessage }],
        },
        user_id: this.opts.userId,
        session_id: this.opts.sessionId,
      },
    };

    try {
      const res = await fetch(this.opts.url, {
        method: "POST",
        signal: this.abort.signal,
        headers: {
          "Content-Type": "application/json",
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

      // streamQuery emits NDJSON (one JSON object per line). Buffer
      // partial lines across chunk boundaries.
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
          // Some Vertex AI deploys wrap streamed lines in `data: ` SSE
          // syntax; strip the prefix if present.
          const json = line.startsWith("data:")
            ? line.slice(5).trim()
            : line;
          if (!json) continue;
          try {
            const adkEvent = JSON.parse(json) as AdkEventLike;
            this.drainCanvasEvents(adkEvent);
          } catch (err) {
            // eslint-disable-next-line no-console
            console.warn(
              "agent-stream: failed to parse streamQuery chunk",
              json,
              err,
            );
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
      console.error("agent-stream: stream error", err);
      this.setState("error");
    } finally {
      this.abort = null;
    }
  }

  /**
   * Extract canvas events from one ADK event's ``actions.state_delta`` and
   * forward each through the ``onEvent`` callback. Tolerates the field
   * being absent (most ADK events don't touch ``canvas_events``).
   */
  private drainCanvasEvents(adkEvent: AdkEventLike): void {
    const list = adkEvent.actions?.state_delta?.canvas_events;
    if (!Array.isArray(list) || list.length <= this.lastEmittedCount) return;
    // Forward only the entries we haven't dispatched yet.
    for (let i = this.lastEmittedCount; i < list.length; i++) {
      const raw = list[i];
      // Each entry is a Pydantic model_dump (Python side) — already a plain
      // dict matching the CanvasEvent discriminated union.
      this.opts.onEvent(raw as CanvasEvent);
    }
    this.lastEmittedCount = list.length;
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
