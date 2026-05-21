"""Shared Pydantic schemas for the Oilfield Services Domain Pack.

Defines structured outputs and inter-agent message payloads. Every agent's
``LlmAgent(output_schema=...)`` references one of these types; A2A handoffs
between Orchestrator and sub-agents use them as wire format; the Operations
Canvas WebSocket consumer mirrors them as TypeScript types (canvas/src/types/).

Pattern (per SPECS.md Architectural principles §2 — Pydantic schemas attached
to ``LlmAgent(output_schema=...)``):

    from agents.schemas import SourcingPlan

    LlmAgent(
        ...,
        output_schema=SourcingPlan,
    )
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_uuid_str() -> str:
    """UUIDv4 as a string.

    Why string and not ``uuid.UUID``: the deployed ADK runtime serializes
    the agent's structured output via stdlib ``json.dumps``, which raises
    ``TypeError: Object of type UUID is not JSON serializable``. Plain
    strings round-trip cleanly through every Pydantic + JSON path.
    """
    return str(uuid4())


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
    # TASK-17: real-doc citations grounding this option (InTouch spec for
    # the asset class, BSEE incident for safety reference, etc.). The
    # canvas renders these as click-through "View source" chips.
    citations: list[Citation] = Field(default_factory=list)


class SourcingPlan(BaseModel):
    """The Capacity Orchestrator's sourcing recommendation."""

    request_id: str = Field(default_factory=_new_uuid_str)
    requested_asset: str  # what the planner asked for
    target_location: GeoPoint  # where they need it
    deadline: datetime
    primary_option: SourcingOption  # the recommended source
    naive_baseline: SourcingOption | None = None  # what they'd have done without the agent
    avoided_cost_usd: int = 0
    reasoning_trace_url: str | None = None


# ============================================================================
# Capacity Orchestrator Workflow plumbing (TASK-04)
# ============================================================================


class CapacityGapRequest(BaseModel):
    """Structured form of a planner's capacity-gap query.

    Produced by the first node in the Capacity Orchestrator Workflow
    (``parse_capacity_gap_request``). Flows through every subsequent node so
    downstream code never has to re-parse the raw query string.

    The optional fields (``canonical_asset_id``, ``target_region``,
    ``customer_id``) are filled in by later nodes (``resolve_canonical_asset``
    and the parallel system queries) — they're None on first parse.
    """

    raw_query: str
    requested_asset: str
    target_location: GeoPoint
    deadline: datetime
    customer_id: str | None = None
    canonical_asset_id: str | None = None
    target_region: str | None = None


class SystemQueryResults(BaseModel):
    """Aggregated results from parallel enterprise-system queries.

    The four fields correspond to the four MCP queries fanned out from
    ``parallel_system_queries``. Typed as ``dict | None`` for now (TASK-04);
    TASK-05 wires real MCP responses and may tighten the shape into per-system
    schemas. ``None`` means the query failed or returned empty.
    """

    maximo: dict | None = None
    sap: dict | None = None
    fdp: dict | None = None
    intouch: dict | None = None


class EquivalentAssetCandidate(BaseModel):
    """Structured output of the ``equivalence_lookup`` LLM Workflow node.

    The LLM is asked to pick ONE functional equivalent for a canonical asset
    given a customer context, and to ground its choice in a Knowledge Catalog
    spec reference.
    """

    canonical_id: str  # e.g. "TX-007" — the chosen substitute's canonical id
    canonical_label: str  # human-readable label, for UI / narration
    confidence: float = Field(ge=0.0, le=1.0)
    rationale_source: str  # spec / InTouch reference grounding the choice
    rationale_summary: str  # 1-2 sentence justification
    equipment_instance_id: str | None = None  # if the LLM identified a concrete instance
    # TASK-17: real-doc citations the LLM grounded the equivalence in.
    citations: list[Citation] = Field(default_factory=list)


# ============================================================================
# Plan Evaluator output (Persona 3 — Plan Evaluator sub-agent)
# ============================================================================


