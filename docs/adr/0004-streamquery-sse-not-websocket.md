# ADR 0004: `streamQuery` SSE proxy instead of WebSocket gateway

## Status

Accepted (TASK-10, 2026-05-20). Supersedes the original "WebSocket
integration" framing in the TASK-10 spec. The SHIPPED PATTERN banner
at the top of `tasks/TASK-10-websocket-integration.md` is the
canonical statement; Steps 3 and 7 of the spec body are marked
[SUPERSEDED].

## Context

The TASK-10 spec was originally titled "WebSocket integration" and
assumed a `bidiInvokeReasoningEngine` WebSocket API on Vertex AI
Agent Engine. The intent: the Capacity Orchestrator runs as a
long-lived bidi connection; the canvas pushes user input and pulls
agent events through a single socket.

Two discoveries before any of that shipped:

1. **The WebSocket API doesn't exist.** Vertex AI Agent Engine
   streams over **Server-Sent Events (SSE)** — there's no
   `bidiInvokeReasoningEngine`. The `--enable-streaming` CLI flag we
   inferred from earlier drafts also doesn't exist; `A2aAgent` only
   accepts `HTTP+JSON` transport. Verified against
   `~/.claude/references/a2a-protocol-and-adk-integration.md` and
   `vertex-agent-engine-deploys.md`.
2. **`A2aAgent`-wrapped Orchestrator was unnecessary.** An interim
   rewrite of the TASK-10 spec proposed wrapping the Orchestrator in
   `A2aAgent` so the canvas could consume `/a2a/v1/message:stream`.
   That added a second protocol surface for no incremental value —
   `AdkApp.async_stream_query` (the body of the deployed
   `streamQuery` REST endpoint) already yields every ADK `Event`,
   including the `event.actions.state_delta` payload our `emit()`
   helper writes canvas events into. The canvas reads from
   `state_delta.canvas_events` and `state_delta.a2ui_envelopes` per
   chunk.

## Decision

**Orchestrator stays `AdkApp`.** The canvas consumes the deployed
`<resource>:streamQuery` REST endpoint directly via a same-origin
Next.js API proxy:

- `canvas/src/app/api/orchestrator/stream/route.ts` — server-side
  proxy. Acquires an OAuth Bearer token via ADC and forwards to
  `https://us-central1-aiplatform.googleapis.com/v1beta1/<resource>:
  streamQuery?alt=sse`. Pipes the upstream NDJSON to the browser.
- `canvas/src/lib/agent-stream.ts` — browser-side reader. Uses
  `fetch` + `ReadableStream` (NOT `EventSource` — that doesn't
  support custom Authorization headers). Tracks `lastEmittedCount` +
  `a2uiEmittedCount` to forward only newly-appended events from the
  cumulative `state_delta` lists.

**Procurement remains `A2aAgent`.** That's the customer-facing
demonstration of the A2A protocol — the Orchestrator calls
Procurement via `RemoteA2aAgent` (A2A client), so the protocol is
exercised end-to-end without requiring the Orchestrator itself to be
an A2A server.

## Consequences

**Positive**

- Authentication is solved server-side; the browser never sees a
  GCP credential. OAuth tokens are refreshed transparently per
  proxy request.
- Cargo-plane Live mode works end-to-end through this path (verified
  in May 2026 — `TX-007` from Lagos, `$474K avoided`).
- One protocol surface to debug instead of two.

**Negative**

- The TASK-10 spec body has stale code samples (the
  A2aAgent-wrapped Orchestrator + EventSource consumer). Marked
  [SUPERSEDED] with banner pointers.
- A2A protocol demonstration is narrower — only the
  Orchestrator → Procurement leg. The bidirectional A2A story is
  thinner than the original "everything's A2A" framing implied.

**Risk**

- Corporate proxies sometimes buffer `text/event-stream` responses,
  breaking real-time delivery. Cloud Run + GCP edge handle this
  correctly. For customer-demo environments behind corporate
  proxies, the Static + Replay canvas modes are the safety net.

## Related work

- `tasks/TASK-10-websocket-integration.md` — SHIPPED PATTERN banner
  at top; Steps 3 and 7 marked [SUPERSEDED].
- `agents/orchestrator_agent/runtime/agent_executor.py` — preserved
  but dormant; wired back in only if we ever re-wrap the Orchestrator
  in `A2aAgent`.
- SPECS.md §Acceptance criteria #9 — inline deviation note.
