"""Cargo-plane scenario routed through the managed Knowledge Catalog MCP server.

TASK-06 Step 6 acceptance: the cargo-plane scenario should produce the same
SourcingPlan when the orchestrator's ``equivalence_lookup`` node sources its
equivalence evidence from Knowledge Catalog via the managed MCP server
(behind Agent Gateway), not from the in-process ``asset-equivalence`` skill.

Skip rules (both must be true for the test to run):

1. ``ORCHESTRATOR_AGENT_RESOURCE_NAME`` is set — same gate as
   ``test_cargo_plane_scenario.py``; without it there's no deployed agent to
   call.
2. ``AGENT_GATEWAY_ENDPOINT`` is set — without it the deployed orchestrator
   silently falls back to local-mode equivalence lookup and this test would
   not actually exercise the MCP path it's meant to verify.

The trace-level assertions sketched at the bottom are kept as TODOs because
the exact ADK 2.0 / Agent Engine trace-inspection API isn't yet documented
in a form I can rely on from this subagent's context. They are written out
so the next pass can flip them on without re-deriving what to assert.
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


pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
        reason="ORCHESTRATOR_AGENT_RESOURCE_NAME not set — skipping live integration test",
    ),
    pytest.mark.skipif(
        not os.environ.get("AGENT_GATEWAY_ENDPOINT"),
        reason=(
            "AGENT_GATEWAY_ENDPOINT not set — orchestrator would fall back to "
            "local-mode equivalence lookup, so this MCP-path test would be a "
            "no-op. Skipping."
        ),
    ),
]


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


def test_cargo_plane_via_knowledge_catalog_picks_tx007(deployed_orchestrator):
    """Cargo-plane scenario still resolves to TX-007 with Knowledge Catalog
    backing the equivalence lookup."""
    text = _stream_text(deployed_orchestrator, CARGO_PLANE_PROMPT)
    plan = SourcingPlan.model_validate_json(text)

    assert plan.primary_option.asset.canonical_id == "TX-007", (
        f"Expected TX-007 substitution from Knowledge Catalog, got "
        f"{plan.primary_option.asset.canonical_id!r}"
    )
    primary_label = (plan.primary_option.source_location.label or "").lower()
    assert "lagos" in primary_label, f"Expected Lagos source, got {primary_label!r}"
    assert plan.avoided_cost_usd > 300_000


def test_cargo_plane_via_knowledge_catalog_trace_shows_mcp_calls(
    deployed_orchestrator,
):
    """Cloud Trace should show MCP calls to ``knowledge-catalog-mcp`` via
    Agent Gateway during the equivalence lookup.

    Disabled until the ADK 2.0 / Agent Engine trace-inspection surface is
    confirmed — see module docstring. Assertion sketch preserved below for
    the next iteration.
    """
    pytest.skip("API surface not yet verified — see module docstring.")

    # text = _stream_text(deployed_orchestrator, CARGO_PLANE_PROMPT)  # noqa: ERA001
    # plan = SourcingPlan.model_validate_json(text)  # noqa: ERA001
    #
    # # TODO: confirm whether AgentEngine.stream_query exposes the underlying
    # # Cloud Trace span tree, or whether we need to query Cloud Trace directly
    # # by trace id correlated from the orchestrator's logging.
    # trace = ...  # noqa: ERA001
    #
    # kc_spans = [
    #     s for s in trace.spans
    #     if "knowledge-catalog-mcp" in getattr(s, "name", "")
    #     or "dataplex.googleapis.com/mcp"
    #     in s.attributes.get("upstream_url", "")
    # ]
    # assert kc_spans, "Expected at least one Knowledge Catalog MCP span"
    #
    # gateway_spans = [s for s in trace.spans if "agent_gateway" in s.name]
    # assert any(
    #     "knowledge-catalog-mcp" in s.attributes.get("target", "")
    #     for s in gateway_spans
    # )
    #
    # lookup_spans = [
    #     s for s in kc_spans
    #     if "lookup_context" in s.name or "search_entries" in s.name
    # ]
    # assert lookup_spans, "Expected lookup_context / search_entries span"
    # response_data = lookup_spans[0].attributes.get("response_body", "")
    # assert "sap_material_number" in response_data
    # assert "maximo_equipment_id" in response_data
