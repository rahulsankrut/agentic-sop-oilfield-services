"""Unit tests for the deterministic logic in every skill's `scripts/tools.py`.

Each skill's tools are pure Python (no LLM calls). These tests lock in the
behavior the agents will rely on at runtime.
"""

from __future__ import annotations

import importlib
import json

import pytest

# Skill tool modules — imported dynamically because the directory names use
# hyphens, which aren't valid Python identifiers.

ASSET_EQUIV = (
    importlib.import_module(
        "agents.orchestrator_agent.skills.asset-equivalence.scripts.tools".replace("-", "_")
    )
    if False
    else None
)  # placeholder; we use load_module below.


def _load_skill_tools(skill_path: str):
    """Helper: load a module from a hyphenated path."""
    import importlib.util
    from pathlib import Path

    # File is at <repo>/agents/tests/unit/test_skills.py → 4 parents up to repo root.
    project_root = Path(__file__).parent.parent.parent.parent
    file_path = project_root / skill_path
    spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Load each skill's tools module once
asset_equiv = _load_skill_tools(
    "agents/orchestrator_agent/skills/asset-equivalence/scripts/tools.py"
)
sourcing = _load_skill_tools("agents/orchestrator_agent/skills/sourcing-logistics/scripts/tools.py")
enterprise = _load_skill_tools(
    "agents/orchestrator_agent/skills/enterprise-systems/scripts/tools.py"
)
plan_eval = _load_skill_tools(
    "agents/orchestrator_agent/plan_evaluator/skills/plan-evaluation/scripts/tools.py"
)
procurement = _load_skill_tools(
    "agents/procurement_approval_agent/skills/procurement-prerequisites/scripts/tools.py"
)
forecast = _load_skill_tools(
    "agents/forecast_review_agent/skills/forecast-rationale/scripts/tools.py"
)
scheduling = _load_skill_tools(
    "agents/capacity_planning_agent/skills/scheduling-probability/scripts/tools.py"
)


# ----------------------------------------------------------------------
# asset-equivalence
# ----------------------------------------------------------------------


def test_resolve_canonical_asset_from_canonical_id():
    out = asset_equiv.resolve_canonical_asset("TX-001")
    assert out["canonical_id"] == "TX-001"
    assert out["canonical_label"] == "Tool X"
    assert out["sap_material_number"] == "MAT-67890"


def test_resolve_canonical_asset_from_sap_material_number():
    out = asset_equiv.resolve_canonical_asset("MAT-67890", source_system="sap")
    assert out["canonical_id"] == "TX-001"


def test_resolve_canonical_asset_from_maximo_id():
    out = asset_equiv.resolve_canonical_asset("EQ-12399", source_system="maximo")
    assert out["canonical_id"] == "TX-007"


def test_resolve_canonical_asset_unknown_raises():
    with pytest.raises(ValueError, match="No canonical asset"):
        asset_equiv.resolve_canonical_asset("BOGUS-12345")


def test_find_functional_equivalents_symmetric():
    """TX-001 ↔ TX-007 — looking up either side returns the other."""
    a_to_b = asset_equiv.find_functional_equivalents("TX-001")
    b_to_a = asset_equiv.find_functional_equivalents("TX-007")
    assert any(e["canonical_id"] == "TX-007" for e in a_to_b)
    assert any(e["canonical_id"] == "TX-001" for e in b_to_a)


def test_find_functional_equivalents_sorted_by_confidence():
    eqs = asset_equiv.find_functional_equivalents("TX-001")
    confidences = [e["confidence"] for e in eqs]
    assert confidences == sorted(confidences, reverse=True)


def test_score_equivalence_confidence_baseline():
    """Customer with no restriction returns base equivalence confidence."""
    score = asset_equiv.score_equivalence_confidence("TX-001", "TX-007", "gulf-petroleum")
    assert score == pytest.approx(0.92)


def test_score_equivalence_confidence_customer_restriction():
    """North Atlantic Resources restricts WIRE-120 → penalty multiplier 0.3."""
    score = asset_equiv.score_equivalence_confidence(
        "WIRE-100", "WIRE-120", "north-atlantic-resources"
    )
    # Base 0.85 × 0.3 = 0.255 (but also has an override of 0.45 in the data,
    # which takes precedence over the substitution_restrictions multiplier).
    assert 0.4 < score < 0.5  # the explicit override value


