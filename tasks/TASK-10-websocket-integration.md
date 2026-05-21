# TASK-10: Stream agent events to canvas via A2A SSE

**Prerequisites:** TASK-09 complete. Canvas renders both scenarios (cargo-plane for Maria, buffer-planning for Tomas) in static demo mode. Workflow Orchestrator running on ADK 2.0 producing deterministic output.

**Estimated effort:** 2-3 days for one engineer.

**Stream:** Both (backend event emission + frontend event consumption)

---

> **Spec-history note (2026-05-20):** This spec was originally titled "WebSocket integration" and assumed a `bidiInvokeReasoningEngine` WebSocket API. That assumption was wrong: Vertex AI Agent Engine streams over **Server-Sent Events (SSE)** on the A2A `message/stream` endpoint, not a separate WebSocket API. The deploy CLI flag (`--enable-streaming`) doesn't exist either — `A2aAgent` only accepts `HTTP+JSON` transport. This rewrite reflects the actual platform surface per `~/.claude/references/a2a-protocol-and-adk-integration.md` and `vertex-agent-engine-deploys.md`. Filename retained for cross-task references.
>
> **Architecture correction (2026-05-20, later):** An earlier version of this rewrite wrapped the **Orchestrator** in `A2aAgent` so the canvas could consume `/a2a/v1/message:stream`. That was over-engineered. `AdkApp.async_stream_query` (the body of the deployed `streamQuery` REST endpoint) already yields every ADK `Event` — including `event.actions.state_delta`, which is exactly where our `emit()` helper writes canvas events. **The Orchestrator stays `AdkApp`**; the canvas consumes `<resource>:streamQuery` directly and drains `state_delta.canvas_events` per chunk (tracking `lastEmittedCount` because our `emit()` returns the full cumulative list each turn).
>
> Procurement remains `A2aAgent` — that's the customer-facing **demonstration** of the A2A protocol, not an architectural requirement. The Orchestrator calls Procurement via `RemoteA2aAgent` (A2A client), which still exercises the protocol end-to-end without requiring the Orchestrator to be a server.
>
> `src/orchestrator_agent/runtime/agent_executor.py` is preserved but dormant — wired back in only if we ever choose to re-wrap the Orchestrator in `A2aAgent`.

---

> **SHIPPED PATTERN (2026-05-21) — supersedes the body of this spec.**
>
> The body below (Steps 3, 4, 7 in particular) describes the
> `A2aAgent`-wrapped Orchestrator + `/a2a/v1/message:stream` pattern that
> the two spec-history notes above already pivoted away from. What
> actually shipped:
>
> 1. **Orchestrator deploys as `AdkApp`** via `agents/orchestrator_agent/deploy.py`,
>    not `A2aAgent`. The deployed `<resource>:streamQuery` REST endpoint
>    surfaces every ADK `Event` with our `state_delta.canvas_events` list
>    intact.
> 2. **Canvas consumes a same-origin Next.js API proxy**
>    (`canvas/src/app/api/orchestrator/stream/route.ts`), which forwards
>    to `streamQuery` server-side with an ADC OAuth Bearer token. The
>    browser never sees a Google Cloud credential.
> 3. **`canvas/src/lib/agent-stream.ts`** uses `fetch + ReadableStream`
>    (NDJSON, not SSE `data:` framing) to drain the proxy. It tracks
>    `lastEmittedCount` because our `emit()` returns the full cumulative
>    list each turn.
> 4. **A second drainer (`drainA2UIEnvelopes`)** added in TASK-45 Phase 2
>    forwards `state_delta.a2ui_envelopes` to the A2UI provider for v0.8
>    surface rendering — same cumulative-tracking pattern.
> 5. **Procurement remains `A2aAgent`**, called from the Orchestrator via
>    `RemoteA2aAgent` (A2A client). This still exercises the A2A protocol
>    end-to-end as the customer-facing demonstration.
> 6. **No `EventSource` and no separate SSE endpoint** — the body's Step 4
>    is informational only. The body's Step 7 integration test
>    (`message:stream` SSE consumer) is **not implemented**; equivalent
>    coverage lives in `agents/tests/unit/test_*` against the deployed
>    `streamQuery` stream.
>
> Why the deviation: `AdkApp.async_stream_query` already yields every
> ADK Event, so `state_delta.canvas_events` is naturally available on
> the standard reasoning-engine stream. Wrapping the Orchestrator in
> `A2aAgent` added a second protocol surface with no incremental value
> over the proxy. We kept A2A demonstration value via the
> Orchestrator → Procurement call.
>
> The **Revised acceptance criteria** at the bottom of this file
> reflects the shipped pattern. The original criteria list (under
> "## Acceptance criteria") is preserved historically.

---

## Context

Until now the canvas runs entirely on hardcoded beat data. The visual choreography is right, the storyboard plays out, but the agent and the canvas are not connected. This task makes them one system: the Capacity Orchestrator emits events as it executes (parallel MCP calls, Knowledge Catalog lookup, plan evaluation, procurement decision), and the canvas consumes those events to update its state.

The platform feature that makes this clean is the **A2A `message/stream` SSE endpoint** — an existing capability of any A2A-wrapped agent on Agent Engine. When the Orchestrator is deployed as an `A2aAgent` (matching the pattern Procurement already uses), it exposes:

```
GET  https://us-central1-aiplatform.googleapis.com/v1beta1/<resource_name>/a2a/v1/card
POST https://us-central1-aiplatform.googleapis.com/v1beta1/<resource_name>/a2a/v1/message:stream
```

