"""Event protocol emitted by the Capacity Orchestrator to the canvas.

This is the contract: every state change the canvas wants to render must be
expressible as one of these events. Adding a visual element requires adding
an event type.

Event IDs are ``str`` not ``uuid.UUID`` (per CLAUDE.md known gotcha — stdlib
``json.dumps`` can't serialize UUID even when Pydantic can). All event types
carry a ``type`` literal discriminator so the canvas reducer can dispatch
via tagged union.

Workflow nodes emit these by appending to ``ctx.state['canvas_events']``
via :func:`src.orchestrator_agent.events.emit.emit`. The A2A executor
(``runtime/agent_executor.py``) reads new entries on each ADK event and
forwards them as A2A ``Message`` events on the SSE stream.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Union

from pydantic import BaseModel, Field


def _new_id() -> str:
    """Generate a string UUID — never a ``uuid.UUID`` object.

    The deployed ADK runtime serializes structured output via stdlib
    ``json.dumps`` which doesn't know how to encode ``uuid.UUID``. See
    CLAUDE.md "UUID fields break ADK output serialization".
    """
    return str(uuid.uuid4())


class BaseEvent(BaseModel):
    """Common envelope for every canvas event."""

    event_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    workflow_id: str
    session_id: str


# --- Workflow lifecycle ----------------------------------------------------


class WorkflowStartedEvent(BaseEvent):
    type: Literal["workflow.started"] = "workflow.started"
    scenario: str  # "cargo-plane" | "buffer-planning"
    user_id: str
    initial_context: dict  # seed memory excerpt (per-persona)


class WorkflowCompletedEvent(BaseEvent):
    type: Literal["workflow.completed"] = "workflow.completed"
    final_output: dict  # SourcingPlan, BufferPlan, etc.
    duration_ms: int


class WorkflowFailedEvent(BaseEvent):
    type: Literal["workflow.failed"] = "workflow.failed"
    node_name: str
    error_class: str  # e.g. "TimeoutError"
    error_message: str


# --- Node lifecycle --------------------------------------------------------


class NodeStartedEvent(BaseEvent):
    type: Literal["node.started"] = "node.started"
    node_name: str
    node_kind: Literal["function", "llm", "router", "subworkflow"]


class NodeCompletedEvent(BaseEvent):
    type: Literal["node.completed"] = "node.completed"
    node_name: str
    duration_ms: int
    output_summary: str | None = None


# --- MCP & Knowledge Catalog calls (platform-visibility moments) ----------


class MCPCallStartedEvent(BaseEvent):
    type: Literal["mcp.call.started"] = "mcp.call.started"
    server: str  # "sap-mcp-server" | "maximo-mcp-server" | "fdp-mcp-server" | ...
    tool: str
    via_gateway: bool = True


class MCPCallCompletedEvent(BaseEvent):
    type: Literal["mcp.call.completed"] = "mcp.call.completed"
    server: str
    tool: str
    duration_ms: int
    result_summary: dict  # small payload — enough for canvas, not full response


class KnowledgeCatalogLookupEvent(BaseEvent):
    type: Literal["knowledge_catalog.lookup"] = "knowledge_catalog.lookup"
    canonical_id: str
    canonical_label: str
    aspects: dict  # full entity payload for the drawer


# --- Decisions -------------------------------------------------------------


class RouterDecisionEvent(BaseEvent):
    type: Literal["router.decision"] = "router.decision"
    router_name: str
    decision: str  # the routing key chosen
    rationale: str | None = None


# --- Cargo-plane specific events ------------------------------------------


class CapacityGapDetectedEvent(BaseEvent):
    type: Literal["capacity.gap_detected"] = "capacity.gap_detected"
    location: dict  # { latitude, longitude, label }
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


# --- Buffer-planning specific events (declared now, used by sibling agents) -


class ForecastLoadedEvent(BaseEvent):
    type: Literal["forecast.loaded"] = "forecast.loaded"
    equipment_class: str
    timeline: list[dict]  # 12-week probabilistic forecast


class BufferRecommendationEvent(BaseEvent):
    type: Literal["buffer.recommendation"] = "buffer.recommendation"
    risk_tolerance: Literal["conservative", "balanced", "aggressive"]
    buffer_pct: float
    expected_idle_cost_usd: float
    expected_late_start_cost_usd: float
    on_time_probability: float


# --- Discriminated union for type-safe dispatch ---------------------------


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