def test_score_equivalence_confidence_no_equivalence():
    """No documented equivalence ⇒ 0.0."""
    assert asset_equiv.score_equivalence_confidence("TX-001", "MWD-300", "gulf-petroleum") == 0.0


# ----------------------------------------------------------------------
# sourcing-logistics
# ----------------------------------------------------------------------


def test_estimate_transit_ground_short_distance():
    # Lagos → Luanda is ~2700 km — that's sea_freight under our thresholds.
    out = sourcing.estimate_transit(6.5244, 3.3792, -8.8390, 13.2894)
    assert out["transit_mode"] in ("sea_freight", "cargo_charter")
    assert out["distance_km"] > 1000


def test_estimate_transit_50km_is_ground():
    out = sourcing.estimate_transit(6.5244, 3.3792, 6.5244, 3.8)
    assert out["transit_mode"] == "ground_transit"


def test_estimate_transit_australia_to_luanda_is_cargo_charter():
    """Darwin → Luanda is the doomed naive baseline."""
    out = sourcing.estimate_transit(-12.4634, 130.8456, -8.8390, 13.2894)
    assert out["transit_mode"] == "cargo_charter"
    assert out["estimated_cost_usd"] > 300_000


def test_calculate_sourcing_cost_adds_certification_and_customs():
    base = sourcing.calculate_sourcing_cost(
        6.5244, 3.3792, -8.8390, 13.2894, certification_hours=0, cross_border=False
    )
    with_extras = sourcing.calculate_sourcing_cost(
        6.5244, 3.3792, -8.8390, 13.2894, certification_hours=4, cross_border=True
    )
    assert with_extras == base + (4 * 150) + 5000


def test_identify_blockers_clean(monkeypatch):
    """Equipment has no open RECERT WOs, no customer restriction → no blockers.

    The BQ-seeded TX-007-LGS-001 actually has an open RECERT WO with
    cert hours remaining; we patch out the WO endpoint for this case
    to assert the clean-path behavior of `identify_blockers`.
    """
    monkeypatch.setattr(sourcing.mcp_client, "fdp_list_customer_restrictions", lambda cid: [])
    monkeypatch.setattr(sourcing.mcp_client, "maximo_get_open_workorders", lambda *a, **kw: [])
    blockers = sourcing.identify_blockers("TX-007", "gulf-petroleum", "TX-007-LGS-001")
    assert blockers == []


def test_identify_blockers_customer_restriction(monkeypatch):
    """A matching FDP restriction row → 'restricts substitution' blocker.

    `bohai-energy` rejects `RIG-LWP-B` (MAT-LWPB) as a substitute. We
    inject the restriction here rather than depend on the seeder
    flattening this from `customers.json::substitution_restrictions`
    (the v1 seeder only handles `v?_substitution_accepted` keys).
    """
    monkeypatch.setattr(
        sourcing.mcp_client,
        "fdp_list_customer_restrictions",
        lambda cid: [
            {
                "customer_id": "bohai-energy",
                "matnr_original": "MAT-LWPA",
                "matnr_substitute_rejected": "MAT-LWPB",
            }
        ],
    )
    blockers = sourcing.identify_blockers("RIG-LWP-B", "bohai-energy", None)
    assert any("restricts substitution" in b for b in blockers)


def test_identify_blockers_unknown_equipment(monkeypatch):
    """An equipment id that no Maximo ASSET row matches → 'not found' blocker."""
    monkeypatch.setattr(sourcing.mcp_client, "fdp_list_customer_restrictions", lambda cid: [])
    blockers = sourcing.identify_blockers("TX-007", "gulf-petroleum", "TX-007-NOWHERE-999")
    assert any("not found" in b for b in blockers)


# ----------------------------------------------------------------------
# enterprise-systems
# ----------------------------------------------------------------------