# NOTE: deliberately (str, Enum) — the deployed Vertex AI Reasoning Engine
# runtime is Python 3.10, where `enum.StrEnum` does not exist. The behaviour
# is identical for JSON serialization.
class Severity(str, Enum):  # noqa: UP042 — see comment above
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

    request_id: str
    overall_score: float  # weighted, 0.0 to 1.0
    criterion_scores: list[CriterionScore]
    findings: list[str] = Field(default_factory=list)
    revision_recommended: bool = False
    # TASK-17: BSEE incident reports + MCC contract citations that grounded
    # criterion scores (especially safety_compliance + regulatory_compliance).
    citations: list[Citation] = Field(default_factory=list)


# ============================================================================
# Procurement Gate output
# ============================================================================


class ProcurementApproval(BaseModel):
    """Procurement Approval Agent's decision on a SourcingPlan."""

    request_id: str
    approved: bool
    blockers: list[str] = Field(default_factory=list)
    audit_trail_url: str | None = None
    # TASK-17: real MSA citations grounding the procurement decision
    # (master service agreement clauses, indemnity, insurance limits, etc.).
    citations: list[Citation] = Field(default_factory=list)


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
    override_id: str
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

    request_id: str
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
    request_id: str
    timestamp: datetime
    payload: dict


# ============================================================================
# Document citations (TASK-17 — unstructured pillar)
#
# Skill tools attach `list[Citation]` to their structured outputs so the agent
# (and the canvas) can surface "agent grounded in this real PDF" alongside
# every decision. The GCS URI points at the actual PDF in the unstructured
# corpus; the canvas can render a click-through.
# ============================================================================


class Citation(BaseModel):
    """One reference to a real document in the unstructured corpus.

    Corpus values: "bsee" (incident reports), "mcc" (SEC EDGAR contracts),
    "intouch" (USPTO/Equinor/OSTI technical docs). `doc_uri` is a GCS URI
    like `gs://oilfield-services-unstructured/intouch_specs/uspto-...pdf`.
    """

    corpus: str
    doc_id: str
    doc_uri: str | None = None  # gs://... GCS URI
    title: str
    publisher: str = ""
    year: int = 0
    snippet: str | None = None  # Optional Vertex AI Search-derived passage


# ============================================================================
# Enterprise-system response schemas (TASK-16 §4 — additive)
#
# These mirror real SAP / Maximo / FDP table layouts so the typed MCP tool
# surface stays identical whether the implementation queries BigQuery (our
# v1) or live OData/REST (a customer's production swap).
# ============================================================================


class SapMaterialMaster(BaseModel):
    """SAP MARA + MAKT join — material master with English description."""

    matnr: str
    description: str | None = None
    material_type: str
    material_group: str | None = None
    base_uom: str = "EA"


class SapPlantData(BaseModel):
    """SAP MARC — per-plant material data."""

    matnr: str
    werks: str
    mrp_controller: str | None = None
    mrp_type: str | None = None
    procurement_type: str | None = None


class SapStorageStock(BaseModel):
    """SAP MARD — unrestricted stock at a (plant, storage location)."""

    matnr: str
    werks: str
    lgort: str
    unrestricted_stock: float
    quality_inspection_stock: float = 0.0


class SapStandardPrice(BaseModel):
    """SAP MBEW — standard price for a material."""

    matnr: str
    stprs: float
    peinh: int = 1
    waers: str = "USD"


class SapCustomer(BaseModel):
    """SAP KNA1 — customer master general data."""

    kunnr: str
    name1: str
    land1: str | None = None  # ISO country
    ort01: str | None = None  # City
    stras: str | None = None  # Street


class SapWorkforce(BaseModel):
    """SAP ZHR_WORKFORCE — workforce-by-basin snapshot (Z-table).

    NAICS_211_STATE_EMPLOYMENT and DATA_SOURCE are TASK-16 Step 4d.3
    additions: real BLS QCEW reference data for US basins, NULL for
    foreign basins where BLS doesn't cover. DATA_SOURCE is a free-form
    citation string suitable for the agent to surface in narration.
    """

    basin: str
    crew_count_available: int
    specialist_count_available: int
    on_call_count: int
    snapshot_date: str  # ISO date string — keep as str per CLAUDE.md gotcha
    naics_211_state_employment: int | None = None
    data_source: str | None = None