The `message:stream` endpoint returns an `text/event-stream` of A2A `ClientEvent`s — `TaskStatusUpdate`, `TaskArtifactUpdate`, `Message` — produced by the agent executor as the underlying Workflow runs. The canvas opens an SSE connection, receives events as the Workflow executes, and reduces them into rendered state.

Cloud Trace, Agent Identity, Agent Gateway, and Model Armor all continue to operate on the underlying tool calls. SSE is just the message bus for surfacing agent state to a companion UI.

The demo upgrade is significant. Previously the demoer pressed Space to advance beats; the canvas faked the agent's work. Now the demoer triggers the real Capacity Orchestrator from Gemini Enterprise chat, and the canvas reacts to actual events from the actual Cloud Trace as the actual agent reasons. The story becomes: *"this is what's happening right now, in this trace, in this Workflow."*

This task also preserves the **static fallback mode** from TASK-08/09 and adds a third **Replay mode** that plays back a pre-recorded event sequence. Customer demos require these safety nets — the platform should not depend on perfect uptime to land the story.

---

## Inputs

- TASK-09 complete (canvas with both scenarios in static mode)
- TASK-04 complete (Workflow Orchestrator on ADK 2.0 with explicit nodes)
- TASK-02 complete (Procurement Approval Agent already deployed via `A2aAgent`; same wrapper for Orchestrator)
- A2A protocol reference: `~/.claude/references/a2a-protocol-and-adk-integration.md` (SSE via `message/stream`, transport restrictions, agent_card structure)
- Vertex AI Agent Engine deploy reference: `~/.claude/references/vertex-agent-engine-deploys.md` (A2A deploy pattern, Pydantic patch, dependency pins)
- Storyboard beats in `docs/planning/persona3_canvas_storyboard.md` define the event protocol implicitly — match the beat-by-beat shape

---

## Deliverables

When this task is complete:

