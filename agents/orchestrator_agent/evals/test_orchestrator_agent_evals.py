"""Eval-suite runner for the Capacity Orchestrator (TASK-EVALS).

Two layers:

- **Fast layer (default):** schema-conformance + evalset-validity checks.
  No LLM. No GCP calls. Safe to run in CI on every PR.
- **Live layer (``-m evals_live`` or ``--run-live-evals``):** drives the
  deployed Reasoning Engine via :streamQuery and asserts on the streamed
  SourcingPlan. Skipped unless ``ORCHESTRATOR_AGENT_RESOURCE_NAME`` is set
  AND the ``--run-live-evals`` flag is passed.

Per agents/<agent>/evals/README.md, run with:

    poetry run pytest agents/orchestrator_agent/evals/                      # fast
    poetry run pytest agents/orchestrator_agent/evals/ --run-live-evals     # full
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agents.schemas import SourcingPlan
from agents.utils.eval_helpers import (
    extract_user_query,
    load_evalset,
    stream_query_text,
)

EVALSET_PATH = Path(__file__).parent / "orchestrator_agent.evalset.json"

# Expected workflow trajectory for the cargo-plane happy path. The graph
# IS the trajectory here (per the Orchestrator's Workflow shape) so we
# encode it as an ordered list and validate the evalset's intermediate_data
# carries the same shape.
EXPECTED_HAPPY_PATH_TRAJECTORY = [
    "parse_capacity_gap_request",
    "resolve_canonical_asset_node",
    "parallel_system_queries",
    "evaluate_direct_availability",
    "equivalence_lookup_agent",
    "build_equivalent_plan",
    "sourcing_logistics_agent",
    "plan_evaluator_tool",
    "finalize_sourcing_plan",
]


# ---------------------------------------------------------------------------
# Fast layer — runs on every CI invocation.
# ---------------------------------------------------------------------------


def test_evalset_file_exists_and_parses():
    """The .evalset.json file is valid JSON and has the expected eval_ids."""
    evalset = load_evalset(EVALSET_PATH)
    eval_ids = {c["eval_id"] for c in evalset["eval_cases"]}
    # Core demo + degradation cases
    assert "happy_path_cargo_plane" in eval_ids
    assert "edge_unknown_customer" in eval_ids
    assert "edge_basin_without_history" in eval_ids
    # Demo-scenario expansion (2026-05-21): FDP penalty, multi-skin,
    # Memory Bank preload, revise loop.
    assert "restriction_penalty_north_atlantic" in eval_ids
    assert "multi_skin_halliburton" in eval_ids
    assert "memory_preload_maria_west_africa" in eval_ids
    assert "revise_loop_low_score_triggers_iteration" in eval_ids


def test_evalset_revise_loop_trajectory_calls_evaluator_twice():
    """The revise-loop case must show plan_evaluator_tool called twice.

    The Orchestrator caps iteration at 2 (see route_on_evaluation_score
    in nodes/routers.py). A revise-loop eval that doesn't show
    plan_evaluator → revise_plan_agent → plan_evaluator wouldn't be
    exercising the loop.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"]
        if c["eval_id"] == "revise_loop_low_score_triggers_iteration"
    )
    tools = [t["name"] for t in case["conversation"][0]["intermediate_data"]["tool_uses"]]
    assert tools.count("plan_evaluator_tool") == 2, (
        f"Expected exactly 2 plan_evaluator_tool invocations, "
        f"got {tools.count('plan_evaluator_tool')}"
    )
    assert "revise_plan_agent" in tools, (
        "revise_plan_agent missing from revise-loop trajectory"
    )


def test_a2ui_demo_envelopes_are_wired_into_nodes():
    """Demo-critical A2UI envelopes (DoomedRoute, RecommendedRoute, KCDrawer
    cost-rollup) must be emitted by the right nodes.

    The streamQuery response doesn't carry the A2UI side channel (it flows
    via SSE through agent_executor), so we can't assert on live emission
    from the eval. But we *can* assert the wiring is intact: the relevant
    node modules import the relevant event classes. If a refactor removes
    a critical envelope, this test catches it before the demo does.
    """
    from agents.orchestrator_agent.nodes import (
        equivalence_lookup,
        finalize,
        sourcing_logistics,
    )

    sl_src = Path(sourcing_logistics.__file__).read_text()
    assert "DoomedRouteProposedEvent" in sl_src, (
        "sourcing_logistics must reference DoomedRouteProposedEvent — demo's "
        "naive-baseline arc on the canvas depends on it."
    )
    assert "RecommendedRouteFinalizedEvent" in sl_src, (
        "sourcing_logistics must reference RecommendedRouteFinalizedEvent — demo's "
        "recommended-route arc + avoided-cost banner depends on it."
    )

    eq_src = Path(equivalence_lookup.__file__).read_text()
    assert "kc_drawer" in eq_src.lower() or "knowledgecatalog" in eq_src.lower(), (
        "equivalence_lookup must emit the KC drawer A2UI envelope — Persona 3's "
        "Issue-4 'taxonomic chaos dissolves' moment depends on it."
    )

    fin_src = Path(finalize.__file__).read_text()
    assert "emit_a2ui" in fin_src, (
        "finalize must call emit_a2ui — cost-rollup banner is the demo's closing visual."
    )


