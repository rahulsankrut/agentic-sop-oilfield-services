"""Unit tests for shared Pydantic schemas.

Verifies every schema can serialize to JSON cleanly and round-trip back to the
same model. Catches accidental field renames / type drift that would break the
A2A wire format between agents.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.schemas import (
    AssetIdentifier,
    BufferOptimization,
    CanvasEventEnvelope,
    CriterionScore,
    ForecastOverride,
    ForecastRationale,
    GeoPoint,
    PlanEvaluation,
    ProcurementApproval,
    Severity,
    SourcingOption,
    SourcingPlan,
    StartDateDistribution,
)


def _now() -> datetime:
    return datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _asset() -> AssetIdentifier:
    return AssetIdentifier(
        canonical_id="TX-001",
        canonical_label="Tool X",
        sap_material_number="MAT-67890",
        maximo_equipment_id="EQ-12345",
        fdp_config_id="TX-CONFIG-A",
        intouch_spec_refs=["spec/3.2"],
    )


def _option() -> SourcingOption:
    return SourcingOption(
        asset=_asset(),
        source_location=GeoPoint(latitude=6.5244, longitude=3.3792, label="Lagos"),
        destination=GeoPoint(latitude=-8.8390, longitude=13.2894, label="Luanda"),
        transit_mode="ground_transit",
        estimated_cost_usd=40_000,
        transit_hours=12.0,
        certification_hours=4.0,
        customer_compatibility=True,
        workforce_available=True,
    )


def _plan() -> SourcingPlan:
    return SourcingPlan(
        requested_asset="Tool X",
        target_location=GeoPoint(latitude=-8.8390, longitude=13.2894, label="Luanda"),
        deadline=_now(),
        primary_option=_option(),
        naive_baseline=_option().model_copy(
            update={"transit_mode": "cargo_charter", "estimated_cost_usd": 420_000}
        ),
        avoided_cost_usd=380_000,
    )


# Parametrized round-trip test — keeps adding schemas as we grow
@pytest.mark.parametrize(
    "instance",
    [
        GeoPoint(latitude=0.0, longitude=0.0),
        _asset(),
        _option(),
        _plan(),
        CriterionScore(
            criterion="safety_compliance",
            score=0.95,
            severity=Severity.LOW,
            rationale="No safety blockers identified.",
        ),
        PlanEvaluation(
            request_id=uuid4(),
            overall_score=0.91,
            criterion_scores=[
                CriterionScore(
                    criterion="safety_compliance",
                    score=0.95,
                    severity=Severity.LOW,
                    rationale="ok",
                ),
            ],
            findings=["No issues."],
            revision_recommended=False,
        ),
        ProcurementApproval(
            request_id=uuid4(),
            approved=True,
            blockers=[],
            audit_trail_url="https://example.invalid/audit/123",
        ),
        ForecastOverride(
            basin="Permian",
            period="2026-Q4",
            metric="completions_revenue",
            original_value=100.0,
            override_value=78.0,
            override_pct_change=-0.22,
            submitted_by="david@example.com",
            submitted_at=_now(),
        ),
        ForecastRationale(
            override_id=uuid4(),
            rationale_tags=["rig_count_decline", "operator_delay"],
            freeform_text="Three operators delaying programs.",
            confidence=0.85,
        ),
        StartDateDistribution(
            requested_date=_now(),
            p10_actual_date=_now(),
            p50_actual_date=_now(),
            p90_actual_date=_now(),
            confidence=0.8,
        ),
        BufferOptimization(
            request_id=uuid4(),
            basin="Permian",
            risk_tolerance=0.7,
            current_buffer_days=14.0,
            recommended_buffer_days=8.0,
            projected_on_time_rate=0.65,
            fleet_utilization_uplift_pct=12.0,
            deferred_capex_usd=4_500_000,
        ),
        CanvasEventEnvelope(
            event_type="sourcing_recommendation",
            request_id=uuid4(),
            timestamp=_now(),
            payload={"foo": "bar"},
        ),
    ],
    ids=lambda i: type(i).__name__,
)
def test_schema_json_round_trip(instance):
    """Every schema serializes to JSON and rehydrates identically."""
    serialized = instance.model_dump_json()
    cls = type(instance)
    rehydrated = cls.model_validate_json(serialized)
    assert rehydrated == instance


def test_severity_is_string_enum():
    """Severity must serialize as string for cross-language compatibility."""
    score = CriterionScore(criterion="test", score=0.5, severity=Severity.HIGH, rationale="x")
    assert '"severity":"high"' in score.model_dump_json()


def test_sourcing_plan_auto_assigns_request_id():
    """A SourcingPlan without request_id should still validate (UUID default)."""
    plan = SourcingPlan(
        requested_asset="Tool X",
        target_location=GeoPoint(latitude=0.0, longitude=0.0),
        deadline=_now(),
        primary_option=_option(),
    )
    assert plan.request_id is not None
    # And re-serializing preserves the assigned UUID
    rehydrated = SourcingPlan.model_validate_json(plan.model_dump_json())
    assert rehydrated.request_id == plan.request_id