1. **Event protocol defined** — `CanvasEvent` schema in shared TypeScript and Python definitions. Event types cover the full Workflow execution: workflow lifecycle, node lifecycle, MCP calls, Knowledge Catalog lookups, decisions, cost computations.
2. **Workflow nodes emit events** — every node in the Capacity Orchestrator emits canvas events at start/complete. Function nodes emit progress events; LLM nodes emit reasoning events; routers emit decision events.
3. **Orchestrator A2A wrapped** — `src/orchestrator_agent/runtime/{agent_card.py, agent_executor.py}` translate ADK Workflow `Event`s into A2A `TaskStatusUpdate`/`Message` events on the SSE stream. `runtime/deploy.py` uses `deploy_a2a_agent_engine` (matching Procurement).
4. **SSE bridge in canvas** — `canvas/lib/agent-stream.ts` opens the A2A `message:stream` endpoint and yields parsed `CanvasEvent`s. Uses `fetch` + `ReadableStream` (not `EventSource`, which doesn't support custom headers for auth).
5. **Event-to-state reducer** — `canvas/hooks/useLiveScenario.ts` reduces incoming events into the same `ScenarioState` shape the static beats produced, so the existing canvas components work unchanged.
6. **Live mode toggle** — keyboard shortcut `L` toggles between Live (SSE-driven), Static (beat-driven), and Replay (recorded events) modes. Mode indicator visible in the UI.
7. **Fallback behavior** — if the SSE connection drops or the agent times out, the canvas auto-falls-back to Static mode with a small notice in the chat panel.
8. **Both scenarios live** — Maria's cargo-plane and Tomas's buffer-planning both work in Live mode.
9. **Cloud Trace consistency** — the live trace and the canvas events tell the same story. Every span in Cloud Trace has a corresponding event the canvas consumed.

---

## Step-by-step instructions

### Step 1 — Define the event protocol

Single source of truth in Pydantic, then generate TypeScript.

`src/orchestrator_agent/events/canvas_events.py`:

```python
"""Event protocol emitted by the Capacity Orchestrator to the canvas.

This is the contract: every state change the canvas wants to render must be
expressible as one of these events. Adding a visual element requires adding
an event type. Event IDs are `str` not `uuid.UUID` (per CLAUDE.md known
gotcha #6 — stdlib json.dumps can't serialize UUID even when Pydantic can).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Union

from pydantic import BaseModel, Field


def _new_id() -> str:
    return str(uuid.uuid4())


class BaseEvent(BaseModel):
    """Common envelope for all canvas events."""
    event_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    workflow_id: str
    session_id: str


# --- Workflow lifecycle ---

class WorkflowStartedEvent(BaseEvent):
    type: Literal["workflow.started"] = "workflow.started"
    scenario: str          # "cargo-plane" | "buffer-planning"
    user_id: str
    initial_context: dict  # seed memory excerpt (per-persona)


class WorkflowCompletedEvent(BaseEvent):
    type: Literal["workflow.completed"] = "workflow.completed"
    final_output: dict     # SourcingPlan, BufferPlan, etc.
    duration_ms: int


class WorkflowFailedEvent(BaseEvent):
    type: Literal["workflow.failed"] = "workflow.failed"
    node_name: str
    error_class: str       # e.g. "TimeoutError"
    error_message: str


# --- Node lifecycle ---

class NodeStartedEvent(BaseEvent):
    type: Literal["node.started"] = "node.started"
    node_name: str
    node_kind: Literal["function", "llm", "router", "subworkflow"]


class NodeCompletedEvent(BaseEvent):
    type: Literal["node.completed"] = "node.completed"
    node_name: str
    duration_ms: int
    output_summary: str | None = None


# --- MCP & Knowledge Catalog calls (platform-visibility moments) ---

class MCPCallStartedEvent(BaseEvent):
    type: Literal["mcp.call.started"] = "mcp.call.started"
    server: str            # "sap-mcp-server" | "maximo-mcp-server" | ...
    tool: str
    via_gateway: bool = True


class MCPCallCompletedEvent(BaseEvent):
    type: Literal["mcp.call.completed"] = "mcp.call.completed"
    server: str
    tool: str
    duration_ms: int
    result_summary: dict   # small payload — enough for canvas, not full response


class KnowledgeCatalogLookupEvent(BaseEvent):
    type: Literal["knowledge_catalog.lookup"] = "knowledge_catalog.lookup"
    canonical_id: str
    canonical_label: str
    aspects: dict          # full entity payload for the drawer


# --- Decisions ---

class RouterDecisionEvent(BaseEvent):
    type: Literal["router.decision"] = "router.decision"
    router_name: str
    decision: str          # the routing key chosen
    rationale: str | None = None


# --- Cargo-plane specific events ---

class CapacityGapDetectedEvent(BaseEvent):
    type: Literal["capacity.gap_detected"] = "capacity.gap_detected"
    location: dict         # { latitude, longitude, label }
    canonical_asset_id: str
    deadline: str


class DoomedRouteProposedEvent(BaseEvent):
    """The naive 'cargo plane from Australia' plan, surfaced for contrast."""
    type: Literal["route.doomed_proposed"] = "route.doomed_proposed"
    from_location: dict
    to_location: dict
    estimated_cost_usd: float
    rationale: str


class EquivalentAssetFoundEvent(BaseEvent):
    """Equivalence node found a functional substitute."""
    type: Literal["equivalence.found"] = "equivalence.found"
    original_asset: dict
    equivalent_asset: dict
    confidence: float
    rationale_source: str
    location: dict


class RecommendedRouteFinalizedEvent(BaseEvent):
    type: Literal["route.recommended"] = "route.recommended"
    from_location: dict
    to_location: dict
    estimated_cost_usd: float
    avoided_cost_usd: float


# --- Buffer-planning specific events ---

class ForecastLoadedEvent(BaseEvent):
    type: Literal["forecast.loaded"] = "forecast.loaded"
    equipment_class: str
    timeline: list[dict]   # 12-week probabilistic forecast


class BufferRecommendationEvent(BaseEvent):
    type: Literal["buffer.recommendation"] = "buffer.recommendation"
    risk_tolerance: Literal["conservative", "balanced", "aggressive"]
    buffer_pct: float
    expected_idle_cost_usd: float
    expected_late_start_cost_usd: float
    on_time_probability: float


# --- Union for type-safe dispatch ---

CanvasEvent = Union[
    WorkflowStartedEvent,
    WorkflowCompletedEvent,
    WorkflowFailedEvent,
    NodeStartedEvent,
    NodeCompletedEvent,
    MCPCallStartedEvent,
    MCPCallCompletedEvent,
    KnowledgeCatalogLookupEvent,
    RouterDecisionEvent,
    CapacityGapDetectedEvent,
    DoomedRouteProposedEvent,
    EquivalentAssetFoundEvent,
    RecommendedRouteFinalizedEvent,
    ForecastLoadedEvent,
    BufferRecommendationEvent,
]
```

Generate the matching TypeScript types (run from the `venv-deploy-310/` venv so Pydantic v2 is on the path):

```bash
source venv-deploy-310/bin/activate
pip install pydantic-to-typescript
pydantic2ts \
    --module src.orchestrator_agent.events.canvas_events \
    --output canvas/lib/canvas-events.ts
```

This produces `canvas/lib/canvas-events.ts` with the matching types.

### Step 2 — Wire event emission into Workflow nodes

ADK 2.0 Workflow nodes return `Event(output=..., state=..., message=...)`. To emit canvas events, accumulate them in session state under a `canvas_events` key. The A2A executor (Step 3) reads this on each Workflow event and pushes new entries onto the SSE stream.

Add a helper at `src/orchestrator_agent/events/emit.py`:

```python
"""Helper to append canvas events to session state.

Workflow nodes call ``emit(ctx, ...)`` to record an event. The A2A executor
(runtime/agent_executor.py) reads ``ctx.state['canvas_events']`` after each
node completes and translates new entries into A2A ``Message`` events on
the SSE stream.
"""

from __future__ import annotations

from typing import Any

from google.adk import Context

from .canvas_events import CanvasEvent


def emit(ctx: Context, event: CanvasEvent) -> dict[str, Any]:
    """Append a canvas event to session state and return the state delta.

    Call from a Workflow node like::

        return Event(
            output=aggregated.model_dump(),
            state=emit(ctx, NodeCompletedEvent(...)),
        )
    """
    existing = ctx.state.get("canvas_events", [])
    return {"canvas_events": [*existing, event.model_dump(mode="json")]}
```

Update `src/orchestrator_agent/core/nodes/parallel_queries.py` to emit MCP call events as queries fan out:

```python
"""Parallel system queries via Agent Gateway → MCP servers.
Emits MCP call events as queries fan out."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from google.adk import Context, Event
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from ...events.emit import emit
from ...events.canvas_events import (
    MCPCallStartedEvent,
    MCPCallCompletedEvent,
    NodeStartedEvent,
    NodeCompletedEvent,
)
from ....schemas import CapacityGapRequest, SystemQueryResults


# DEMO NARRATION: "Notice the trace — and the canvas. Three parallel MCP
# calls light up as pills, one per system. The canvas is consuming events
# from the Workflow via the A2A SSE stream. This isn't polling; it's the
# agent broadcasting its state."
async def parallel_system_queries(node_input: dict, ctx: Context) -> Event:
    """Fan out parallel MCP queries; emit canvas events."""
    request = CapacityGapRequest(**node_input["request"])
    workflow_id = ctx.state.get("workflow_id", "")
    session_id = ctx.state.get("session_id", "")

    started = NodeStartedEvent(
        workflow_id=workflow_id, session_id=session_id,
        node_name="parallel_system_queries", node_kind="function",
    )
    canvas_state = emit(ctx, started)

    async def call_mcp(toolset: McpToolset, server: str, tool: str, **kwargs) -> dict:
        nonlocal canvas_state
        canvas_state = {**canvas_state, **emit(
            ctx,
            MCPCallStartedEvent(
                workflow_id=workflow_id, session_id=session_id,
                server=server, tool=tool,
            ),
        )}
        start = datetime.utcnow()
        result = await toolset.call(tool, **kwargs)
        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        canvas_state = {**canvas_state, **emit(
            ctx,
            MCPCallCompletedEvent(
                workflow_id=workflow_id, session_id=session_id,
                server=server, tool=tool, duration_ms=duration_ms,
                result_summary=_summarize(result),
            ),
        )}
        return result

    # Toolsets are constructed lazily — see existing parallel_queries.py
    sap_toolset, maximo_toolset, fdp_toolset = _gateway_toolsets()

    sap_task = call_mcp(
        sap_toolset, "sap-mcp-server", "sap_resolve_material_number",
        material_number=request.sap_material_number,
    )
    maximo_task = call_mcp(
        maximo_toolset, "maximo-mcp-server", "maximo_query_availability",
        canonical_id=request.canonical_asset_id,
        region_filter=request.target_region,
    )
    fdp_task = call_mcp(
        fdp_toolset, "fdp-mcp-server", "fdp_get_customer_config",
        customer_id=request.customer_id,
        asset_canonical_id=request.canonical_asset_id,
    )
    results = await asyncio.gather(sap_task, maximo_task, fdp_task)

    aggregated = SystemQueryResults(
        sap=results[0], maximo=results[1], fdp=results[2],
    )

    completed = NodeCompletedEvent(
        workflow_id=workflow_id, session_id=session_id,
        node_name="parallel_system_queries", duration_ms=0,
        output_summary="3 systems queried in parallel",
    )
    canvas_state = {**canvas_state, **emit(ctx, completed)}

    return Event(
        message="Parallel system queries complete",
        output=aggregated.model_dump(),
        state=canvas_state,
    )


def _summarize(result: dict) -> dict:
    """Strip large fields for canvas-friendly payload."""
    return {k: v for k, v in result.items() if k not in ("raw_response",)}
```

Apply the same pattern to:
- `parse_request.py` — emit `CapacityGapDetectedEvent` for cargo-plane scenarios
- `equivalence_lookup.py` — emit `KnowledgeCatalogLookupEvent` + `EquivalentAssetFoundEvent`
- `sourcing_logistics.py` — emit `DoomedRouteProposedEvent` + `RecommendedRouteFinalizedEvent`
- `routers.py` — emit `RouterDecisionEvent`
- `finalize.py` — emit `WorkflowCompletedEvent`

**Important corrections from prior spec drafts:**
- ADK 2.0 uses `Event(output=...)` not `Event(payload=...)` — verified at `~/.claude/references/google-adk-2.0.md` §Event.
- MCP toolset is `from google.adk.tools.mcp_tool import McpToolset` (not `MCPClient` — that's the 1.x ghost name).
- Function nodes that take `ctx: Context` get it auto-injected by the Workflow runtime (no manual passing).

### Step 3 — Switch Orchestrator deploy to `A2aAgent` [SUPERSEDED — see banner at top]

> **NOTE (2026-05-21):** The SHIPPED PATTERN banner at the top of this file
> supersedes this step. We did NOT wrap the Orchestrator in A2aAgent.
> `agents/orchestrator_agent/deploy.py` deploys via `AdkApp` and the canvas
> consumes `<resource>:streamQuery` via the same-origin Next.js proxy at
> `canvas/src/app/api/orchestrator/stream/route.ts`. The code samples below
> are kept as a historical record of the path we considered.

The Orchestrator currently deploys as `AdkApp(agent=root_agent, app_name="capacity_orchestrator_agent")` (see `src/orchestrator_agent/runtime/deploy.py`). For SSE streaming, switch to the A2A wrapper pattern Procurement already uses.

The repo already has the A2A scaffolding in place:
- `src/orchestrator_agent/runtime/agent_card.py` — define the `AgentCard`
- `src/orchestrator_agent/runtime/agent_executor.py` — `AgentExecutor` that runs the Workflow and yields A2A events
- `src/orchestrator_agent/runtime/local_server.py` — local A2A server (port 8083)
- `src/orchestrator_agent/runtime/test_client.py` — A2A test client

Wire the executor to translate Workflow events → A2A events. Add to `src/orchestrator_agent/runtime/agent_executor.py`:

```python
"""A2A Agent Executor for the Capacity Orchestrator.

Runs the deployed Workflow against incoming A2A messages and yields
A2A status updates as canvas events arrive on session state.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, TaskState, TextPart
from a2a.utils import new_agent_text_message
from google.adk import Runner
from google.genai import types

logger = logging.getLogger(__name__)


class CapacityOrchestratorExecutor(AgentExecutor):
    """Run the Capacity Orchestrator and stream canvas events to the A2A peer."""

    def __init__(self) -> None:
        self.runner: Runner | None = None

    def _init_agent(self) -> None:
        if self.runner is None:
            from ..core.agent import root_agent  # noqa: PLC0415
            self.runner = Runner(
                agent=root_agent,
                app_name="capacity_orchestrator_agent",
                # session_service + memory_service wired by AdkApp/Runner defaults
            )

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        self._init_agent()
        user_message = context.message.parts[0].text if context.message else ""
        session_id = context.context_id
        user_id = context.user_id

        # Emit each new canvas event as an A2A Message to the SSE stream
        last_emitted = 0
        async for adk_event in self.runner.run_async(
            session_id=session_id,
            user_id=user_id,
            new_message=types.Content(role="user", parts=[types.Part(text=user_message)]),
        ):
            canvas_events = adk_event.actions.state_delta.get("canvas_events", []) \
                if adk_event.actions and adk_event.actions.state_delta else []
            for evt in canvas_events[last_emitted:]:
                await event_queue.enqueue_event(
                    new_agent_text_message(text=str(evt))
                )
            last_emitted = len(canvas_events)
            if adk_event.is_final_response():
                # Final completion update
                await event_queue.enqueue_event(
                    new_agent_text_message(text=f"workflow.completed: {adk_event.content}")
                )
                return
```

Update `runtime/deploy.py` to use `deploy_a2a_agent_engine` (matching Procurement's pattern):

```python
"""Deploy the Capacity Orchestrator as an A2aAgent.

Pattern matches src/procurement_approval_agent/runtime/deploy.py. The A2A
wrapper exposes `/a2a/v1/message:stream` for the canvas SSE consumer.
"""

from __future__ import annotations

import os

from a2a.types import TransportProtocol
from dotenv import load_dotenv
from vertexai.preview.reasoning_engines import A2aAgent

from src.utils.deploy import deploy_a2a_agent_engine

from .agent_card import create_capacity_orchestrator_card
from .agent_executor import CapacityOrchestratorExecutor
from ..services.memory_manager import create_orchestrator_memory_topics

load_dotenv()


def deploy_orchestrator() -> str:
    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("AGENT_ENGINE_LOCATION", "us-central1")
    staging_bucket = os.environ["BUCKET_URI"]

    card = create_capacity_orchestrator_card()
    card.preferred_transport = TransportProtocol.http_json
    a2a_agent = A2aAgent(
        agent_card=card,
        agent_executor_builder=CapacityOrchestratorExecutor,
    )

    return deploy_a2a_agent_engine(
        agent=a2a_agent,
        display_name="Capacity Orchestrator Agent",
        description=(
            "Lead architect for service capacity gap resolution. Streams "
            "canvas events via A2A SSE."
        ),
        extra_packages=["src/orchestrator_agent", "src/utils", "src/schemas.py"],
        requirements=[
            "google-cloud-aiplatform[agent_engines,evaluation]>=1.121.0",
            "google-adk>=2.0.0,<2.1",
            "a2a-sdk[http-server]>=0.3.9,<1.0",
            "pydantic>=2.12.0",
            "python-dotenv>=1.0.0",
        ],
        env_vars={
            "GOOGLE_GENAI_USE_VERTEXAI": "true",
            "ORCHESTRATOR_MODEL": os.environ.get(
                "ORCHESTRATOR_MODEL", "gemini-3.1-pro-preview"
            ),
            "PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME": os.environ.get(
                "PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME", ""
            ),
        },
        context_spec={
            "memory_bank_config": {
                "customization_configs": [create_orchestrator_memory_topics()],
            },
        },
        project=project_id,
        location=location,
        staging_bucket=staging_bucket,
    )


if __name__ == "__main__":
    print("Deployed:", deploy_orchestrator())
```

After deploy, capture the resource name and the A2A SSE URL:

```bash
make deploy-orchestrator
# Resource: projects/.../reasoningEngines/<id>
# Stream URL: https://us-central1-aiplatform.googleapis.com/v1beta1/projects/.../reasoningEngines/<id>/a2a/v1/message:stream
```

Add to `.env`:
```
ORCHESTRATOR_STREAM_URL=https://us-central1-aiplatform.googleapis.com/v1beta1/<resource_name>/a2a/v1/message:stream
```

### Step 4 — Build the SSE client in the canvas

We can't use the browser's built-in `EventSource` API — it doesn't support custom `Authorization` headers, and the A2A endpoint requires a Bearer token. Use `fetch` + `ReadableStream` instead.

`canvas/lib/agent-stream.ts`:

```typescript
import type { CanvasEvent } from "./canvas-events";

export type ConnectionState = "idle" | "connecting" | "open" | "closed" | "error";

export interface AgentStreamOptions {
  /** The A2A message:stream endpoint, e.g.
   *  https://us-central1-aiplatform.googleapis.com/v1beta1/projects/.../reasoningEngines/.../a2a/v1/message:stream
   */
  url: string;
  sessionId: string;
  userId: string;
  /** OAuth Bearer token; refresh before expiry by re-issuing connect(). */
  authToken: string;
  /** Initial user message that kicks off the workflow. */
  userMessage: string;
  onEvent: (event: CanvasEvent) => void;
  onStateChange?: (state: ConnectionState) => void;
}

export class AgentStream {
  private abort: AbortController | null = null;
  private opts: AgentStreamOptions;
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
      metadata: { context_id: this.opts.sessionId, user_id: this.opts.userId },
    };

    try {
      const res = await fetch(this.opts.url, {
        method: "POST",
        signal: this.abort.signal,
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
          "Authorization": `Bearer ${this.opts.authToken}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok || !res.body) {
        throw new Error(`Stream open failed: ${res.status}`);
      }
      this.setState("open");

      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffered = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffered += value;
        // SSE messages are separated by blank lines; lines beginning with
        // "data:" carry the JSON payload.
        const blocks = buffered.split("\n\n");
        buffered = blocks.pop() ?? "";
        for (const block of blocks) {
          const dataLine = block.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          const json = dataLine.slice(5).trim();
          if (!json) continue;
          try {
            const evt = JSON.parse(json) as CanvasEvent;
            this.opts.onEvent(evt);
          } catch (e) {
            console.warn("Failed to parse SSE event:", json, e);
          }
        }
      }
      this.setState("closed");
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      console.error("SSE error:", err);
      this.setState("error");
    } finally {
      this.abort = null;
    }
  }

  close(): void {
    this.abort?.abort();
    this.abort = null;
    this.setState("closed");
  }

  private setState(s: ConnectionState) {
    this.state = s;
    this.opts.onStateChange?.(s);
  }
}
```

### Step 5 — Build the event-to-state reducer

The reducer takes the SSE event stream and produces the same `ScenarioState` shape the static beats produced — so existing canvas components don't change.

`canvas/hooks/useLiveScenario.ts`:

```typescript
"use client";

