"""Cargo-plane scenario end-to-end test (TASK-03 Step 13).

Maria asks for Tool X in Luanda by Friday. The Orchestrator should:

1. Resolve Tool X → canonical TX-001.
2. Find no TX-001 in West Africa (Maximo only has Darwin / Houston / Aberdeen /
   Singapore).
3. Find functional equivalents — TX-007 with confidence 0.92.
4. Discover TX-007-LGS-001 in Lagos (after recert, 4h).
5. Verify Gulf Petroleum FDP config accepts V7 substitution.
6. Estimate transit Lagos → Luanda as sea_freight (~2700 km).
7. Recommend that as the primary option (~$216K transit + cert + customs).
8. Set the naive baseline as the Darwin cargo charter (~$700K+).
9. Pass Plan Evaluator scoring (overall_score >= 0.85).
10. Pass Procurement Approval (cost < $500K threshold).
11. Return a SourcingPlan with avoided_cost_usd ~ $300K-$500K.

Skipped automatically when ``ORCHESTRATOR_AGENT_RESOURCE_NAME`` is unset.
This is the hero-scenario regression test.
"""

from __future__ import annotations

import os

import pytest
import vertexai
from vertexai import agent_engines

from src.schemas import SourcingPlan

CARGO_PLANE_PROMPT = (
    "I need a Tool X variant on site in Luanda, Angola by Friday. "
    "Customer: Gulf Petroleum. Authorization tier: standard. What are my options?"
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason="ORCHESTRATOR_AGENT_RESOURCE_NAME not set — skipping live integration test",
)


@pytest.fixture(scope="module")
def deployed_orchestrator():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    vertexai.init(project=project, location=location)
    return agent_engines.get(os.environ["ORCHESTRATOR_AGENT_RESOURCE_NAME"])


def _stream_text(agent, prompt: str, user_id: str = "maria_chen") -> str:
    buf: list[str] = []
    for event in agent.stream_query(message=prompt, user_id=user_id):
        for part in event.get("content", {}).get("parts", []):
            if "text" in part and part["text"]:
                buf.append(part["text"])
    return "".join(buf)


def test_cargo_plane_picks_lagos_as_primary(deployed_orchestrator):
    """The primary option should source from Lagos, not Darwin."""
    text = _stream_text(deployed_orchestrator, CARGO_PLANE_PROMPT)
    plan = SourcingPlan.model_validate_json(text)

    primary_label = (plan.primary_option.source_location.label or "").lower()
    assert "lagos" in primary_label, f"Expected Lagos source, got {primary_label!r}"


def test_cargo_plane_primary_is_tx007(deployed_orchestrator):
    """The substitute variant (TX-007) should be the primary canonical asset."""
    text = _stream_text(deployed_orchestrator, CARGO_PLANE_PROMPT)
    plan = SourcingPlan.model_validate_json(text)
    assert plan.primary_option.asset.canonical_id == "TX-007", (
        f"Expected TX-007 substitution, got {plan.primary_option.asset.canonical_id!r}"
    )


def test_cargo_plane_primary_is_ground_or_sea_not_charter(deployed_orchestrator):
    """A 50km Lagos→Luanda hop should be ground or sea, not cargo charter."""
    text = _stream_text(deployed_orchestrator, CARGO_PLANE_PROMPT)
    plan = SourcingPlan.model_validate_json(text)
    assert plan.primary_option.transit_mode in ("ground_transit", "sea_freight")


def test_cargo_plane_avoided_cost_is_substantial(deployed_orchestrator):
    """The savings vs. naive Darwin baseline should be a six-figure number."""
    text = _stream_text(deployed_orchestrator, CARGO_PLANE_PROMPT)
    plan = SourcingPlan.model_validate_json(text)
    assert plan.avoided_cost_usd > 100_000, (
        f"Avoided cost ${plan.avoided_cost_usd:,} below the threshold — "
        "Orchestrator may not be comparing against the cargo-charter baseline."
    )


def test_cargo_plane_customer_compatibility(deployed_orchestrator):
    """Gulf Petroleum accepts V7 substitution per FDP config."""
    text = _stream_text(deployed_orchestrator, CARGO_PLANE_PROMPT)
    plan = SourcingPlan.model_validate_json(text)
    assert plan.primary_option.customer_compatibility is True
    assert plan.primary_option.blockers == [], (
        f"Unexpected blockers: {plan.primary_option.blockers}"
    )


def test_cargo_plane_baseline_is_cargo_charter(deployed_orchestrator):
    """Naive baseline should be the long-haul cargo charter (Darwin or similar)."""
    text = _stream_text(deployed_orchestrator, CARGO_PLANE_PROMPT)
    plan = SourcingPlan.model_validate_json(text)
    assert plan.naive_baseline is not None
    assert plan.naive_baseline.transit_mode == "cargo_charter"
    assert plan.naive_baseline.estimated_cost_usd > plan.primary_option.estimated_cost_usd