def test_query_maximo_availability_returns_lagos_instance():
    rows = enterprise.query_maximo_availability("TX-007")
    # Q8 (TASK-16 Step 9): location.description replaces legacy
    # location.label. The Lagos repair shop's DESCRIPTION column carries
    # "Lagos repair shop, Nigeria" in the seeded data.
    descriptions = [r["location"]["description"] for r in rows]
    assert any("Lagos" in (d or "") for d in descriptions)


def test_query_maximo_availability_region_filter():
    rows = enterprise.query_maximo_availability("TX-001", region_filter="europe")
    assert all(r["location"]["region"] == "europe" for r in rows)


def test_query_sap_workforce_known_basin():
    out = enterprise.query_sap_workforce("permian")
    assert out["crew_count_available"] > 0


def test_query_sap_workforce_unknown_basin_returns_zeros():
    out = enterprise.query_sap_workforce("nowhere")
    assert out == {"crew_count_available": 0, "specialist_count_available": 0, "on_call_count": 0}


def test_query_fdp_customer_config_gulf_petroleum_tx001():
    # TASK-16 Step 9: substitution_accepted keys are now derived from the
    # substitute's canonical_id suffix (e.g. "TX-007" → "007"), not the
    # legacy free-form JSON key names ("v7_substitution_accepted" → "V7").
    # The BQ APPROVED_SUBSTITUTIONS row links MAT-67890 → MAT-67899; the
    # alias table reverses MAT-67899 → TX-007 → "007".
    cfg = enterprise.query_fdp_customer_config("gulf-petroleum", "TX-001")
    assert cfg["approved"] is True
    assert "007" in cfg["substitution_accepted"]
    assert cfg["substitution_accepted"]["007"] is True


def test_query_intouch_specs_returns_relevant_docs():
    # TASK-16 Step 9: query_intouch_specs now returns list[str] (the
    # ARRAY<STRING> column from oilfield_kc.cross_system_aliases), not
    # a list of {spec_id, title} dicts.
    specs = enterprise.query_intouch_specs("TX-007")
    assert "spec-3.2-2024" in specs
    assert "v7-upgrade-guide-2023" in specs


# ----------------------------------------------------------------------
# plan-evaluation
# ----------------------------------------------------------------------


def _cargo_plane_plan_json() -> str:
    return json.dumps(
        {
            "request_id": "00000000-0000-0000-0000-000000000000",
            "requested_asset": "Tool X",
            "target_location": {"latitude": -8.84, "longitude": 13.29, "label": "Luanda"},
            "deadline": "2026-05-22T00:00:00Z",
            "primary_option": {
                "asset": {
                    "canonical_id": "TX-007",
                    "canonical_label": "Tool X-V7",
                    "intouch_spec_refs": ["spec-3.2-2024"],
                },
                "source_location": {
                    "latitude": 6.52,
                    "longitude": 3.38,
                    "label": "Lagos repair shop",
                },
                "destination": {"latitude": -8.84, "longitude": 13.29, "label": "Luanda"},
                "transit_mode": "sea_freight",
                "estimated_cost_usd": 40_000,
                "transit_hours": 12.0,
                "certification_hours": 4,
                "customer_compatibility": True,
                "workforce_available": True,
                "blockers": [],
            },
            "naive_baseline": {
                "asset": {"canonical_id": "TX-001", "canonical_label": "Tool X"},
                "source_location": {
                    "latitude": -12.46,
                    "longitude": 130.85,
                    "label": "Darwin warehouse",
                },
                "destination": {"latitude": -8.84, "longitude": 13.29, "label": "Luanda"},
                "transit_mode": "cargo_charter",
                "estimated_cost_usd": 420_000,
                "transit_hours": 30.0,
                "customer_compatibility": True,
                "workforce_available": True,
                "blockers": [],
            },
            "avoided_cost_usd": 380_000,
        }
    )


def test_evaluate_plan_deterministic_cargo_plane_scenario():
    result = plan_eval.evaluate_plan_deterministic(_cargo_plane_plan_json())
    assert result["cost_optimality"] >= 0.85  # $380K avoided / $420K baseline = 0.90+
    assert result["schedule_feasibility"] >= 0.85
    assert result["logistics_feasibility"] == 1.0