# ----- FDP (Forecast Demand Planner) — TASK-16 Step 7 -----------------------
#
# FDP is the OFS major's homegrown forecasting / customer-config tool. There
# is no public schema; the contract is the columns. Customer brings their
# FDP-equivalent extract as a flat table of
# (customer_id, material_number, approved_flag, accepted_substitutes[], notes).


class FdpCustomerConfig(BaseModel):
    """FDP per-customer per-material configuration record."""

    customer_id: str
    matnr: str
    approved: bool
    notes: str | None = None
    effective_date: str | None = None  # ISO date string


class FdpSubstitution(BaseModel):
    """FDP-approved substitute mapping (one row of the APPROVED_SUBSTITUTIONS table)."""

    customer_id: str
    matnr_original: str
    matnr_substitute: str
    accepted: bool


class FdpRestriction(BaseModel):
    """Derived: a substitution this customer has REJECTED (ACCEPTED=FALSE).

    Used by sourcing-logistics + asset-equivalence to apply the customer
    restriction multiplier when scoring equivalence confidence.
    """

    customer_id: str
    matnr_original: str
    matnr_substitute_rejected: str


# ----- Maximo — TASK-16 Step 6 ----------------------------------------------
#
# Mirror the real Maximo MAS 9.x table layout (ASSET / ITEM / INVENTORY /
# INVBALANCES / LOCATIONS / WORKORDER). The typed MCP tool surface stays
# identical whether the implementation queries our `maximo_extract.*` BQ
# dataset (v1) or a live MAS via the Maximo REST API (a customer's
# production swap). Dates serialized as ISO strings per the CLAUDE.md UUID
# gotcha (deployed ADK runtime uses stdlib json.dumps).


class MaximoItem(BaseModel):
    """Maximo ITEM — Item Master."""

    itemnum: str
    itemsetid: str = "SET1"
    description: str | None = None
    commoditygroup: str | None = None


class MaximoLocation(BaseModel):
    """Maximo LOCATIONS — Location Master with inline lat/lon + WPI port ref."""

    siteid: str
    location: str
    description: str | None = None
    type: str | None = None
    status: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    region: str | None = None
    wpi_port_index_number: int | None = None
    wpi_port_name: str | None = None


class MaximoAssetWithLocation(BaseModel):
    """Maximo ASSET joined to LOCATIONS — single physical unit + its place.

    Substitutes the legacy `EquipmentInstance` shape on the v2 tool surface.
    `location.description` replaces the legacy `location.label` (Q8 resolution).
    """

    assetnum: str
    itemnum: str | None = None
    status: str
    siteid: str
    description: str | None = None
    serialnum: str | None = None
    assettype: str | None = None
    installdate: str | None = None  # ISO date string
    location: MaximoLocation


class MaximoWorkOrder(BaseModel):
    """Maximo WORKORDER — recert + repair tracking."""

    wonum: str
    siteid: str
    assetnum: str | None = None
    location: str | None = None
    status: str
    worktype: str | None = None
    reportdate: str | None = None  # ISO timestamp string
    schedstart: str | None = None  # ISO timestamp string
    actstart: str | None = None  # ISO timestamp string
    est_lab_hrs: float | None = None
    act_lab_hrs: float | None = None
    bsee_lease_ref: str | None = None
    bsee_incident_date: str | None = None  # ISO date string


class InvBalance(BaseModel):
    """Maximo INVBALANCES — per-bin / per-lot stock balance."""

    itemnum: str
    itemsetid: str = "SET1"
    location: str
    siteid: str
    binnum: str
    lotnum: str | None = None
    conditioncode: str | None = None
    physcnt: float | None = None
    physcntdate: str | None = None  # ISO date string
    curbal: float | None = None