import { useEffect, useReducer, useRef, useState } from "react";

import { AgentStream, ConnectionState } from "@/lib/agent-stream";
import type { CanvasEvent } from "@/lib/canvas-events";
import type { ScenarioState } from "@/data/demoScenarios";

interface UseLiveScenarioOptions {
  scenarioName: "cargo-plane" | "buffer-planning";
  sessionId: string;
  userId: string;
  userMessage: string;     // the prompt that kicks off the workflow
  enabled: boolean;
  initialState: ScenarioState;
}

function eventReducer(state: ScenarioState, event: CanvasEvent): ScenarioState {
  switch (event.type) {
    case "workflow.started":
      return { ...state, drawer: { open: false }, costBanner: { visible: false } };

    case "capacity.gap_detected":
      return {
        ...state,
        mapCenter: [event.location.longitude, event.location.latitude],
        assets: [
          ...state.assets,
          {
            id: "capacity-gap",
            location: [event.location.longitude, event.location.latitude],
            state: "blocked",
            label: `Gap: ${event.canonical_asset_id}`,
            pulse: true, size: "lg",
          },
        ],
      };

    case "mcp.call.started":
      return {
        ...state,
        activeMcpCalls: [...(state.activeMcpCalls ?? []), {
          server: event.server, tool: event.tool, startedAt: event.timestamp,
        }],
      };

    case "mcp.call.completed":
      return {
        ...state,
        activeMcpCalls: (state.activeMcpCalls ?? []).filter(
          (c) => !(c.server === event.server && c.tool === event.tool),
        ),
      };

    case "route.doomed_proposed":
      return {
        ...state,
        arcs: [...state.arcs, {
          id: "doomed",
          from: [event.from_location.longitude, event.from_location.latitude],
          to: [event.to_location.longitude, event.to_location.latitude],
          color: "#6b7280", dashed: true, animateDraw: true,
        }],
        costBanner: { ...state.costBanner, doomed: event.estimated_cost_usd },
      };

    case "knowledge_catalog.lookup":
      return {
        ...state,
        drawer: {
          open: true,
          entity: {
            canonicalId: event.canonical_id,
            canonicalLabel: event.canonical_label,
            aspects: event.aspects as any,
          },
        },
      };

    case "equivalence.found":
      return {
        ...state,
        assets: [...state.assets, {
          id: `equivalent-${event.equivalent_asset.canonical_id}`,
          location: [event.location.longitude, event.location.latitude],
          state: "available", label: event.equivalent_asset.label,
          pulse: true, size: "lg",
        }],
      };

    case "route.recommended":
      return {
        ...state,
        arcs: [
          ...state.arcs.map((a) => a.id === "doomed" ? { ...a, opacity: 0.3 } : a),
          {
            id: "recommended",
            from: [event.from_location.longitude, event.from_location.latitude],
            to: [event.to_location.longitude, event.to_location.latitude],
            color: "#10b981", animateDraw: true,
          },
        ],
        costBanner: {
          visible: true,
          doomed: state.costBanner.doomed,
          recommended: event.estimated_cost_usd,
          avoided: event.avoided_cost_usd,
        },
      };

    case "forecast.loaded":
      return { ...state, showTimeline: true, timeline: event.timeline };

    case "buffer.recommendation":
      return { ...state, bufferOption: event.risk_tolerance, drawerOpen: true };

    default:
      return state;
  }
}