def test_evaluate_plan_deterministic_with_blockers():
    plan = json.loads(_cargo_plane_plan_json())
    plan["primary_option"]["blockers"] = ["customs delay", "missing cert"]
    result = plan_eval.evaluate_plan_deterministic(json.dumps(plan))
    assert result["logistics_feasibility"] == 0.5


# ----------------------------------------------------------------------
# procurement-prerequisites
# ----------------------------------------------------------------------


def test_check_budget_threshold_under_standard_tier():
    out = procurement.check_budget_threshold(_cargo_plane_plan_json(), "standard")
    assert out["passed"] is True


def test_check_budget_threshold_exceeds_junior_tier():
    plan = json.loads(_cargo_plane_plan_json())
    plan["primary_option"]["estimated_cost_usd"] = 300_000
    out = procurement.check_budget_threshold(json.dumps(plan), "junior")
    assert out["passed"] is False
    assert "exceeds" in out["blocker"]


def test_check_certification_chain_passes_when_spec_refs_present():
    out = procurement.check_certification_chain(_cargo_plane_plan_json())
    assert out["passed"] is True


def test_check_certification_chain_fails_without_spec_refs():
    plan = json.loads(_cargo_plane_plan_json())
    plan["primary_option"]["asset"]["intouch_spec_refs"] = []
    out = procurement.check_certification_chain(json.dumps(plan))
    assert out["passed"] is False


# ----------------------------------------------------------------------
# forecast-rationale
# ----------------------------------------------------------------------


def test_extract_rationale_tags_rig_decline():
    tags = forecast.extract_rationale_tags("Rig count declining across the basin")
    assert "rig_count_decline" in tags


def test_extract_rationale_tags_multiple():
    tags = forecast.extract_rationale_tags(
        "Operator deferred their drilling program and a storm hit Q4 too"
    )
    assert {"operator_delay", "weather_disruption"}.issubset(set(tags))


def test_extract_rationale_tags_empty():
    assert forecast.extract_rationale_tags("Nothing in particular") == []


def test_compute_override_significance_large():
    sig = forecast.compute_override_significance(100.0, 78.0, historical_volatility_pct=0.05)
    assert sig > 0.5


def test_compute_override_significance_trivial():
    sig = forecast.compute_override_significance(100.0, 101.0, historical_volatility_pct=0.05)
    assert sig < 0.2


# ----------------------------------------------------------------------
# scheduling-probability
# ----------------------------------------------------------------------


def test_get_start_date_distribution_permian():
    dist = scheduling.get_start_date_distribution("permian")
    assert dist["sample_size"] > 0
    assert dist["p90_offset_days"] >= dist["p50_offset_days"] >= dist["p10_offset_days"]


def test_get_start_date_distribution_unknown_basin_returns_default():
    dist = scheduling.get_start_date_distribution("antarctica")
    assert dist["sample_size"] == 0
    assert dist["p50_offset_days"] == 14


def test_compute_optimal_buffer_higher_risk_tolerance_yields_larger_buffer():
    low = scheduling.compute_optimal_buffer(-2, 5, 15, risk_tolerance=0.2)
    high = scheduling.compute_optimal_buffer(-2, 5, 15, risk_tolerance=0.85)
    assert high["recommended_buffer_days"] > low["recommended_buffer_days"]
    assert high["projected_on_time_rate"] > low["projected_on_time_rate"]


def test_compute_fleet_utilization_impact_reduces_when_buffer_lowered():
    impact = scheduling.compute_fleet_utilization_impact(
        "permian", recommended_buffer_days=8.0, current_buffer_days=14.0
    )
    assert impact["fleet_utilization_uplift_pct"] > 0
    assert impact["deferred_capex_usd"] > 0


def test_compute_fleet_utilization_impact_zero_when_buffer_unchanged():
    impact = scheduling.compute_fleet_utilization_impact(
        "permian", recommended_buffer_days=14.0, current_buffer_days=14.0
    )
    assert impact["fleet_utilization_uplift_pct"] == 0.0
    assert impact["deferred_capex_usd"] == 0
