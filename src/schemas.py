"""Shared Pydantic schemas for the Oilfield Services Domain Pack.

Defines structured outputs and inter-agent message payloads. Every agent's
``LlmAgent(output_schema=...)`` references one of these types; A2A handoffs
between Orchestrator and sub-agents use them as wire format; the Operations
Canvas WebSocket consumer mirrors them as TypeScript types (canvas/src/types/).

Pattern (per SPECS.md Architectural principles §2 — Pydantic schemas attached
to ``LlmAgent(output_schema=...)``):

    from src.schemas import SourcingPlan

    LlmAgent(
        ...,
        output_schema=SourcingPlan,
    )
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ============================================================================
# Geographic and identity primitives
# ============================================================================


class GeoPoint(BaseModel):
    """Latitude/longitude point with an optional human label."""

    latitude: float
    longitude: float
    label: str | None = None


class AssetIdentifier(BaseModel):
    """A canonical asset with its cross-system aliases.

    The Knowledge Catalog stores the canonical entry; per-system identifiers
    are aliases. Agents reason on ``canonical_id`` / ``canonical_label`` and
    the cross-system aliases get resolved by MCP queries.
    """

    canonical_id: str  # e.g. "TX-001"
    canonical_label: str  # e.g. "Tool X"
    sap_material_number: str | None = None  # e.g. "MAT-67890"
    maximo_equipment_id: str | None = None  # e.g. "EQ-12345"
    fdp_config_id: str | None = None  # e.g. "TX-CONFIG-A"
    intouch_spec_refs: list[str] = Field(default_factory=list)


# ============================================================================
# Sourcing plan (Persona 3 — Maria)
# ============================================================================


class SourcingOption(BaseModel):
    """A single sourcing option (where to get an asset from)."""

    asset: AssetIdentifier
    source_location: GeoPoint
    destination: GeoPoint
    transit_mode: str  # "ground_transit" | "cargo_charter" | "sea_freight"
    estimated_cost_usd: int
    transit_hours: float
    certification_hours: float = 0
    customer_compatibility: bool
    workforce_available: bool
    blockers: list[str] = Field(default_factory=list)


class SourcingPlan(BaseModel):
    """The Capacity Orchestrator's sourcing recommendation."""

    request_id: UUID = Field(default_factory=uuid4)
    requested_asset: str  # what the planner asked for
    target_location: GeoPoint  # where they need it
    deadline: datetime
    primary_option: SourcingOption  # the recommended source
    naive_baseline: SourcingOption | None = None  # what they'd have done without the agent
    avoided_cost_usd: int = 0
    reasoning_trace_url: str | None = None


# ============================================================================
# Plan Evaluator output (Persona 3 — Plan Evaluator sub-agent)
# ============================================================================


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CriterionScore(BaseModel):
    criterion: str
    score: float  # 0.0 to 1.0
    severity: Severity
    rationale: str


class PlanEvaluation(BaseModel):
    """Plan Evaluator's evaluation of a SourcingPlan."""

    request_id: UUID
    overall_score: float  # weighted, 0.0 to 1.0
    criterion_scores: list[CriterionScore]
    findings: list[str] = Field(default_factory=list)
    revision_recommended: bool = False


# ============================================================================
# Procurement Gate output
# ============================================================================


class ProcurementApproval(BaseModel):
    """Procurement Approval Agent's decision on a SourcingPlan."""

    request_id: UUID
    approved: bool
    blockers: list[str] = Field(default_factory=list)
    audit_trail_url: str | None = None


# ============================================================================
# Forecast review (Persona 1 — David)
# ============================================================================


class ForecastOverride(BaseModel):
    basin: str
    period: str  # e.g. "2026-Q4"
    metric: str  # e.g. "completions_revenue"
    original_value: float
    override_value: float
    override_pct_change: float
    submitted_by: str
    submitted_at: datetime


class ForecastRationale(BaseModel):
    override_id: UUID
    rationale_tags: list[str]  # e.g. ["rig_count_decline", "operator_delay"]
    freeform_text: str
    confidence: float


# ============================================================================
# Buffer optimization (Persona 2 — Tomas)
# ============================================================================


class StartDateDistribution(BaseModel):
    """Probabilistic distribution of an actual start date vs. requested."""

    requested_date: datetime
    p10_actual_date: datetime
    p50_actual_date: datetime
    p90_actual_date: datetime
    confidence: float


class BufferOptimization(BaseModel):
    """Capacity Planning Agent's buffer recommendation for a fleet."""

    request_id: UUID
    basin: str
    risk_tolerance: float  # 0.0 to 1.0
    current_buffer_days: float
    recommended_buffer_days: float
    projected_on_time_rate: float  # 0.0 to 1.0
    fleet_utilization_uplift_pct: float
    deferred_capex_usd: int


# ============================================================================
# WebSocket event envelope (for Operations Canvas)
# ============================================================================


class CanvasEventEnvelope(BaseModel):
    """Wraps any agent event for transmission to the Operations Canvas."""

    event_type: str
    request_id: UUID
    timestamp: datetime
    payload: dict