export function useLiveScenario(opts: UseLiveScenarioOptions) {
  const [state, dispatch] = useReducer(eventReducer, opts.initialState);
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const streamRef = useRef<AgentStream | null>(null);

  useEffect(() => {
    if (!opts.enabled) return;

    const stream = new AgentStream({
      url: process.env.NEXT_PUBLIC_ORCHESTRATOR_STREAM_URL!,
      sessionId: opts.sessionId,
      userId: opts.userId,
      userMessage: opts.userMessage,
      authToken: getAuthToken(),
      onEvent: (event) => dispatch(event),
      onStateChange: setConnectionState,
    });
    stream.connect();
    streamRef.current = stream;

    return () => {
      stream.close();
      streamRef.current = null;
    };
  }, [opts.enabled, opts.sessionId, opts.userId, opts.userMessage]);

  return { state, connectionState };
}

function getAuthToken(): string {
  // Demo: read from a secure cookie set by the GE app shell.
  // Production: use Workload Identity or a server-side proxy that injects auth.
  return document.cookie.split("auth_token=")[1]?.split(";")[0] ?? "";
}
```

### Step 6 — Wire the mode toggle into the scenario pages

Add Live/Static/Replay tri-state mode to `canvas/app/scenarios/cargo-plane/page.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { GlobalMap } from "@/components/canvas/GlobalMap";
import { useScenario } from "@/hooks/useScenario";
import { useLiveScenario } from "@/hooks/useLiveScenario";
import { useReplayScenario } from "@/hooks/useReplayScenario";
import { cargoPlaneBeats } from "@/data/demoScenarios";