def test_evalset_memory_preload_appears_before_parse():
    """The Memory Bank preload must run before the request is parsed.

    The whole point of Persona 3's demo opening — Maria's West Africa
    context, customer commit, unit preference — is that they're already
    in context when the parse node runs, not loaded mid-workflow.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"]
        if c["eval_id"] == "memory_preload_maria_west_africa"
    )
    tools = [t["name"] for t in case["conversation"][0]["intermediate_data"]["tool_uses"]]
    assert tools[0] == "preload_memory", (
        f"Expected preload_memory first, got {tools[0]!r}"
    )
    assert tools.index("preload_memory") < tools.index("parse_capacity_gap_request")


def test_evalset_happy_path_trajectory_is_correct():
    """The happy-path eval case encodes the canonical Workflow trajectory.

    This is the trajectory contract for the Orchestrator's graph: parse →
    resolve → parallel → eval availability → equivalence (LLM) → build
    equivalent → logistics (LLM) → plan evaluator → finalize.
    """
    evalset = load_evalset(EVALSET_PATH)
    happy = next(c for c in evalset["eval_cases"] if c["eval_id"] == "happy_path_cargo_plane")
    tool_uses = happy["conversation"][0]["intermediate_data"]["tool_uses"]
    trajectory = [t["name"] for t in tool_uses]
    assert trajectory == EXPECTED_HAPPY_PATH_TRAJECTORY


def test_evalset_expected_responses_validate_against_schema():
    """Every eval case's expected final response must parse as a SourcingPlan-shaped fragment.

    We're not strict-validating the whole SourcingPlan (the evalset fragments
    are intentionally partial, since they document the load-bearing fields,
    not the full envelope), but we check that the expected text is JSON and
    has the load-bearing keys we assert against in the live layer.
    """
    import json as _json

    evalset = load_evalset(EVALSET_PATH)
    for case in evalset["eval_cases"]:
        for inv in case["conversation"]:
            text = inv["final_response"]["parts"][0]["text"]
            parsed = _json.loads(text)
            assert "primary_option" in parsed, (
                f"{case['eval_id']}: expected response missing primary_option"
            )


def test_sourcing_plan_schema_roundtrips():
    """A minimal SourcingPlan instance round-trips JSON cleanly.

    Sanity check that the agent's output_schema is healthy at the time the
    evalset runs.
    """
    plan = SourcingPlan.model_validate(
        {
            "requested_asset": "Tool X",
            "target_location": {"latitude": -8.83, "longitude": 13.23, "label": "Luanda"},
            "deadline": "2026-05-25T00:00:00Z",
            "primary_option": {
                "asset": {"canonical_id": "TX-007", "canonical_label": "Tool X-V7"},
                "source_location": {"latitude": 6.5, "longitude": 3.4, "label": "Lagos"},
                "destination": {"latitude": -8.83, "longitude": 13.23, "label": "Luanda"},
                "transit_mode": "sea_freight",
                "estimated_cost_usd": 40000,
                "transit_hours": 96.0,
                "customer_compatibility": True,
                "workforce_available": True,
            },
            "avoided_cost_usd": 380000,
        }
    )
    assert plan.avoided_cost_usd == 380000
    # Round-trip through JSON the way the deployed runtime will.
    rebuilt = SourcingPlan.model_validate_json(plan.model_dump_json())
    assert rebuilt.primary_option.asset.canonical_id == "TX-007"


# ---------------------------------------------------------------------------
# Live layer — costs real money. Marked ``evals_live`` and gated on the
# env var + ``--run-live-evals`` flag (registered in agents/tests/conftest.py).
# ---------------------------------------------------------------------------


pytestmark_live = [
    pytest.mark.evals_live,
    pytest.mark.skipif(
        not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
        reason="ORCHESTRATOR_AGENT_RESOURCE_NAME not set",
    ),
]


@pytest.fixture(scope="module")
def cargo_plane_response() -> str:
    """Run the cargo-plane happy path once; share the response across asserts.

    ~120s end-to-end per the spec — caching avoids re-running for each
    assertion in this module.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "happy_path_cargo_plane")
    prompt = extract_user_query(case)
    return stream_query_text("ORCHESTRATOR_AGENT_RESOURCE_NAME", prompt, user_id="eval-maria")


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason="ORCHESTRATOR_AGENT_RESOURCE_NAME not set",
)
def test_live_happy_path_returns_valid_sourcing_plan(cargo_plane_response):
    plan = SourcingPlan.model_validate_json(cargo_plane_response)
    assert plan.primary_option.estimated_cost_usd > 0


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason="ORCHESTRATOR_AGENT_RESOURCE_NAME not set",
)
def test_live_happy_path_picks_tx007_substitute(cargo_plane_response):
    """The equivalence path should pick TX-007 (Tool X V7) as the substitute."""
    plan = SourcingPlan.model_validate_json(cargo_plane_response)
    assert plan.primary_option.asset.canonical_id == "TX-007", (
        f"Expected TX-007 substitute, got {plan.primary_option.asset.canonical_id!r}"
    )


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason="ORCHESTRATOR_AGENT_RESOURCE_NAME not set",
)
def test_live_happy_path_sources_from_lagos(cargo_plane_response):
    plan = SourcingPlan.model_validate_json(cargo_plane_response)
    label = (plan.primary_option.source_location.label or "").lower()
    assert "lagos" in label, f"Expected Lagos source, got {label!r}"


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason="ORCHESTRATOR_AGENT_RESOURCE_NAME not set",
)
def test_live_happy_path_avoided_cost_positive(cargo_plane_response):
    plan = SourcingPlan.model_validate_json(cargo_plane_response)
    assert plan.avoided_cost_usd > 0, (
        f"Avoided cost {plan.avoided_cost_usd} is not positive — the Orchestrator "
        "may not be computing the naive baseline."
    )


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason="ORCHESTRATOR_AGENT_RESOURCE_NAME not set",
)
def test_live_edge_unknown_customer_degrades_gracefully():
    """An unknown customer should NOT crash the workflow.

    Either the plan comes back with customer_compatibility=False + blockers,
    OR the response is empty/error-text — both acceptable. We assert the
    workflow either produces a SourcingPlan-shaped JSON or surfaces a
    structured error string. No silent infinite loop.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "edge_unknown_customer")
    prompt = extract_user_query(case)
    text = stream_query_text("ORCHESTRATOR_AGENT_RESOURCE_NAME", prompt, user_id="eval-edge")
    assert text, "Orchestrator returned empty response for unknown customer"
    # Don't assert on exact shape — we only need graceful degradation.
    # Either valid SourcingPlan (with low/zero customer_compatibility) or
    # an error message is acceptable.
    try:
        SourcingPlan.model_validate_json(text)
    except Exception:
        # Non-JSON or partial — that's fine, just don't crash silently.
        assert len(text) > 20, "Response too short to be a meaningful error"


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason="ORCHESTRATOR_AGENT_RESOURCE_NAME not set",
)
def test_live_restriction_penalty_lowers_compatibility():
    """A customer who has rejected the substitute in FDP must see a
    compatibility hit or an explicit blocker.

    north-atlantic-resources has TX-007 in its rejected list per
    skins/default/customer.yaml's FDP seed (verified in
    scripts/smoke_cargo_plane.py:9 — fdp.list_customer_restrictions
    returns 1+ row for this customer). Either customer_compatibility
    flips to False, or a blocker mentions the restriction.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"]
        if c["eval_id"] == "restriction_penalty_north_atlantic"
    )
    prompt = extract_user_query(case)
    text = stream_query_text(
        "ORCHESTRATOR_AGENT_RESOURCE_NAME", prompt, user_id="eval-restriction"
    )
    plan = SourcingPlan.model_validate_json(text)
    blocker_text = " ".join(plan.blockers or []).lower()
    incompatible = plan.primary_option.customer_compatibility is False
    mentions_restriction = any(
        kw in blocker_text for kw in ("restrict", "reject", "north-atlantic", "fdp")
    )
    assert incompatible or mentions_restriction, (
        f"Expected restriction signal — "
        f"compatibility={plan.primary_option.customer_compatibility}, "
        f"blockers={plan.blockers}"
    )


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason="ORCHESTRATOR_AGENT_RESOURCE_NAME not set",
)
def test_live_multi_skin_halliburton_returns_valid_plan():
    """Same cargo-plane shape against the halliburton-pattern customer.

    Skin is configured via the CUSTOMER_SKIN env var at deploy time; the
    agent reads display names through normalize_customer_id. This test
    just verifies the workflow doesn't break when a non-default customer
    name flows through.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "multi_skin_halliburton")
    prompt = extract_user_query(case)
    text = stream_query_text(
        "ORCHESTRATOR_AGENT_RESOURCE_NAME", prompt, user_id="eval-halliburton"
    )
    plan = SourcingPlan.model_validate_json(text)
    # Don't assert TX-007 here — different skins can route to different
    # source locations. The contract is "valid SourcingPlan returned".
    assert plan.primary_option.estimated_cost_usd > 0
