/**
 * canvas-events.ts
 *
 * TypeScript types mirroring the Pydantic schemas the Capacity Orchestrator
 * will emit on its A2A SSE stream (see
 * `src/orchestrator_agent/events/canvas_events.py`).
 *
 * Hand-authored against the TASK-10 spec — the matching Pydantic module is
 * being built in parallel by the backend agent. If the backend introduces
 * additional fields, update them here. The contract is enforced by the
 * deployed Orchestrator's `output_schema=`-style validation; the canvas
 * trusts the wire format and parses optimistically.
 *
 * Per the spec, all IDs are `string` (the backend uses `str` not
 * `uuid.UUID`; see CLAUDE.md known gotcha #6 — stdlib `json.dumps` can't
 * serialize `UUID` even when Pydantic can). Discriminated union via the
 * `type` literal.
 */

// ---------------------------------------------------------------------------
// Shared base envelope
// ---------------------------------------------------------------------------

export interface BaseEvent {
  event_id: string;
  /** ISO-8601 timestamp from the backend (datetime.utcnow().isoformat()). */
  timestamp: string;
  workflow_id: string;
  session_id: string;
}

// ---------------------------------------------------------------------------
// Geographic / asset payload shapes used across multiple event types
// ---------------------------------------------------------------------------

export interface EventLocation {
  latitude: number;
  longitude: number;
  label?: string;
}

export interface EventAsset {
  canonical_id: string;
  label: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Workflow lifecycle
// ---------------------------------------------------------------------------

export interface WorkflowStartedEvent extends BaseEvent {
  type: "workflow.started";
  scenario: "cargo-plane" | "buffer-planning";
  user_id: string;
  initial_context: Record<string, unknown>;
}

export interface WorkflowCompletedEvent extends BaseEvent {
  type: "workflow.completed";
  final_output: Record<string, unknown>;
  duration_ms: number;
}

export interface WorkflowFailedEvent extends BaseEvent {
  type: "workflow.failed";
  node_name: string;
  error_class: string;
  error_message: string;
}

// ---------------------------------------------------------------------------
// Node lifecycle
// ---------------------------------------------------------------------------

export type NodeKind = "function" | "llm" | "router" | "subworkflow";

export interface NodeStartedEvent extends BaseEvent {
  type: "node.started";
  node_name: string;
  node_kind: NodeKind;
}

export interface NodeCompletedEvent extends BaseEvent {
  type: "node.completed";
  node_name: string;
  duration_ms: number;
  output_summary?: string | null;
}

// ---------------------------------------------------------------------------
// MCP & Knowledge Catalog calls (platform-visibility moments)
// ---------------------------------------------------------------------------

export interface MCPCallStartedEvent extends BaseEvent {
  type: "mcp.call.started";
  server: string;
  tool: string;
  via_gateway?: boolean;
}

export interface MCPCallCompletedEvent extends BaseEvent {
  type: "mcp.call.completed";
  server: string;
  tool: string;
  duration_ms: number;
  result_summary: Record<string, unknown>;
}

export interface KnowledgeCatalogLookupEvent extends BaseEvent {
  type: "knowledge_catalog.lookup";
  canonical_id: string;
  canonical_label: string;
  aspects: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Decisions
// ---------------------------------------------------------------------------

export interface RouterDecisionEvent extends BaseEvent {
  type: "router.decision";
  router_name: string;
  decision: string;
  rationale?: string | null;
}

// ---------------------------------------------------------------------------
// Cargo-plane specific events
// ---------------------------------------------------------------------------

export interface CapacityGapDetectedEvent extends BaseEvent {
  type: "capacity.gap_detected";
  location: EventLocation;
  canonical_asset_id: string;
  deadline: string;
}

export interface DoomedRouteProposedEvent extends BaseEvent {
  type: "route.doomed_proposed";
  from_location: EventLocation;
  to_location: EventLocation;
  estimated_cost_usd: number;
  rationale: string;
}

export interface EquivalentAssetFoundEvent extends BaseEvent {
  type: "equivalence.found";
  original_asset: EventAsset;
  equivalent_asset: EventAsset;
  confidence: number;
  rationale_source: string;
  location: EventLocation;
}

export interface RecommendedRouteFinalizedEvent extends BaseEvent {
  type: "route.recommended";
  from_location: EventLocation;
  to_location: EventLocation;
  estimated_cost_usd: number;
  avoided_cost_usd: number;
}

// ---------------------------------------------------------------------------
// Buffer-planning specific events
// ---------------------------------------------------------------------------

export interface ForecastLoadedEvent extends BaseEvent {
  type: "forecast.loaded";
  equipment_class: string;
  timeline: Array<Record<string, unknown>>;
}

export type BufferRiskTolerance = "conservative" | "balanced" | "aggressive";

export interface BufferRecommendationEvent extends BaseEvent {
  type: "buffer.recommendation";
  risk_tolerance: BufferRiskTolerance;
  buffer_pct: number;
  expected_idle_cost_usd: number;
  expected_late_start_cost_usd: number;
  on_time_probability: number;
}

// ---------------------------------------------------------------------------
// Discriminated union
// ---------------------------------------------------------------------------

export type CanvasEvent =
  | WorkflowStartedEvent
  | WorkflowCompletedEvent
  | WorkflowFailedEvent
  | NodeStartedEvent
  | NodeCompletedEvent
  | MCPCallStartedEvent
  | MCPCallCompletedEvent
  | KnowledgeCatalogLookupEvent
  | RouterDecisionEvent
  | CapacityGapDetectedEvent
  | DoomedRouteProposedEvent
  | EquivalentAssetFoundEvent
  | RecommendedRouteFinalizedEvent
  | ForecastLoadedEvent
  | BufferRecommendationEvent;

/** Convenient union of every `type` literal. */
export type CanvasEventType = CanvasEvent["type"];