type Mode = "static" | "live" | "replay";

const MARIA_SESSION_ID = "demo-maria-cargo-plane-v1";
const MARIA_USER_ID = "maria-occ-planner-west-africa";
const MARIA_PROMPT = "I need a Tool X variant in Luanda by Friday — what are my options?";

export default function CargoPlaneScenarioPage() {
  const [mode, setMode] = useState<Mode>("static");

  const staticScenario = useScenario({ beats: cargoPlaneBeats });
  const liveScenario = useLiveScenario({
    scenarioName: "cargo-plane",
    sessionId: MARIA_SESSION_ID, userId: MARIA_USER_ID,
    userMessage: MARIA_PROMPT,
    enabled: mode === "live",
    initialState: cargoPlaneBeats[0].state,
  });
  const replayScenario = useReplayScenario({
    recordingPath: "/recorded_events/cargo_plane_v1.json",
    enabled: mode === "replay",
    initialState: cargoPlaneBeats[0].state,
  });

  // Auto-fallback if Live errors
  useEffect(() => {
    if (mode === "live" && liveScenario.connectionState === "error") {
      console.warn("Live SSE failed, falling back to Static");
      setMode("static");
    }
  }, [mode, liveScenario.connectionState]);

  // L key cycles Static → Live → Replay → Static
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "l" && !e.metaKey && !e.ctrlKey) {
        setMode((m) => m === "static" ? "live" : m === "live" ? "replay" : "static");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const state =
    mode === "live" ? liveScenario.state :
    mode === "replay" ? replayScenario.state :
    staticScenario.state;

  return (
    <CanvasShell
      chat={<ChatPanel mode={mode} connectionState={liveScenario.connectionState} />}
      drawer={state.drawer.entity ? <KnowledgeCatalogDrawer {...state.drawer.entity} /> : null}
      drawerOpen={state.drawer.open}
      canvas={
        <>
          <GlobalMap center={state.mapCenter} zoom={state.mapZoom} />
          <CostRollupBanner {...state.costBanner} />
          <ModeIndicator mode={mode} connectionState={liveScenario.connectionState} />
        </>
      }
    />
  );
}
```

### Step 7 — Integration test [SUPERSEDED]

> **NOTE (2026-05-21):** This step's integration test consumed
> `/a2a/v1/message:stream` — superseded by direct streamQuery smokes
> (see `scripts/smoke_cargo_plane.py` for the data-flow probe and the
> repo-root live smoke runs in the May 2026 commit history). The script
> below is preserved as a historical record of the path we considered.

`tests/integration/test_live_sse.py`:

```python
"""Integration test for the Orchestrator's A2A SSE stream."""

