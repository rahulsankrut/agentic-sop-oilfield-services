/**
 * agent-stream.ts
 *
 * Browser-side streaming client for the Capacity Orchestrator.
 *
 * **Hits a same-origin Next.js API route** (``/api/orchestrator/stream``)
 * which proxies to the deployed Vertex AI ``streamQuery`` endpoint
 * server-side. The proxy injects an ADC OAuth Bearer token so the
 * browser never sees a Google Cloud credential. See
 * ``src/app/api/orchestrator/stream/route.ts`` for the server side.
 *
 * The proxy pipes the ADK ``Event`` JSON objects emitted by the
 * underlying ``Runner.run_async`` loop straight through to the browser
 * (one JSON object per line, NDJSON). Each ADK event carries the
 * workflow node's state delta — including the ``canvas_events`` list
 * our nodes append to via ``src.orchestrator_agent.events.emit``. The
 * client drains new canvas events out of each chunk and forwards them
 * through ``onEvent``.
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
   * The deployed Vertex AI ``streamQuery`` URL (passed through to the
   * server-side proxy in the request body). The browser never calls it
   * directly. Looks like
   * ``https://us-central1-aiplatform.googleapis.com/v1beta1/projects/<n>/locations/us-central1/reasoningEngines/<id>:streamQuery``.
   */
  streamUrl: string;
  /** Same-origin proxy path. Default: ``/api/orchestrator/stream``. */
  proxyPath?: string;
  sessionId: string;
  userId: string;
  /** Initial user message that kicks off the workflow. */
  userMessage: string;
  /**
   * Called for every canvas event drained out of the stream. May be
   * called zero, one, or many times per ADK chunk depending on how many
   * canvas events the node appended to the state delta.
   */
  onEvent: (event: CanvasEvent) => void;
  /**
   * Optional. Called for every A2UI envelope drained from the stream
   * (TASK-45 Phase 2). Typically wired to `A2UIProvider.processMessages`
   * — the canvas's A2UI renderer then updates the corresponding surfaces.
   */
  onA2UIMessage?: (message: unknown) => void;
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
      // TASK-45 Phase 2 — A2UI v0.8 ServerToClientMessage[] envelopes
      // emitted by orchestrator nodes. The canvas's A2UIProvider drains
      // these and renders the surfaces client-side.
      a2ui_envelopes?: unknown[];
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

    // POST to the same-origin proxy. The proxy attaches the ADC Bearer
    // token server-side and forwards to streamQuery.
    const body = {
      streamUrl: this.opts.streamUrl,
      sessionId: this.opts.sessionId,
      userId: this.opts.userId,
      userMessage: this.opts.userMessage,
    };

    try {
      const res = await fetch(this.opts.proxyPath ?? "/api/orchestrator/stream", {
        method: "POST",
        signal: this.abort.signal,
        headers: { "Content-Type": "application/json" },
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
            this.drainA2UIEnvelopes(adkEvent);
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

  /**
   * Track A2UI envelopes across ADK chunks the same way we track canvas
   * events — the backend appends cumulatively, we only forward the
   * newly-added entries.
   */
  private a2uiEmittedCount = 0;

  /**
   * Extract A2UI v0.8 envelopes from the ADK state_delta and forward
   * each to ``onA2UIMessage``. Tolerates field absence.
   */
  private drainA2UIEnvelopes(adkEvent: AdkEventLike): void {
    if (!this.opts.onA2UIMessage) return;
    const list = adkEvent.actions?.state_delta?.a2ui_envelopes;
    if (!Array.isArray(list) || list.length <= this.a2uiEmittedCount) return;
    for (let i = this.a2uiEmittedCount; i < list.length; i++) {
      this.opts.onA2UIMessage(list[i]);
    }
    this.a2uiEmittedCount = list.length;
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