import asyncio
import json
import os
from datetime import timedelta

import httpx
import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_STREAM_URL"),
    reason="Set ORCHESTRATOR_STREAM_URL to a deployed A2A endpoint to run.",
)


async def consume_sse(url: str, body: dict, token: str, timeout_s: int = 30):
    """Open the SSE endpoint and yield parsed canvas events."""
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        async with client.stream(
            "POST", url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            },
            json=body,
        ) as resp:
            resp.raise_for_status()
            async for raw in resp.aiter_lines():
                if not raw.startswith("data:"):
                    continue
                yield json.loads(raw[5:].strip())


async def test_cargo_plane_workflow_emits_canvas_events():
    """The Workflow should emit a canonical sequence of canvas events."""
    body = {
        "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": (
                "I need a Tool X variant in Luanda by Friday — what are my options?"
            )}],
        },
        "metadata": {
            "context_id": "test-live-sse-cargo",
            "user_id": "maria-occ-planner-west-africa",
        },
    }
    token = os.environ["GCP_AUTH_TOKEN"]  # gcloud auth print-access-token
    received = []
    async for evt in consume_sse(os.environ["ORCHESTRATOR_STREAM_URL"], body, token):
        received.append(evt)
        if evt.get("type") == "workflow.completed":
            break

    types_seen = [e.get("type") for e in received]
    assert "workflow.started" in types_seen
    assert "capacity.gap_detected" in types_seen
    assert types_seen.count("mcp.call.started") >= 3      # SAP + Maximo + FDP
    assert "knowledge_catalog.lookup" in types_seen
    assert "equivalence.found" in types_seen
    assert "route.doomed_proposed" in types_seen
    assert "route.recommended" in types_seen
    assert "workflow.completed" in types_seen
```

### Step 8 — Record canonical events for Replay mode

For the highest-stakes demo (first customer meeting), pre-record a successful run of the cargo-plane scenario as a JSON sequence:

```bash
make record-canonical-cargo-plane-events
# Saves to: canvas/data/recorded_events/cargo_plane_v1.json
```

`canvas/hooks/useReplayScenario.ts`:

```typescript
"use client";

import { useEffect, useReducer, useState } from "react";

interface ReplayOptions {
  recordingPath: string;          // e.g. "/recorded_events/cargo_plane_v1.json"
  enabled: boolean;
  initialState: ScenarioState;
}

interface Recording {
  events: Array<{ delayMsFromStart: number; event: CanvasEvent }>;
}

export function useReplayScenario(opts: ReplayOptions) {
  const [state, dispatch] = useReducer(eventReducer, opts.initialState);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!opts.enabled) return;
    let cancelled = false;
    fetch(opts.recordingPath).then(r => r.json()).then((rec: Recording) => {
      rec.events.forEach(({ delayMsFromStart, event }) => {
        setTimeout(() => {
          if (cancelled) return;
          dispatch(event);
          setProgress(p => p + 1);
        }, delayMsFromStart);
      });
    });
    return () => { cancelled = true; };
  }, [opts.enabled, opts.recordingPath]);

  return { state, progress };
}
```

The recording is a "guaranteed-good demo." Live and Replay produce identical canvas behavior; only the source of events differs.

### Step 9 — Update the brief narration

Add a sentence to `docs/planning/agentic_sop_oilfield_services_brief.md` in the Persona 3 section:

> *"The canvas is consuming events directly from the Workflow execution via the A2A `message:stream` SSE endpoint — same protocol Gemini Enterprise itself uses to surface agent status. When the agent's parallel_system_queries node fans out, the canvas shows it in real time. When the Knowledge Catalog lookup completes, the drawer opens. Same Workflow, same trace, same story."*

### Step 10 — Commit

```bash
git add .
git commit -m "feat: stream Workflow events to canvas via A2A SSE (TASK-10)"
git push
```

---

## Acceptance criteria

- [ ] `CanvasEvent` protocol defined in Pydantic (using `str` IDs, not `uuid.UUID`) + matching TypeScript generated via `pydantic2ts`
- [ ] `src/orchestrator_agent/events/emit.py` helper appends canvas events to session state
- [ ] All Workflow nodes emit appropriate events (workflow lifecycle, node lifecycle, MCP calls, KC lookups, decisions, scenario-specific)
- [ ] Orchestrator deploy switched from `AdkApp` to `A2aAgent` via `deploy_a2a_agent_engine`; SSE URL captured in `.env` as `ORCHESTRATOR_STREAM_URL`
- [ ] `canvas/lib/agent-stream.ts` opens an SSE connection via `fetch + ReadableStream` (NOT `EventSource` — it can't carry auth headers)
- [ ] `canvas/hooks/useLiveScenario.ts` reduces SSE events into `ScenarioState`
- [ ] `canvas/hooks/useReplayScenario.ts` plays recorded events on original timing
- [ ] Three-mode toggle works for both scenarios (Static → Live → Replay via L key)
- [ ] Auto-fallback to Static on SSE error
- [ ] Mode indicator visible in the canvas at all times
- [ ] Integration test verifies the expected event sequence is emitted from the deployed endpoint
- [ ] Brief updated with SSE narration moment
- [ ] Commit pushed

---

## Common pitfalls

**Don't use `EventSource`.** The browser's built-in SSE client doesn't support custom HTTP headers, so it can't carry the `Authorization: Bearer` token that the A2A endpoint requires. Use `fetch` + `ReadableStream` as shown in Step 4.

**Event ordering vs. concurrent execution.** Workflow nodes can execute in parallel. The reducer must rely on the `timestamp` field, not arrival order, for any logic that depends on sequence.

**Auth token expiry.** Bearer tokens from `gcloud auth print-access-token` last ~1 hour. Long demos may outlast a token — refresh via OAuth flow before reconnecting the SSE stream. For production: a server-side proxy that injects a service-account-derived token is more robust than passing user tokens through the browser.

**SSE through corporate proxies.** Customer environments sometimes buffer `text/event-stream` responses, breaking real-time delivery. For the first customer demo: (1) test on the actual demo network well in advance, (2) keep Replay mode as the demo-day safety net, (3) configure the Cloud Run / proxy layer (if any) for `X-Accel-Buffering: no`.

**Event payload bloat.** Tempting to include the full MCP response in `MCPCallCompletedEvent.result_summary`. Resist: large payloads add SSE chunk size and parsing latency. Strip aggressively in `_summarize`.

**Static fallback drift.** As the live event protocol evolves, the static beats can drift out of sync. Periodically regenerate the static beats from a recorded run (the Replay-mode workflow produces this naturally).

**Demo room WiFi.** Live mode depends on stable WiFi + GCP reachability. Always have Replay mode tested on the demo network. Test in the actual conference room ahead of time.

**Cloud Trace divergence.** If Workflow nodes emit events that don't correspond to actual Cloud Trace spans, the customer's audit team will notice. Always emit the event *after* the underlying call completes, with the actual timestamp from the call.

**Auth on the browser side.** Storing a long-lived Bearer token in a cookie is acceptable for the demo (the Gemini Enterprise app shell can issue one) but not for production. Document the dev/prod split clearly.

---

## References

- A2A SSE protocol: `~/.claude/references/a2a-protocol-and-adk-integration.md` §JSON-RPC methods, §Streaming vs synchronous
- Vertex AI Agent Engine A2A deploys: `~/.claude/references/vertex-agent-engine-deploys.md` §A2A-wrapped agent deploys
- ADK 2.0 Event API + Workflow nodes: `~/.claude/references/google-adk-2.0.md` §Event, §Nodes
- McpToolset: `~/.claude/references/google-adk-2.0.md` §McpToolset
- Procurement Approval Agent (the canonical A2A example in this repo): `src/procurement_approval_agent/runtime/`
- Pydantic to TypeScript: `https://github.com/phillipdupuis/pydantic-to-typescript`

---

*When TASK-10 is complete, the canvas is no longer faking the agent's behavior — it's reacting to actual events from the actual Workflow over the A2A SSE stream. The customer's first demo plays out in three modes: Static (safe), Live (real), Replay (recorded). The story is the same in all three.*
